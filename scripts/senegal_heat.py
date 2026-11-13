#!/usr/bin/env python3
"""Build the data for the Senegal heat map (/campaigns/senegal/heat/).

Downloads health facilities in Senegal from the healthsites.io API and daily
heat metrics from the HeatReady API, joins them, and writes one GeoJSON file
that the page reads:

    theme/static/geojson/sen_facility_heat.geojson

Both APIs need keys, so this runs on your computer, never in the browser.
Neither key is written to the site. Uses only Python's standard library.

Run from the repository root:

    python3 scripts/senegal_heat.py save-key     store your healthsites.io API key (once)
    python3 scripts/senegal_heat.py facilities   download Senegal's facilities
    python3 scripts/senegal_heat.py cells        group facilities into ~9 km weather cells
    python3 scripts/senegal_heat.py create       create the HeatReady project (once)
    python3 scripts/senegal_heat.py status       is the HeatReady project ready?
    python3 scripts/senegal_heat.py build        fetch recent heat and write the map file

To refresh the map later, run `build` again. Run `facilities`, `cells` and
`build` if you also want newly mapped facilities (see `cells` for the catch).

HeatReady credentials are read from ~/.heatready/credentials, the file that
heatready.py writes when you redeem your invite.
"""

import argparse
import bisect
import getpass
import json
import os
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

COUNTRY = "Senegal"
HS_API = "https://healthsites.io/api/v3/facilities/"
HS_KEY_FILE = Path.home() / ".healthsites" / "api-key"
HS_FREE_CALLS_PER_DAY = 50

HR_API_DEFAULT = "https://5trhrgas69.execute-api.us-east-1.amazonaws.com/v1/evaluate"
HR_CRED_FILE = Path.home() / ".heatready" / "credentials"
PROJECT_ID = "senegal-facility-heat"
HR_PAGE = 2000

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "senegal-heat"
FACILITIES_FILE = CACHE / "facilities.json"
CELLS_FILE = CACHE / "cells.geojson"
SETTINGS_FILE = CACHE / "settings.json"
REGIONS_FILE = ROOT / "theme" / "static" / "geojson" / "sen_admin1.geojson"
OUT_FILE = ROOT / "theme" / "static" / "geojson" / "sen_facility_heat.geojson"

LARGE_PROJECT = 1500  # cells; above this, suggest coarser cells


# ---------- small helpers ----------

def die(msg):
    sys.exit(f"Stopped: {msg}")


def read_json(path, what):
    if not path.exists():
        die(f"{rel(path)} not found. Run `{what}` first.")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def mb(path):
    return path.stat().st_size / 1e6


def rel(path):
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


# ---------- healthsites.io ----------

def hs_key():
    key = os.environ.get("HEALTHSITES_API_KEY", "").strip()
    if not key and HS_KEY_FILE.exists():
        key = HS_KEY_FILE.read_text().strip()
    if not key:
        die("no healthsites.io API key. Run: python3 scripts/senegal_heat.py save-key")
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


def hs_get(params):
    url = HS_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "campaigns.healthsites.io heat map build"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            die("healthsites.io refused the key. Check it with `save-key`.")
        if e.code == 429:
            die("healthsites.io daily limit reached. Try again tomorrow.")
        die(f"healthsites.io returned HTTP {e.code}.")
    except urllib.error.URLError as e:
        die(f"could not reach healthsites.io ({e.reason}).")


def facility_record(item):
    a = item.get("attributes") or {}
    coords = (item.get("centroid") or {}).get("coordinates")
    if not coords or len(coords) < 2:
        return None
    return {
        "id": f"{item.get('osm_type', '')}/{item.get('osm_id', '')}",
        "name": (a.get("name") or "").strip(),
        "type": (a.get("healthcare") or a.get("amenity") or "").strip(),
        "lon": round(float(coords[0]), 6),
        "lat": round(float(coords[1]), 6),
    }


def cmd_facilities(args):
    key = hs_key()
    facilities, page, skipped = [], 1, 0
    while page <= args.max_pages:
        data = hs_get({"country": COUNTRY, "page": page, "api-key": key})
        if not data:
            break
        for item in data:
            rec = facility_record(item)
            if rec:
                facilities.append(rec)
            else:
                skipped += 1
        print(f"  page {page}: {len(facilities)} facilities so far", flush=True)
        page += 1
    calls = page  # the last, empty page counts too
    write_json(FACILITIES_FILE, {
        "country": COUNTRY,
        "downloaded": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "facilities": facilities,
    })
    print(f"Downloaded {len(facilities)} facilities in {calls} requests "
          f"-> {rel(FACILITIES_FILE)}")
    if skipped:
        print(f"Skipped {skipped} records with no location.")
    if calls > HS_FREE_CALLS_PER_DAY:
        print(f"Note: that is more than the free allowance of {HS_FREE_CALLS_PER_DAY} requests a day.")


# ---------- weather cells ----------

def cell_key(lon, lat, step):
    """Index of the weather grid point nearest a location."""
    return round(lon / step), round(lat / step)


def cell_name(ix, iy, step):
    return f"cell_{iy * step:.2f}_{ix * step:.2f}"


def cmd_cells(args):
    step = args.step
    facilities = read_json(FACILITIES_FILE, "facilities")["facilities"]
    counts = {}
    for f in facilities:
        k = cell_key(f["lon"], f["lat"], step)
        counts[k] = counts.get(k, 0) + 1
    half = step / 2
    features = []
    for (ix, iy), n in sorted(counts.items()):
        lon, lat = ix * step, iy * step
        ring = [[round(lon - half, 4), round(lat - half, 4)],
                [round(lon + half, 4), round(lat - half, 4)],
                [round(lon + half, 4), round(lat + half, 4)],
                [round(lon - half, 4), round(lat + half, 4)],
                [round(lon - half, 4), round(lat - half, 4)]]
        features.append({"type": "Feature",
                         "properties": {"name": cell_name(ix, iy, step), "facilities": n},
                         "geometry": {"type": "Polygon", "coordinates": [ring]}})
    write_json(CELLS_FILE, {"type": "FeatureCollection", "features": features})
    write_json(SETTINGS_FILE, {"step": step, "project_id": PROJECT_ID})
    print(f"{len(facilities)} facilities fall in {len(features)} cells of {step} degrees "
          f"-> {rel(CELLS_FILE)} ({mb(CELLS_FILE):.2f} MB)")
    print("Each cell is centred on a HeatReady weather grid point, so every facility "
          "gets the value of its nearest grid point.")
    if len(features) > LARGE_PROJECT:
        print(f"That is a large HeatReady project. Consider: cells --step {round(step * 2, 2)}")
    print("Catch: once the HeatReady project exists, facilities that fall in a new cell "
          "show as 'no heat data' until the project is recreated.")


# ---------- HeatReady ----------

def hr_creds():
    if not HR_CRED_FILE.exists():
        die(f"{HR_CRED_FILE} not found. Redeem your HeatReady invite with heatready.py first.")
    creds = {}
    for line in HR_CRED_FILE.read_text().splitlines():
        if "=" in line:
            k, v = line.strip().split("=", 1)
            creds[k] = v.strip().strip('"')
    if not creds.get("HR_USER") or not creds.get("HR_KEY"):
        die(f"{HR_CRED_FILE} is missing HR_USER or HR_KEY.")
    creds.setdefault("HR_API", HR_API_DEFAULT)
    return creds


def hr_call(action, payload=None):
    c = hr_creds()
    body = json.dumps({"username": c["HR_USER"], "key": c["HR_KEY"],
                       "action": action, "payload": payload or {}}).encode()
    req = urllib.request.Request(c["HR_API"] or HR_API_DEFAULT, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read() or b"{}")
        except ValueError:
            data = {"error": f"HTTP {e.code}"}
        return e.code, data
    except urllib.error.URLError as e:
        die(f"could not reach HeatReady ({e.reason}).")


def hr_fail(status, data):
    if status >= 400 or "error" in data:
        hint = {
            "rate_limit_exceeded": " Wait until the next full hour and run it again.",
            "invalid_credentials": " Check ~/.heatready/credentials.",
        }.get(data.get("code"), "")
        die(f"HeatReady said {status} {data.get('code', '')}: {data.get('error', data)}.{hint}")


def project_id():
    if SETTINGS_FILE.exists():
        return read_json(SETTINGS_FILE, "cells").get("project_id", PROJECT_ID)
    return PROJECT_ID


def cmd_create(args):
    cells = read_json(CELLS_FILE, "cells")
    n = len(cells["features"])
    if mb(CELLS_FILE) > 5:
        die("the cells file is over 5 MB. Run `cells --step 0.2` for fewer, larger cells.")
    pid = project_id()
    if not args.yes:
        answer = input(f"Create HeatReady project '{pid}' with {n} cells? "
                       "HeatReady prepares it in the background, usually 20 to 35 minutes, "
                       "longer for big projects. [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Not created.")
            return
    status, data = hr_call("evaluate-heat-risk", {"project_id": pid, "json_obj": cells})
    hr_fail(status, data)
    if status == 202:
        print(f"Project '{pid}' is being prepared "
              f"(HeatReady estimates {data.get('estimated_minutes', '?')} minutes). "
              "Check with: python3 scripts/senegal_heat.py status")
    else:
        print(f"Project '{pid}' already exists and is ready. Run: python3 scripts/senegal_heat.py build")


def cmd_status(_args):
    pid = project_id()
    status, data = hr_call("get-project-status", {"project_id": pid})
    hr_fail(status, data)
    ready = bool(data.get("start"))
    print(f"Project:       {pid}")
    print(f"Ready:         {'yes' if ready else 'not yet, still preparing'}")
    print(f"Cells:         {data.get('polygon_count')}")
    print(f"Weather data:  {data.get('era5_dataset')}")
    print(f"Last updated:  {data.get('last_updated')}")
    if ready:
        print("Next: python3 scripts/senegal_heat.py build")


def f_to_c(f):
    return None if f is None else (f - 32) * 5 / 9


def fetch_rows(pid, date_from):
    rows, offset = [], 0
    while True:
        status, data = hr_call("evaluate-heat-risk", {
            "project_id": pid, "limit": HR_PAGE, "offset": offset, "date_from": date_from})
        hr_fail(status, data)
        if status == 202:
            die("the HeatReady project is still being prepared. Try `status` later.")
        page = data.get("metrics", [])
        rows.extend(page)
        print(f"  {len(rows)} of {data.get('total_rows')} heat rows", flush=True)
        if len(page) < HR_PAGE:
            return rows
        offset += HR_PAGE


def pick_dates(rows, days):
    """The latest `days` dates that are about as complete as the best date.

    Cells whose grid point is over water can have no values on any date, so
    completeness is measured against the most complete date, not the cell count.
    """
    per_date = {}
    for r in rows:
        if r.get("day_t2m_max") is not None:
            per_date[r["date"]] = per_date.get(r["date"], 0) + 1
    if not per_date:
        return []
    best = max(per_date.values())
    good = sorted(d for d, c in per_date.items() if c >= 0.95 * best)
    return good[-days:]


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
    for name, polys in regions:
        for poly in polys:
            if point_in_ring(lon, lat, poly[0]) and not any(
                    point_in_ring(lon, lat, hole) for hole in poly[1:]):
                return name
    return ""


def load_regions():
    gj = read_json(REGIONS_FILE, "a git pull")
    out = []
    for f in gj["features"]:
        p, g = f["properties"], f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        out.append((p.get("adm1_name") or p.get("name") or "", polys))
    return out


def r1(v):
    return None if v is None else round(v, 1)


def cmd_build(args):
    settings = read_json(SETTINGS_FILE, "cells")
    step, pid = settings["step"], settings.get("project_id", PROJECT_ID)
    facilities = read_json(FACILITIES_FILE, "facilities")["facilities"]

    status, info = hr_call("get-project-status", {"project_id": pid})
    hr_fail(status, info)
    if not info.get("start"):
        die("the HeatReady project is still being prepared. Try `status` later.")

    date_from = (date.today() - timedelta(days=args.days + 14)).isoformat()
    rows = fetch_rows(pid, date_from)
    dates = pick_dates(rows, args.days)
    if not dates:
        die("HeatReady returned no complete days yet. Try again tomorrow.")
    chosen = set(dates)

    by_cell = {}
    provisional = set()
    for r in rows:
        if r["date"] not in chosen:
            continue
        if r.get("data_source") and r["data_source"] != "era5":
            provisional.add(r["date"])
        c = by_cell.setdefault(r["name"], {"t": [], "hi": [], "wbgt": []})
        if r.get("day_t2m_max") is not None:
            c["t"].append(r["day_t2m_max"])
        if r.get("day_hi_max") is not None:
            c["hi"].append(f_to_c(r["day_hi_max"]))
        if r.get("day_wbgt_max") is not None:
            c["wbgt"].append(r["day_wbgt_max"])
    cell_values = {name: {k: (statistics.fmean(v) if v else None) for k, v in vals.items()}
                   for name, vals in by_cell.items()}

    regions = load_regions()
    feats, temps = [], []
    for f in facilities:
        ix, iy = cell_key(f["lon"], f["lat"], step)
        v = cell_values.get(cell_name(ix, iy, step), {})
        t = r1(v.get("t"))
        feats.append({"f": f, "t": t, "hi": r1(v.get("hi")), "wbgt": r1(v.get("wbgt"))})
        if t is not None:
            temps.append(t)
    if not temps:
        die("no facility could be matched to a heat value. Was the project created from these cells?")

    temps.sort()
    n = len(temps)
    breaks = [temps[min(n - 1, int(q * n))] for q in (0.2, 0.4, 0.6, 0.8)]
    classes = {}
    out = []
    for item in feats:
        f, t = item["f"], item["t"]
        c = pct = None
        if t is not None:
            c = bisect.bisect_left(breaks, t) + 1
            pct = round(100 * bisect.bisect_left(temps, t) / n)
            lo, hi = classes.get(c, (t, t))
            classes[c] = (min(lo, t), max(hi, t))
        out.append({"type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [round(f["lon"], 5), round(f["lat"], 5)]},
                    "properties": {"n": f["name"], "t": f["type"], "r": region_of(f["lon"], f["lat"], regions),
                                   "id": f["id"], "tmax": t, "hi": item["hi"], "wbgt": item["wbgt"],
                                   "p": pct, "c": c}})

    metadata = {
        "title": "Heat at health facilities in Senegal",
        "metric": "Mean of the daily maximum air temperature at 2 m (degrees C)",
        "date_from": dates[0], "date_to": dates[-1], "days": len(dates),
        "provisional_dates": sorted(provisional),
        "generated": date.today().isoformat(),
        "facilities": len(out), "with_heat": n,
        "cell_step_deg": step,
        "classes": [{"c": k, "min": r1(lo), "max": r1(hi)} for k, (lo, hi) in sorted(classes.items())],
        "sources": {
            "facilities": "healthsites.io / (c) OpenStreetMap contributors, ODbL 1.0",
            "heat": "HeatReady, CrisisReady; ERA5-Land, Copernicus Climate Change Service; "
                    "recent days filled with Open-Meteo (CC BY 4.0)",
        },
        "licence": "ODbL 1.0",
    }
    write_json(OUT_FILE, {"type": "FeatureCollection", "metadata": metadata, "features": out})
    print(f"Wrote {rel(OUT_FILE)} ({mb(OUT_FILE):.2f} MB): "
          f"{len(out)} facilities, {n} with heat values, {dates[0]} to {dates[-1]}.")
    missing = len(out) - n
    if missing:
        print(f"{missing} facilities have no heat value (new cells, or cells over water).")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("save-key", help="store your healthsites.io API key").set_defaults(fn=cmd_save_key)
    s = sub.add_parser("facilities", help="download Senegal's facilities")
    s.add_argument("--max-pages", type=int, default=200)
    s.set_defaults(fn=cmd_facilities)
    s = sub.add_parser("cells", help="group facilities into weather cells")
    s.add_argument("--step", type=float, default=0.1, help="cell size in degrees (default 0.1, about 9 km)")
    s.set_defaults(fn=cmd_cells)
    s = sub.add_parser("create", help="create the HeatReady project")
    s.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    s.set_defaults(fn=cmd_create)
    sub.add_parser("status", help="is the HeatReady project ready?").set_defaults(fn=cmd_status)
    s = sub.add_parser("build", help="fetch recent heat and write the map file")
    s.add_argument("--days", type=int, default=7, help="number of recent days to average (default 7)")
    s.set_defaults(fn=cmd_build)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
