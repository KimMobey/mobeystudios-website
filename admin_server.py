#!/usr/bin/env python3
"""
Portfolio admin server — stdlib only, no installs required.
Run from project root: python3 admin_server.py
Then visit:           http://localhost:8080
"""

import http.server
import io
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs

from PIL import Image, UnidentifiedImageError

from admin import editions as editions_mod

PORT = 8080
ROOT             = Path(__file__).parent
ADMIN_HTML       = ROOT / 'static' / 'admin' / 'index.html'
PORTFOLIO        = ROOT / 'content' / 'portfolio'
CONTENT_ESSAYS    = ROOT / 'content' / 'studio' / 'essays'
CONTENT_ARTICLES  = ROOT / 'content' / 'studio' / 'articles'
CONTENT_DOCUMENTS = ROOT / 'content' / 'studio' / 'documents'
CONTENT_MEDIA     = ROOT / 'content' / 'studio' / 'media'
STATIC            = ROOT / 'static'
IMAGES_ROOT       = STATIC / 'images'

STUDIO_SECTIONS = {
    'essays':    CONTENT_ESSAYS,
    'articles':  CONTENT_ARTICLES,
    'documents': CONTENT_DOCUMENTS,
    'media':     CONTENT_MEDIA,
}
SECTION_RE = '|'.join(STUDIO_SECTIONS.keys())

# Whitelist of "page-level" markdown files exposed in the admin Pages tab.
# Adding a new entry here is the only way to make a file editable as a page —
# everything else 404s, so the admin can never overwrite layouts or config.
PAGES = [
    {'id': 'home',      'label': 'Home',                  'path': 'content/_index.md'},
    {'id': 'contact',   'label': 'Contact',               'path': 'content/contact.md'},
    {'id': 'pricelist', 'label': 'Pricelist (private)',   'path': 'content/good-things-happen.md'},
    {'id': 'portfolio', 'label': 'Portfolio (intro)',     'path': 'content/portfolio/_index.md'},
    {'id': 'studio',    'label': 'Studio (intro)',        'path': 'content/studio/_index.md'},
    {'id': 'essays',    'label': 'Studio: Essays index',    'path': 'content/studio/essays/_index.md'},
    {'id': 'articles',  'label': 'Studio: Articles index',  'path': 'content/studio/articles/_index.md'},
    {'id': 'documents', 'label': 'Studio: Documents index', 'path': 'content/studio/documents/_index.md'},
    {'id': 'media',     'label': 'Studio: Media index',     'path': 'content/studio/media/_index.md'},
]
PAGES_BY_ID = {p['id']: p for p in PAGES}

PATHWAYS_PATH = ROOT / 'data' / 'pathways.json'
PATHWAY_KEYS  = ('title', 'description', 'href', 'image')

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

# Inputs the upload endpoint will accept and convert to .webp. RAW formats
# (.cr2/.nef/.arw/.dng) and HEIC are deliberately excluded — supporting them
# would mean pulling in rawpy/pillow-heif and dealing with vendor-specific
# quirks. The upload handler rejects anything outside this set with a clear
# message instead of failing silently.
UPLOAD_INPUT_EXTS = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.webp', '.bmp'}

# Resize cap on upload: longest edge in pixels. Photos larger than this are
# downscaled before encoding to .webp (lossless), so worst-case file size
# stays bounded. Smaller images pass through untouched.
MAX_LONG_EDGE = 1500

# Directories under static/images/ that the admin image picker can access.
# `portfolio` has its own matching system; `home` holds hero images that
# shouldn't be writable from article editing. `articles`, `essays`, and
# `documents` are reserved as *parents* — uploads must target a per-slug
# subdir (e.g. `essays/<slug>`), never the parent itself. This keeps each
# piece's images grouped as the catalogue grows.
RESERVED_IMAGE_DIRS = {'portfolio', 'home', 'articles', 'essays', 'documents'}
# Allow a single segment (e.g. `shared`), a per-slug subdir
# (e.g. `articles/<slug>`), or a per-slug bucket subdir
# (e.g. `articles/<slug>/grid`). The leading `[a-z0-9-]+` rules out anything
# starting with `_` (e.g. `_src`), keeping originals out of the API surface.
IMAGE_DIR_PATTERN   = re.compile(r'^[a-z0-9-]+(/[a-z0-9-]+){0,2}$')


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

        elif path == '/api/pages':
            self._json(self._list_pages())

        elif path == '/api/pathways':
            self._json(self._list_pathways())

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

        elif path == '/api/editions':
            self._json(editions_mod.list_summary())

        elif path == '/api/edition-template':
            self._json(editions_mod.load_template())

        else:
            m = re.match(r'^/api/editions/([a-z0-9][a-z0-9-]*)$', path)
            if m:
                rec = editions_mod.get(m.group(1))
                if rec is None:
                    self.send_error(404, 'Edition not found')
                else:
                    self._json(rec)
                return
            # GET /api/edition-images/<slug> → serve editions/_images/<slug>.webp
            m = re.match(r'^/api/edition-images/([a-z0-9][a-z0-9-]*)\.webp$', path)
            if m:
                img = editions_mod.IMAGES / f'{m.group(1)}.webp'
                if img.is_file():
                    self._file(img, 'image/webp')
                else:
                    self.send_error(404)
                return
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path

        # /api/editions/bulk-add-image — upload one image, auto-create edition
        if path == '/api/editions/bulk-add-image':
            self._upload_edition_image()
            return

        # /api/editions/bulk-set-prices — propagate tier prices to all records
        if path == '/api/editions/bulk-set-prices':
            length = int(self.headers.get('Content-Length', 0))
            try:
                data = json.loads(self.rfile.read(length))
            except json.JSONDecodeError as e:
                self.send_error(400, f'Invalid JSON: {e}')
                return
            prices = data.get('prices') or []
            if not isinstance(prices, list) or not prices:
                self.send_error(400, 'prices must be a non-empty list')
                return
            # Sanity-check shape — let server-side validation reject bad rows.
            cleaned = []
            for p in prices:
                if not isinstance(p, dict):
                    self.send_error(400, 'each price entry must be an object')
                    return
                lbl = (p.get('label') or '').strip()
                if not editions_mod.LABEL_RE.match(lbl):
                    self.send_error(400, f'invalid label: {lbl!r}')
                    return
                price = p.get('price', 0)
                if not isinstance(price, (int, float)) or price < 0:
                    self.send_error(400, f'invalid price for {lbl!r}')
                    return
                currency = (p.get('currency') or '').strip().upper()
                if price > 0 and not currency:
                    self.send_error(400, f'currency required when price > 0 ({lbl!r})')
                    return
                cleaned.append({'label': lbl, 'price': price, 'currency': currency})
            summary = editions_mod.bulk_set_tier_prices(cleaned)
            if data.get('update_template'):
                editions_mod.update_template_prices(cleaned)
                summary['template_updated'] = True
            else:
                summary['template_updated'] = False
            self._json(summary)
            return

        # /api/editions/<slug>/delete  (must come before generic save route)
        m = re.match(r'^/api/editions/([a-z0-9][a-z0-9-]*)/delete$', path)
        if m:
            ok, err = editions_mod.delete(m.group(1))
            if ok:
                self._json({'ok': True, 'slug': m.group(1)})
            else:
                self.send_error(409, err or 'delete failed')
            return

        # /api/editions/<slug>  → save (create or update)
        m = re.match(r'^/api/editions/([a-z0-9][a-z0-9-]*)$', path)
        if m:
            slug = m.group(1)
            length = int(self.headers.get('Content-Length', 0))
            try:
                data = json.loads(self.rfile.read(length))
            except json.JSONDecodeError as e:
                self.send_error(400, f'Invalid JSON: {e}')
                return
            try:
                saved = editions_mod.save(slug, data)
            except editions_mod.ValidationError as e:
                # 409 with structured error list so the UI can highlight fields.
                payload = json.dumps({'errors': e.errors}, ensure_ascii=False).encode('utf-8')
                self.send_response(409)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', len(payload))
                self.end_headers()
                self.wfile.write(payload)
                return
            self._json({'ok': True, 'slug': slug, 'edition': saved})
            return

        # /api/works/<slug>/delete  (must come before the generic save route)
        m = re.match(r'^/api/works/([\w-]+)/delete$', path)
        if m:
            self._delete_work(m.group(1))
            return

        # /api/articles/<section>/<slug>/delete  (must come before the generic save route)
        m = re.match(rf'^/api/articles/({SECTION_RE})/([\w-]+)/delete$', path)
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

        elif path.startswith('/api/pages/'):
            page_id = unquote(path[len('/api/pages/'):]).strip('/')
            if page_id not in PAGES_BY_ID:
                self.send_error(404, f'Unknown page: {page_id}')
                return
            length = int(self.headers.get('Content-Length', 0))
            data   = json.loads(self.rfile.read(length))
            self._save_page(page_id, data)

        elif path == '/api/pathways':
            length = int(self.headers.get('Content-Length', 0))
            data   = json.loads(self.rfile.read(length))
            self._save_pathways(data)

        elif path.startswith('/api/articles/'):
            rest = unquote(path[len('/api/articles/'):])
            parts = rest.split('/', 1)
            if len(parts) != 2 or parts[0] not in STUDIO_SECTIONS:
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

    def _list_pages(self):
        pages = []
        for entry in PAGES:
            f = ROOT / entry['path']
            if not f.is_file():
                continue
            parsed = parse_front_matter(f.read_text('utf-8'))
            pages.append({
                'id':    entry['id'],
                'label': entry['label'],
                'path':  entry['path'],
                'fm':    parsed['fm'],
                'body':  parsed['body'],
            })
        return pages

    def _list_pathways(self):
        if not PATHWAYS_PATH.is_file():
            return {'items': []}
        return json.loads(PATHWAYS_PATH.read_text('utf-8'))

    def _save_pathways(self, data):
        items = data.get('items')
        if not isinstance(items, list) or not items:
            self.send_error(400, 'items must be a non-empty list')
            return
        # Reject anything that doesn't match the known schema. The four
        # known keys are required; nothing else is written so the editor
        # can't smuggle in extra YAML/JSON keys.
        cleaned = []
        for it in items:
            if not isinstance(it, dict):
                self.send_error(400, 'each item must be an object')
                return
            entry = {}
            for k in PATHWAY_KEYS:
                v = it.get(k, '')
                if not isinstance(v, str):
                    self.send_error(400, f'{k} must be a string')
                    return
                entry[k] = v.strip()
            cleaned.append(entry)
        PATHWAYS_PATH.write_text(
            json.dumps({'items': cleaned}, indent=2, ensure_ascii=False) + '\n',
            'utf-8',
        )
        self._json({'ok': True, 'count': len(cleaned)})

    def _save_page(self, page_id, data):
        entry = PAGES_BY_ID[page_id]
        f = ROOT / entry['path']
        if not f.is_file():
            self.send_error(404, f"{entry['path']} not found")
            return
        # Preserve any existing front-matter keys not sent by the editor
        # (e.g. type, sitemap.disable) by merging client fm onto the
        # current on-disk fm.
        current = parse_front_matter(f.read_text('utf-8'))['fm']
        client_fm = data.get('fm') or {}
        merged = {**current, **client_fm}
        body = data.get('body', '')
        body = body.replace('\r\n', '\n').replace('\r', '\n')
        body = '\n'.join(ln.rstrip() for ln in body.split('\n')).strip('\n')
        f.write_text(serialize(merged, body), 'utf-8')
        self._json({'ok': True, 'id': page_id})

    def _list_articles(self):
        articles = []
        for section, base in STUDIO_SECTIONS.items():
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
        src = Path(filename)
        ext = src.suffix.lower()
        if ext not in UPLOAD_INPUT_EXTS:
            self.send_error(
                400,
                f"Unsupported format '{ext}'. Supported: jpg, jpeg, png, tif, tiff, "
                "bmp, webp. RAW (.cr2/.nef/.arw/.dng) and HEIC are not supported — "
                "please export to JPEG or PNG first."
            )
            return
        length = int(self.headers.get('Content-Length', 0))
        if length <= 0:
            self.send_error(400, 'Empty body')
            return
        raw = self.rfile.read(length)

        # Open & validate the bytes before touching the filesystem.
        try:
            im = Image.open(io.BytesIO(raw))
            im.load()
        except (UnidentifiedImageError, OSError):
            self.send_error(400, 'File is not a valid image, or is corrupt.')
            return

        # Site convention is .webp — output filename is always <stem>.webp.
        out_name = src.stem + '.webp'
        dest     = target / out_name
        if dest.exists():
            self.send_error(
                409,
                f"'{out_name}' already exists in this folder. "
                "Pick a different filename or remove the existing file first."
            )
            return

        # Downscale if needed (longest edge to MAX_LONG_EDGE). Never upscale.
        longest = max(im.size)
        if longest > MAX_LONG_EDGE:
            ratio    = MAX_LONG_EDGE / longest
            new_size = (round(im.size[0] * ratio), round(im.size[1] * ratio))
            im       = im.resize(new_size, Image.LANCZOS)

        # Lossless webp preserves quality (the user prefers higher quality for
        # an art site). Mode normalisation: webp encoder accepts RGB/RGBA only.
        if im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGBA' if 'A' in im.getbands() else 'RGB')

        target.mkdir(parents=True, exist_ok=True)
        (target / '_src').mkdir(parents=True, exist_ok=True)

        # Archive the original alongside the converted .webp. _src/ is excluded
        # from the S3 sync, so this stays out of the deployed site.
        src_archive = target / '_src' / filename
        if not src_archive.exists():
            src_archive.write_bytes(raw)

        try:
            im.save(dest, 'WEBP', lossless=True, quality=100, method=6)
        except Exception as e:
            self.send_error(500, f'WebP encode failed: {e}')
            return

        self._json({
            'ok':       True,
            'filename': out_name,
            'path':     f'/images/{dir_name}/{out_name}',
        })

    def _upload_edition_image(self):
        """Bulk-add path: one image upload → editions/_images/<slug>.webp +
        a fresh edition record with default tiers from the template.

        The filename's stem IS the slug — Kim's workflow is to name files in
        slug form before upload. Mismatched names are rejected so there's no
        ambiguity later about which image belongs to which record."""
        filename = self.headers.get('X-Filename', '').strip()
        if not filename or not re.match(r'^[\w.-]+$', filename):
            self.send_error(400, 'Missing or invalid X-Filename header')
            return
        src = Path(filename)
        slug = src.stem.lower()
        if not editions_mod.SLUG_RE.match(slug):
            self.send_error(
                400,
                f"Filename stem must be slug-shaped (lowercase, digits, hyphens). "
                f"Got: {src.stem!r}. Rename the file before upload."
            )
            return
        ext = src.suffix.lower()
        if ext not in UPLOAD_INPUT_EXTS:
            self.send_error(
                400,
                f"Unsupported format '{ext}'. Supported: jpg, jpeg, png, tif, tiff, "
                "bmp, webp. RAW (.cr2/.nef/.arw/.dng) and HEIC are not supported."
            )
            return

        # Refuse early if either the edition record OR the image file exists —
        # bulk-add is a create-only path, not a replace path.
        if (editions_mod.EDITIONS / f'{slug}.json').is_file():
            self.send_error(409, f"Edition {slug!r} already exists.")
            return
        dest = editions_mod.IMAGES / f'{slug}.webp'
        if dest.exists():
            self.send_error(409, f"Image {slug}.webp already exists in editions/_images/.")
            return

        length = int(self.headers.get('Content-Length', 0))
        if length <= 0:
            self.send_error(400, 'Empty body')
            return
        raw = self.rfile.read(length)
        try:
            im = Image.open(io.BytesIO(raw))
            im.load()
        except (UnidentifiedImageError, OSError):
            self.send_error(400, 'File is not a valid image, or is corrupt.')
            return

        # Same downscale + lossless-webp pipeline used for site images.
        longest = max(im.size)
        if longest > MAX_LONG_EDGE:
            ratio    = MAX_LONG_EDGE / longest
            new_size = (round(im.size[0] * ratio), round(im.size[1] * ratio))
            im       = im.resize(new_size, Image.LANCZOS)
        if im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGBA' if 'A' in im.getbands() else 'RGB')

        editions_mod.IMAGES.mkdir(parents=True, exist_ok=True)
        (editions_mod.IMAGES / '_src').mkdir(parents=True, exist_ok=True)
        src_archive = editions_mod.IMAGES / '_src' / filename
        if not src_archive.exists():
            src_archive.write_bytes(raw)

        try:
            im.save(dest, 'WEBP', lossless=True, quality=100, method=6)
        except Exception as e:
            self.send_error(500, f'WebP encode failed: {e}')
            return

        # Create the edition record (default tiers from template).
        try:
            rec = editions_mod.bulk_add_create_record(slug)
        except (FileExistsError, ValueError) as e:
            # Image saved but record creation failed; surface, leave the image
            # in place so a retry/manual recovery is possible.
            self.send_error(500, f'Image saved but record creation failed: {e}')
            return

        self._json({
            'ok':         True,
            'slug':       slug,
            'image_path': f'/api/edition-images/{slug}.webp',
            'edition':    rec,
        })

    def _save_article(self, section, slug, data):
        base = STUDIO_SECTIONS[section]
        base.mkdir(parents=True, exist_ok=True)
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
        # Articles, essays, and documents all use per-slug image directories.
        # Create the folder + _src/ on save (idempotent) so the destination
        # exists when the user goes looking for it via file manager — they
        # shouldn't have to guess whether it'll be created on first upload.
        if section in ('articles', 'essays', 'documents'):
            (IMAGES_ROOT / section / slug / '_src').mkdir(parents=True, exist_ok=True)
            # `grid/` holds images that appear in the article-end "More from
            # this article" grid (see related-grids.html). Pre-created so the
            # admin's image picker has a target directory the moment a new
            # piece is saved.
            (IMAGES_ROOT / section / slug / 'grid').mkdir(parents=True, exist_ok=True)
        self._json({'ok': True, 'slug': slug, 'section': section})

    def _save_work(self, slug, data):
        path = PORTFOLIO / f'{slug}.md'
        fm   = data.get('fm', {})
        # A stub stops being a stub once every required field is populated —
        # auto-clear so completed works don't linger under the Stubs filter.
        if fm.get('stub') and _is_complete_work(fm):
            fm.pop('stub', None)
        content = serialize(fm, data.get('body', ''))
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
        base = STUDIO_SECTIONS[section]
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
        # Local-only dev tool: never cache. Editing admin/index.html or
        # static images and reloading should always show the new bytes
        # without a hard-refresh dance.
        self.send_header('Cache-Control', 'no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
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
                line_rest = lines[i][4:]
                # A dict item starts with `  - key: value`; a scalar item is
                # just `  - value`. Continuation lines for a dict item use a
                # 4-space indent (`    key: value`).
                dm = re.match(r'^([a-zA-Z][\w-]*)\s*:\s*(.*)$', line_rest)
                if dm:
                    obj = {dm.group(1): parse_scalar(dm.group(2).strip())}
                    i += 1
                    while i < len(lines):
                        cm = re.match(r'^    ([a-zA-Z][\w-]*)\s*:\s*(.*)$', lines[i])
                        if not cm:
                            break
                        obj[cm.group(1)] = parse_scalar(cm.group(2).strip())
                        i += 1
                    items.append(obj)
                else:
                    items.append(parse_scalar(line_rest.strip()))
                    i += 1
            fm[key] = items
        else:
            fm[key] = parse_scalar(rest)
            i += 1

    return {'fm': fm, 'body': body}


REQUIRED_WORK_FIELDS = ('title', 'image', 'media', 'forms', 'dimensions', 'category', 'statuses')

def _is_complete_work(fm):
    """Mirror the admin's REQUIRED_FIELDS check (static/admin/index.html)."""
    for k in REQUIRED_WORK_FIELDS:
        v = fm.get(k)
        if v is None or v == '' or (isinstance(v, list) and not v):
            return False
    return True


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
                    if isinstance(item, dict):
                        keys = list(item.keys())
                        for j, ik in enumerate(keys):
                            prefix = '  - ' if j == 0 else '    '
                            lines.append(f'{prefix}{ik}: {scalar_out(item[ik])}')
                    else:
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
