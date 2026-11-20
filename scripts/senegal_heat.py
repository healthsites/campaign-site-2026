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
    python3 scripts/senegal_heat.py sample       save 20 heat rows and list their fields
    python3 scripts/senegal_heat.py build        fetch recent heat and write the map file
    python3 scripts/senegal_heat.py build --from 2026-11-07 --to 2026-11-13
                                                 the same, for a fixed week
    python3 scripts/senegal_heat.py build --cached --from … --to …
                                                 rebuild from the last fetch, no HeatReady calls

The map uses HeatReady's downscaled values (the `downscaled` block of each
row), or the 9 km grid where HeatReady falls back to it. "Above normal" is
measured on the 9 km grid, because HeatReady's 2016-2025 baseline exists only
for the grid. Heat values are CC BY 4.0; facility fields are ODbL 1.0.

To refresh the map later, run `build` again. Run `facilities`, `cells` and
`build` if you also want newly mapped facilities (see `cells` for the catch).

HeatReady credentials are read from ~/.heatready/credentials, the file that
heatready.py writes when you redeem your invite.
"""

import argparse
import bisect
import getpass
import json
import math
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
HR_PAGE = 500       # rows per call. A row with the downscaled block is about 4.8 KB, so 500 rows
                    # is about 2.4 MB, well under API Gateway's 6 MB response limit
HR_PAGE_MAX = 1000  # about 4.8 MB: larger pages go over the 6 MB limit (the API itself allows 2,000)

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


def hr_fail(status, data, what=""):
    """Stop if a HeatReady call failed. `what` names the call, e.g. "the status check"."""
    if status >= 400 or "error" in data:
        hint = {
            "rate_limit_exceeded": " Wait until the next full hour and run it again.",
            "invalid_credentials": " Check ~/.heatready/credentials.",
        }.get(data.get("code"), "")
        if status == 502 and data == {"message": "Internal server error"} and "page" in what:
            hint = (" A bare 'Internal server error' can mean the page was over API Gateway's "
                    "6 MB response limit. Try a smaller --page-size.")
        where = f" on {what}" if what else ""
        code = f" {data['code']}" if data.get("code") else ""
        die(f"HeatReady said {status}{code}{where}: {data.get('error', data)}.{hint}")


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
    hr_fail(status, data, "the project request")
    if status == 202:
        print(f"Project '{pid}' is being prepared "
              f"(HeatReady estimates {data.get('estimated_minutes', '?')} minutes). "
              "Check with: python3 scripts/senegal_heat.py status")
    else:
        print(f"Project '{pid}' already exists and is ready. Run: python3 scripts/senegal_heat.py build")


def cmd_status(_args):
    pid = project_id()
    status, data = hr_call("get-project-status", {"project_id": pid})
    hr_fail(status, data, "the status check")
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


ROWS_FILE = CACHE / "rows.json"

# downscaled.data_source, from no correction to a real observation (HeatReady API docs).
GRID = "era5_land_grid"
SOURCES = (GRID, "era5_land_downscaled", "era5_land_station_blended", "metar_station")
STATION_SOURCES = ("era5_land_station_blended", "metar_station")
CONFIDENCE = ("low", "medium", "high")   # lowest first
FINAL_BAND = "era5"   # top-level data_source once ERA5-Land has replaced Open-Meteo
COMPLETE_SHARE = 0.95
BASELINE_YEARS = "2016–2025"
MEANS = ("tmax", "tmin", "wbgt", "hi", "utci", "tmax_grid")

COPERNICUS = ("Generated using Copernicus Climate Change Service (C3S) information via the "
              "ERA5 reanalysis ({year}). Neither the European Commission nor ECMWF is "
              "responsible for any use that may be made of the Copernicus information or "
              "data it contains.")

FIELDS = {
    "n": "Facility name (OpenStreetMap)",
    "t": "Facility type (OpenStreetMap healthcare or amenity tag)",
    "r": "Region (admin 1). Facilities just outside every region outline get the nearest region",
    "id": "OpenStreetMap ID (node/…, way/… or relation/…)",
    "tmax": "Daytime high: mean of the daily maximum air temperature at 2 m, downscaled by HeatReady (°C)",
    "tmin": "Night-time low: mean of the minimum air temperature at 2 m from 18:00 to 05:59, "
            "downscaled by HeatReady (°C)",
    "wbgt": "Heat stress: mean of the daily maximum wet bulb globe temperature, downscaled by HeatReady (°C)",
    "hi": "Mean of the daily maximum heat index, downscaled by HeatReady, converted from °F (°C)",
    "utci": "Mean of the daily maximum Universal Thermal Climate Index, downscaled by HeatReady (°C)",
    "anom": "Above normal: mean daily maximum on the 9 km grid (tmax_grid) minus the "
            f"{BASELINE_YEARS} 9 km baseline for the same calendar days (°C)",
    "tmax_grid": "Mean of the daily maximum air temperature at 2 m on the 9 km ERA5-Land grid, "
                 "before downscaling (°C)",
    "src": "Most common HeatReady source over the week: era5_land_downscaled (corrected), "
           "era5_land_station_blended or metar_station (weather station), era5_land_grid (9 km grid, "
           "not corrected)",
    "conf": "Lowest HeatReady confidence grade over the week: low, medium or high. Null for grid values",
    "ood": "Number of days outside the conditions the downscaling model was tested on",
    "p": "Percentile of tmax among facilities in Senegal (0 to 100)",
    "c": "Class by tmax: 1 (coolest 20%) to 5 (hottest 20%)",
}


def fetch_rows(pid, date_from, page_size=HR_PAGE):
    rows, offset, n = [], 0, 1
    while True:
        what = f"page {n} (rows {offset + 1:,} to {offset + page_size:,}, page size {page_size:,})"
        status, data = hr_call("evaluate-heat-risk", {
            "project_id": pid, "limit": page_size, "offset": offset, "date_from": date_from})
        hr_fail(status, data, what)
        if status == 202:
            die("the HeatReady project is still being prepared. Try `status` later.")
        page = data.get("metrics", [])
        rows.extend(page)
        print(f"  page {n}: {len(rows)} of {data.get('total_rows')} heat rows", flush=True)
        if len(page) < page_size:
            return rows
        offset += page_size
        n += 1


def save_rows(rows, date_from):
    write_json(ROWS_FILE, {"fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                           "date_from": date_from, "rows": rows})


def load_rows():
    data = read_json(ROWS_FILE, "build (without --cached)")
    if isinstance(data, list):   # an older cache: just the rows
        return data, None
    return data["rows"], data.get("fetched")


def date_counts(rows):
    per_date = {}
    for r in rows:
        if r.get("day_t2m_max") is not None:
            per_date[r["date"]] = per_date.get(r["date"], 0) + 1
    return per_date


def pick_dates(rows, days):
    """The latest `days` dates that are about as complete as the best date.

    Cells whose grid point is over water can have no values on any date, so
    completeness is measured against the most complete date, not the cell count.
    """
    per_date = date_counts(rows)
    if not per_date:
        return []
    best = max(per_date.values())
    good = sorted(d for d, c in per_date.items() if c >= COMPLETE_SHARE * best)
    return good[-days:]


def dates_in_range(rows, date_from, date_to):
    """Every date from date_from to date_to. Stops if one has no complete data."""
    try:
        d0, d1 = date.fromisoformat(date_from), date.fromisoformat(date_to)
    except ValueError:
        die("--from and --to must be dates like 2026-11-07.")
    if d1 < d0:
        die("--to is before --from.")
    wanted = [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]
    per_date = date_counts(rows)
    best = max(per_date.values()) if per_date else 0
    missing = [d for d in wanted if not best or per_date.get(d, 0) < COMPLETE_SHARE * best]
    if missing:
        detail = ", ".join(f"{d} ({per_date.get(d, 0)} of {best} cells)" for d in missing)
        die(f"no complete heat data for {detail}. HeatReady may not have these days yet; "
            "try again later, or check the dates.")
    return wanted


def row_values(r):
    """One cell-day: HeatReady's downscaled values, or the 9 km grid values
    when HeatReady fell back to the grid (no downscaled block, or era5_land_grid)."""
    ds = r.get("downscaled")
    src, metrics = GRID, None
    if isinstance(ds, dict):
        src = ds.get("data_source") or GRID
        if src not in SOURCES:
            die(f"HeatReady returned an unknown downscaled data_source '{src}' "
                f"({r.get('name')}, {r.get('date')}). Check the API documentation.")
        m = ds.get("metrics")
        if src != GRID and isinstance(m, dict) and m.get("day_t2m_max") is not None:
            metrics = m
        else:
            src = GRID
    conf = ood = None
    if metrics is not None:
        conf = ds.get("confidence")
        if conf is not None and conf not in CONFIDENCE:
            die(f"HeatReady returned an unknown confidence grade '{conf}' "
                f"({r.get('name')}, {r.get('date')}).")
        ood = bool(ds.get("out_of_distribution"))
    v = metrics if metrics is not None else r
    return {
        "tmax": v.get("day_t2m_max"),
        "tmin": v.get("nighttime_t2m_min"),
        "wbgt": v.get("day_wbgt_max"),
        "hi": f_to_c(v.get("day_hi_max")),
        "utci": v.get("day_utci_max"),
        "tmax_grid": r.get("day_t2m_max"),
        "ref": r.get("ref_day_t2m_mean"),   # 9 km grid baseline: there is no downscaled one
        "src": src,
        "conf": conf,
        "ood": bool(ood),
        "band": r.get("data_source"),
        "model": ds.get("model_version") if isinstance(ds, dict) else None,
    }


def aggregate(rows, dates):
    """Per cell: the mean of each value over the dates, plus src, conf, ood and anom."""
    chosen = set(dates)
    acc = {}
    for r in rows:
        if r.get("date") not in chosen:
            continue
        v = row_values(r)
        a = acc.get(r["name"])
        if a is None:
            a = acc[r["name"]] = {k: [] for k in MEANS}
            a.update(src=[], conf=[], ood=0, anom=[])
        for k in MEANS:
            if v[k] is not None:
                a[k].append(v[k])
        a["src"].append(v["src"])
        if v["conf"]:
            a["conf"].append(v["conf"])
        a["ood"] += v["ood"]
        # Like with like: the grid daytime high against the grid baseline, same day.
        if v["tmax_grid"] is not None and v["ref"] is not None:
            a["anom"].append(v["tmax_grid"] - v["ref"])
    cells = {}
    for name, a in acc.items():
        cell = {k: (statistics.fmean(a[k]) if a[k] else None) for k in MEANS}
        cell["anom"] = statistics.fmean(a["anom"]) if a["anom"] else None
        counts = {}
        for s in a["src"]:
            counts[s] = counts.get(s, 0) + 1
        # Most common source; a tie goes to the less corrected one.
        cell["src"] = max(counts, key=lambda s: (counts[s], -SOURCES.index(s))) if counts else None
        cell["conf"] = min(a["conf"], key=CONFIDENCE.index) if a["conf"] else None
        cell["ood"] = a["ood"]
        cells[name] = cell
    return cells


def provisional_dates(rows, dates):
    chosen = set(dates)
    return sorted({r["date"] for r in rows if r.get("date") in chosen
                   and r.get("data_source") and r["data_source"] != FINAL_BAND})


def model_versions(rows, dates):
    chosen = set(dates)
    return sorted({(r.get("downscaled") or {}).get("model_version") for r in rows
                   if r.get("date") in chosen and isinstance(r.get("downscaled"), dict)} - {None})


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


def nearest_region(lon, lat, regions):
    """The region whose outline is closest, for points on a coast or a border."""
    k = math.cos(math.radians(lat))   # degrees of longitude are shorter away from the equator
    best, best_name = math.inf, ""
    for name, polys in regions:
        for poly in polys:
            ring = poly[0]
            for (ax, ay), (bx, by) in zip(ring, ring[1:]):
                ax, bx, px = ax * k, bx * k, lon * k
                dx, dy = bx - ax, by - ay
                t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (lat - ay) * dy)
                                                         / (dx * dx + dy * dy)))
                d = (px - ax - t * dx) ** 2 + (lat - ay - t * dy) ** 2
                if d < best:
                    best, best_name = d, name
    return best_name


def region_for(lon, lat, regions):
    """(region, True if it came from the nearest outline)."""
    name = region_of(lon, lat, regions)
    return (name, False) if name else (nearest_region(lon, lat, regions), True)


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


def build_metadata(dates, provisional, models, n_out, n_heat, n_grid, step, classes):
    year = dates[-1][:4]
    return {
        "title": "Heat at health facilities in Senegal",
        "metric": "Mean of the daily maximum air temperature at 2 m, downscaled by HeatReady (°C)",
        "date_from": dates[0], "date_to": dates[-1], "days": len(dates),
        "provisional_dates": provisional,
        "generated": date.today().isoformat(),
        "facilities": n_out, "with_heat": n_heat, "grid_fallback": n_grid,
        "cell_step_deg": step,
        "classes": classes,
        "baseline": f"{BASELINE_YEARS}, same calendar days. 9 km ERA5-Land grid baseline "
                    "(HeatReady ref_day_t2m_mean: mean daily maximum within 7 days of each "
                    "calendar day). HeatReady has no downscaled baseline, so anom compares the "
                    "9 km daytime high (tmax_grid) with the 9 km baseline.",
        "downscaling_model": models,
        "fields": FIELDS,
        "sources": {
            "facilities": "healthsites.io / (c) OpenStreetMap contributors, ODbL 1.0",
            "heat": "HeatReady, CrisisReady, CC BY 4.0. Daily values from ERA5-Land, downscaled "
                    "by HeatReady, with the most recent days filled from Open-Meteo (CC BY 4.0) "
                    f"until ERA5-Land replaces them. Baseline: {BASELINE_YEARS}, same calendar "
                    "days, 9 km grid.",
        },
        "licences": {
            "facility_fields": "ODbL 1.0: n, t, r, id and the point geometry",
            "heat_fields": "CC BY 4.0: tmax, tmin, wbgt, hi, utci, anom, tmax_grid, src, conf, ood, p, c",
        },
        "attribution": {
            "facilities": "Health facility data: healthsites.io / © OpenStreetMap contributors (ODbL)",
            "heat": "Heat values: HeatReady (CrisisReady), CC BY 4.0",
            "copernicus": COPERNICUS.format(year=year),
        },
    }


def build_geojson(facilities, cells, step, regions, dates, provisional, models):
    """The map file, plus the names of facilities placed by the nearest region."""
    feats, temps, nearest = [], [], []
    for f in facilities:
        ix, iy = cell_key(f["lon"], f["lat"], step)
        v = cells.get(cell_name(ix, iy, step), {})
        region, by_nearest = region_for(f["lon"], f["lat"], regions)
        if by_nearest:
            nearest.append((f["name"] or "Unnamed facility", region))
        t = r1(v.get("tmax"))
        feats.append((f, region, t, v))
        if t is not None:
            temps.append(t)
    if not temps:
        die("no facility could be matched to a heat value. Was the project created from these cells?")

    temps.sort()
    n = len(temps)
    breaks = [temps[min(n - 1, int(q * n))] for q in (0.2, 0.4, 0.6, 0.8)]
    classes, out, n_grid = {}, [], 0
    for f, region, t, v in feats:
        c = pct = None
        if t is not None:
            c = bisect.bisect_left(breaks, t) + 1
            pct = round(100 * bisect.bisect_left(temps, t) / n)
            lo, hi = classes.get(c, (t, t))
            classes[c] = (min(lo, t), max(hi, t))
            n_grid += v.get("src") == GRID
        out.append({"type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [round(f["lon"], 5), round(f["lat"], 5)]},
                    "properties": {"n": f["name"], "t": f["type"], "r": region, "id": f["id"],
                                   "tmax": t, "hi": r1(v.get("hi")), "wbgt": r1(v.get("wbgt")),
                                   "p": pct, "c": c,
                                   "tmin": r1(v.get("tmin")), "utci": r1(v.get("utci")),
                                   "anom": r1(v.get("anom")), "tmax_grid": r1(v.get("tmax_grid")),
                                   "src": v.get("src"), "conf": v.get("conf"),
                                   "ood": v.get("ood") if t is not None else None}})
    metadata = build_metadata(dates, provisional, models, len(out), n, n_grid, step,
                              [{"c": k, "min": r1(lo), "max": r1(hi)} for k, (lo, hi) in sorted(classes.items())])
    return {"type": "FeatureCollection", "metadata": metadata, "features": out}, nearest


def mean_of(values):
    values = [v for v in values if v is not None]
    return statistics.fmean(values) if values else None


def summary(gj, nearest):
    """The check summary printed at the end of `build`."""
    meta, props = gj["metadata"], [f["properties"] for f in gj["features"]]
    heat = [p for p in props if p["tmax"] is not None]
    fmt = lambda v, signed=False: "  —" if v is None else (f"{v:+.1f}" if signed else f"{v:.1f}")
    lines = ["", "Check summary", "-------------",
             f"Dates:        {meta['date_from']} to {meta['date_to']} ({meta['days']} days)",
             f"Provisional:  {', '.join(meta['provisional_dates']) or 'none'}",
             f"Downscaling:  model {', '.join(meta['downscaling_model']) or 'none'}",
             f"Facilities:   {len(props):,}, {len(heat):,} with heat values, "
             f"{meta['grid_fallback']:,} using the 9 km grid fallback",
             f"Sources:      " + ", ".join(f"{s} {sum(p['src'] == s for p in heat):,}" for s in SOURCES),
             f"Confidence:   " + ", ".join(f"{c} {sum(p['conf'] == c for p in heat):,}" for c in CONFIDENCE),
             f"Out of distribution on at least one day: {sum((p['ood'] or 0) > 0 for p in heat):,}",
             f"Region from the nearest outline: {len(nearest)}"]
    lines += [f"  {name} -> {region}" for name, region in nearest]
    lines += ["", "Top 10 by daytime high (tmax, °C; 9 km grid in brackets)"]
    top = sorted(heat, key=lambda p: (-p["tmax"], p["n"]))[:10]
    w = max(len(p["n"] or "Unnamed facility") for p in top)
    for i, p in enumerate(top, 1):
        lines.append(f"  {i:>2}. {(p['n'] or 'Unnamed facility'):<{w}}  {p['r']:<12} "
                     f"{p['tmax']:.1f} ({fmt(p['tmax_grid'])})")
    lines += ["", "By region, averaged over facilities (°C)",
              f"  {'Region':<13}{'Facilities':>10}{'tmax':>7}{'tmin':>7}{'wbgt':>7}{'anom':>7}{'grid':>7}"]
    regions = {}
    for p in heat:
        regions.setdefault(p["r"], []).append(p)
    rows = [(r, ps, mean_of(p["tmax"] for p in ps)) for r, ps in regions.items()]
    for r, ps, t in sorted(rows, key=lambda x: -x[2]):
        lines.append(f"  {r:<13}{len(ps):>10,}{fmt(t):>7}{fmt(mean_of(p['tmin'] for p in ps)):>7}"
                     f"{fmt(mean_of(p['wbgt'] for p in ps)):>7}"
                     f"{fmt(mean_of(p['anom'] for p in ps), True):>7}"
                     f"{fmt(mean_of(p['tmax_grid'] for p in ps)):>7}")
    lines.append("  (grid = mean 9 km daytime high, tmax_grid; anom is measured on the 9 km grid)")
    return "\n".join(lines)


def day_counts(rows, dates, n_cells):
    """Rows HeatReady returned for each day, out of the project's squares."""
    lines = [f"Rows per day, out of {n_cells} squares (heat = has a daytime high; "
             "corrected = downscaled or station, not the 9 km grid; band = top-level source)"]
    for d in dates:
        day = [r for r in rows if r.get("date") == d]
        heat = sum(r.get("day_t2m_max") is not None for r in day)
        corrected = sum(row_values(r)["src"] != GRID for r in day if r.get("day_t2m_max") is not None)
        bands = {}
        for r in day:
            bands[r.get("data_source")] = bands.get(r.get("data_source"), 0) + 1
        band = ", ".join(f"{b} {n}" for b, n in sorted(bands.items(), key=lambda x: str(x[0])))
        lines.append(f"  {d}  {len(day):>4} rows  {heat:>4} heat  {corrected:>4} corrected  ({band})")
    return "\n".join(lines)


def cmd_build(args):
    settings = read_json(SETTINGS_FILE, "cells")
    step, pid = settings["step"], settings.get("project_id", PROJECT_ID)
    facilities = read_json(FACILITIES_FILE, "facilities")["facilities"]
    if bool(args.date_from) != bool(args.date_to):
        die("give both --from and --to, or neither.")
    if not 1 <= args.page_size <= HR_PAGE_MAX:
        die(f"--page-size must be from 1 to {HR_PAGE_MAX}.")

    if args.cached:
        rows, fetched = load_rows()
        print(f"Using {len(rows):,} cached heat rows from {fetched or 'an earlier fetch'} "
              f"({rel(ROWS_FILE)}). No HeatReady calls.")
    else:
        status, info = hr_call("get-project-status", {"project_id": pid})
        hr_fail(status, info, "the status check")
        if not info.get("start"):
            die("the HeatReady project is still being prepared. Try `status` later.")
        date_from = args.date_from or (date.today() - timedelta(days=args.days + 14)).isoformat()
        rows = fetch_rows(pid, date_from, args.page_size)
        save_rows(rows, date_from)
        print(f"Saved the rows to {rel(ROWS_FILE)}. Rebuild without calling HeatReady: build --cached")

    if args.date_from:
        dates = dates_in_range(rows, args.date_from, args.date_to)
    else:
        dates = pick_dates(rows, args.days)
        if not dates:
            die("HeatReady returned no complete days yet. Try again tomorrow.")

    cells = aggregate(rows, dates)
    gj, nearest = build_geojson(facilities, cells, step, load_regions(), dates,
                                provisional_dates(rows, dates), model_versions(rows, dates))
    write_json(OUT_FILE, gj)
    meta = gj["metadata"]
    print(f"Wrote {rel(OUT_FILE)} ({mb(OUT_FILE):.2f} MB): "
          f"{meta['facilities']} facilities, {meta['with_heat']} with heat values, "
          f"{dates[0]} to {dates[-1]}.")
    missing = meta["facilities"] - meta["with_heat"]
    if missing:
        print(f"{missing} facilities have no heat value (new cells, or cells over water).")
    print(summary(gj, nearest))
    print()
    print(day_counts(rows, dates, len(read_json(CELLS_FILE, "cells")["features"])))


SAMPLE_FILE = CACHE / "sample-rows.json"


def field_list(obj, prefix=""):
    """[(dotted.name, example)] for every field, including nested blocks."""
    out = []
    for k, v in obj.items():
        name = f"{prefix}{k}"
        if isinstance(v, dict):
            out.append((name, "{…}"))
            out.extend(field_list(v, name + "."))
        else:
            out.append((name, v))
    return out


def cmd_sample(args):
    pid = project_id()
    status, info = hr_call("get-project-status", {"project_id": pid})
    hr_fail(status, info, "the status check")
    if not info.get("start"):
        die("the HeatReady project is still being prepared. Try `status` later.")
    rows = []
    for back in range(1, 8):  # newest date with data; usually the first call
        day = (date.today() - timedelta(days=back)).isoformat()
        status, data = hr_call("evaluate-heat-risk", {
            "project_id": pid, "limit": 200, "offset": 0, "date_from": day})
        hr_fail(status, data, f"the sample request for {day}")
        rows = data.get("metrics", [])
        if rows:
            break
    if not rows:
        die("HeatReady returned no rows for the last 7 days.")
    latest = max(r["date"] for r in rows)
    rows = [r for r in rows if r["date"] == latest][:args.n]
    write_json(SAMPLE_FILE, rows)
    print(f"{len(rows)} rows for {latest} -> {rel(SAMPLE_FILE)}\n")
    # Prefer a row with a downscaled block as the example.
    example = next((r for r in rows if isinstance(r.get("downscaled"), dict)), rows[0])
    seen = {}
    for r in rows:
        for name, _ in field_list(r):
            seen[name] = seen.get(name, 0) + 1
    width = max(len(n) for n in seen)
    for name, value in field_list(example):
        print(f"  {name:<{width}}  {json.dumps(value, ensure_ascii=False)[:60]}  "
              f"(in {seen.get(name, 0)} of {len(rows)} rows)")
    extra = sorted(set(seen) - {n for n, _ in field_list(example)})
    for name in extra:
        print(f"  {name:<{width}}  (not in the example row; in {seen[name]} rows)")


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
    s = sub.add_parser("sample", help="save a few heat rows and list their fields")
    s.add_argument("-n", type=int, default=20, help="rows to keep (default 20)")
    s.set_defaults(fn=cmd_sample)
    s = sub.add_parser("build", help="fetch recent heat and write the map file")
    s.add_argument("--days", type=int, default=7, help="number of recent days to average (default 7)")
    s.add_argument("--from", dest="date_from", help="first day of a fixed week, YYYY-MM-DD (use with --to)")
    s.add_argument("--to", dest="date_to", help="last day of a fixed week, YYYY-MM-DD (use with --from)")
    s.add_argument("--cached", action="store_true",
                   help=f"rebuild from {ROWS_FILE.relative_to(ROOT)} without calling HeatReady")
    s.add_argument("--page-size", type=int, default=HR_PAGE,
                   help=f"heat rows per HeatReady call (default {HR_PAGE}, maximum {HR_PAGE_MAX})")
    s.set_defaults(fn=cmd_build)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
