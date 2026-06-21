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
import hashlib
import base64
import urllib.parse
from urllib.parse import unquote

APP_DIR   = os.environ.get('TREE_DIR', os.path.dirname(os.path.abspath(__file__)))
BASE_DIR  = APP_DIR
SERVE_DIR = APP_DIR
TMP_DATA_JSON = os.path.join(SERVE_DIR, 'data.json')
TMP_MEDIA_DIR = os.path.join(SERVE_DIR, 'media')

# Защита паролем включается, только если задана переменная окружения TREE_PASSWORD.
# Без неё (локальный запуск) сайт открывается без пароля.
PASSWORD = os.environ.get('TREE_PASSWORD')


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

    # ── вход по cookie (пароль вводится один раз и запоминается на устройстве) ──
    def _token(self):
        return hashlib.sha256((str(PASSWORD) + 'family-tree-v1').encode()).hexdigest()

    def _authed(self):
        if not PASSWORD:
            return True
        cookie = self.headers.get('Cookie', '')
        for part in cookie.split(';'):
            if '=' in part:
                k, v = part.strip().split('=', 1)
                if k == 'tree_auth' and v == self._token():
                    return True
        # запасной вариант — HTTP Basic (для прямых запросов/curl)
        hdr = self.headers.get('Authorization', '')
        if hdr.startswith('Basic '):
            try:
                dec = base64.b64decode(hdr[6:]).decode('utf-8', 'ignore')
                if ':' in dec and dec.split(':', 1)[1] == PASSWORD:
                    return True
            except Exception:
                pass
        return False

    def _login_page(self, error=False):
        msg = '<p class="err">Неверный пароль</p>' if error else ''
        html = """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Вход — Родословная</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,system-ui,'Segoe UI',sans-serif;
background:#efe7d6;color:#4a3f2e;min-height:100dvh;
display:flex;align-items:center;justify-content:center;padding:24px}
.box{width:100%;max-width:320px;text-align:center}
.leaf{font-size:2.4rem;margin-bottom:10px}
h1{font-size:1.4rem;margin-bottom:6px;color:#6b4f2a}
p.sub{color:#9a8a6a;font-size:.9rem;margin-bottom:24px}
input{width:100%;padding:14px 16px;font-size:1rem;border:1px solid #cbb78f;
border-radius:12px;margin-bottom:12px;background:#fbf7ee}
button{width:100%;padding:14px;font-size:1rem;font-weight:600;border:none;
border-radius:12px;background:#8a6d3b;color:#fff;cursor:pointer}
button:hover{background:#765d31}
.err{color:#a8462f;font-size:.85rem;margin-bottom:12px}
</style></head><body><div class="box">
<div class="leaf">\U0001F333</div>
<h1>Родословная</h1><p class="sub">Семейный архив</p>
__MSG__
<form method="POST" action="/login">
<input type="password" name="password" placeholder="Пароль" autofocus autocomplete="current-password">
<button type="submit">Войти</button>
</form></div></body></html>""".replace('__MSG__', msg)
        data = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if PASSWORD and path == '/login':
            self._login_page()
            return
        if not self._authed():
            self.send_response(302)
            self.send_header('Location', '/login')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if PASSWORD and path == '/login':
            self._handle_login()
            return
        if not self._authed():
            self.send_error(401)
            return
        if self.path.startswith('/api/upload-photo'):
            self._handle_upload()
        elif self.path.startswith('/api/upload-doc'):
            self._handle_upload_doc()
        elif self.path == '/api/update-data':
            self._handle_update_data()
        else:
            self.send_error(404)

    def _handle_login(self):
        length = int(self.headers.get('Content-Length', 0) or 0)
        body = self.rfile.read(length).decode('utf-8', 'ignore') if length else ''
        pw = urllib.parse.parse_qs(body).get('password', [''])[0]
        if pw == PASSWORD:
            self.send_response(303)
            self.send_header('Location', '/')
            self.send_header('Set-Cookie',
                'tree_auth=' + self._token() +
                '; Max-Age=31536000; Path=/; HttpOnly; SameSite=Lax; Secure')
            self.send_header('Content-Length', '0')
            self.end_headers()
        else:
            self._login_page(error=True)

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
            # Иначе для не-jpg (png/webp) ссылка ломалась: голый id всегда трактовался как .jpg.
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
