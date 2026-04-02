Here it is:

---

**KIM MOBEY — HUGO SITE CONTROLLED VOCABULARY** *Reference document for front matter fields and taxonomy terms* *Version 1.0 — April 2026*

---

**TAXONOMIES** *These drive navigation and filtering. Values must match exactly — capitalisation and spelling are fixed.*

**medium** Values: `oil` `acrylic` `pastel` `charcoal` `ink` `mixed-media` `bronze` `resin` `pewter` `concrete` `linocut` `etching` `screenprint` `aquarelle`

**form** Values: `portrait` `figure` `landscape` `floral` `interior` `abstract` `still-life` `hybrid` *Note: still-life to be confirmed pending portfolio review*

**theme** Values: `migration` `identity` `mythology` `ecology` *Note: this list is deliberately short at launch — add terms only when three or more works share a theme*

**status** Values: `available` `reserved` `sold`

**series** *Values to be populated as named bodies of work are confirmed. Leave blank rather than invent a series name.*

---

**FRONT MATTER FIELDS** *These appear on individual work pages and feed captions, the pricing page, and the catalogue.*

| Field | Type | Public | Notes |
| ----- | ----- | ----- | ----- |
| `title` | text | yes | Use title case |
| `year` | integer | yes | Year of completion |
| `medium` | taxonomy | yes | Base material only — oil, acrylic etc |
| `substrate` | text | yes | canvas, linen, board, paper, resin etc |
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

Dimensions always written as: H × W cm (e.g. 90 × 120cm) Taxonomy values always lowercase with hyphens, no spaces Title case for all work titles Year as four-digit integer Price as integer in EUR, no symbol, no decimals

---

**WHAT DOES NOT GO IN TAXONOMY**

Substrate — front matter text field only Price — hidden field only Collection — hidden field only Edition data — hidden field only

---

*This document should be updated whenever a new taxonomy term is added or a field definition changes. The version number increments with each substantive change.*

---

That should serve as a stable reference point for both threads. Copy it somewhere permanent — your PARA system would be the right place, probably under Career/DigitalPresence or Enterprise/CatalogueAndRecords.

