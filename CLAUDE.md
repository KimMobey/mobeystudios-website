# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Start local dev server (live reload)
hugo server

# Build for production
hugo

# Build with drafts visible
hugo server -D
```

The site is served at `http://localhost:1313/`. Netlify deploys from the `public/` directory using Hugo 0.160.0.

## Local development workflow

**Default behaviour: never push to remote unless explicitly instructed to do so in the current prompt.** If a task implies pushing — such as "deploy", "go live", "publish", or "send to Netlify" — ask for confirmation before proceeding. A local commit is always the default endpoint for any task unless the prompt contains the exact words "push to remote" or "git push".

Netlify free tier allows 300 credits per month. Each production deploy costs 15 credits, giving a maximum of 20 deploys per month. Credits reset on the 1st of each month.

All development and testing must be done locally using `hugo server` before any push to remote. A pre-push hook at `.git/hooks/pre-push` enforces a confirmation step before every push — type `YES` to proceed, anything else cancels.

Push only when a meaningful and tested set of changes is complete. Batch related changes into single commits. Never push for individual small fixes.

**The site is currently paused until May 1 when credits reset. Do not push to remote until then.**

## Architecture

This is a Hugo static site with **no theme** — all layouts are hand-built under `layouts/`. CSS lives in `assets/css/main.css` (processed via Hugo Pipes) and is referenced in `layouts/_default/baseof.html`.

### Content sections

| Section | Path | Purpose |
|---|---|---|
| Portfolio | `content/portfolio/` | Artwork — each work is a page bundle (folder with `index.md` + image file) |
| Studio → Essays | `content/studio/essays/` | Writing, CV content |
| Studio → Practice | `content/studio/practice/` | Process/making content |
| About | `content/about.md` | Biography and artist statement |
| Contact | `content/contact.md` | Contact page |

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

`content/about.md` and `content/contact.md` sit at the root of `content/` with no section. They must declare `type` explicitly in front matter (`type: "about"`, `type: "contact"`) so Hugo resolves the correct layout template regardless of version.

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
