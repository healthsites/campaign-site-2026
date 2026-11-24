#!/usr/bin/env python3
"""Create a page for every region of a country that does not have one yet.

Reads the country's QGIS boundary file and writes one small page per missing
region to content/campaigns/<country>/<region>.md. Each page holds only front
matter: the region template writes the text, the map and the figures from the
same boundary and facility files as the country page. Existing pages are never
touched, so this is safe to run again.

    python3 scripts/region_pages.py sen --campaign Ziguinchor Sédhiou Kédougou Kolda Kaffrine
    python3 scripts/region_pages.py sen --dry-run

Regions named after --campaign get "Region_tier: campaign": they invite support.
The others get "Region_tier: open-data": a map, the facility count and the API.
To move a region later, change that one line in its page.
Standard library only.
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEOJSON = ROOT / "theme" / "static" / "geojson"
CONTENT = ROOT / "content" / "campaigns"

# ISO3 code -> the country page's name and slug, and its two map files.
COUNTRIES = {
    "sen": {"country": "Senegal", "slug": "senegal",
            "boundaries": "sen_admin1.geojson", "facilities": "sen_facilities.geojson"},
}


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def front_matter(path):
    """The front matter of a Pelican markdown page, as a dict with lowercase keys."""
    meta = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "---":
            continue
        m = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if not m:
            break
        meta[m.group(1).lower()] = m.group(2).strip()
    return meta


def existing_regions(slug):
    """Region names (adm1_name or Region) that already have a page for this country."""
    found = {}
    for path in CONTENT.rglob("*.md"):
        meta = front_matter(path)
        if meta.get("template") == "region" and meta.get("country_slug") == slug and not meta.get("parent_url"):
            found[meta.get("adm1_name") or meta.get("region", "")] = path
    return found


def page_text(cfg, region, campaign, order):
    slug = slugify(region)
    lines = [
        f"Title: {region}",
        "Template: region",
        f"Slug: campaigns/{cfg['slug']}/{slug}",
        "Lang: en",
        "Status: published",
        f"Country: {cfg['country']}",
        f"Country_slug: {cfg['slug']}",
        f"Region: {region}",
        f"Region_tier: {'campaign' if campaign else 'open-data'}",
        f"geojson_file: {cfg['boundaries']}",
        f"facilities_geojson: {cfg['facilities']}",
    ]
    if campaign:
        lines += [
            "Campaign_status: Inviting support",
            f"Order: {order:02d}",
            f"Cta_primary_label: Support a campaign in {region}",
            "Cta_primary_url: https://healthsites.io/contact",
            f"Cta_secondary_label: See {region} on healthsites.io",
            f"Cta_secondary_url: https://healthsites.io/map?place={region}",
        ]
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("iso3", choices=sorted(COUNTRIES))
    p.add_argument("--campaign", nargs="*", default=[], help="regions that invite support (exact boundary names)")
    p.add_argument("--first-order", type=int, default=10, help="Order of the first new campaign card")
    p.add_argument("--dry-run", action="store_true", help="list what would be written, write nothing")
    args = p.parse_args()

    cfg = COUNTRIES[args.iso3]
    regions = [f["properties"].get("adm1_name") or f["properties"].get("name")
               for f in json.loads((GEOJSON / cfg["boundaries"]).read_text(encoding="utf-8"))["features"]]
    unknown = [c for c in args.campaign if c not in regions]
    if unknown:
        sys.exit(f"Stopped: not in {cfg['boundaries']}: {', '.join(unknown)}. Names: {', '.join(regions)}")

    have = existing_regions(cfg["slug"])
    print(f"| Region | Page | Tier |\n|---|---|---|")
    for region in regions:
        if region in have:
            print(f"| {region} | {have[region].relative_to(ROOT)} (kept) | — |")
            continue
        campaign = region in args.campaign
        order = args.first_order + (args.campaign.index(region) if campaign else 0)
        path = CONTENT / cfg["slug"] / f"{slugify(region)}.md"
        if path.exists():
            print(f"| {region} | {path.relative_to(ROOT)} exists without a matching Region: line (kept) | — |")
            continue
        if not args.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(page_text(cfg, region, campaign, order), encoding="utf-8")
        tier = "campaign" if campaign else "open-data"
        print(f"| {region} | {path.relative_to(ROOT)}{' (dry run)' if args.dry_run else ''} | {tier} |")
    for c in args.campaign:
        if c in have:
            print(f"\nNote: {c} already has a page. Add 'Region_tier: campaign' to it yourself.")


if __name__ == "__main__":
    main()
