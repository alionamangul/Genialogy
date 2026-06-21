#!/usr/bin/env python3
"""
Family tree dev server with file upload support.
Serves static files + handles photo/doc uploads and data saves.
"""
import http.server
import json
import os
import time
import shutil
from urllib.parse import unquote

BASE_DIR  = '/Users/alyona/Downloads/family-tree'  # permanent storage (may be read-only from sandbox)
SERVE_DIR = '/tmp/family-tree'                      # served to browser, always writable
TMP_DATA_JSON = os.path.join(SERVE_DIR, 'data.json')
TMP_MEDIA_DIR = os.path.join(SERVE_DIR, 'media')


def save_data(data):
    """Write data.json to SERVE_DIR (always), and attempt BASE_DIR (may be blocked by sandbox)."""
    os.makedirs(SERVE_DIR, exist_ok=True)
    with open(TMP_DATA_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Best-effort write to permanent storage
    try:
        base_json = os.path.join(BASE_DIR, 'data.json')
        with open(base_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_data():
    """Read data.json — prefer SERVE_DIR (freshest), fall back to BASE_DIR."""
    for path in [TMP_DATA_JSON, os.path.join(BASE_DIR, 'data.json')]:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    return {}


def save_media_file(rel_path, file_bytes):
    """Save a media file to SERVE_DIR and attempt BASE_DIR."""
    tmp_dest = os.path.join(SERVE_DIR, rel_path)
    os.makedirs(os.path.dirname(tmp_dest), exist_ok=True)
    with open(tmp_dest, 'wb') as f:
        f.write(file_bytes)
    try:
        base_dest = os.path.join(BASE_DIR, rel_path)
        os.makedirs(os.path.dirname(base_dest), exist_ok=True)
        with open(base_dest, 'wb') as f:
            f.write(file_bytes)
    except Exception:
        pass


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
        elif self.path.startswith('/api/delete-photo'):
            self._handle_delete_photo()
        elif self.path.startswith('/api/delete-doc'):
            self._handle_delete_doc()
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

    def _parse_qs(self):
        qs = self.path.split('?', 1)[1] if '?' in self.path else ''
        out = {}
        for p in qs.split('&'):
            if '=' in p:
                k, v = p.split('=', 1)
                out[k] = unquote(v)
        return out

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length) if length else b''

    def _handle_upload(self):
        try:
            params = self._parse_qs()
            person_id = params.get('personId', '')
            orig_name = params.get('filename', 'photo.jpg')

            file_bytes = self._read_body()
            if not file_bytes:
                self._json_response({'error': 'no file'}, 400)
                return

            ext = os.path.splitext(orig_name)[1].lower() or '.jpg'
            if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                ext = '.jpg'

            photo_id = str(int(time.time() * 1000) % 100000000)
            filename = photo_id + ext
            save_media_file(os.path.join('media', filename), file_bytes)

            # Храним имя файла С РАСШИРЕНИЕМ (напр. 123.png) — photoUrl() достроит ./media/123.png.
            if person_id:
                data = load_data()
                p = data.get('individuals', {}).get(person_id)
                if p is not None:
                    if 'photoIds' not in p or p['photoIds'] is None:
                        p['photoIds'] = []
                    p['photoIds'].append(filename)
                    save_data(data)

            self._json_response({'photoId': filename, 'filename': filename})

        except Exception as e:
            self._json_response({'error': str(e)}, 500)

    def _handle_upload_doc(self):
        try:
            params = self._parse_qs()
            person_id = params.get('personId', '')
            orig_name = params.get('filename', 'doc.jpg')
            doc_title = params.get('title', '')

            file_bytes = self._read_body()
            if not file_bytes:
                self._json_response({'error': 'no file'}, 400)
                return

            ext = os.path.splitext(orig_name)[1].lower() or '.jpg'
            if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.pdf'):
                ext = '.jpg'

            file_id = str(int(time.time() * 1000) % 100000000)
            filename = file_id + ext
            save_media_file(os.path.join('media', 'docs', filename), file_bytes)

            # Локально храним имя файла — docUrl() достроит ./media/docs/<filename>.
            if person_id:
                data = load_data()
                p = data.get('individuals', {}).get(person_id)
                if p is not None:
                    if 'documents' not in p or p['documents'] is None:
                        p['documents'] = []
                    p['documents'].append({'file': filename, 'title': doc_title or orig_name})
                    save_data(data)

            self._json_response({'filename': filename})

        except Exception as e:
            self._json_response({'error': str(e)}, 500)

    def _handle_update_data(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body.decode('utf-8'))
            save_data(data)
            self._json_response({'ok': True})
        except Exception as e:
            self._json_response({'error': str(e)}, 500)

    # ── удаление фото/документов ──
    def _media_path_for_photo(self, ref):
        ref = str(ref)
        if ref.startswith('http') or ref.startswith('/'):
            return None
        low = ref.lower()
        has_ext = any(low.endswith(e) for e in ('.jpg', '.jpeg', '.png', '.webp', '.gif'))
        name = os.path.basename(ref if has_ext else ref + '.jpg')
        return os.path.join(SERVE_DIR, 'media', name)

    def _media_path_for_doc(self, ref):
        ref = str(ref)
        if ref.startswith('http') or ref.startswith('/'):
            return None
        return os.path.join(SERVE_DIR, 'media', 'docs', os.path.basename(ref))

    def _ref_used_elsewhere(self, data, ref, kind):
        for ind in data.get('individuals', {}).values():
            if kind == 'photo':
                if ref in (ind.get('photoIds') or []):
                    return True
            else:
                if any((d or {}).get('file') == ref for d in (ind.get('documents') or [])):
                    return True
        return False

    def _handle_delete_photo(self):
        try:
            params = self._parse_qs()
            person_id = params.get('personId', '')
            ref = params.get('ref', '')
            if not person_id or not ref:
                self._json_response({'error': 'personId и ref обязательны'}, 400)
                return
            data = load_data()
            p = data.get('individuals', {}).get(person_id)
            if p is None:
                self._json_response({'error': 'нет такого человека'}, 404)
                return
            ids = p.get('photoIds') or []
            if ref in ids:
                ids.remove(ref)
                p['photoIds'] = ids
                save_data(data)
            path = self._media_path_for_photo(ref)
            if path and os.path.exists(path) and not self._ref_used_elsewhere(data, ref, 'photo'):
                try:
                    os.remove(path)
                except Exception:
                    pass
            self._json_response({'ok': True})
        except Exception as e:
            self._json_response({'error': str(e)}, 500)

    def _handle_delete_doc(self):
        try:
            params = self._parse_qs()
            person_id = params.get('personId', '')
            ref = params.get('ref', '')
            if not person_id or not ref:
                self._json_response({'error': 'personId и ref обязательны'}, 400)
                return
            data = load_data()
            p = data.get('individuals', {}).get(person_id)
            if p is None:
                self._json_response({'error': 'нет такого человека'}, 404)
                return
            docs = p.get('documents') or []
            p['documents'] = [d for d in docs if (d or {}).get('file') != ref]
            if len(p['documents']) != len(docs):
                save_data(data)
            path = self._media_path_for_doc(ref)
            if path and os.path.exists(path) and not self._ref_used_elsewhere(data, ref, 'doc'):
                try:
                    os.remove(path)
                except Exception:
                    pass
            self._json_response({'ok': True})
        except Exception as e:
            self._json_response({'error': str(e)}, 500)


if __name__ == '__main__':
    os.makedirs(SERVE_DIR, exist_ok=True)
    os.makedirs(TMP_MEDIA_DIR, exist_ok=True)
    # Initial sync: copy everything from BASE_DIR to SERVE_DIR
    for root, dirs, files in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for fname in files:
            if fname.startswith('.'): continue
            rel = os.path.relpath(os.path.join(root, fname), BASE_DIR)
            src = os.path.join(BASE_DIR, rel)
            dst = os.path.join(SERVE_DIR, rel)
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
            except Exception:
                pass

    port = 8081
    server = http.server.HTTPServer(('', port), Handler)
    print(f'Serving at http://localhost:{port}')
    server.serve_forever()
