# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Publishing rule

**Never run `git commit` or `git push` until Mark types "publish".** "Go ahead", "OK", "continue" and similar mean keep working, not publish. This overrides any task file or handoff that says to commit or push after an OK.

## Commands

```bash
# Activate venv first — required before running pelican directly
source venv/bin/activate

make serve      # Build then start dev server with auto-reload at http://127.0.0.1:8000
make build      # One-off build to output/
make publish    # Build using publishconf.py (SITEURL = https://campaigns.healthsites.io)
make clean      # Remove output/
```

`make serve` runs `pelican content` then `pelican --listen` — both steps require the venv to be active.

## Architecture

This is a **Pelican static site** serving multilingual health facility mapping campaign pages for African countries.

### Multi-language system

The only active plugin is `i18n_subsites`. It generates language sub-sites at `/fr/`, `/pt/`, `/ar/` from English source content. Language-specific variants of a page are created by appending `-{lang}` to the filename (e.g., `index-fr.md` is the French translation of `index.md`).

Language-to-country mapping (enforced in templates, not automatically by Pelican):
- Senegal → EN + FR only
- Mozambique → EN + PT only
- South Sudan → EN + AR only
- South Africa → EN only

Arabic pages set `dir="rtl"` on the `<html>` tag. Templates detect the current language via:
```jinja2
{% set is_fr = (page and page.lang == 'fr') or DEFAULT_LANG == 'fr' %}
```

Untranslated pages fall back to English (`I18N_UNTRANSLATED_PAGES = 'cleanurl'`).

**Known issue:** The language switcher in `base.html` has hardcoded `http://127.0.0.1:8000` URLs instead of using `SITEURL`. These must be updated manually before production builds.

### Content structure

- `content/` — Root-level pages: `index.md`, `about.md` (and their `-fr`, `-pt`, `-ar` variants)
- `content/about/` — Sub-pages of About (e.g. `methodology.md`)
- `content/campaigns/index.md` — Campaign listing page (template: `campaigns`)
- `content/campaigns/{country}/index.md` — Per-country page (template: `country`)
- `content/campaigns/{country}/{region}.md` — Per-region page (template: `region`)

The campaign listing uses `campaigns-fr.md`, `campaigns-pt.md`, `campaigns-ar.md` as translation variants of `index.md` in the campaigns directory.

### Campaign page metadata

**Country index pages** (`country` template):
- `Country`, `Total_regions`

**Region pages** (`region` template):

| Field | Description |
|---|---|
| `Country` | Display name (e.g. `Mozambique`) |
| `Country_slug` | URL slug (e.g. `mozambique`) |
| `Region` | Region name for breadcrumb |
| `Campaign_status` | Status label (e.g. `Active - Seeking Funding`) |
| `Budget_needed` | Phase 1 budget (e.g. `€75,000`) |
| `Facilities_target` | Target count for Phase 1 |
| `Facilities_validated` | Validated count (shown when complete) |
| `Emergency_facilities` | Emergency facilities identified |
| `Start_date` | Year or date |
| `Cta_primary_url` / `Cta_primary_label` | Primary action button |
| `Cta_secondary_url` / `Cta_secondary_label` | Secondary action button |
| `Phase2_status` | If set, renders a Phase 2 sidebar block |
| `Phase2_target` / `Phase2_budget` / `Phase2_cta_url` / `Phase2_cta_label` | Phase 2 details |

### Adding a new region

Two changes are required:
1. Create `content/campaigns/{country}/{region}.md` (and translation variants)
2. Manually add the region card to `country.html` — region cards are hardcoded per-country, not auto-generated from content files

### Region maps

A region page reuses its country's two map files. Add to its front matter:

```
geojson_file: sen_admin1.geojson          # same boundary file as the country page
facilities_geojson: sen_facilities.geojson # same healthsites.io API download
```

### Region tiers

Every region page has `Region_tier: campaign` (invites support) or `Region_tier: open-data` (map, facility figures, API ask and a "Want a campaign here? Tell us" link). Change that one line to move a region. Pages without it are campaigns if they have a `Campaign_status`.

- `python3 scripts/region_pages.py sen --campaign <names>` creates a front-matter-only page for every region in the boundary file that has no page yet. It never touches existing pages. Region pages without a body get their text from `region.html`, in English and French.
- The Senegal page builds its region cards from the region pages: every campaign region, plus any page with `Card_text`. Cards sort by `Order` (two digits, e.g. `01`). `Card_status` overrides the chip text.
- The country map colours regions from the pages: `status: complete` in the boundary file is green (validated), `Region_tier: campaign` is red (inviting support), the rest grey (open data). The boundary file's `planned` value is no longer used once a country has region pages.

`partials/campaign_map.html` then zooms the map to the region, fades the others and shows only that region's facilities. `Region:` must match `adm1_name` in the boundary file exactly (accents included); if it differs, add `adm1_name: <exact name>`. The country map's region popups link to every published region page automatically.

### Adding a campaign country

Every campaign country has four files (The Gambia, `gmb`, is the worked example):

1. `theme/static/geojson/<iso3>_admin1.geojson`: exported from QGIS (EPSG:4326, 6 decimals,
   field `adm1_name`, optionally `adm1_pcode`), with its filled-in `<iso3>_admin1.qmd`.
   QGIS is the source of truth: never hand-edit the GeoJSON.
2. A line in `COUNTRIES` in `scripts/healthsites_facilities.py`:
   `"<iso3>": {"name": "<country name the API accepts>", "boundaries": "<iso3>_admin1.geojson"}`.
   Then `python3 scripts/healthsites_facilities.py refresh <iso3>` writes
   `<iso3>_facilities.geojson`, and the Monday refresh includes the country.
3. `content/campaigns/<slug>.md` with `Template: country`, `campaign_country: true`, `stage`,
   `order`, `geojson_file`, `facilities_geojson`, `map_center_lat`, `map_center_lng` and
   `map_zoom`. Copy `ghana.md`.

### Templates

Located in `theme/templates/` (Jinja2):
- `base.html` — Layout, nav, language switcher
- `index.html` — Homepage with ityped.js typing animation
- `campaigns.html` — Campaign listing
- `country.html` — Per-country page with hardcoded region cards per country
- `region.html` — Per-region page with sidebar stats and optional Phase 2 block
- `macros/typed.html` — Reusable ityped macro

### Styling and JS

`theme/static/css/vanilla.css` is hand-written (no preprocessor/bundler). CSS variables define the color palette (primary red: `#f44a52`). Fonts loaded from Google Fonts: Raleway (headings), Ubuntu (body), Noto Sans Arabic.

`theme/static/js/ityped.min.js` is vendored. No npm build step — `package.json` only tracks the `ityped` version as a reference.

### URL structure

Pages are served at `/{slug}/index.html`. Navigation menus are defined per-language in `pelicanconf.py` as `MENUITEMS`, `MENUITEMS_FR`, `MENUITEMS_PT`, `MENUITEMS_AR`. All menu links require a leading slash.
