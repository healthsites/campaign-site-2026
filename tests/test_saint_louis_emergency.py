"""Tests for scripts/saint_louis_emergency.py and the HIGHLIGHTS part of the plugin.

Run: python -m unittest discover -s tests -v
Made-up data only. The main test: nothing from the survey but counts reaches the public file.
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins"))

spec = importlib.util.spec_from_file_location("sle", ROOT / "scripts" / "saint_louis_emergency.py")
sle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sle)

import healthsites_facilities as plugin  # noqa: E402


def point(osm_id, lon, lat, name, region="Saint-Louis", **extra):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"id": osm_id, "n": name, "t": "doctor", "r": region, **extra}}


FACILITIES = {"type": "FeatureCollection", "features": [
    point("node/1", -16.0, 16.0, "poste de sante de exemple"),
    point("node/2", -16.0002, 16.0, "pharmacie voisine"),          # ~20 m away, another name
    point("node/3", -15.5, 15.97, "case de sante de autre", region="Louga"),
    point("node/4", -14.0, 16.2, "case de sante sor diagne"),
]}
HEAT = {"type": "FeatureCollection",
        "metadata": {"date_from": "2026-11-07", "date_to": "2026-11-13", "classes": [], "metric": "tmax"},
        "features": [point("node/1", -16.0, 16.0, "x", tmax=40.9, p=99, c=5),
                     point("node/3", -15.5, 15.97, "x", tmax=38.0, p=60, c=3),
                     point("node/4", -14.0, 16.2, "x", tmax=37.0, p=40, c=2)]}


def row(name, lon, lat, doctors="NA"):
    return {"name_of_facility": name, "longitude": str(lon), "latitude": str(lat),
            "phone_number": "770000000", "number_of_beds": "3", "number_of_doctors": doctors,
            "number_of_nurses": "1", "city": "Exemple"}


class BuildTest(unittest.TestCase):
    def build(self):
        rows = [row("Poste de santé de Exemple", -16.0001, 16.0),   # closer to the pharmacy, same name as node/1
                row("Case de santé de Autre", -15.5, 15.97, doctors="1"),
                row("Ministère de la santé", -14.0001, 16.2)]        # no name match: nearest record
        return sle.build(rows, FACILITIES, HEAT)

    def test_name_beats_a_closer_record_with_another_name(self):
        gj, checks = self.build()
        ids = {c[0]: c[2] for c in checks}
        self.assertEqual(ids["Poste de santé de Exemple"], "node/1")
        self.assertEqual(ids["Ministère de la santé"], "node/4")

    def test_only_public_fields_and_counts(self):
        gj, _ = self.build()
        text = json.dumps(gj, ensure_ascii=False)
        for secret in ("770000000", "Ministère", "Exemple\"", "number_of"):
            self.assertNotIn(secret, text)
        for f in gj["features"]:
            self.assertLessEqual(set(f["properties"]), set(sle.PUBLIC_FIELDS))
        m = gj["metadata"]
        self.assertEqual((m["total"], m["hottest_20"], m["hottest_40"], m["no_doctor_2022"], m["outside_saint_louis"]),
                         (3, 1, 2, 2, 1))
        self.assertEqual([f["properties"]["id"] for f in gj["features"]], ["node/1", "node/3", "node/4"])  # hottest first

    def test_no_record_nearby_stops(self):
        with self.assertRaises(SystemExit):
            sle.build([row("Nulle part", -10.0, 10.0)], FACILITIES, HEAT)


class PluginTest(unittest.TestCase):
    def test_reads_highlights(self):
        with tempfile.TemporaryDirectory() as d:
            gj = {"type": "FeatureCollection",
                  "metadata": {"total": 1, "heat_from": "2026-11-07", "heat_to": "2026-11-13"},
                  "features": [point("node/1", -16.0, 16.0, "poste", tmax=40.9, p=99, c=5)]}
            Path(d, "sen_saint_louis_emergency.geojson").write_text(json.dumps(gj))
            result = plugin.load_highlights(d)
        h = result["sen_saint_louis_emergency.geojson"]
        self.assertEqual(h["heat_range"], "7–13 November 2026")
        self.assertEqual(h["rows"][0]["p"], 99)


if __name__ == "__main__":
    unittest.main()
