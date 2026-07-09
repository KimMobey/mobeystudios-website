# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Production status (READ FIRST)

- **Live production site:** this Hugo repo, served from AWS S3 + CloudFront at `kimmobey.com`. **The DNS cutover from Google Sites is DONE (2026-07):** `kimmobey.com` and `www.kimmobey.com` resolve to the CloudFront distribution (stack `kimmobey-site`, domain `dl42l828yesn9.cloudfront.net`) and serve the S3-hosted build. Google Sites no longer serves this domain. Verified: content deployed via `deploy.sh` appears live at `kimmobey.com`.
- **Production domain:** `kimmobey.com` (apex + www). **Not** `mobey.co.za` — that is a legacy domain Kim still uses for email only. **Its web redirect is broken** (verified 2026-07-09: `http://mobey.co.za` 301s to `https://mobey.co.za`, which has no TLS endpoint and dead-ends — it does *not* reach kimmobey.com). Known issue, fix deferred; do not describe the redirect as working.
- **Hosting target:** AWS S3 + CloudFront, provisioned by CloudFormation. **Deploys are manual** — there is no GitHub Actions workflow and there will never be one. After pushing to GitHub, run `hugo && STACK_NAME=kimmobey-site ./infrastructure/deploy.sh` from a shell with AWS CLI credentials. The script syncs `public/` to S3 and invalidates CloudFront `/*`.
  - Region: `eu-west-1` (Ireland — closest to the European buyer base)
  - Route 53 hosted zone for kimmobey.com: `Z0282701OSAPI8VKA1OT`
  - ACM certificate provisioned in `us-east-1` (CloudFront requirement, regardless of stack region)
  - Private S3 bucket with Origin Access Control — never use S3 static website hosting mode
- **Netlify is dead.** Do not reference it, do not consult `netlify.toml` for deploy behaviour, do not treat it as a fallback. It was disconnected from the repo and the file has been removed.
- **DNS cutover (Google Sites → CloudFront on kimmobey.com) is COMPLETE** (2026-07). The apex and `www` now point at the `kimmobey-site` CloudFront distribution. Google Sites is no longer authoritative for the site.
- **AWS inventory (verified 2026-07-09).** **Live SES/email records (DKIM, SPF, MX) on this zone must never be touched.** Existing ACM validation CNAMEs must not be modified. Three CloudFront distributions exist, all enabled:
  - `E34TQS4N4SASKJ` (`dl42l828yesn9.cloudfront.net`) — **the live site**, aliases `kimmobey.com` + `www.kimmobey.com`.
  - `E37NODD9EU82A8` (`d2qpmq0g3x3tv.cloudfront.net`) — leftover from the ~3-year-old partial migration, **no aliases since the cutover re-pointed the apex**. Cleanup candidate; do not disable/delete without Kim's explicit instruction.
  - `E34OLWMUFNSCWQ` (`d1hr4gcvv1txzh.cloudfront.net`) — alias `dev.kimmobey.com`, still resolving. Cleanup candidate; same rule.
- **Form handling:** Formspree (external), unchanged through migration.
- **Audience:** buyers are mostly European. Kim has lived in South Africa and Uruguay — do not infer audience from her residence.

### Pending feature work

- **Article-image lightbox: "View in portfolio" link** — the article/essay image lightbox in `layouts/partials/article-lightbox-js.html` currently shows image + caption + archival disclaimer. It does *not* yet show a "View in portfolio →" link for images that correspond to a portfolio work. Implementation needs (1) a Hugo shortcode `{{< work-image src="..." caption="..." slug="..." >}}` that emits `<img data-portfolio-slug="...">`, and (2) a dropdown in the admin editor listing portfolio works when inserting an article image, so the shortcode form is selectable. The JS already has a TODO comment with the plan; uncomment/extend the open() handler when (1) and (2) land.

## Commands

```bash
# Start local dev server (live reload)
hugo server

# Build for production
hugo

# Build with drafts visible
hugo server -D
```

The site is served at `http://localhost:1313/`. Build output lives in `public/` and is built with Hugo 0.162.1 (extended).

## Local development workflow

Test locally with `hugo server` before pushing. Standard git workflow applies — commit and push as you would on any other project. **Pushing to GitHub does not deploy.** After every push you want live, run `hugo && STACK_NAME=kimmobey-site ./infrastructure/deploy.sh` to sync to S3 and invalidate CloudFront. There is no auto-deploy and there will not be one.

**Session-start check:** run `./infrastructure/preflight.sh` before starting work — especially on a machine not used recently. It reports whether the working tree, GitHub, and the live site agree, and re-verifies the environment claims in this file (Hugo version, AWS credentials, CloudFront serving, pricelist gate). If it flags red, resolve that first.

**Deploy safety rails** (`infrastructure/deploy.sh`): refuses to deploy if deploy-relevant paths are dirty (`FORCE_DIRTY=1` to override) or if local main is ahead of/behind `origin/main` (`FORCE_SYNC=1` to override). Every deploy stamps `/build-info.json` (commit SHA + UTC timestamp + dirty flag) into the site root — this is how `preflight.sh` compares live against GitHub.

**Local-only data backup:** `editions/` (private sales/edition records) and `_dev/` (briefs, specs, design references) are gitignored — they exist only on the working machine until backed up. Run `./infrastructure/backup-editions.sh` after any editions change and before travel or switching machines. It mirrors both directories to the private, versioned bucket in the `kimmobey-backups` stack (`infrastructure/backups.yaml`); deleted/overwritten versions stay recoverable for 180 days. Restore: `aws s3 sync s3://<bucket>/<dir>/ <dir>/`.

## Architecture

This is a Hugo static site with **no theme** — all layouts are hand-built under `layouts/`. CSS lives in `assets/css/main.css` (processed via Hugo Pipes) and is referenced in `layouts/_default/baseof.html`.

### Content sections

| Section | Path | Purpose |
|---|---|---|
| Portfolio | `content/portfolio/` | Artwork — each work is a page bundle (folder with `index.md` + image file) |
| Studio → Essays | `content/studio/essays/` | Writing, CV content |
| Studio → Articles | `content/studio/articles/` | Process/making content — combined list also surfaces `content/studio/media/` entries. Renamed from `practice` 2026-04-28; old URLs redirect via Hugo aliases on each article. |
| Contact | `content/contact.md` | Contact page |

The About section has been decommissioned. `layouts/about/single.html` remains in the repo as dormant code; there is no `content/about.md` and nothing renders at `/about/`. Do not add About back without explicit instruction.

**Studio image directories (articles, essays, documents):** all three sections use per-slug subdirectories under `static/images/<section>/<slug>/`. Source files (jpg/png/raw) are archived under `<slug>/_src/`, which is excluded from the S3 sync. The admin form's body-image grid uploads into the per-slug dir; uploads to the parent `articles/`, `essays/`, or `documents/` are rejected (reserved-parent rule in `admin_server.py`).

### Taxonomies

Defined in `hugo.toml`. Values are controlled — see `PricingAndVocabulary.md` for the full list.

| Taxonomy | Hugo key | Controls |
|---|---|---|
| `form` | `forms` | What is depicted (portrait, figure, landscape, etc.) |
| `theme` | `themes` | What it is about (migration, identity, etc.) — optional |
| `medium` | `media` | Base material (oil, acrylic, bronze, etc.) |
| `status` | `statuses` | `available` / `reserved` / `sold` |
| `series` | `series` | Named body of work — optional |

### Portfolio filtering

`layouts/portfolio/list.html` loads [Isotope](https://isotope.metafizzy.co/) to filter the grid. The `card.html` partial stamps CSS classes (`form-*`, `status-*`) and `data-*` attributes onto each card for Isotope to filter against. Filter UI is rendered by `filters.html` using `.Site.Taxonomies`.

### Artwork front matter

Each portfolio work (`content/portfolio/<work>/index.md`) uses these fields:

**Public (rendered in captions/cards):** `title`, `year`, `medium`, `substrate`, `dimensions`, `form`, `theme`, `status`, `series`

**Private (not rendered publicly):** `category`, `price`, `collection`, `edition`, `featured`, `miniature`

Dimension format: W × H, cm always implied and never written. Whitespace around × is flexible — `50×60`, `50 x 60`, and `50 × 60` are all acceptable. Taxonomy values always lowercase with hyphens.

### Root-level content pages

`content/contact.md` sits at the root of `content/` with no section. It must declare `type` explicitly in front matter (`type: "contact"`) so Hugo resolves the correct layout template regardless of version.

### Controlled vocabulary

`PricingAndVocabulary.md` is the authoritative reference for all taxonomy values, field definitions, pricing formula, and YAML file management rules. Consult it before adding new taxonomy terms or front matter fields.

### Hugo v0.160.0 taxonomy behaviour

Two version-specific rules that must be followed:

1. **Front matter taxonomy keys must use the plural form** (as defined in `hugo.toml`). The singular form silently produces no term pages. Use `forms:`, `statuses:`, `media:`, `themes:`, `series:` — never `form:`, `status:`, `medium:`, `theme:`.
2. **Taxonomy term pages require `layouts/_default/list.html`** for HTML output. `layouts/taxonomy/list.html` alone is not sufficient in v0.160.0+.

## Colour palette and accessibility

The site uses a deliberately muted, refined palette. All colours are defined as CSS custom properties in `static/css/main.css` — never hardcode colour values. All colour decisions must satisfy WCAG AA contrast requirements.

### CSS custom properties

| Custom property | Value | Role |
|---|---|---|
| `--color-bg-primary` | `#ffffff` | Page background |
| `--color-bg-secondary` | `#f0efed` | Header, footer, cards, pathway blocks |
| `--color-text-primary` | `#1a1a1a` | Body copy, headings, primary labels |
| `--color-text-secondary` | `#6a5f56` | Captions, metadata, secondary labels, filter options |
| `--color-accent` | `#7a6e65` | Interactive states, focus rings, active filters, taxonomy links, button background |
| `--color-border` | `#e0e0e0` | Dividers, input borders |
| `--color-white` | `#ffffff` | Button text on accent background |

**Important distinction — secondary vs accent:** `--color-text-secondary` (`#6a5f56`) is darker than `--color-accent` (`#7a6e65`). Secondary is used for text that must meet 4.5:1 contrast. Accent is used for interactive and decorative elements where the contrast threshold is met by size, weight, or context. Do not swap them.

### Contrast ratios

**WCAG AA thresholds:** 4.5:1 for normal text (below 18px regular or 14px bold) — 3:1 for large text.

| Pair | Ratio | Notes |
|---|---|---|
| `#1a1a1a` on `#ffffff` | ~17:1 | Well clear |
| `#1a1a1a` on `#f0efed` | ~15:1 | Well clear |
| `#6a5f56` on `#ffffff` | 5.74:1 | Passes AA normal text — `--color-text-secondary` |
| `#6a5f56` on `#f0efed` | ~5.3:1 | Passes AA normal text |
| `#7a6e65` on `#ffffff` | 4.32:1 | Fails AA normal text — do not use for body text |
| `#ffffff` on `#7a6e65` | 4.32:1 | Passes AA large text — button/accent use only |

### Rules to follow

- **`--color-text-secondary` (`#6a5f56`) is the floor for small text.** Do not use a lighter colour for text below 18px. Do not lighten this value.
- **`--color-accent` (`#7a6e65`) must not be used for normal body text** — it fails AA at small sizes. Restrict it to interactive states, decorative elements, and large text contexts.
- **All colours via custom properties.** Never hardcode hex values in CSS or templates.
- **Decorative elements are exempt.** Borders, dividers, and background fills do not need to meet contrast ratios.
- **Hover states using opacity:** opacity reductions on text lower effective contrast. Keep opacity reductions modest (floor ~0.6) and only on elements that already pass with margin to spare.
