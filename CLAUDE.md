# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Production status (READ FIRST)

- **Live production site:** Google Sites at `kimmobey.com`. **This Hugo repo does not yet serve any live traffic.**
- **Production domain:** `kimmobey.com` (apex + www). **Not** `mobey.co.za` — that is a legacy domain Kim still uses for email; it DNS-redirects to kimmobey.com but does not serve a website.
- **Hosting target:** AWS S3 + CloudFront, provisioned by CloudFormation, with GitHub Actions (OIDC, no long-lived keys) building Hugo and syncing to S3 on push to `main`.
  - Region: `eu-west-1` (Ireland — closest to the European buyer base)
  - Route 53 hosted zone for kimmobey.com: `Z0282701OSAPI8VKA1OT`
  - ACM certificate provisioned in `us-east-1` (CloudFront requirement, regardless of stack region)
  - Private S3 bucket with Origin Access Control — never use S3 static website hosting mode
- **Netlify is being decommissioned.** It was the previous deploy target during early development. Do not treat any Netlify constraints (15 credits/deploy, 20 deploys/month) as live. `netlify.toml` is kept until the AWS pipeline is confirmed working, then deleted in a small dedicated commit *after* disconnecting Netlify from the GitHub repo in the Netlify console.
- **DNS cutover (Google Sites → CloudFront on kimmobey.com) is the final step**, performed manually by Kim only after the CloudFront distribution and ACM certificate are validated. Until then the Google Sites setup must remain untouched.
- **Pre-existing AWS infrastructure on kimmobey.com from a partial migration ~3 years ago.** Treat as untouchable until inventoried. **Live SES/email records (DKIM, SPF, MX) on this zone must never be touched.** Dormant CloudFront distributions exist (apex points to `d2qpmq0g3x3tv.cloudfront.net`, `dev.kimmobey.com` points to `d1hr4gcvv1txzh.cloudfront.net`). Existing ACM validation CNAMEs and `www` CNAME must also not be modified. Any new CloudFormation work must inventory these and surface conflicts before provisioning.
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

The site is served at `http://localhost:1313/`. Build output lives in `public/` and is built with Hugo 0.160.0.

## Local development workflow

Test locally with `hugo server` before pushing. Standard git workflow applies — commit and push as you would on any other project. The previous Netlify-era restrictions (the `YES` pre-push hook and the per-push authorisation gate) have been removed; they existed only to ration Netlify's 15-credit-per-deploy cost. With GitHub Actions building to S3+CloudFront, deploys are effectively free.

## Architecture

This is a Hugo static site with **no theme** — all layouts are hand-built under `layouts/`. CSS lives in `assets/css/main.css` (processed via Hugo Pipes) and is referenced in `layouts/_default/baseof.html`.

### Content sections

| Section | Path | Purpose |
|---|---|---|
| Portfolio | `content/portfolio/` | Artwork — each work is a page bundle (folder with `index.md` + image file) |
| Studio → Essays | `content/studio/essays/` | Writing, CV content |
| Studio → Practice | `content/studio/practice/` | Process/making content — combined list also surfaces `content/studio/media/` entries |
| Contact | `content/contact.md` | Contact page |

The About section has been decommissioned. `layouts/about/single.html` remains in the repo as dormant code; there is no `content/about.md` and nothing renders at `/about/`. Do not add About back without explicit instruction.

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
