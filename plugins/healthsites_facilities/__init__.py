"""Facility counts for templates, from the committed map files.

Reads the metadata of theme/static/geojson/*_facilities.geojson, which
scripts/healthsites_facilities.py writes. Makes no network calls, so the
build never depends on the healthsites.io API or its key.

Templates read HEALTHSITES["<iso3>_facilities.geojson"], a dict with
total, by_region, by_type, country, updated (ISO date) and updated_day
("23 November 2026"). A missing or unreadable file is simply absent.
"""
import json
import logging
from datetime import date
from pathlib import Path

from pelican import signals

log = logging.getLogger(__name__)

PATTERN = "*_facilities.geojson"


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


def load(pelican):
    folder = Path(pelican.settings.get("THEME", "theme")) / "static" / "geojson"
    result = load_dir(folder)
    for name, s in result.items():
        log.info("healthsites facilities: %s: %d facilities (%s)", name, s["total"], s["updated"])
    pelican.settings["HEALTHSITES"] = result


def register():
    signals.initialized.connect(load)
