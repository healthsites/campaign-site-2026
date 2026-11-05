"""Fetch HOT Tasking Manager projects per campaign at build time.

Settings:
    TASKING_MANAGER_CAMPAIGNS  dict of country_slug -> campaign tag
    TASKING_MANAGER_TTL_HOURS  cache lifetime in hours (default 6)

Environment:
    TM_OFFLINE=1               read the cache only, never fetch

Templates read the result as TASKING_MANAGER[slug] (a summary dict, or None
when there is no data). The build never fails because of the Tasking Manager.
"""
import json
import logging
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pelican import signals

log = logging.getLogger(__name__)

API = "https://tasking-manager-production-api.hotosm.org/api/v2/projects/"
TM_PROJECT_URL = "https://tasks.hotosm.org/projects/{id}"
KEEP = ("projectId", "name", "status", "percentMapped", "percentValidated",
        "totalContributors", "difficulty", "lastUpdated")
CACHE_DIR = Path(".cache/tasking-manager")


def fetch_campaign(campaign, timeout=20, max_pages=10):
    """Return {"projects": [...], "features": [...]} for one campaign tag.

    This is the only function that talks to the data source. To switch to
    another source (e.g. an insta-tm snapshot), replace it and keep the
    return shape: projects as in the TM API `results`, features as in
    `mapResults.features`.
    """
    projects, features, page = [], [], 1
    while page <= max_pages:
        q = urllib.parse.urlencode({"campaign": campaign,
                                    "projectStatuses": "PUBLISHED,ARCHIVED",
                                    "page": page})
        req = urllib.request.Request(f"{API}?{q}", headers={
            "Accept": "application/json",
            "User-Agent": "campaigns.healthsites.io static build"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        projects += data.get("results", [])
        features += (data.get("mapResults") or {}).get("features", [])
        if not (data.get("pagination") or {}).get("hasNext"):
            break
        page += 1
    return {"projects": projects, "features": features}


def _parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


def _day(dt):
    return f"{dt.day} {dt:%b %Y}" if dt else ""


def summarise(raw, campaign, fetched_at):
    by_id = {}
    for p in raw.get("projects", []):
        by_id[p["projectId"]] = {k: p.get(k) for k in KEEP}

    prefix = f"{campaign}: "
    for p in by_id.values():
        dt = _parse(p["lastUpdated"])
        p["short_name"] = p["name"][len(prefix):] if p["name"].startswith(prefix) else p["name"]
        p["url"] = TM_PROJECT_URL.format(id=p["projectId"])
        p["last_day"] = _day(dt)
        p["_dt"] = dt

    projects = sorted(by_id.values(),
                      key=lambda p: p["_dt"] or datetime.min.replace(tzinfo=timezone.utc),
                      reverse=True)
    open_ = [p for p in projects if p["status"] == "PUBLISHED"]
    # Biggest gap between mapped and validated first: validation is the bottleneck.
    open_.sort(key=lambda p: (p["percentMapped"] or 0) - (p["percentValidated"] or 0),
               reverse=True)
    done = [p for p in projects if p["status"] == "ARCHIVED"]

    features, seen = [], set()
    for f in raw.get("features", []):
        pid = f["properties"]["projectId"]
        if pid in by_id and pid not in seen:
            seen.add(pid)
            lng, lat = f["geometry"]["coordinates"]
            features.append({"id": pid, "lat": lat, "lng": lng,
                             "name": by_id[pid]["short_name"],
                             "open": by_id[pid]["status"] == "PUBLISHED"})

    last = projects[0]["_dt"] if projects else None
    for p in projects:
        p.pop("_dt")
    return {
        "campaign": campaign,
        "total": len(projects),
        "open_count": len(open_),
        "done_count": len(done),
        "open": open_,
        "done": done,
        "features": features,
        "last_edit": f"{_day(last)}, {last:%H:%M} UTC" if last else "",
        "fetched": _day(fetched_at),
    }


def _read_cache(path):
    """Return (raw, fetched_at) from a cache file, or (None, None)."""
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
        return cached["raw"], datetime.fromtimestamp(cached["fetched_at"], timezone.utc)
    except (OSError, ValueError, KeyError, TypeError):
        return None, None


def _write_cache(path, raw, fetched_at):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"fetched_at": fetched_at.timestamp(), "raw": raw}),
                       encoding="utf-8")
        tmp.replace(path)
    except OSError as e:
        log.warning("Tasking Manager: could not write cache %s: %s", path, e)


def load_campaign(slug, campaign, ttl_hours, offline, cache_dir=None):
    """Return (summary or None, source) for one campaign."""
    path = (cache_dir or CACHE_DIR) / f"{slug}.json"
    raw, fetched_at = _read_cache(path)
    fresh = raw is not None and time.time() - fetched_at.timestamp() < ttl_hours * 3600

    source = None
    if raw is not None and (fresh or offline):
        source = "cache"
    elif not offline:
        try:
            raw, fetched_at = fetch_campaign(campaign), datetime.now(timezone.utc)
            _write_cache(path, raw, fetched_at)
            source = "api"
        except Exception as e:  # network, HTTP or JSON errors must not break the build
            log.warning("Tasking Manager: fetch failed for %s (%s): %s", slug, campaign, e)
            if raw is not None:
                source = "stale-cache"

    if source is None:
        return None, "none"
    try:
        return summarise(raw, campaign, fetched_at), source
    except Exception as e:
        log.warning("Tasking Manager: could not summarise %s: %s", slug, e)
        return None, "none"


def load(pelican):
    settings = pelican.settings
    campaigns = settings.get("TASKING_MANAGER_CAMPAIGNS") or {}
    ttl_hours = float(settings.get("TASKING_MANAGER_TTL_HOURS", 6))
    offline = os.environ.get("TM_OFFLINE") == "1"

    result = {}
    for slug, campaign in campaigns.items():
        summary, source = load_campaign(slug, campaign, ttl_hours, offline)
        result[slug] = summary
        count = summary["total"] if summary else 0
        log.info("Tasking Manager: %s: %d projects (source: %s)", slug, count, source)
    settings["TASKING_MANAGER"] = result


def register():
    signals.initialized.connect(load)
