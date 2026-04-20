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
from urllib.parse import urlparse, unquote, parse_qs

PORT = 8080
ROOT             = Path(__file__).parent
ADMIN_HTML       = ROOT / 'static' / 'admin' / 'index.html'
PORTFOLIO        = ROOT / 'content' / 'portfolio'
CONTENT_ESSAYS   = ROOT / 'content' / 'studio' / 'essays'
CONTENT_PRACTICE = ROOT / 'content' / 'studio' / 'practice'
STATIC           = ROOT / 'static'
IMAGES_ROOT      = STATIC / 'images'

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

# Directories under static/images/ that the admin image picker can access.
# `portfolio` has its own matching system; `home` holds hero images that
# shouldn't be writable from article editing.
RESERVED_IMAGE_DIRS = {'portfolio', 'home'}
IMAGE_DIR_PATTERN   = re.compile(r'^[a-z0-9-]+$')


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
                ct  = {'.jpg':'image/jpeg', '.jpeg':'image/jpeg',
                       '.png':'image/png',  '.webp':'image/webp',
                       '.gif':'image/gif'}.get(ext, 'application/octet-stream')
                self._file(img, ct)
            else:
                self.send_error(404)

        elif path == '/api/works':
            self._json(self._list_works())

        elif path == '/api/articles':
            self._json(self._list_articles())

        elif path == '/api/images':
            qs = parse_qs(urlparse(self.path).query)
            directory = (qs.get('dir') or [''])[0]
            images = self._list_images(directory)
            if images is None:
                self.send_error(400, 'Invalid or reserved dir')
                return
            self._json(images)

        elif path == '/api/orphans':
            self._json(self._list_orphans())

        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path

        # /api/works/<slug>/delete  (must come before the generic save route)
        m = re.match(r'^/api/works/([\w-]+)/delete$', path)
        if m:
            self._delete_work(m.group(1))
            return

        # /api/articles/<section>/<slug>/delete  (must come before the generic save route)
        m = re.match(r'^/api/articles/(essays|practice)/([\w-]+)/delete$', path)
        if m:
            self._delete_article(m.group(1), m.group(2))
            return

        # /api/stubs/<slug>/attach
        m = re.match(r'^/api/stubs/([\w-]+)/attach$', path)
        if m:
            length = int(self.headers.get('Content-Length', 0))
            data   = json.loads(self.rfile.read(length))
            self._attach_stub(m.group(1), data)
            return

        if path.startswith('/api/works/'):
            slug = unquote(path[len('/api/works/'):])
            if not re.match(r'^[\w-]+$', slug):
                self.send_error(400, 'Invalid slug')
                return
            length = int(self.headers.get('Content-Length', 0))
            data   = json.loads(self.rfile.read(length))
            self._save_work(slug, data)

        elif path == '/api/stubs/empty':
            length = int(self.headers.get('Content-Length', 0))
            data   = json.loads(self.rfile.read(length))
            self._create_empty_stub(data)

        elif path == '/api/stubs':
            length = int(self.headers.get('Content-Length', 0))
            data   = json.loads(self.rfile.read(length))
            self._create_stub(data)

        elif path == '/api/images':
            qs = parse_qs(urlparse(self.path).query)
            directory = (qs.get('dir') or [''])[0]
            self._upload_image(directory)
            return

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
        def _key(w):
            order = str(w['fm'].get('order', '')).strip()
            title = str(w['fm'].get('title', '')).lower()
            # With a catalogue number: group 0, sort by order then title.
            # Without a catalogue number: group 1, sort alphabetically by title.
            return (0, order, title) if order else (1, title, '')
        works.sort(key=_key)
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

    def _resolve_image_dir(self, dir_name):
        """Return the absolute Path for a valid media-type image directory, or None."""
        if not dir_name or not IMAGE_DIR_PATTERN.match(dir_name):
            return None
        if dir_name in RESERVED_IMAGE_DIRS:
            return None
        target = (IMAGES_ROOT / dir_name).resolve()
        try:
            target.relative_to(IMAGES_ROOT.resolve())
        except ValueError:
            return None
        return target

    def _list_images(self, dir_name):
        target = self._resolve_image_dir(dir_name)
        if target is None:
            return None
        if not target.exists():
            return []
        files = []
        for f in sorted(target.iterdir()):
            if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
                files.append({
                    'filename': f.name,
                    'path':     f'/images/{dir_name}/{f.name}',
                })
        return files

    def _upload_image(self, dir_name):
        target = self._resolve_image_dir(dir_name)
        if target is None:
            self.send_error(400, 'Invalid or reserved dir')
            return
        filename = self.headers.get('X-Filename', '').strip()
        if not filename or not re.match(r'^[\w.-]+$', filename):
            self.send_error(400, 'Missing or invalid X-Filename header')
            return
        ext = Path(filename).suffix.lower()
        if ext not in IMAGE_EXTS:
            self.send_error(400, f'Unsupported extension {ext}')
            return
        length = int(self.headers.get('Content-Length', 0))
        if length <= 0:
            self.send_error(400, 'Empty body')
            return
        target.mkdir(parents=True, exist_ok=True)
        dest = target / filename
        dest.write_bytes(self.rfile.read(length))
        self._json({'ok': True, 'filename': filename, 'path': f'/images/{dir_name}/{filename}'})

    def _save_article(self, section, slug, data):
        base = CONTENT_ESSAYS if section == 'essays' else CONTENT_PRACTICE
        path = base / f'{slug}.md'
        fm   = data.get('fm', {})
        # Studio content is not a blog — date is never written by the admin.
        fm.pop('date', None)
        body = data.get('body', '')
        # Normalise whitespace: CRLF → LF, strip trailing ws, single trailing newline.
        body = body.replace('\r\n', '\n').replace('\r', '\n')
        body = '\n'.join(ln.rstrip() for ln in body.split('\n')).strip('\n')
        content = serialize(fm, body)
        path.write_text(content, 'utf-8')
        self._json({'ok': True, 'slug': slug, 'section': section})

    def _save_work(self, slug, data):
        path    = PORTFOLIO / f'{slug}.md'
        content = serialize(data['fm'], data.get('body', ''))
        path.write_text(content, 'utf-8')
        self._json({'ok': True, 'slug': slug})

    def _list_orphans(self):
        img_dir = STATIC / 'images' / 'portfolio'
        if not img_dir.is_dir():
            return []

        # Collect every image stem referenced by any .md (image + gallery).
        # Matching by stem so .jpg/.webp siblings of a referenced file aren't
        # treated as orphans.
        referenced = set()
        for f in PORTFOLIO.glob('*.md'):
            if f.name == '_index.md':
                continue
            fm = parse_front_matter(f.read_text('utf-8'))['fm']
            img = fm.get('image')
            if isinstance(img, str) and img:
                referenced.add(Path(img).stem.lower())
            gallery = fm.get('gallery')
            if isinstance(gallery, list):
                for g in gallery:
                    if isinstance(g, str) and g:
                        referenced.add(Path(g).stem.lower())

        orphans = []
        seen_stems = set()
        exts = {'.jpg', '.jpeg', '.png', '.webp'}
        # Prefer .jpg over .webp if both exist for the same stem
        priority = {'.jpg': 0, '.jpeg': 0, '.png': 1, '.webp': 2}
        files = [p for p in img_dir.iterdir() if p.is_file() and p.suffix.lower() in exts]
        files.sort(key=lambda p: (p.stem.lower(), priority.get(p.suffix.lower(), 9)))
        for img in files:
            stem = img.stem.lower()
            if stem in referenced or stem in seen_stems:
                continue
            seen_stems.add(stem)
            orphans.append({
                'filename': img.name,
                'path':     f'/images/portfolio/{img.name}',
                'stem':     img.stem,
            })
        return orphans

    def _create_stub(self, data):
        image = data.get('image', '')
        slug  = data.get('slug', '').strip()
        if not image or not slug or not re.match(r'^[\w-]+$', slug):
            self.send_error(400, 'Missing or invalid image/slug')
            return
        path = PORTFOLIO / f'{slug}.md'
        if path.exists():
            self.send_error(409, f'{slug}.md already exists')
            return
        title = slug.replace('-', ' ').title()
        path.write_text(serialize(_stub_fm(title, image), ''), 'utf-8')
        self._json({'ok': True, 'slug': slug})

    def _create_empty_stub(self, data):
        title = (data.get('title') or '').strip()
        slug  = (data.get('slug') or '').strip()
        if not title or not slug or not re.match(r'^[\w-]+$', slug):
            self.send_error(400, 'Missing or invalid title/slug')
            return
        path = PORTFOLIO / f'{slug}.md'
        if path.exists():
            self.send_error(409, f'{slug}.md already exists')
            return
        path.write_text(serialize(_stub_fm(title, ''), ''), 'utf-8')
        self._json({'ok': True, 'slug': slug})

    def _attach_stub(self, slug, data):
        image = (data.get('image') or '').strip()
        if not image:
            self.send_error(400, 'Missing image')
            return
        path = PORTFOLIO / f'{slug}.md'
        if not path.exists():
            self.send_error(404, f'{slug}.md not found')
            return
        parsed = parse_front_matter(path.read_text('utf-8'))
        if not parsed['fm'].get('stub'):
            self.send_error(409, 'Refusing to attach to non-stub work')
            return
        fm = parsed['fm']
        fm['image'] = image
        path.write_text(serialize(fm, parsed['body']), 'utf-8')
        self._json({'ok': True, 'slug': slug})

    def _delete_article(self, section, slug):
        base = CONTENT_ESSAYS if section == 'essays' else CONTENT_PRACTICE
        path = base / f'{slug}.md'
        if not path.exists():
            self.send_error(404, f'{section}/{slug}.md not found')
            return
        if slug == '_index':
            self.send_error(409, 'Refusing to delete section index')
            return
        path.unlink()
        self._json({'ok': True, 'section': section, 'slug': slug})

    def _delete_work(self, slug):
        if not re.match(r'^[\w-]+$', slug):
            self.send_error(400, 'Invalid slug')
            return
        path = PORTFOLIO / f'{slug}.md'
        if not path.exists():
            self.send_error(404, f'{slug}.md not found')
            return
        parsed = parse_front_matter(path.read_text('utf-8'))
        if not parsed['fm'].get('stub'):
            self.send_error(409, 'Refusing to delete non-stub work')
            return
        path.unlink()
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


# ── Stub helpers ──────────────────────────────────────────────────────────────

def _stub_fm(title, image):
    return {
        'title':      title,
        'order':      '',
        'image':      image,
        'media':      [],
        'substrate':  [],
        'dimensions': '',
        'forms':      [],
        'themes':     [],
        'statuses':   'available',
        'category':   '',
        'price':      0,
        'visible':    False,
        'stub':       True,
    }


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
