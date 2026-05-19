"""
Editions tracking — record-keeping for editioned works (reproduction prints,
sculptures, original prints), and any sale information that comes to be
recorded against the prints later.

The unit tracked is the *print*: a physical object that is signed and numbered.
Issuing a print (signing it) is what consumes a number from the edition.
Selling that print is a separate, later, optional event. See
_dev/editions-system-spec.md, §3 "Data shape" and "The print/sale distinction".

One file per work, stored as JSON under editions/<slug>.json. JSON (not YAML)
because the data nests three deep (work → tiers → prints) and the existing
markdown-frontmatter YAML parser only handles two levels. Editions data is
never hand-edited and never read by Hugo, so the human-readable-YAML argument
doesn't apply.
"""

import json
import re
import secrets
from datetime import date
from pathlib import Path

ROOT          = Path(__file__).parent.parent
EDITIONS      = ROOT / 'editions'
IMAGES        = EDITIONS / '_images'
TEMPLATE_PATH = Path(__file__).parent / 'edition_template.json'

SLUG_RE  = re.compile(r'^[a-z0-9][a-z0-9-]*$')
LABEL_RE = re.compile(r'^[a-z0-9][a-z0-9-]*$')

VALID_TYPES    = ('reproduction', 'sculpture', 'original-print')
VALID_TRACKING = ('strict', 'loose')
VALID_STATUS   = ('active', 'paused', 'closed')

# The two parallel print lists on a tier. `prints` is the main edition pool;
# `ap_prints` is artist proofs / non-commerce prints (separate ceiling).
PRINT_LISTS = ('prints', 'ap_prints')


# ── I/O ──────────────────────────────────────────────────────────────────────

def _path(slug):
    return EDITIONS / f'{slug}.json'


def _read(slug):
    p = _path(slug)
    if not p.is_file():
        return None
    return json.loads(p.read_text('utf-8'))


def _write(slug, data):
    EDITIONS.mkdir(exist_ok=True)
    _path(slug).write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + '\n',
        'utf-8',
    )


# ── Counting ─────────────────────────────────────────────────────────────────

def _active_prints(tier):
    """Non-deleted prints from the main edition pool."""
    return [p for p in tier.get('prints', []) if not p.get('deleted')]


def _is_sold(record):
    """A print is sold if any sale field carries information.
    Canonical signal is `date_sold`; client_name and a non-zero price are
    accepted as fallbacks so that a record-in-progress isn't misclassified."""
    if record.get('deleted'):
        return False
    if (record.get('date_sold') or '').strip():
        return True
    if (record.get('client_name') or '').strip():
        return True
    price = record.get('price')
    if isinstance(price, (int, float)) and price > 0:
        return True
    return False


def _count_issued(edition):
    return sum(len(_active_prints(t)) for t in edition.get('tiers', []))


def _count_sold(edition):
    total = 0
    for t in edition.get('tiers', []):
        for key in PRINT_LISTS:
            for rec in t.get(key, []) or []:
                if _is_sold(rec):
                    total += 1
    return total


def _ceiling_total(edition):
    total = 0
    for t in edition.get('tiers', []):
        c = t.get('ceiling')
        if isinstance(c, int) and c > 0:
            total += c
    return total


# ── Tier template ────────────────────────────────────────────────────────────

def load_template():
    """Read the tier template. Returns the parsed dict — caller decides how
    to use it (defaults vs variation toggles vs full listing)."""
    return json.loads(TEMPLATE_PATH.read_text('utf-8'))


def _tier_from_template(entry):
    """Project a template entry into a fresh tier record (no `default_enabled`,
    no prints yet). `default_price` and `default_currency` from the template
    are snapshotted onto the tier as `price`/`currency` — after this they live
    independent of the template, so Kim can override per image."""
    return {
        'label':       entry['label'],
        'dimensions':  entry.get('dimensions', ''),
        'substrate':   entry.get('substrate', ''),
        'material':    entry.get('material', ''),
        'spec':        entry.get('spec', ''),
        'ceiling':     entry.get('ceiling', 0),
        'ap_ceiling':  entry.get('ap_ceiling', 0),
        'price':       entry.get('default_price', 0),
        'currency':    entry.get('default_currency', ''),
        'tracking':    'strict',
        'status':      'active',
        'notes':       '',
        'prints':      [],
        'ap_prints':   [],
    }


def build_default_tiers():
    """Return the list of tier records to instantiate on a brand-new edition.
    Only template entries with `default_enabled: true` are included; variations
    are added per-image via the detail view."""
    tmpl = load_template()
    return [_tier_from_template(t) for t in tmpl.get('tiers', []) if t.get('default_enabled')]


def available_variations():
    """Return template entries with default_enabled=False — opt-in tiers."""
    tmpl = load_template()
    return [t for t in tmpl.get('tiers', []) if not t.get('default_enabled')]


# ── Bulk add ─────────────────────────────────────────────────────────────────

def _humanize_slug(slug):
    """Turn 'atilla-pathways' into 'Atilla Pathways' — first-cut title.
    Kim will refine in the detail view."""
    return ' '.join(w.capitalize() for w in slug.replace('_', '-').split('-') if w)


def bulk_add_create_record(slug):
    """Create a fresh edition record for `slug`. Assumes the image already
    exists at editions/_images/<slug>.webp. Refuses if the edition record
    already exists. Returns the created record."""
    if not SLUG_RE.match(slug):
        raise ValueError(f'Invalid slug: {slug!r}')
    if _path(slug).is_file():
        raise FileExistsError(f'Edition {slug!r} already exists')
    tmpl = load_template()
    data = {
        'title':          _humanize_slug(slug),
        'type':           tmpl.get('type', 'reproduction'),
        'portfolio_slug': '',
        'created':        date.today().isoformat(),
        'notes':          '',
        'tiers':          build_default_tiers(),
    }
    normalise(data, None)
    _write(slug, data)
    return data


# ── List + summary ───────────────────────────────────────────────────────────

def _tier_summary(tier):
    prints = tier.get('prints', []) or []
    active = [p for p in prints if not p.get('deleted')]
    return {
        'label':    tier.get('label', ''),
        'ceiling':  tier.get('ceiling', 0),
        'issued':   len(active),
        'sold':     sum(1 for p in active if _is_sold(p)),
    }


def list_summary():
    """Return one dict per edition with enough info to render the grid."""
    EDITIONS.mkdir(exist_ok=True)
    out = []
    for f in sorted(EDITIONS.glob('*.json')):
        try:
            d = json.loads(f.read_text('utf-8'))
        except json.JSONDecodeError:
            continue
        tiers = d.get('tiers', []) or []
        has_image = (IMAGES / f'{f.stem}.webp').is_file()
        out.append({
            'slug':           f.stem,
            'title':          d.get('title', ''),
            'type':           d.get('type', ''),
            'portfolio_slug': d.get('portfolio_slug', ''),
            'has_image':      has_image,
            'tiers':          [_tier_summary(t) for t in tiers],
            'issued':         _count_issued(d),
            'sold':           _count_sold(d),
            'ceiling_total':  _ceiling_total(d),
        })
    return out


# ── Validation ───────────────────────────────────────────────────────────────

class ValidationError(Exception):
    """Carries a list of (code, message) tuples."""
    def __init__(self, errors):
        self.errors = errors
        super().__init__('; '.join(m for _, m in errors))


def _is_iso_date(s):
    if not isinstance(s, str):
        return False
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


def validate(slug, data, existing):
    """
    Validate an incoming edition record.
    `existing` is the on-disk record (or None for create) — used to enforce
    ceiling-immutable-after-first-print.
    Raises ValidationError on failure.
    """
    errors = []

    if not SLUG_RE.match(slug):
        errors.append(('slug_invalid', f'Slug must be lowercase-hyphenated: {slug!r}'))

    if not isinstance(data, dict):
        raise ValidationError([('shape', 'Record must be an object')])

    title = data.get('title', '').strip() if isinstance(data.get('title'), str) else ''
    if not title:
        errors.append(('title_missing', 'Title is required'))

    typ = data.get('type', '')
    if typ not in VALID_TYPES:
        errors.append(('type_invalid', f"Type must be one of {VALID_TYPES}"))

    ps = data.get('portfolio_slug', '')
    if ps and not SLUG_RE.match(ps):
        errors.append(('portfolio_slug_invalid', f'portfolio_slug must be slug-shaped: {ps!r}'))

    tiers = data.get('tiers', [])
    if not isinstance(tiers, list) or not tiers:
        errors.append(('tiers_missing', 'At least one tier is required'))
        raise ValidationError(errors)

    existing_tiers = {t.get('label'): t for t in (existing or {}).get('tiers', [])}
    seen_labels = set()

    for idx, tier in enumerate(tiers):
        prefix = f'tier[{idx}]'
        if not isinstance(tier, dict):
            errors.append((f'{prefix}.shape', f'{prefix} must be an object'))
            continue

        label = tier.get('label', '')
        if not LABEL_RE.match(label or ''):
            errors.append((f'{prefix}.label_invalid', f'{prefix}.label must be lowercase-hyphenated'))
        elif label in seen_labels:
            errors.append((f'{prefix}.label_duplicate', f'Duplicate tier label: {label!r}'))
        else:
            seen_labels.add(label)

        tracking = tier.get('tracking', 'strict')
        if tracking not in VALID_TRACKING:
            errors.append((f'{prefix}.tracking_invalid', f'tracking must be one of {VALID_TRACKING}'))

        status = tier.get('status', 'active')
        if status not in VALID_STATUS:
            errors.append((f'{prefix}.status_invalid', f'status must be one of {VALID_STATUS}'))

        ceiling = tier.get('ceiling')
        if tracking == 'strict':
            if not isinstance(ceiling, int) or ceiling < 1:
                errors.append((f'{prefix}.ceiling_required', f'strict tier {label!r}: ceiling must be a positive integer'))

        ap_ceiling = tier.get('ap_ceiling', 0)
        if ap_ceiling not in (None, '') and (not isinstance(ap_ceiling, int) or ap_ceiling < 0):
            errors.append((f'{prefix}.ap_ceiling_invalid', f'ap_ceiling must be a non-negative integer or empty'))

        # Default tier price + currency. Same rule as print-level: currency
        # required only when there's a non-zero price to attach it to.
        tier_price = tier.get('price', 0)
        if tier_price not in (None, '', 0) and not isinstance(tier_price, (int, float)):
            errors.append((f'{prefix}.price_invalid', f'{prefix}: tier price must be a number'))
        if isinstance(tier_price, (int, float)) and tier_price > 0:
            cur = tier.get('currency', '')
            if not isinstance(cur, str) or not cur.strip():
                errors.append((f'{prefix}.currency_missing', f'{prefix}: currency required when tier price > 0'))

        prints    = tier.get('prints',    []) or []
        ap_prints = tier.get('ap_prints', []) or []

        _validate_print_list(errors, f'{prefix}.prints',    prints)
        _validate_print_list(errors, f'{prefix}.ap_prints', ap_prints)

        # Uniqueness across prints + ap_prints (including deleted — spec §5:
        # "number stays consumed — soft-delete does not free it").
        numbers = [p.get('number') for p in (prints + ap_prints) if isinstance(p.get('number'), str)]
        seen = set()
        for n in numbers:
            if n in seen:
                errors.append((f'{prefix}.number_duplicate', f'Duplicate print number in tier {label!r}: {n!r}'))
                break
            seen.add(n)

        # Strict-mode invariants.
        if tracking == 'strict' and isinstance(ceiling, int) and ceiling >= 1:
            active_count = sum(1 for p in prints if not p.get('deleted'))
            if active_count > ceiling:
                errors.append((
                    f'{prefix}.over_ceiling',
                    f'tier {label!r}: {active_count} prints issued exceed ceiling of {ceiling}',
                ))
            # Ceiling immutable after first print issued.
            ex = existing_tiers.get(label)
            if ex and ex.get('tracking') == 'strict':
                ex_prints = ex.get('prints', []) or []
                ex_ceiling = ex.get('ceiling')
                if len(ex_prints) >= 1 and ex_ceiling != ceiling:
                    errors.append((
                        f'{prefix}.ceiling_immutable',
                        f"tier {label!r}: ceiling cannot change once a print is issued "
                        f"(was {ex_ceiling}, requested {ceiling})",
                    ))

    if errors:
        raise ValidationError(errors)


def _validate_print_list(errors, prefix, prints):
    if not isinstance(prints, list):
        errors.append((f'{prefix}.shape', f'{prefix} must be a list'))
        return
    for j, rec in enumerate(prints):
        p = f'{prefix}[{j}]'
        if not isinstance(rec, dict):
            errors.append((f'{p}.shape', f'{p} must be an object'))
            continue
        # Existence — required.
        if not isinstance(rec.get('number'), str) or not rec.get('number').strip():
            errors.append((f'{p}.number_missing', f'{p}: number is required'))
        ds = rec.get('date_signed', '')
        if not _is_iso_date(ds):
            errors.append((f'{p}.date_signed_invalid', f'{p}: date_signed must be ISO date (YYYY-MM-DD)'))
        # Sale — optional but constrained when present.
        sold = rec.get('date_sold', '')
        if sold and not _is_iso_date(sold):
            errors.append((f'{p}.date_sold_invalid', f'{p}: date_sold must be ISO date (YYYY-MM-DD) when set'))
        price = rec.get('price', 0)
        if price not in (None, '', 0) and not isinstance(price, (int, float)):
            errors.append((f'{p}.price_invalid', f'{p}: price must be a number'))
        cur = rec.get('currency', '')
        if isinstance(price, (int, float)) and price > 0:
            if not isinstance(cur, str) or not cur.strip():
                errors.append((f'{p}.currency_missing', f'{p}: currency required when price > 0'))


# ── Normalisation & ID assignment ────────────────────────────────────────────

def _gen_print_id(existing_ids):
    while True:
        pid = 'p-' + secrets.token_hex(4)
        if pid not in existing_ids:
            return pid


def normalise(data, existing):
    """
    Fill in auto fields:
    - `created` set if missing (date of first save)
    - print `id` generated if missing or duplicate
    - empty-string defaults for documented optional fields so downstream code
      never KeyErrors
    Returns the normalised dict (mutates in place but also returns).
    """
    if not data.get('created'):
        data['created'] = (existing or {}).get('created') or date.today().isoformat()

    all_ids = set()
    for tier in data.get('tiers', []):
        tier.setdefault('notes', '')
        tier.setdefault('ap_ceiling', 0)
        tier.setdefault('status', 'active')
        tier.setdefault('tracking', 'strict')
        tier.setdefault('price', 0)
        tier.setdefault('currency', '')
        for key in PRINT_LISTS:
            for rec in tier.get(key, []) or []:
                pid = rec.get('id')
                if not pid or pid in all_ids:
                    pid = _gen_print_id(all_ids)
                    rec['id'] = pid
                all_ids.add(pid)
                for k in ('date_sold', 'client_name', 'country',
                          'invoice_ref', 'customs_ref', 'notes', 'currency'):
                    rec.setdefault(k, '')
                rec.setdefault('price', 0)
                rec.setdefault('photos', [])
    return data


# ── Public operations ────────────────────────────────────────────────────────

def get(slug):
    if not SLUG_RE.match(slug):
        return None
    return _read(slug)


def save(slug, data):
    if not SLUG_RE.match(slug):
        raise ValidationError([('slug_invalid', f'Slug must be lowercase-hyphenated: {slug!r}')])
    existing = _read(slug)
    validate(slug, data, existing)
    normalise(data, existing)
    _write(slug, data)
    return data


def delete(slug):
    """Hard-delete the file. Spec §12 says delete is v2 and rare; for MVP
    we allow deleting empty records (no prints) but refuse if any print exists."""
    if not SLUG_RE.match(slug):
        return False, 'invalid slug'
    p = _path(slug)
    if not p.is_file():
        return False, 'not found'
    existing = _read(slug)
    issued = _count_issued(existing or {})
    if issued > 0:
        return False, f'refusing to delete: {issued} print record(s) exist'
    p.unlink()
    return True, None
