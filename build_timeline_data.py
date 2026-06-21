#!/usr/bin/env python3
"""
Transform Twitter archive (tweets.js) into timeline JSON structure.
Output: theme/static/twitter_timeline_data.json
"""
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ARCHIVE = Path.home() / "twitter-archive" / "data" / "tweets.js"
OUTPUT = Path("theme/static/twitter_timeline_data.json")

PHASES = [
    {"id": "foundation",    "label": "Foundation & Mission",      "range": "2015–2019", "years": range(2015, 2019)},
    {"id": "crisis",        "label": "Crisis Response & Scale",   "range": "2019–2021", "years": range(2019, 2022)},
    {"id": "institutional", "label": "Institutional Partnership", "range": "2022–2024", "years": range(2022, 2025)},
]

def year_to_phase(year):
    for p in PHASES:
        if year in p["years"]:
            return p["id"]
    return None

raw = ARCHIVE.read_text(encoding="utf-8")
raw = re.sub(r"^window\.\w+\.\w+\.\w+ = ", "", raw.strip())
data = json.loads(raw)
tweets = [item["tweet"] for item in data]
print(f"Loaded {len(tweets)} tweets from archive")

buckets = {p["id"]: [] for p in PHASES}
skipped = 0

for tw in tweets:
    text = tw.get("full_text", "")
    if text.startswith("RT @"):
        skipped += 1
        continue

    created_at = tw.get("created_at", "")
    try:
        dt = parsedate_to_datetime(created_at)
    except Exception:
        skipped += 1
        continue

    phase_id = year_to_phase(dt.year)
    if phase_id is None:
        skipped += 1
        continue

    tweet_id = tw.get("id_str", tw.get("id", ""))

    entities = tw.get("entities", {})
    hashtags = [h["text"].lower() for h in entities.get("hashtags", [])]
    mentions = [m["screen_name"] for m in entities.get("user_mentions", [])]

    # Strip hashtag tokens from text so template can render them as styled chips
    clean = text
    for tag in hashtags:
        clean = re.sub(rf"#(?i:{re.escape(tag)})\b", "", clean)
    clean = re.sub(r"\s{2,}", " ", clean).strip()

    buckets[phase_id].append({
        "id": tweet_id,
        "date": dt.strftime("%Y-%m-%d"),
        "date_display": dt.strftime("%d %b %Y"),
        "text": clean,
        "hashtags": hashtags,
        "mentions": mentions,
        "url": f"https://x.com/healthsites_io/status/{tweet_id}",
    })

# Sort each bucket oldest-first
for phase_id in buckets:
    buckets[phase_id].sort(key=lambda t: t["date"])

included = sum(len(v) for v in buckets.values())
output = {
    "account": "healthsites_io",
    "profile_url": "https://x.com/healthsites_io",
    "total_tweets": included,
    "range": "2015–2024",
    "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    "phases": [
        {
            "id": p["id"],
            "label": p["label"],
            "range": p["range"],
            "tweets": buckets[p["id"]],
        }
        for p in PHASES
    ],
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"Skipped {skipped} tweets (retweets / unparseable dates / out-of-range)")
print(f"Wrote {included} tweets to {OUTPUT}")
for p in PHASES:
    print(f"  {p['label']}: {len(buckets[p['id']])} tweets")
