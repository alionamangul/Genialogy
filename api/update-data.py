import json, os, base64
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
REPO = 'alionamangul/Genialogy'
BRANCH = 'main'


def _gh_headers():
    return {
        'Authorization': f'Bearer {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'genialogy-app',
    }


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

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body.decode('utf-8'))

            file_info = gh_get_file('data.json')
            sha = file_info['sha']
            content_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
            gh_put_file('data.json', content_bytes, sha, 'Обновление данных семейного дерева')

            self._json({'ok': True})
        except Exception as e:
            self._json({'error': str(e)}, 500)
