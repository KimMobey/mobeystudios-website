#!/usr/bin/env python3
"""
Portfolio admin server — stdlib only, no installs required.
Run from project root: python3 admin_server.py
Then visit:           http://localhost:8080
"""

import http.server
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

PORT = 8080
ROOT             = Path(__file__).parent
ADMIN_HTML       = ROOT / 'static' / 'admin' / 'index.html'
PORTFOLIO        = ROOT / 'content' / 'portfolio'
CONTENT_ESSAYS   = ROOT / 'content' / 'studio' / 'essays'
CONTENT_PRACTICE = ROOT / 'content' / 'studio' / 'practice'
STATIC           = ROOT / 'static'


# ── Request handler ───────────────────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        path = urlparse(self.path).path

        if path in ('', '/', '/admin', '/admin/'):
            self._file(ADMIN_HTML, 'text/html; charset=utf-8')

        elif path.startswith('/images/'):
            # Serve from static/images/...
            img = STATIC / path.lstrip('/')
            if img.is_file():
                ext = img.suffix.lower()
                ct = 'image/jpeg' if ext in ('.jpg', '.jpeg') else \
                     'image/png'  if ext == '.png' else 'application/octet-stream'
                self._file(img, ct)
            else:
                self.send_error(404)

        elif path == '/api/works':
            self._json(self._list_works())

        elif path == '/api/articles':
            self._json(self._list_articles())

        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path.startswith('/api/works/'):
            slug = unquote(path[len('/api/works/'):])
            if not re.match(r'^[\w-]+$', slug):
                self.send_error(400, 'Invalid slug')
                return
            length = int(self.headers.get('Content-Length', 0))
            data   = json.loads(self.rfile.read(length))
            self._save_work(slug, data)

        elif path.startswith('/api/articles/'):
            rest = unquote(path[len('/api/articles/'):])
            parts = rest.split('/', 1)
            if len(parts) != 2 or parts[0] not in ('essays', 'practice'):
                self.send_error(400, 'Expected /api/articles/<section>/<slug>')
                return
            section, slug = parts
            if not re.match(r'^[\w-]+$', slug):
                self.send_error(400, 'Invalid slug')
                return
            length = int(self.headers.get('Content-Length', 0))
            data   = json.loads(self.rfile.read(length))
            self._save_article(section, slug, data)

        else:
            self.send_error(404)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _list_works(self):
        works = []
        for f in PORTFOLIO.glob('*.md'):
            if f.name == '_index.md':
                continue
            parsed = parse_front_matter(f.read_text('utf-8'))
            works.append({
                'slug':     f.stem,
                'filename': f.name,
                'fm':       parsed['fm'],
                'body':     parsed['body'],
            })
        works.sort(key=lambda w: str(w['fm'].get('order', '')))
        return works

    def _list_articles(self):
        articles = []
        for section, base in [('essays', CONTENT_ESSAYS), ('practice', CONTENT_PRACTICE)]:
            if not base.exists():
                continue
            for f in sorted(base.glob('*.md')):
                if f.name == '_index.md':
                    continue
                parsed = parse_front_matter(f.read_text('utf-8'))
                articles.append({
                    'slug':     f.stem,
                    'section':  section,
                    'filename': f.name,
                    'fm':       parsed['fm'],
                    'body':     parsed['body'],
                })
        return articles

    def _save_article(self, section, slug, data):
        from datetime import date as _date
        base = CONTENT_ESSAYS if section == 'essays' else CONTENT_PRACTICE
        path = base / f'{slug}.md'
        fm   = data.get('fm', {})
        if 'date' not in fm or not fm['date']:
            fm['date'] = str(_date.today())
        content = serialize(fm, data.get('body', ''))
        path.write_text(content, 'utf-8')
        self._json({'ok': True, 'slug': slug, 'section': section})

    def _save_work(self, slug, data):
        path    = PORTFOLIO / f'{slug}.md'
        content = serialize(data['fm'], data.get('body', ''))
        path.write_text(content, 'utf-8')
        self._json({'ok': True, 'slug': slug})

    def _file(self, path, ct):
        data = Path(path).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print(f'  {args[0]:<35} {args[1]}')


# ── YAML parser ───────────────────────────────────────────────────────────────

def parse_front_matter(text):
    if not text.startswith('---'):
        return {'fm': {}, 'body': text.strip()}
    close = text.find('\n---', 3)
    if close == -1:
        return {'fm': {}, 'body': text.strip()}
    yaml_src = text[4:close]
    body     = text[close + 4:].lstrip('\n').strip()

    fm    = {}
    lines = yaml_src.split('\n')
    i     = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        m = re.match(r'^([a-zA-Z][\w-]*)\s*:\s*(.*)', lines[i])
        if not m:
            i += 1
            continue
        key  = m.group(1)
        rest = m.group(2).strip()
        if rest in ('', '[]'):
            items = []
            i += 1
            while i < len(lines) and lines[i].startswith('  - '):
                items.append(parse_scalar(lines[i][4:].strip()))
                i += 1
            fm[key] = items
        else:
            fm[key] = parse_scalar(rest)
            i += 1

    return {'fm': fm, 'body': body}


def parse_scalar(s):
    if s == 'true':  return True
    if s == 'false': return False
    if s in ('null', '~'): return None
    if re.match(r'^-?\d+$', s):      return int(s)
    if re.match(r'^-?\d*\.\d+$', s): return float(s)
    if len(s) >= 2 and s[0] in ('"', "'") and s[-1] == s[0]:
        return s[1:-1].replace('\\"', '"').replace('\\n', '\n')
    return s


# ── YAML serializer ───────────────────────────────────────────────────────────

def serialize(fm, body):
    lines = ['---']
    for k, v in fm.items():
        if v is None:
            continue
        if isinstance(v, list):
            if not v:
                lines.append(f'{k}: []')
            else:
                lines.append(f'{k}:')
                for item in v:
                    lines.append(f'  - {scalar_out(item)}')
        else:
            lines.append(f'{k}: {scalar_out(v)}')
    lines.append('---')
    if body:
        lines += ['', body]
    return '\n'.join(lines) + '\n'


def scalar_out(v):
    if isinstance(v, bool):  return 'true' if v else 'false'
    if isinstance(v, int):   return str(v)
    if isinstance(v, float): return str(v)
    if v is None or v == '': return '""'
    s = str(v).replace('\\', '\\\\').replace('"', '\\"')
    return f'"{s}"'


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if not PORTFOLIO.is_dir():
        print(f'\n  Error: portfolio directory not found at {PORTFOLIO}')
        print('  Run this script from the project root.\n')
        sys.exit(1)

    server = http.server.HTTPServer(('127.0.0.1', PORT), Handler)
    print(f'\n  Portfolio admin  →  http://localhost:{PORT}/')
    print(f'  Project root:       {ROOT}')
    print(f'  Works directory:    {PORTFOLIO}')
    print('\n  Ctrl+C to stop.\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  Stopped.')
