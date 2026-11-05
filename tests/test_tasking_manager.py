"""Tests for plugins/tasking_manager. Run: python -m unittest discover -s tests -v"""
import copy
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins"))

import tasking_manager as tm  # noqa: E402

CAMPAIGN = "DRC Ebola 2026"
FIXTURE = ROOT / "tests" / "fixtures" / "tm_drc_page1.json"
FETCHED = datetime(2026, 11, 5, 9, 0, tzinfo=timezone.utc)


def load_fixture():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {"projects": data["results"], "features": data["mapResults"]["features"]}


def with_open_projects(raw):
    """Fixture page 1 is all ARCHIVED: reopen three projects with known progress."""
    raw = copy.deepcopy(raw)
    progress = [(40, 30), (90, 10), (60, 55)]  # gaps: 10, 80, 5
    for p, (mapped, validated) in zip(raw["projects"], progress):
        p["status"] = "PUBLISHED"
        p["percentMapped"], p["percentValidated"] = mapped, validated
    return raw


class SummariseTest(unittest.TestCase):

    def setUp(self):
        self.raw = load_fixture()

    def test_deduplicates_projects(self):
        raw = {"projects": self.raw["projects"] * 2, "features": self.raw["features"]}
        s = tm.summarise(raw, CAMPAIGN, FETCHED)
        ids = [p["projectId"] for p in s["open"] + s["done"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(s["total"], len({p["projectId"] for p in self.raw["projects"]}))

    def test_counts_open_and_done(self):
        s = tm.summarise(with_open_projects(self.raw), CAMPAIGN, FETCHED)
        self.assertEqual(s["open_count"], 3)
        self.assertEqual(s["done_count"], len(self.raw["projects"]) - 3)
        self.assertEqual(s["total"], s["open_count"] + s["done_count"])
        self.assertTrue(all(p["status"] == "PUBLISHED" for p in s["open"]))
        self.assertTrue(all(p["status"] == "ARCHIVED" for p in s["done"]))

    def test_no_published_projects(self):
        raw = copy.deepcopy(self.raw)
        for p in raw["projects"]:
            p["status"] = "ARCHIVED"
        s = tm.summarise(raw, CAMPAIGN, FETCHED)
        self.assertEqual(s["open_count"], 0)
        self.assertEqual(s["open"], [])
        self.assertEqual(s["done_count"], s["total"])
        self.assertFalse(any(f["open"] for f in s["features"]))

    def test_open_sorted_by_validation_gap(self):
        s = tm.summarise(with_open_projects(self.raw), CAMPAIGN, FETCHED)
        gaps = [p["percentMapped"] - p["percentValidated"] for p in s["open"]]
        self.assertEqual(gaps, [80, 10, 5])

    def test_strips_campaign_prefix(self):
        s = tm.summarise(self.raw, CAMPAIGN, FETCHED)
        for p in s["done"]:
            self.assertFalse(p["short_name"].startswith(CAMPAIGN + ": "), p["short_name"])
        names = {p["projectId"]: p["short_name"] for p in s["done"]}
        self.assertEqual(names[67887], "Residential Areas 13")

    def test_features_once_known_only_with_open_flag(self):
        raw = with_open_projects(self.raw)
        stranger = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [1, 2]},
                    "properties": {"projectId": 1}}
        raw["features"] = raw["features"] * 2 + [stranger]
        s = tm.summarise(raw, CAMPAIGN, FETCHED)
        known = {p["projectId"] for p in raw["projects"]}
        ids = [f["id"] for f in s["features"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(set(ids) <= known)
        self.assertNotIn(1, ids)
        open_ids = {p["projectId"] for p in s["open"]}
        for f in s["features"]:
            self.assertEqual(f["open"], f["id"] in open_ids)

    def test_last_edit_format(self):
        raw = copy.deepcopy(self.raw)
        for p in raw["projects"]:
            p["lastUpdated"] = "2026-10-01T08:00:00.000000Z"
        raw["projects"][0]["lastUpdated"] = "2026-10-22T12:30:45.123456Z"
        s = tm.summarise(raw, CAMPAIGN, FETCHED)
        self.assertEqual(s["last_edit"], "22 Oct 2026, 12:30 UTC")
        self.assertEqual(s["fetched"], "5 Nov 2026")


class LoadTest(unittest.TestCase):

    def test_offline_without_cache_sets_none(self):
        pelican = SimpleNamespace(settings={"TASKING_MANAGER_CAMPAIGNS": {"drc": CAMPAIGN}})
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(tm, "CACHE_DIR", Path(d) / "tm"), \
                mock.patch.dict(os.environ, {"TM_OFFLINE": "1"}), \
                mock.patch.object(tm, "fetch_campaign", side_effect=AssertionError("fetched")):
            tm.load(pelican)
        self.assertEqual(pelican.settings["TASKING_MANAGER"], {"drc": None})


if __name__ == "__main__":
    unittest.main()
