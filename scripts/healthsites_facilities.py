#!/usr/bin/env python3
"""Download health facilities from the healthsites.io API for the campaign maps.

Writes one file per country, which the country page maps read:

    theme/static/geojson/<iso3>_facilities.geojson

The API needs a key, so this runs on your computer or in the weekly GitHub
Action, never in the browser. The key is never written to the site, printed
or put in the report. Uses only Python's standard library.

Run from the repository root:

    python3 scripts/healthsites_facilities.py save-key         store your API key (once)
    python3 scripts/healthsites_facilities.py refresh          download every country
    python3 scripts/healthsites_facilities.py refresh sen cod  download some countries
    python3 scripts/healthsites_facilities.py build            rewrite the map files from
                                                               the last download, no API calls

The key is read from the HEALTHSITES_API_KEY environment variable (used by
GitHub Actions) or from ~/.healthsites/api-key (the file the heat map uses).

Safety: if a country comes back with less than 90% of the facilities in the
current map file, or the download fails, the current file is kept and the
report says so. Use --force to accept a large drop.
"""

import argparse
import getpass
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HS_API = "https://healthsites.io/api/v3/facilities/"
HS_KEY_FILE = Path.home() / ".healthsites" / "api-key"

# ISO3 code -> the country name the API expects, and the QGIS boundary file
# used to count facilities per region. Add a country here to give it a map file.
COUNTRIES = {
    "sen": {"name": "Senegal", "boundaries": "sen_admin1.geojson"},
    "cod": {"name": "Democratic Republic of the Congo", "boundaries": "cod_admin1.geojson"},
    "gha": {"name": "Ghana", "boundaries": "gha_admin1.geojson"},
    "tun": {"name": "Tunisia", "boundaries": "tun_admin1.geojson"},
    "zaf": {"name": "South Africa", "boundaries": "zaf_admin1.geojson"},
    "ssd": {"name": "South Sudan", "boundaries": "ssd_admin1.geojson"},
    "moz": {"name": "Mozambique", "boundaries": "moz_admin1.geojson"},
    "gmb": {"name": "The Gambia", "boundaries": "gmb_admin1.geojson"},
}

ROOT = Path(__file__).resolve().parent.parent
GEOJSON_DIR = ROOT / "theme" / "static" / "geojson"
CACHE = ROOT / ".cache" / "healthsites"

SNAP_METRES = 1000    # a facility just outside every region (coastline, river bank) joins
                      # the nearest region if it is this close to its boundary
KEEP_IF_BELOW = 0.9   # keep the current file if the new total is below 90% of it
MIN_FOR_GUARD = 50    # ...unless the current file is this small
RETRIES = 3

# Grouped types, most specific level of care first. Used for counts only;
# the map shows the type as OpenStreetMap records it.
TYPE_GROUPS = (
    ("hospital", ("hospital",)),
    ("clinic", ("clinic", "centre", "center", "health_post")),
    ("doctor", ("doctor",)),
    ("pharmacy", ("pharmacy", "chemist")),
)
OTHER = "other"


class ApiError(Exception):
    """The API refused or failed. The message never contains the key."""


# ---------- small helpers ----------

def die(msg):
    sys.exit(f"Stopped: {msg}")


def rel(path):
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    """Write atomically, so a failed run never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    tmp.replace(path)


def out_file(iso3):
    return GEOJSON_DIR / f"{iso3}_facilities.geojson"


def cache_file(iso3):
    return CACHE / f"{iso3}.json"


def today():
    return datetime.now(timezone.utc).date().isoformat()


# ---------- the API ----------

def hs_key():
    key = os.environ.get("HEALTHSITES_API_KEY", "").strip()
    if not key and HS_KEY_FILE.exists():
        key = HS_KEY_FILE.read_text().strip()
    if not key:
        die("no healthsites.io API key. Run: python3 scripts/healthsites_facilities.py save-key")
    return key


def cmd_save_key(_args):
    key = getpass.getpass("Paste your healthsites.io API key (it will not show): ").strip()
    if not key:
        die("nothing was pasted.")
    HS_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(HS_KEY_FILE.parent, 0o700)
    HS_KEY_FILE.write_text(key + "\n")
    os.chmod(HS_KEY_FILE, 0o600)
    print(f"Saved to {HS_KEY_FILE} (readable only by you).")


def api_reason(err, key):
    """The API's own short explanation of an HTTP error, with the key removed."""
    try:
        text = err.read().decode("utf-8", "replace").strip()
    except Exception:
        return ""
    if not text or text.startswith("<"):
        return ""  # empty, or an HTML error page
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("detail") or data.get("message") or data.get("error") or data
        text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    except ValueError:
        pass
    for secret in {key, urllib.parse.quote(key)} - {""}:
        text = text.replace(secret, "***")
    return " ".join(text.split())[:200]


def hs_get(params):
    """One API call. Returns the parsed JSON, or None for a page past the end."""
    url = HS_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "campaigns.healthsites.io map build"})
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404 and params.get("page", 1) > 1:
                return None  # some paginated APIs answer 404 past the last page
            if e.code in (401, 403):
                raise ApiError("healthsites.io refused the key") from None
            if e.code == 429:
                raise ApiError("healthsites.io daily limit reached") from None
            if e.code < 500 or attempt == RETRIES:
                reason = api_reason(e, params.get("api-key", ""))
                raise ApiError(f"healthsites.io returned HTTP {e.code}"
                               + (f" ({reason})" if reason else "")) from None
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            if attempt == RETRIES:
                reason = getattr(e, "reason", None) or type(e).__name__
                raise ApiError(f"could not read from healthsites.io ({reason})") from None
        time.sleep(5 * attempt)
    raise ApiError("healthsites.io did not answer")


def facility_record(item):
    a = item.get("attributes") or {}
    coords = (item.get("centroid") or {}).get("coordinates")
    if not coords or len(coords) < 2:
        return None
    try:
        lon, lat = float(coords[0]), float(coords[1])
    except (TypeError, ValueError):
        return None
    return {
        "id": f"{item.get('osm_type', '')}/{item.get('osm_id', '')}",
        "name": (a.get("name") or "").strip(),
        "type": (a.get("healthcare") or a.get("amenity") or "").strip(),
        "lon": round(lon, 5),
        "lat": round(lat, 5),
    }


def download(iso3, key, max_pages):
    """All facilities for one country, as small records. Returns (records, calls)."""
    name = COUNTRIES[iso3]["name"]
    records, seen, page = [], set(), 1
    while page <= max_pages:
        data = hs_get({"country": name, "page": page, "api-key": key})
        if not data:
            break
        if not isinstance(data, list):
            raise ApiError("healthsites.io returned an unexpected answer")
        for item in data:
            rec = facility_record(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                records.append(rec)
        if page % 10 == 0:
            print(f"  {iso3}: page {page}, {len(records)} facilities so far", flush=True)
        page += 1
    else:
        raise ApiError(f"stopped after {max_pages} pages; raise --max-pages")
    return records, page  # the last, empty page counts as a call too


# ---------- regions ----------

def load_regions(filename):
    """[(name, bbox, polygons)] from a QGIS admin-1 export."""
    path = GEOJSON_DIR / filename
    if not path.exists():
        return []
    out = []
    for f in read_json(path)["features"]:
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        if g.get("type") == "Polygon":
            polys = [g["coordinates"]]
        elif g.get("type") == "MultiPolygon":
            polys = g["coordinates"]
        else:
            continue
        xs = [pt[0] for poly in polys for pt in poly[0]]
        ys = [pt[1] for poly in polys for pt in poly[0]]
        name = p.get("adm1_name") or p.get("name") or ""
        out.append((name, (min(xs), min(ys), max(xs), max(ys)), polys))
    return out


def point_in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def region_of(lon, lat, regions):
    for name, (x0, y0, x1, y1), polys in regions:
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        for poly in polys:
            if point_in_ring(lon, lat, poly[0]) and not any(
                    point_in_ring(lon, lat, hole) for hole in poly[1:]):
                return name
    return ""


def metres_to_ring(lon, lat, ring):
    """Approximate distance in metres from a point to a polygon ring (fine below ~10 km)."""
    kx = 111320 * math.cos(math.radians(lat))
    ky = 110540
    px, py = lon * kx, lat * ky
    best = float("inf")
    for (ax, ay, *_), (bx, by, *_) in zip(ring, ring[1:]):
        ax, ay, bx, by = ax * kx, ay * ky, bx * kx, by * ky
        dx, dy = bx - ax, by - ay
        t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(px - ax - t * dx, py - ay - t * dy))
    return best


def nearest_region(lon, lat, regions, limit=SNAP_METRES):
    """The region whose boundary is within `limit` metres of the point, or ''."""
    pad = limit / 100000  # ~1 km in degrees, generous enough for the bbox test
    best, name_best = limit, ""
    for name, (x0, y0, x1, y1), polys in regions:
        if not (x0 - pad <= lon <= x1 + pad and y0 - pad <= lat <= y1 + pad):
            continue
        for poly in polys:
            d = metres_to_ring(lon, lat, poly[0])
            if d <= best:
                best, name_best = d, name
    return name_best


def type_group(t):
    t = (t or "").lower()
    for group, words in TYPE_GROUPS:
        if any(w in t for w in words):
            return group
    return OTHER


# ---------- the map file ----------

def build_geojson(iso3, records, downloaded, calls):
    """The map file for one country: small points plus counts in the metadata."""
    regions = load_regions(COUNTRIES[iso3]["boundaries"])
    by_region = {name: 0 for name, _, _ in regions}
    by_type = {g: 0 for g, _ in TYPE_GROUPS}
    by_type[OTHER] = 0
    features, outside, unnamed, snapped = [], 0, 0, 0
    for r in sorted(records, key=lambda r: r["id"]):
        region = region_of(r["lon"], r["lat"], regions) if regions else ""
        if not region and regions:
            region = nearest_region(r["lon"], r["lat"], regions)
            snapped += bool(region)
        if region:
            by_region[region] += 1
        elif regions:
            outside += 1
        if not r["name"]:
            unnamed += 1
        by_type[type_group(r["type"])] += 1
        features.append({"type": "Feature",
                         "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                         "properties": {"n": r["name"], "t": r["type"], "id": r["id"], "r": region}})
    metadata = {
        "title": f"Health facilities in {COUNTRIES[iso3]['name']} on OpenStreetMap",
        "country": COUNTRIES[iso3]["name"],
        "iso3": iso3,
        "total": len(features),
        "by_type": by_type,
        "by_region": by_region,
        "outside_regions": outside,
        "snapped_to_region": snapped,
        "unnamed": unnamed,
        "downloaded": downloaded,
        "api_calls": calls,
        "includes": "All facility types the healthsites.io API serves, including pharmacies.",
        "source": "healthsites.io API v3",
        "attribution": "healthsites.io / (c) OpenStreetMap contributors",
        "licence": "ODbL 1.0",
    }
    return {"type": "FeatureCollection", "metadata": metadata, "features": features}


def current_ids(iso3):
    path = out_file(iso3)
    if not path.exists():
        return None
    try:
        return {f["properties"]["id"] for f in read_json(path)["features"]}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save(iso3, records, downloaded, calls, force, report):
    """Write the map file unless the new download looks broken. Returns True if written."""
    old = current_ids(iso3)
    new = {r["id"] for r in records}
    label = f"{COUNTRIES[iso3]['name']} ({iso3})"
    if not records:
        report.append(f"| {label} | — | — | **Kept the current file:** the API returned no facilities. |")
        return False
    if (old is not None and len(old) >= MIN_FOR_GUARD and not force
            and len(new) < KEEP_IF_BELOW * len(old)):
        report.append(f"| {label} | {len(new):,} | {len(old):,} before | "
                      f"**Kept the current file:** the new total is more than "
                      f"{round(100 * (1 - KEEP_IF_BELOW))}% lower. Check, then rerun with --force. |")
        return False
    gj = build_geojson(iso3, records, downloaded, calls)
    write_json(out_file(iso3), gj)
    meta = gj["metadata"]
    if old is None:
        change = "new file"
    else:
        change = f"+{len(new - old):,} / −{len(old - new):,}"
    notes = []
    if meta["snapped_to_region"]:
        notes.append(f"{meta['snapped_to_region']:,} just outside a boundary, placed in the nearest region")
    if meta["outside_regions"]:
        notes.append(f"{meta['outside_regions']:,} outside every region boundary")
    report.append(f"| {label} | {meta['total']:,} | {change} | {'; '.join(notes)} |")
    return True


# ---------- commands ----------

def pick(codes):
    codes = [c.lower() for c in codes] or list(COUNTRIES)
    unknown = [c for c in codes if c not in COUNTRIES]
    if unknown:
        die(f"unknown country code {', '.join(unknown)}. Known: {', '.join(COUNTRIES)}")
    return codes


def report_header():
    return ["## Health facility refresh", "",
            f"Downloaded from the healthsites.io API on {today()}.", "",
            "| Country | Facilities | Change since the last file | Notes |",
            "|---|---:|---|---|"]


def finish(report, path, calls, ok, failed):
    report += ["", f"API calls: {calls:,}."]
    if failed:
        report += ["", "Not refreshed: " + ", ".join(failed) + ". Their current files are unchanged."]
    report += ["", "Review a country page on localhost or after merging. Facility names, types "
               "and locations: © OpenStreetMap contributors, ODbL 1.0."]
    text = "\n".join(report) + "\n"
    if path:
        Path(path).write_text(text, encoding="utf-8")
    print()
    print(text)
    if not ok:
        sys.exit(1)


def cmd_refresh(args):
    key = hs_key()
    report, calls, ok, failed = report_header(), 0, 0, []
    for iso3 in pick(args.countries):
        name = COUNTRIES[iso3]["name"]
        print(f"{name}: downloading…", flush=True)
        try:
            records, n = download(iso3, key, args.max_pages)
        except ApiError as e:
            report.append(f"| {name} ({iso3}) | — | — | **Kept the current file:** {e}. |")
            failed.append(name)
            print(f"{name}: {e}. Keeping the current file.", flush=True)
            continue
        calls += n
        write_json(cache_file(iso3), {"country": name, "downloaded": today(),
                                      "api_calls": n, "facilities": records})
        if save(iso3, records, today(), n, args.force, report):
            ok += 1
            print(f"{name}: {len(records):,} facilities in {n} calls -> {rel(out_file(iso3))}", flush=True)
        else:
            failed.append(name)
    finish(report, args.report, calls, ok, failed)


def cmd_build(args):
    report, ok, failed = report_header(), 0, []
    report[2] = "Rebuilt from the last download (no API calls)."
    for iso3 in pick(args.countries):
        path = cache_file(iso3)
        if not path.exists():
            print(f"{iso3}: no download yet. Run: refresh {iso3}")
            failed.append(COUNTRIES[iso3]["name"])
            continue
        c = read_json(path)
        if save(iso3, c["facilities"], c["downloaded"], c.get("api_calls"), args.force, report):
            ok += 1
        else:
            failed.append(COUNTRIES[iso3]["name"])
    finish(report, args.report, 0, ok, failed)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("save-key", help="store your healthsites.io API key").set_defaults(fn=cmd_save_key)
    for name, fn, text in (("refresh", cmd_refresh, "download from the API and write the map files"),
                           ("build", cmd_build, "rewrite the map files from the last download")):
        s = sub.add_parser(name, help=text)
        s.add_argument("countries", nargs="*", help=f"ISO3 codes (default: all of {', '.join(COUNTRIES)})")
        s.add_argument("--force", action="store_true", help="write the file even if the total drops by over 10%%")
        s.add_argument("--report", help="also write the summary to this markdown file")
        if name == "refresh":
            s.add_argument("--max-pages", type=int, default=2000)
        s.set_defaults(fn=fn)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
