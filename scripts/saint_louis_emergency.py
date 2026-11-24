#!/usr/bin/env python3
"""Build the public map file of the 35 Saint-Louis emergency pregnancy facilities.

In 2022 the Saint-Louis campaign found 35 facilities likely to support an
emergency pregnancy: clinic, doctors or hospital, at least one bed, emergency
services, and a published phone number. This script matches each one to its
OpenStreetMap record and adds this week's heat, for two pages:

    /campaigns/senegal/saint-louis/          the 35 in red on the region map
    /campaigns/senegal/saint-louis/etape-2/  the 35 coloured by heat, with a list

Run from the repository root, after scripts/senegal_heat.py build:

    python3 scripts/saint_louis_emergency.py build <survey.csv>

<survey.csv> is the 2022 survey list with the columns of
github.com/afrimapr/senegal-healthsites-2022/blob/main/data/emerg-preg-stlouis-osmsurvey.csv
(or Mark's spreadsheet saved as CSV with the same columns). Keep it out of the
repository: it holds phone numbers.

Writes theme/static/geojson/sen_saint_louis_emergency.geojson. Each facility
keeps only public OpenStreetMap fields (OSM ID, name, type, region) and its
heat. Phone numbers, staffing and beds from the survey never reach the file;
the metadata holds only counts. Standard library only.
"""

import argparse
import csv
import difflib
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEOJSON = ROOT / "theme" / "static" / "geojson"
FACILITIES = GEOJSON / "sen_facilities.geojson"
HEAT = GEOJSON / "sen_facility_heat.geojson"
OUT = GEOJSON / "sen_saint_louis_emergency.geojson"

MATCH_METRES = 150      # look for the OpenStreetMap record this close to the survey point
SAME_NAME = 0.6         # name similarity that beats a closer record with another name
PUBLIC_FIELDS = ("id", "n", "t", "r", "tmax", "p", "c")


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(de|du|la|le|des|d)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(s.split())


def metres(lon1, lat1, lon2, lat2):
    return math.hypot((lon1 - lon2) * 111320 * math.cos(math.radians(lat1)), (lat1 - lat2) * 110540)


def match(row, features):
    """(feature, metres, name similarity) for one survey row, or (None, None, 0)."""
    lon, lat = float(row["longitude"]), float(row["latitude"])
    name = norm(row["name_of_facility"])
    near = []
    for f in features:
        flon, flat = f["geometry"]["coordinates"]
        if abs(flon - lon) > 0.01 or abs(flat - lat) > 0.01:
            continue
        d = metres(lon, lat, flon, flat)
        if d <= MATCH_METRES:
            near.append((d, difflib.SequenceMatcher(None, name, norm(f["properties"]["n"])).ratio(), f))
    if not near:
        return None, None, 0
    named = [c for c in near if c[1] >= SAME_NAME]
    d, sim, f = max(named, key=lambda c: (c[1], -c[0])) if named else min(near, key=lambda c: c[0])
    return f, d, sim


def no_doctor(row):
    return (row.get("number_of_doctors") or "").strip() in ("", "0", "NA")


def build(rows, facilities, heat):
    by_id = {f["properties"]["id"]: f["properties"] for f in heat["features"]}
    hm = heat.get("metadata", {})
    features, checks, seen = [], [], set()
    for row in rows:
        f, d, sim = match(row, facilities["features"])
        if f is None:
            raise SystemExit(f"Stopped: no OpenStreetMap record within {MATCH_METRES} m of "
                             f"'{row['name_of_facility']}'.")
        p = f["properties"]
        if p["id"] in seen:
            raise SystemExit(f"Stopped: two survey rows match {p['id']} ({p['n']}).")
        seen.add(p["id"])
        h = by_id.get(p["id"], {})
        props = {"id": p["id"], "n": p["n"], "t": p["t"], "r": p["r"],
                 "tmax": h.get("tmax"), "p": h.get("p"), "c": h.get("c")}
        features.append({"type": "Feature", "geometry": f["geometry"], "properties": props})
        checks.append((row["name_of_facility"], p["n"], p["id"], round(d), round(sim, 2), p["r"]))
    features.sort(key=lambda f: (-(f["properties"]["p"] or -1), f["properties"]["n"]))
    pct = [f["properties"]["p"] for f in features if f["properties"]["p"] is not None]
    meta = {
        "title": "Saint-Louis: 35 facilities likely to support an emergency pregnancy (2022 survey)",
        "total": len(features),
        "with_heat": len(pct),
        "hottest_20": sum(1 for x in pct if x >= 80),
        "hottest_40": sum(1 for x in pct if x >= 60),
        "no_doctor_2022": sum(1 for r in rows if no_doctor(r)),
        "outside_saint_louis": sum(1 for f in features if f["properties"]["r"] != "Saint-Louis"),
        "heat_from": hm.get("date_from"),
        "heat_to": hm.get("date_to"),
        "heat_classes": hm.get("classes"),
        "heat_metric": hm.get("metric"),
        "fields": {"n": "Name (OpenStreetMap)", "t": "Type (OpenStreetMap)", "r": "Region (admin 1)",
                   "id": "OpenStreetMap ID", "tmax": "Daytime high over the heat week (°C), HeatReady",
                   "p": "Percentile of tmax among Senegal's mapped health facilities",
                   "c": "Heat class 1 (coolest 20%) to 5 (hottest 20%)"},
        "source": "2022 Saint-Louis campaign survey, matched to healthsites.io / OpenStreetMap; heat from HeatReady",
        "attribution": "healthsites.io / (c) OpenStreetMap contributors; HeatReady",
        "licence": "ODbL 1.0",
    }
    return {"type": "FeatureCollection", "metadata": meta, "features": features}, checks


def cmd_build(args):
    with open(args.survey, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("name_of_facility") or "").strip()]
    facilities = json.loads(FACILITIES.read_text(encoding="utf-8"))
    heat = json.loads(HEAT.read_text(encoding="utf-8"))
    gj, checks = build(rows, facilities, heat)
    OUT.write_text(json.dumps(gj, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("| Survey name | OpenStreetMap name | OSM ID | Distance (m) | Name match | Region |")
    print("|---|---|---|---:|---:|---|")
    for c in checks:
        flag = " **check**" if c[4] < SAME_NAME else ""
        print(f"| {c[0]} | {c[1]}{flag} | {c[2]} | {c[3]} | {c[4]} | {c[5]} |")
    m = gj["metadata"]
    print(f"\n{m['total']} facilities -> {OUT.relative_to(ROOT)}. Heat {m['heat_from']} to {m['heat_to']}: "
          f"{m['hottest_20']} in the hottest 20%, {m['hottest_40']} in the hottest 40%. "
          f"No doctor recorded in 2022: {m['no_doctor_2022']}. Outside the Saint-Louis outline: "
          f"{m['outside_saint_louis']}.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="write the public map file of the 35")
    b.add_argument("survey", help="the 2022 survey list as CSV (kept out of the repository)")
    b.set_defaults(fn=cmd_build)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
