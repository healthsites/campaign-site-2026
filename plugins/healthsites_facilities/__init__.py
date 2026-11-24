"""Facility counts for templates, from the committed map files.

Reads the metadata of theme/static/geojson/*_facilities.geojson, which
scripts/healthsites_facilities.py writes. Makes no network calls, so the
build never depends on the healthsites.io API or its key.

Templates read HEALTHSITES["<iso3>_facilities.geojson"], a dict with
total, by_region, by_type, country, updated (ISO date) and updated_day
("23 November 2026"). A missing or unreadable file is simply absent.

Templates also read HIGHLIGHTS["<name>_emergency.geojson"], a dict with
metadata, rows (the facility properties, in file order) and heat_range
("7–13 November 2026"), from the files scripts/saint_louis_emergency.py writes.
"""
import json
import logging
from datetime import date
from pathlib import Path

from pelican import signals

log = logging.getLogger(__name__)

PATTERN = "*_facilities.geojson"
HIGHLIGHT_PATTERN = "*_emergency.geojson"


def _day(iso):
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    return f"{d.day} {d:%B %Y}"


def summarise(path):
    """The template summary for one map file, or None if it can't be read."""
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))["metadata"]
        return {
            "country": meta.get("country", ""),
            "total": int(meta["total"]),
            "by_region": meta.get("by_region") or {},
            "by_type": meta.get("by_type") or {},
            "updated": meta.get("downloaded", ""),
            "updated_day": _day(meta.get("downloaded")),
        }
    except (OSError, ValueError, KeyError, TypeError) as e:
        log.warning("healthsites facilities: could not read %s: %s", path.name, e)
        return None


def load_dir(folder):
    result = {}
    for path in sorted(Path(folder).glob(PATTERN)):
        summary = summarise(path)
        if summary:
            result[path.name] = summary
    return result


def _range(a, b):
    """'7–13 November 2026' from two ISO dates (or '' if either is missing)."""
    try:
        d1, d2 = date.fromisoformat(a), date.fromisoformat(b)
    except (TypeError, ValueError):
        return ""
    if (d1.year, d1.month) == (d2.year, d2.month):
        return f"{d1.day}–{d2.day} {d2:%B %Y}"
    return f"{_day(a)} – {_day(b)}"


def load_highlights(folder):
    result = {}
    for path in sorted(Path(folder).glob(HIGHLIGHT_PATTERN)):
        try:
            gj = json.loads(path.read_text(encoding="utf-8"))
            meta = gj["metadata"]
            result[path.name] = {
                "metadata": meta,
                "rows": [f["properties"] for f in gj["features"]],
                "heat_range": _range(meta.get("heat_from"), meta.get("heat_to")),
            }
        except (OSError, ValueError, KeyError, TypeError) as e:
            log.warning("healthsites highlights: could not read %s: %s", path.name, e)
    return result


def load(pelican):
    folder = Path(pelican.settings.get("THEME", "theme")) / "static" / "geojson"
    result = load_dir(folder)
    for name, s in result.items():
        log.info("healthsites facilities: %s: %d facilities (%s)", name, s["total"], s["updated"])
    pelican.settings["HEALTHSITES"] = result
    pelican.settings["HIGHLIGHTS"] = load_highlights(folder)


def register():
    signals.initialized.connect(load)
