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

### Root-level content pages

`content/about.md` and `content/contact.md` sit at the root of `content/` with no section. They must declare `type` explicitly in front matter (`type: "about"`, `type: "contact"`) so Hugo resolves the correct layout template regardless of version.

### Controlled vocabulary

`PricingAndVocabulary.md` is the authoritative reference for all taxonomy values, field definitions, pricing formula, and YAML file management rules. Consult it before adding new taxonomy terms or front matter fields.

### Hugo v0.160.0 taxonomy behaviour

Two version-specific rules that must be followed:

1. **Front matter taxonomy keys must use the plural form** (as defined in `hugo.toml`). The singular form silently produces no term pages. Use `forms:`, `statuses:`, `media:`, `themes:`, `series:` — never `form:`, `status:`, `medium:`, `theme:`.
2. **Taxonomy term pages require `layouts/_default/list.html`** for HTML output. `layouts/taxonomy/list.html` alone is not sufficient in v0.160.0+.

## Colour palette and accessibility

The site uses a deliberately muted, refined palette. All colour decisions must satisfy WCAG AA contrast requirements — this is a non-negotiable constraint that must be maintained alongside the aesthetic.

### Palette

| Role | Value | Usage |
|---|---|---|
| Primary text | `#333333` | Body copy, headings, nav |
| Taupe accent | `#7a6e65` | Secondary text, captions, borders, hover states, button background |
| Light background | `#f5f5f5` | Header, footer, cards, filter buttons |
| White | `#ffffff` | Page background, button text on taupe |

### Contrast rules

**WCAG AA thresholds:** 4.5:1 for text below 18px (or 14px bold) — 3:1 for large text (18px+ regular, 14px+ bold).

| Pair | Ratio | Threshold |
|---|---|---|
| `#333` on `#ffffff` | 12.63:1 | Well clear |
| `#333` on `#f5f5f5` | 11.59:1 | Well clear |
| `#7a6e65` on `#ffffff` | 4.95:1 | Passes — small margin |
| `#7a6e65` on `#f5f5f5` | 4.54:1 | Passes — tight (do not lighten either value) |
| `#ffffff` on `#7a6e65` | 4.95:1 | Passes (button text) |

### Rules to follow

- **`#7a6e65` is the floor for small text.** Do not use a lighter colour for any text below 18px on white or `#f5f5f5` backgrounds.
- **Large text (18px+) has more latitude.** The 3:1 threshold gives room for lighter/more decorative tones on large Cormorant Garamond headings if needed.
- **Decorative elements are exempt.** Borders, dividers, background fills, and purely visual accents do not need to meet contrast requirements — only text and interactive controls do.
- **Hover and focus states must maintain contrast.** Use explicit colour shifts rather than `opacity` reductions on text — opacity lowers contrast and can cause failures.
- **Do not reduce the footer text size below 13px.** At 13px, `#7a6e65` on `#f5f5f5` passes at 4.54:1 but has no margin. Any size reduction would require a darker colour.
- **Interactive controls** (buttons, filter buttons, form inputs) must maintain contrast in all states: default, hover, focus, active.
