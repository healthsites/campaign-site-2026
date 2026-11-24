"""Tests for scripts/region_pages.py. Run: python -m unittest discover -s tests -v"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("rp", ROOT / "scripts" / "region_pages.py")
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)


class RegionPagesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        (base / "geo").mkdir()
        (base / "content" / "tst").mkdir(parents=True)
        feats = [{"type": "Feature", "properties": {"adm1_name": n}, "geometry": None}
                 for n in ("Kédougou", "Saint-Louis", "Dakar")]
        (base / "geo" / "tst_admin1.geojson").write_text(json.dumps({"features": feats}))
        (base / "content" / "saint-louis.md").write_text(
            "---\nTitle: Saint-Louis\nTemplate: region\nCountry_slug: testland\nRegion: Saint-Louis\n---\n\nBody\n")
        cfg = {"tst": {"country": "Testland", "slug": "testland",
                       "boundaries": "tst_admin1.geojson", "facilities": "tst_facilities.geojson"}}
        for p in (mock.patch.object(rp, "GEOJSON", base / "geo"), mock.patch.object(rp, "CONTENT", base / "content"),
                  mock.patch.object(rp, "ROOT", base), mock.patch.dict(rp.COUNTRIES, cfg, clear=True)):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.base = base

    def run_script(self, *args):
        with mock.patch.object(sys, "argv", ["region_pages.py", "tst", *args]), \
                mock.patch("builtins.print"):
            rp.main()

    def test_creates_missing_pages_and_keeps_existing(self):
        self.run_script("--campaign", "Kédougou")
        out = self.base / "content" / "testland"
        self.assertEqual(sorted(p.name for p in out.iterdir()), ["dakar.md", "kedougou.md"])
        ked = (out / "kedougou.md").read_text()
        self.assertIn("Region: Kédougou\n", ked)
        self.assertIn("Region_tier: campaign\n", ked)
        self.assertIn("Order: 10\n", ked)
        self.assertIn("Region_tier: open-data\n", (out / "dakar.md").read_text())
        self.assertIn("Body", (self.base / "content" / "saint-louis.md").read_text())

    def test_running_again_changes_nothing(self):
        self.run_script("--campaign", "Kédougou")
        page = self.base / "content" / "testland" / "dakar.md"
        page.write_text(page.read_text() + "Lede: edited by hand\n")
        self.run_script()
        self.assertIn("edited by hand", page.read_text())

    def test_unknown_campaign_region_stops(self):
        with self.assertRaises(SystemExit):
            self.run_script("--campaign", "Kedougou")      # no accent: not the boundary name

    def test_slugify(self):
        self.assertEqual(rp.slugify("Sédhiou"), "sedhiou")
        self.assertEqual(rp.slugify("Saint-Louis"), "saint-louis")


if __name__ == "__main__":
    unittest.main()
