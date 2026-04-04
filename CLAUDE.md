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

The site is served at `http://localhost:1313/`. Netlify deploys from the `public/` directory using Hugo 0.140.2.

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

Dimension format: `H × W cm` (e.g. `90 × 120cm`). Taxonomy values always lowercase with hyphens.

### Controlled vocabulary

`PricingAndVocabulary.md` is the authoritative reference for all taxonomy values, field definitions, pricing formula, and YAML file management rules. Consult it before adding new taxonomy terms or front matter fields.
