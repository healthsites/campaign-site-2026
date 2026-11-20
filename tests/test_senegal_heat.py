"""Tests for scripts/senegal_heat.py. Run: python3 -m unittest discover -s tests -v

Standard library only, made-up rows, no network calls.
"""
import io
import json
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import senegal_heat as sh  # noqa: E402

CELL = "cell_16.00_-16.00"

COPERNICUS_2026 = (
    "Generated using Copernicus Climate Change Service (C3S) information via the ERA5 "
    "reanalysis (2026). Neither the European Commission nor ECMWF is responsible for any "
    "use that may be made of the Copernicus information or data it contains.")


def row(day, name=CELL, *, tmax=38.0, grid=37.0, night=24.0, ref=35.5, hi_f=95.0, wbgt=27.0,
        utci=40.0, src="era5_land_downscaled", band="era5", conf="medium", ood=False,
        block=True):
    """One HeatReady row shaped like the API's: grid values at the top level,
    corrected values in the downscaled block."""
    r = {"name": name, "date": day, "data_source": band,
         "day_t2m_max": grid, "nighttime_t2m_min": night + 1.0, "day_hi_max": 90.0,
         "day_wbgt_max": wbgt - 1.0, "day_utci_max": utci - 1.0, "ref_day_t2m_mean": ref}
    if block:
        r["downscaled"] = {
            "data_source": src, "base_source": "era5_land", "applied": src != "era5_land_grid",
            "confidence": conf, "out_of_distribution": ood, "model_version": "ds-test",
            "metrics": {"day_t2m_max": tmax, "nighttime_t2m_min": night, "day_hi_max": hi_f,
                        "day_wbgt_max": wbgt, "day_utci_max": utci},
        }
    return r


def week(first=7, last=13, **kw):
    return [row(f"2026-11-{d:02d}", **kw) for d in range(first, last + 1)]


def square(x0, y0, x1, y1):
    return [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]


REGIONS = [("West", [square(0, 0, 1, 1)]), ("East", [square(2, 0, 3, 1)])]


class FixedWeek(unittest.TestCase):
    def test_uses_only_dates_in_the_range(self):
        rows = week(1, 20)
        dates = sh.dates_in_range(rows, "2026-11-07", "2026-11-13")
        self.assertEqual(dates, [f"2026-11-{d:02d}" for d in range(7, 14)])
        rows.append(row("2026-11-14", tmax=99.0))           # outside the week
        rows.append(row("2026-11-06", tmax=99.0, grid=99.0))
        self.assertAlmostEqual(sh.aggregate(rows, dates)[CELL]["tmax"], 38.0)

    def test_stops_when_a_date_is_missing(self):
        rows = [r for r in week() if r["date"] != "2026-11-10"]
        with self.assertRaises(SystemExit) as e:
            sh.dates_in_range(rows, "2026-11-07", "2026-11-13")
        self.assertIn("2026-11-10", str(e.exception))

    def test_stops_when_a_date_is_mostly_empty(self):
        rows = week(name="a") + week(name="b") + week(name="c", last=12)
        with self.assertRaises(SystemExit) as e:
            sh.dates_in_range(rows, "2026-11-07", "2026-11-13")
        self.assertIn("2026-11-13 (2 of 3 cells)", str(e.exception))

    def test_bad_dates_stop(self):
        for a, b in (("2026-11-13", "2026-11-07"), ("7 Nov", "2026-11-13")):
            with self.assertRaises(SystemExit):
                sh.dates_in_range(week(), a, b)

    def test_provisional_dates(self):
        rows = week(7, 8) + week(9, 13, band="open_meteo")
        dates = sh.dates_in_range(rows, "2026-11-07", "2026-11-13")
        self.assertEqual(sh.provisional_dates(rows, dates)[0], "2026-11-09")
        self.assertEqual(len(sh.provisional_dates(rows, dates)), 5)


class Values(unittest.TestCase):
    def cell(self, rows):
        dates = sorted({r["date"] for r in rows})
        return sh.aggregate(rows, dates)[CELL]

    def test_uses_downscaled_and_keeps_grid(self):
        c = self.cell(week(tmax=38.0, grid=36.0, night=24.5, wbgt=27.0, utci=41.0))
        self.assertAlmostEqual(c["tmax"], 38.0)
        self.assertAlmostEqual(c["tmax_grid"], 36.0)
        self.assertAlmostEqual(c["tmin"], 24.5)              # downscaled, not the grid's 25.5
        self.assertAlmostEqual(c["wbgt"], 27.0)
        self.assertAlmostEqual(c["utci"], 41.0)
        self.assertEqual(c["src"], "era5_land_downscaled")

    def test_grid_fallback_sets_src(self):
        for rows in (week(block=False),                      # no downscaled block
                     week(src="era5_land_grid", conf=None),   # HeatReady fell back to the grid
                     [dict(r, downscaled=None) for r in week()]):
            c = self.cell(rows)
            self.assertEqual(c["src"], "era5_land_grid")
            self.assertAlmostEqual(c["tmax"], 37.0)           # the grid value
            self.assertIsNone(c["conf"])
            self.assertEqual(c["ood"], 0)

    def test_station_source_is_kept(self):
        self.assertEqual(self.cell(week(src="metar_station"))["src"], "metar_station")

    def test_most_common_source_lowest_confidence_and_ood_days(self):
        rows = (week(7, 10, conf="high") + week(11, 12, src="era5_land_grid")
                + week(13, 13, conf="low", ood=True))
        c = self.cell(rows)
        self.assertEqual(c["src"], "era5_land_downscaled")   # 5 of 7 days
        self.assertEqual(c["conf"], "low")
        self.assertEqual(c["ood"], 1)

    def test_heat_index_ends_up_in_celsius(self):
        self.assertAlmostEqual(self.cell(week(hi_f=95.0))["hi"], 35.0)

    def test_unknown_values_stop(self):
        for kw in ({"src": "something_new"}, {"conf": "very high"}):
            with self.assertRaises(SystemExit):
                self.cell(week(7, 7, **kw))


class AboveNormal(unittest.TestCase):
    def test_anom_compares_grid_with_grid_baseline(self):
        rows = week(tmax=40.0, grid=37.0, ref=35.5)
        c = sh.aggregate(rows, sorted({r["date"] for r in rows}))[CELL]
        self.assertAlmostEqual(c["anom"], 1.5)               # 37.0 - 35.5, never 40.0 - 35.5

    def test_anom_pairs_the_same_days(self):
        rows = [row("2026-11-07", grid=36.0, ref=35.0), row("2026-11-08", grid=38.0, ref=None)]
        c = sh.aggregate(rows, ["2026-11-07", "2026-11-08"])[CELL]
        self.assertAlmostEqual(c["anom"], 1.0)               # the day without a baseline is left out

    def test_no_baseline_no_anom(self):
        rows = week(ref=None)
        self.assertIsNone(sh.aggregate(rows, sorted({r["date"] for r in rows}))[CELL]["anom"])


class Regions(unittest.TestCase):
    def test_inside_a_region(self):
        self.assertEqual(sh.region_for(0.5, 0.5, REGIONS), ("West", False))

    def test_just_outside_gets_the_nearest_region(self):
        self.assertEqual(sh.region_for(1.1, 0.5, REGIONS), ("West", True))
        self.assertEqual(sh.region_for(1.9, 0.5, REGIONS), ("East", True))
        self.assertEqual(sh.region_for(2.5, -0.05, REGIONS), ("East", True))


class Output(unittest.TestCase):
    def build(self):
        facilities = [{"id": "node/1", "name": "Poste de santé", "type": "clinic", "lon": 1.05, "lat": 0.5},
                      {"id": "node/2", "name": "Hôpital", "type": "hospital", "lon": 2.5, "lat": 0.5}]
        step = 0.1
        names = [sh.cell_name(*sh.cell_key(f["lon"], f["lat"], step), step) for f in facilities]
        rows = week(name=names[0], tmax=38.0) + week(name=names[1], tmax=36.0, src="era5_land_grid")
        dates = sh.dates_in_range(rows, "2026-11-07", "2026-11-13")
        return sh.build_geojson(facilities, sh.aggregate(rows, dates), step, REGIONS, dates,
                                sh.provisional_dates(rows, dates), sh.model_versions(rows, dates))

    def test_keeps_existing_properties(self):
        gj, nearest = self.build()
        for f in gj["features"]:
            for k in ("n", "t", "r", "id", "tmax", "hi", "wbgt", "p", "c"):
                self.assertIn(k, f["properties"])
            self.assertTrue(f["properties"]["r"])
        self.assertEqual(nearest, [("Poste de santé", "West")])
        self.assertEqual(gj["metadata"]["grid_fallback"], 1)

    def test_licences_and_attribution(self):
        meta = self.build()[0]["metadata"]
        self.assertNotIn("licence", meta)
        self.assertEqual(set(meta["licences"]), {"facility_fields", "heat_fields"})
        self.assertIn("ODbL 1.0", meta["licences"]["facility_fields"])
        self.assertIn("CC BY 4.0", meta["licences"]["heat_fields"])
        self.assertEqual(meta["attribution"]["copernicus"], COPERNICUS_2026)
        self.assertIn("HeatReady (CrisisReady), CC BY 4.0", meta["attribution"]["heat"])
        self.assertIn("9 km", meta["baseline"])
        self.assertEqual(set(meta["fields"]), {"n", "t", "r", "id", "tmax", "tmin", "wbgt", "hi", "utci",
                                               "anom", "tmax_grid", "src", "conf", "ood", "p", "c"})

    def test_summary_lists_regions(self):
        gj, nearest = self.build()
        text = sh.summary(gj, nearest)
        self.assertIn("2026-11-07 to 2026-11-13", text)
        self.assertIn("West", text)
        self.assertIn("1 using the 9 km grid fallback", text)


class Paging(unittest.TestCase):
    """build --page-size, and errors that say which HeatReady call failed."""

    def fake(self, total, fail_on=None):
        calls = []

        def hr_call(action, payload=None):
            calls.append(dict(payload))
            if fail_on and len(calls) == fail_on:
                return 502, {"message": "Internal server error"}
            start, size = payload["offset"], payload["limit"]
            return 200, {"total_rows": total,
                         "metrics": [{"n": i} for i in range(start, min(total, start + size))]}
        return hr_call, calls

    def test_page_size_is_sent_and_paging_stops_on_a_short_page(self):
        hr_call, calls = self.fake(450)
        with mock.patch.object(sh, "hr_call", hr_call), redirect_stdout(io.StringIO()):
            rows = sh.fetch_rows("p", "2026-11-07", 200)
        self.assertEqual(len(rows), 450)
        self.assertEqual([(c["limit"], c["offset"]) for c in calls], [(200, 0), (200, 200), (200, 400)])

    def test_default_page_size_is_500(self):
        self.assertEqual(sh.HR_PAGE, 500)                # 2,000 rows went over the 6 MB limit
        self.assertEqual(sh.HR_PAGE_MAX, 1000)           # stays under the 6 MB limit
        hr_call, calls = self.fake(10)
        with mock.patch.object(sh, "hr_call", hr_call), redirect_stdout(io.StringIO()):
            sh.fetch_rows("p", "2026-11-07")
        self.assertEqual(calls[0]["limit"], 500)

    def test_error_names_the_page(self):
        hr_call, _ = self.fake(1000, fail_on=3)
        with mock.patch.object(sh, "hr_call", hr_call), redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as e:
                sh.fetch_rows("p", "2026-11-07", 200)
        msg = str(e.exception)
        self.assertIn("502 on page 3 (rows 401 to 600, page size 200)", msg)
        self.assertIn("6 MB", msg)

    def test_error_names_the_status_check(self):
        with self.assertRaises(SystemExit) as e:
            sh.hr_fail(502, {"message": "Internal server error"}, "the status check")
        self.assertIn("502 on the status check", str(e.exception))
        self.assertNotIn("6 MB", str(e.exception))      # the page-size hint is for pages only


NODE = shutil.which("node")
HEAT_JS = ROOT / "theme" / "static" / "js" / "heat-map.js"


class PageSizeOption(unittest.TestCase):
    def test_build_refuses_a_page_over_1000(self):
        args = mock.Mock(date_from=None, date_to=None, page_size=1001, cached=True, days=7)
        with mock.patch.object(sh, "read_json", return_value={"step": 0.1, "facilities": []}):
            with self.assertRaises(SystemExit) as e:
                sh.cmd_build(args)
        self.assertIn("from 1 to 1000", str(e.exception))


@unittest.skipUnless(NODE, "Node.js is not installed")
class HeatMapPage(unittest.TestCase):
    """Wording in heat-map.js, run in Node, and in the page template."""

    def js(self, expr):
        script = f"const h = require({json.dumps(str(HEAT_JS))}); console.log(JSON.stringify({expr}));"
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    def test_above_normal_says_it_is_the_9km_grid(self):
        title = self.js("h.legendTitle(h.VIEWS.anom, '7 to 13 November 2026')")
        self.assertTrue(title.startswith(
            "Daytime high compared with the 9 km grid's 2016–2025 average for the same days"))
        self.assertIn("7 to 13 November 2026", title)
        self.assertNotIn("compared with other facilities", title)
        day = self.js("h.legendTitle(h.VIEWS.day, '7 to 13 November 2026')")
        self.assertIn("compared with other facilities in Senegal", day)
        popup = self.js("h.popupHtml({n: 'Poste', tmax: 38, tmin: 24, wbgt: 27, anom: 1.8, "
                        "src: 'era5_land_downscaled', conf: 'medium', ood: 0}, h.VIEWS.day, {p: 90})")
        self.assertIn("<dt>Above normal (9 km grid)</dt><dd>+1.8 °C</dd>", popup)
        template = (ROOT / "theme" / "templates" / "senegal-heat.html").read_text(encoding="utf-8")
        self.assertIn('<th scope="col">Above normal (9 km grid)</th>', template)

    def test_closing_line_has_no_night_figure(self):
        meta = {"date_from": "2026-11-07", "date_to": "2026-11-13"}
        stats = [{"region": "Saint-Louis", "tmin": 25.6, "anom": 1.6}]
        self.assertEqual(self.js(f"h.closingText({json.dumps(meta)}, {json.dumps(stats)})"),
                         "From 7 to 13 November, days at Saint-Louis facilities ran 1.6 °C above normal.")
        stats[0]["anom"] = None
        self.assertIsNone(self.js(f"h.closingText({json.dumps(meta)}, {json.dumps(stats)})"))

    def test_trust_line_for_each_source(self):
        def line(src, conf=None, ood=0):
            return self.js(f"h.trustLine({json.dumps({'src': src, 'conf': conf, 'ood': ood})})")
        self.assertIn("From a weather station in the same 9 km square.", line("metar_station"))
        self.assertIn("Corrected with nearby weather station data (confidence: high).",
                      line("era5_land_station_blended", "high"))
        self.assertIn("Corrected for local conditions (confidence: low).", line("era5_land_downscaled", "low"))
        self.assertIn("From the 9 km grid, likely below the real daytime high.", line("era5_land_grid"))
        self.assertIn("On 3 days, outside the conditions the model was tested on.",
                      line("era5_land_downscaled", "low", 3))


if __name__ == "__main__":
    unittest.main()
