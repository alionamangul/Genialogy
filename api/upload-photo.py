import json, os, base64, cgi, time
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
BLOB_TOKEN = os.environ.get('BLOB_READ_WRITE_TOKEN', '')
REPO = 'alionamangul/Genialogy'
BRANCH = 'main'


def _gh_headers():
    return {
        'Authorization': f'Bearer {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'genialogy-app',
    }


def blob_upload(pathname, file_bytes, content_type):
    """Upload file to Vercel Blob storage."""
    url = f'https://blob.vercel-storage.com/{pathname}'
    req = urllib.request.Request(url, data=file_bytes, method='PUT', headers={
        'Authorization': f'Bearer {BLOB_TOKEN}',
        'Content-Type': content_type,
        'x-api-version': '7',
        'x-content-type': content_type,
    })
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def gh_get_file(path):
    url = f'https://api.github.com/repos/{REPO}/contents/{path}?ref={BRANCH}'
    req = urllib.request.Request(url, headers=_gh_headers())
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def gh_put_file(path, data_bytes, sha, message):
    url = f'https://api.github.com/repos/{REPO}/contents/{path}'
    payload = json.dumps({
        'message': message,
        'content': base64.b64encode(data_bytes).decode(),
        'sha': sha,
        'branch': BRANCH,
    }).encode()
    req = urllib.request.Request(url, data=payload, method='PUT', headers={
        **_gh_headers(),
        'Content-Type': 'application/json',
    })
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


class handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self._cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def _parse_qs(self):
        qs = self.path.split('?', 1)[1] if '?' in self.path else ''
        return dict(p.split('=', 1) for p in qs.split('&') if '=' in p)

    def do_POST(self):
        try:
            params = self._parse_qs()
            person_id = params.get('personId', '')

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
                return self._json({'error': 'no file'}, 400)

            file_bytes = file_data if isinstance(file_data, bytes) else file_data.encode('latin-1')

            ext = os.path.splitext(orig_name)[1].lower()
            if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                ext = '.jpg'
            content_type = 'image/jpeg' if ext in ('.jpg', '.jpeg') else f'image/{ext.lstrip(".")}'

            photo_id = str(int(time.time() * 1000) % 100000000)
            filename = f'{photo_id}{ext}'
            pathname = f'media/{filename}'

            # Upload to Vercel Blob
            blob_result = blob_upload(pathname, file_bytes, content_type)
            photo_url = blob_result.get('url', f'/media/{filename}')

            # Update data.json via GitHub API
            if person_id:
                file_info = gh_get_file('data.json')
                data = json.loads(base64.b64decode(file_info['content']).decode('utf-8'))
                p = data.get('individuals', {}).get(person_id)
                if p is not None:
                    if 'photoIds' not in p or p['photoIds'] is None:
                        p['photoIds'] = []
                    p['photoIds'].append(photo_url)
                    content_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
                    gh_put_file('data.json', content_bytes, file_info['sha'],
                                f'Добавлено фото для {person_id}')

            self._json({'photoId': photo_url, 'url': photo_url, 'filename': filename})

        except Exception as e:
            self._json({'error': str(e)}, 500)
