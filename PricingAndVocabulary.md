Here it is:

---

**KIM MOBEY — HUGO SITE CONTROLLED VOCABULARY** *Reference document for front matter fields and taxonomy terms* *Version 1.0 — April 2026*

---

**TAXONOMIES** *These drive navigation and filtering. Values must match exactly — capitalisation and spelling are fixed.*

**medium** Values: `oil` `acrylic` `pastel` `charcoal` `ink` `mixed-media` `bronze` `resin` `pewter` `concrete` `linocut` `etching` `screenprint` `aquarelle` *Now list-valued on each work — a single piece can list multiple media (e.g. oil + charcoal).*

**substrate** Values: `canvas` `linen` `board` `paper` `wood` `stone` `metal` `ceramic` *Now list-valued. Optional — sculpture often has no substrate. Extend the list as new materials enter the practice.*

**form** Values: `portrait` `figure` `landscape` `floral` `interior` `abstract` `still-life` `hybrid` `surreal` *Note: still-life to be confirmed pending portfolio review*

**theme** Values: `migration` `identity` `mythology` `ecology` `political` `biography` *Note: this list is deliberately short at launch — add terms only when three or more works share a theme*

**status** Values: `available` `reserved` `sold`

**series** *Values to be populated as named bodies of work are confirmed. Leave blank rather than invent a series name.*

---

**FRONT MATTER FIELDS** *These appear on individual work pages and feed captions, the pricing page, and the catalogue.*

| Field | Type | Public | Notes |
| ----- | ----- | ----- | ----- |
| `title` | text | yes | Use title case |
| `year` | integer | yes | Year of completion |
| `medium` | taxonomy (list) | yes | Base material(s) — oil, acrylic etc. Mandatory. |
| `substrate` | taxonomy (list) | yes | canvas, linen, board, paper etc. Optional — sculpture often has none. |
| `dimensions` | text | yes | Format: 90 × 120cm always |
| `form` | taxonomy | yes | What is depicted |
| `theme` | taxonomy | yes | What it is about — optional |
| `status` | taxonomy | yes | available / reserved / sold |
| `series` | taxonomy | yes | Named body of work — optional |
| `category` | text | no | original / study / work-on-paper / miniature |
| `price` | integer | no | EUR value, no symbol |
| `collection` | text | no | Collector name or "private collection" |
| `edition` | text | no | For prints and cast works only |
| `featured` | boolean | no | true for works to surface prominently |
| `miniature` | boolean | no | true for works below \~160cm² |

---

**GALLERY IMAGES — MULTI-ANGLE WORKS**

Applies to sculptures and any other work requiring multiple photographs.

Naming convention: where a work has multiple images, all image files for that work use a zero-padded two-digit numeric suffix before the file extension. The primary image is always -01.

The primary image filename goes in the `image` field and is used as the portfolio grid thumbnail. Additional angles go in the `gallery` field as an array. Single-image works do not use a numeric suffix and omit the gallery field entirely — do not include it as an empty array.

The admin interface gallery input must be a dynamic list — add and remove rows — to accommodate works with any number of additional angles.

```yaml
image: "wabele-01.jpg"
gallery:
  - "wabele-02.jpg"
  - "wabele-03.jpg"
```

---

**PRICING FRAMEWORK**

**Equation:** (H \+ W) × index

**Current index:** €23

**Category modifiers:**

* `original` — no modifier, full equation  
* `study` — equation × 0.6  
* `work-on-paper` — equation × 0.7  
* `miniature` — flat pricing, set per work

**Floor price:** €1800 across all categories

**Miniature threshold:** works below approximately 160cm² (roughly 13×13cm). Review case by case for works between 160cm² and 900cm².

**Index revision triggers:** significant competition placement, institutional exhibition, residency completion, gallery representation

---

**FORMATTING CONVENTIONS**

Dimensions: W × H, cm always implied and never written. Whitespace around × is flexible — 50×60, 50 x 60, and 50 × 60 are all acceptable. Taxonomy values always lowercase with hyphens, no spaces. Title case for all work titles. Year as four-digit integer. Price as integer in EUR, no symbol, no decimals.

---

**WHAT DOES NOT GO IN TAXONOMY**

Substrate — front matter text field only Price — hidden field only Collection — hidden field only Edition data — hidden field only

---

*This document should be updated whenever a new taxonomy term is added or a field definition changes. The version number increments with each substantive change.*

---

**COLOUR PALETTE**

All colours are defined as CSS custom properties in `static/css/main.css`. Never hardcode hex values in CSS or templates.

| Custom property | Value | Role |
|---|---|---|
| `--color-bg-primary` | `#ffffff` | Page background |
| `--color-bg-secondary` | `#f0efed` | Header, footer, cards, pathway blocks |
| `--color-text-primary` | `#1a1a1a` | Body copy, headings, primary labels |
| `--color-text-secondary` | `#6a5f56` | Captions, metadata, secondary labels, filter options |
| `--color-accent` | `#7a6e65` | Interactive states, focus rings, active filters, taxonomy links, button background |
| `--color-border` | `#e0e0e0` | Dividers, input borders |
| `--color-white` | `#ffffff` | Button text on accent background |

**Secondary vs accent — an important distinction:** `--color-text-secondary` (`#6a5f56`) is darker than `--color-accent` (`#7a6e65`). They are not interchangeable. Accent is the warmer taupe used for interactive and decorative states. Secondary text is the slightly darker value used for body text to meet WCAG AA contrast requirements (5.74:1 on white). Do not lighten either value.

`--color-accent` (`#7a6e65`) achieves only 4.32:1 on white — it fails AA for normal text below 18px and must not be used for body copy.

---

**HUGO VERSION NOTES**

Hugo version: 0.160.0

Two version-specific behaviours discovered during build:

1. Front matter taxonomy keys must use the plural form as defined in `hugo.toml`. The singular form silently fails. Correct examples:
   ```yaml
   forms:
     - "portrait"
   statuses:
     - "available"
   ```

2. Taxonomy term pages require `layouts/_default/list.html` for HTML output. `layouts/taxonomy/list.html` alone is insufficient in Hugo v0.160.0+.

---

That should serve as a stable reference point for both threads. Copy it somewhere permanent — your PARA system would be the right place, probably under Career/DigitalPresence or Enterprise/CatalogueAndRecords.

Here's the addition to append to `PricingAndVocabulary.md`:

---

**YAML FILE MANAGEMENT**

*Artwork data lives in multiple YAML files in the `data/` folder, one file per logical body of work or grouping. Hugo reads all files automatically — no configuration required when adding new files.*

---

**Current files and contents**

| File | Contents |
|------|---------|
| `portraits.yaml` | Portrait works not belonging to a named series |
| `migration-works.yaml` | Works primarily themed around migration |
| `sculpture.yaml` | All sculpture regardless of series |
| `prints.yaml` | All printmaking and editions |
| `studies.yaml` | Studies, works on paper, smaller experimental works |

*Update this table whenever a new file is added.*

---

**When to create a new file**

Create a new YAML file when:
- A named body of work reaches three or more works
- A new medium or discipline is introduced that doesn't fit existing files
- A commission series or collaboration warrants its own record group

Do not create a new file for:
- A single work that doesn't yet belong to a series — add to the most logical existing file
- Variations on an existing series — add to that series file

---

**How to add a new file**

1. Create the file in `data/` following the naming convention: lowercase, hyphens, no underscores — e.g. `hiding-and-emerging.yaml`
2. Add the first entry in correctly formatted YAML
3. Add the filename and description to the table above
4. Add the new filename to the admin interface file selector dropdown — one line change in the admin interface

Hugo picks up the new file automatically on the next build. No template or configuration changes required.

---

**Naming convention**

All YAML filenames: lowercase, hyphens only, no underscores, no spaces, descriptive of contents.

Examples:
- `hiding-and-emerging.yaml` ✓
- `Hiding_And_Emerging.yaml` ✗
- `new works.yaml` ✗

---

That can be appended directly to the existing `PricingAndVocabulary.md` as a new section. The current files listed in the table are placeholders based on our earlier discussions — update them to reflect whatever files actually get created during the build.
