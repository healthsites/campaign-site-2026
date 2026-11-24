"""Tests for scripts/healthsites_facilities.py and plugins/healthsites_facilities.

Run: python -m unittest discover -s tests -v
No network calls: the API is replaced with made-up pages.
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins"))

spec = importlib.util.spec_from_file_location("hsf", ROOT / "scripts" / "healthsites_facilities.py")
hsf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hsf)

import healthsites_facilities as plugin  # noqa: E402

KEY = "SECRET-KEY-123"


def square(x0, y0, x1, y1):
    return [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]


BOUNDARIES = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {"adm1_name": "West"},
     "geometry": {"type": "Polygon", "coordinates": square(0, 0, 1, 1)}},
    {"type": "Feature", "properties": {"adm1_name": "East"},
     "geometry": {"type": "MultiPolygon", "coordinates": [square(1, 0, 2, 1), square(3, 0, 4, 1)]}},
]}


def item(osm_id, lon, lat, name="Poste de santé", healthcare="clinic", amenity=None):
    return {"osm_type": "node", "osm_id": osm_id,
            "centroid": {"type": "Point", "coordinates": [lon, lat]},
            "attributes": {"name": name, "healthcare": healthcare, "amenity": amenity}}


class Sandbox(unittest.TestCase):
    """Point the script at a temporary folder with one made-up country, 'tst'."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.geo = base / "geojson"
        self.geo.mkdir()
        (self.geo / "tst_admin1.geojson").write_text(json.dumps(BOUNDARIES))
        patches = [
            mock.patch.object(hsf, "GEOJSON_DIR", self.geo),
            mock.patch.object(hsf, "CACHE", base / "cache"),
            mock.patch.dict(hsf.COUNTRIES, {"tst": {"name": "Testland", "boundaries": "tst_admin1.geojson"}},
                            clear=True),
            mock.patch.object(hsf.time, "sleep", lambda s: None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def fake_pages(self, pages):
        """hs_get replacement: page n returns pages[n-1], then an empty page."""
        calls = []

        def hs_get(params):
            calls.append(dict(params))
            n = params["page"]
            return pages[n - 1] if n <= len(pages) else []
        return hs_get, calls


class DownloadTest(Sandbox):
    def test_reads_every_page_and_cleans_records(self):
        hs_get, calls = self.fake_pages([
            [item(2, 0.5, 0.5), item(1, 1.5, 0.5), {"osm_type": "node", "osm_id": 9, "centroid": None}],
            [item(1, 1.5, 0.5), item(3, 9.0, 9.0, name="")],   # 1 repeats; 3 is outside
        ])
        with mock.patch.object(hsf, "hs_get", hs_get):
            records, n = hsf.download("tst", KEY, 50)
        self.assertEqual(n, 3)                                  # two pages plus the empty one
        self.assertEqual(sorted(r["id"] for r in records), ["node/1", "node/2", "node/3"])
        self.assertTrue(all(c["country"] == "Testland" for c in calls))

    def test_page_limit_is_an_error(self):
        hs_get, _ = self.fake_pages([[item(i, 0.5, 0.5)] for i in range(1, 10)])
        with mock.patch.object(hsf, "hs_get", hs_get):
            with self.assertRaises(hsf.ApiError):
                hsf.download("tst", KEY, 3)


class BuildTest(Sandbox):
    def records(self):
        return [
            {"id": "node/3", "name": "Hôpital régional", "type": "hospital", "lon": 0.5, "lat": 0.5},
            {"id": "node/1", "name": "Pharmacie", "type": "pharmacy", "lon": 1.5, "lat": 0.5},
            {"id": "node/2", "name": "", "type": "doctor, pharmacy, birthing center", "lon": 3.5, "lat": 0.5},
            {"id": "way/7", "name": "Cabinet dentaire", "type": "dentist", "lon": 9, "lat": 9},
        ]

    def test_regions_types_and_order(self):
        gj = hsf.build_geojson("tst", self.records(), "2026-11-23", 2)
        ids = [f["properties"]["id"] for f in gj["features"]]
        self.assertEqual(ids, sorted(ids))                     # stable order, small weekly diffs
        regions = {f["properties"]["id"]: f["properties"]["r"] for f in gj["features"]}
        self.assertEqual(regions, {"node/3": "West", "node/1": "East", "node/2": "East", "way/7": ""})
        meta = gj["metadata"]
        self.assertEqual(meta["total"], 4)
        self.assertEqual(meta["by_region"], {"West": 1, "East": 2})
        self.assertEqual(meta["outside_regions"], 1)
        self.assertEqual(meta["unnamed"], 1)
        self.assertEqual(meta["by_type"], {"hospital": 1, "clinic": 1, "doctor": 0, "pharmacy": 1, "other": 1})
        self.assertEqual(meta["licence"], "ODbL 1.0")

    def test_just_outside_a_boundary_joins_the_nearest_region(self):
        # 0.005 degrees is about 550 m: inside the 1 km limit. 0.05 is about 5.5 km: outside it.
        recs = [{"id": "node/8", "name": "Poste côtier", "type": "clinic", "lon": -0.005, "lat": 0.5},
                {"id": "node/9", "name": "Au large", "type": "clinic", "lon": -0.05, "lat": 0.5}]
        gj = hsf.build_geojson("tst", recs, "2026-11-24", 1)
        regions = {f["properties"]["id"]: f["properties"]["r"] for f in gj["features"]}
        self.assertEqual(regions, {"node/8": "West", "node/9": ""})
        self.assertEqual(gj["metadata"]["snapped_to_region"], 1)
        self.assertEqual(gj["metadata"]["outside_regions"], 1)
        self.assertEqual(gj["metadata"]["by_region"], {"West": 1, "East": 0})

    def test_only_small_public_properties(self):
        gj = hsf.build_geojson("tst", self.records(), "2026-11-23", 2)
        for f in gj["features"]:
            self.assertEqual(set(f["properties"]), {"n", "t", "id", "r"})

    def test_large_drop_keeps_the_current_file(self):
        many = [{"id": f"node/{i}", "name": "x", "type": "clinic", "lon": 0.5, "lat": 0.5} for i in range(100)]
        report = []
        self.assertTrue(hsf.save("tst", many, "2026-11-16", 2, False, report))
        before = hsf.out_file("tst").read_text()
        self.assertFalse(hsf.save("tst", many[:80], "2026-11-23", 2, False, report))
        self.assertEqual(hsf.out_file("tst").read_text(), before)
        self.assertIn("Kept the current file", report[-1])
        self.assertTrue(hsf.save("tst", many[:80], "2026-11-23", 2, True, report))   # --force
        self.assertEqual(json.loads(hsf.out_file("tst").read_text())["metadata"]["total"], 80)

    def test_empty_download_keeps_the_current_file(self):
        report = []
        self.assertFalse(hsf.save("tst", [], "2026-11-23", 1, True, report))
        self.assertFalse(hsf.out_file("tst").exists())

    def test_report_shows_the_change(self):
        report = []
        hsf.save("tst", self.records()[:2], "2026-11-16", 2, False, report)
        hsf.save("tst", self.records()[1:], "2026-11-23", 2, False, report)
        self.assertIn("+2 / −1", report[-1])


class KeyTest(Sandbox):
    """The key must never reach the map file, the cache, the report or the output."""

    def run_refresh(self, urlopen):
        report = Path(self.tmp.name) / "report.md"
        args = SimpleNamespace(countries=[], max_pages=50, force=False, report=str(report))
        out = io.StringIO()
        code = 0
        with mock.patch.dict(os.environ, {"HEALTHSITES_API_KEY": KEY}), \
                mock.patch.object(hsf.urllib.request, "urlopen", urlopen), redirect_stdout(out):
            try:
                hsf.cmd_refresh(args)
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), report.read_text()

    def test_refused_key(self):
        def urlopen(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
        code, out, report = self.run_refresh(urlopen)
        self.assertEqual(code, 1)                              # nothing refreshed: the workflow fails
        self.assertIn("refused the key", report)
        self.assertNotIn(KEY, out + report)

    def test_success(self):
        pages = {1: [item(1, 0.5, 0.5)], 2: []}

        def urlopen(req, timeout=None):
            self.assertIn("api-key=", req.full_url)            # sent to the API only
            page = int(req.full_url.split("page=")[1].split("&")[0])
            return io.BytesIO(json.dumps(pages.get(page, [])).encode())
        code, out, report = self.run_refresh(urlopen)
        self.assertEqual(code, 0)
        written = hsf.out_file("tst").read_text() + hsf.cache_file("tst").read_text()
        self.assertNotIn(KEY, out + report + written)
        self.assertIn("| Testland (tst) | 1 | new file |", report)

    def test_server_error_is_retried(self):
        attempts = []

        def urlopen(req, timeout=None):
            attempts.append(1)
            if len(attempts) < 3:
                raise urllib.error.HTTPError(req.full_url, 502, "Bad Gateway", {}, None)
            return io.BytesIO(b"[]")
        with mock.patch.object(hsf.urllib.request, "urlopen", urlopen):
            self.assertEqual(hsf.hs_get({"country": "Testland", "page": 1, "api-key": KEY}), [])
        self.assertEqual(len(attempts), 3)


class PluginTest(unittest.TestCase):
    def test_reads_metadata_and_skips_broken_files(self):
        with tempfile.TemporaryDirectory() as d:
            gj = {"type": "FeatureCollection", "features": [],
                  "metadata": {"country": "Senegal", "total": 1905, "downloaded": "2026-11-23",
                               "by_region": {"Tambacounda": 35}, "by_type": {"pharmacy": 678}}}
            Path(d, "sen_facilities.geojson").write_text(json.dumps(gj))
            Path(d, "cod_facilities.geojson").write_text("{not json")
            Path(d, "sen_admin1.geojson").write_text("{}")         # not a facility file
            with self.assertLogs(plugin.log, "WARNING"):
                result = plugin.load_dir(d)
        self.assertEqual(list(result), ["sen_facilities.geojson"])
        s = result["sen_facilities.geojson"]
        self.assertEqual((s["total"], s["updated_day"]), (1905, "23 November 2026"))
        self.assertEqual(s["by_region"]["Tambacounda"], 35)


if __name__ == "__main__":
    unittest.main()
