#!/usr/bin/env python3
"""
Family tree dev server with file upload support.
Serves static files + handles photo uploads via POST /api/upload-photo
"""
import http.server
import json
import os
import re
import time
import cgi
import shutil

BASE_DIR  = '/Users/alyona/Downloads/family-tree'  # permanent storage
SERVE_DIR = '/tmp/family-tree'                      # served to browser (sandbox-accessible)
DATA_JSON = os.path.join(BASE_DIR, 'data.json')
MEDIA_DIR = os.path.join(BASE_DIR, 'media')
TMP_DIR   = '/tmp/family-tree'


def sync_to_tmp(rel_path):
    """Copy a file from BASE_DIR to TMP_DIR (no-op if they are the same)."""
    src = os.path.join(BASE_DIR, rel_path)
    dst = os.path.join(TMP_DIR, rel_path)
    if os.path.abspath(src) == os.path.abspath(dst):
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SERVE_DIR, **kwargs)

    def log_message(self, fmt, *args):
        pass  # suppress access log noise

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_POST(self):
        if self.path.startswith('/api/upload-photo'):
            self._handle_upload()
        elif self.path.startswith('/api/upload-doc'):
            self._handle_upload_doc()
        elif self.path == '/api/update-data':
            self._handle_update_data()
        else:
            self.send_error(404)

    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self._cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def _handle_upload(self):
        try:
            # Parse query string for personId
            qs = self.path.split('?', 1)[1] if '?' in self.path else ''
            params = dict(p.split('=', 1) for p in qs.split('&') if '=' in p)
            person_id = params.get('personId', '')

            # Parse multipart form
            ctype, pdict = cgi.parse_header(self.headers.get('Content-Type', ''))
            if 'boundary' in pdict:
                pdict['boundary'] = pdict['boundary'].encode('utf-8')
            pdict['CONTENT-LENGTH'] = int(self.headers.get('Content-Length', 0))

            form = cgi.parse_multipart(self.rfile, pdict)
            file_data = form.get('photo', [None])[0]
            orig_name = form.get('filename', [b'photo.jpg'])[0]
            if isinstance(orig_name, bytes):
                orig_name = orig_name.decode('utf-8', errors='replace')

            if not file_data:
                self._json_response({'error': 'no file'}, 400)
                return

            # Determine extension
            ext = os.path.splitext(orig_name)[1].lower() or '.jpg'
            if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                ext = '.jpg'

            # Generate unique photo ID (numeric to match existing style)
            photo_id = str(int(time.time() * 1000) % 100000000)

            # Save file
            filename = photo_id + ext
            dest = os.path.join(MEDIA_DIR, filename)
            with open(dest, 'wb') as f:
                f.write(file_data if isinstance(file_data, bytes) else file_data.encode('latin-1'))

            # Update data.json if personId given
            if person_id:
                with open(DATA_JSON, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                p = data['individuals'].get(person_id)
                if p is not None:
                    if 'photoIds' not in p or p['photoIds'] is None:
                        p['photoIds'] = []
                    p['photoIds'].append(photo_id)
                    with open(DATA_JSON, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    # Sync both files to /tmp
                    sync_to_tmp('data.json')

            # Sync photo to /tmp
            sync_to_tmp(os.path.join('media', filename))

            self._json_response({'photoId': photo_id, 'filename': filename})

        except Exception as e:
            self._json_response({'error': str(e)}, 500)

    def _handle_upload_doc(self):
        try:
            qs = self.path.split('?', 1)[1] if '?' in self.path else ''
            params = dict(p.split('=', 1) for p in qs.split('&') if '=' in p)
            person_id = params.get('personId', '')

            ctype, pdict = cgi.parse_header(self.headers.get('Content-Type', ''))
            if 'boundary' in pdict:
                pdict['boundary'] = pdict['boundary'].encode('utf-8')
            pdict['CONTENT-LENGTH'] = int(self.headers.get('Content-Length', 0))

            form = cgi.parse_multipart(self.rfile, pdict)
            file_data = form.get('doc', [None])[0]
            orig_name = form.get('filename', [b'doc.jpg'])[0]
            doc_title = form.get('title', [b''])[0]
            if isinstance(orig_name, bytes):
                orig_name = orig_name.decode('utf-8', errors='replace')
            if isinstance(doc_title, bytes):
                doc_title = doc_title.decode('utf-8', errors='replace')

            if not file_data:
                self._json_response({'error': 'no file'}, 400)
                return

            ext = os.path.splitext(orig_name)[1].lower() or '.jpg'
            if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.pdf'):
                ext = '.jpg'

            file_id = str(int(time.time() * 1000) % 100000000)
            filename = file_id + ext

            docs_dir = os.path.join(MEDIA_DIR, 'docs')
            os.makedirs(docs_dir, exist_ok=True)
            dest = os.path.join(docs_dir, filename)
            with open(dest, 'wb') as f:
                f.write(file_data if isinstance(file_data, bytes) else file_data.encode('latin-1'))

            if person_id:
                with open(DATA_JSON, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                p = data['individuals'].get(person_id)
                if p is not None:
                    if 'documents' not in p or p['documents'] is None:
                        p['documents'] = []
                    p['documents'].append({'file': filename, 'title': doc_title or orig_name})
                    with open(DATA_JSON, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    sync_to_tmp('data.json')

            sync_to_tmp(os.path.join('media', 'docs', filename))
            self._json_response({'fileId': file_id, 'filename': filename})

        except Exception as e:
            self._json_response({'error': str(e)}, 500)

    def _handle_update_data(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body.decode('utf-8'))
            with open(DATA_JSON, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            sync_to_tmp('data.json')
            self._json_response({'ok': True})
        except Exception as e:
            self._json_response({'error': str(e)}, 500)


if __name__ == '__main__':
    os.makedirs(TMP_DIR, exist_ok=True)
    # Initial sync of all files to /tmp
    for root, dirs, files in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for fname in files:
            if fname.startswith('.'): continue
            rel = os.path.relpath(os.path.join(root, fname), BASE_DIR)
            try:
                sync_to_tmp(rel)
            except Exception:
                pass

    port = 8081
    server = http.server.HTTPServer(('', port), Handler)
    print(f'Serving {BASE_DIR} at http://localhost:{port}')
    server.serve_forever()
