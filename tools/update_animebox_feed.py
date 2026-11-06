#!/usr/bin/env python3
"""Refresh the bundled Anime Box Explore feed.

This intentionally does not touch the YouTube Data API.  It reads the public
channel page (for the current video grid, durations and badges) and the
channel RSS feed (for exact publication timestamps), then writes a small JSON
snapshot used by the desktop app.  Running this script is optional: the app
ships with a snapshot so opening Explore costs zero API quota.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "gui" / "assets" / "animebox_feed.json"

CHANNEL_ID = "UCCjDVYW8t7cEC-IQY55JFQg"
CHANNEL_NAME = "Anime Box"
CHANNEL_HANDLE = "@AnimeBox666"
CHANNEL_URL = f"https://www.youtube.com/channel/{CHANNEL_ID}"
VIDEOS_URL = f"https://www.youtube.com/channel/{CHANNEL_ID}/videos"
RSS_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}
DURATION_RE = re.compile(r"^\d{1,2}(?::\d{2}){1,2}$")
COUNT_RE = re.compile(r"^\d[\d,.]*\s*[KMB]?$", re.IGNORECASE)


def fetch(url: str, *, timeout: int = 60) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def initial_data(html: str) -> Dict[str, Any]:
    match = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    if not match:
        raise ValueError("YouTube did not return ytInitialData")
    return json.loads(match.group(1))


def find_key(node: Any, key: str) -> Any:
    if isinstance(node, dict):
        if key in node:
            return node[key]
        for value in node.values():
            found = find_key(value, key)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = find_key(value, key)
            if found is not None:
                return found
    return None


def walk_key(node: Any, key: str) -> List[Any]:
    found: List[Any] = []
    if isinstance(node, dict):
        for k, value in node.items():
            if k == key:
                found.append(value)
            found.extend(walk_key(value, key))
    elif isinstance(node, list):
        for value in node:
            found.extend(walk_key(value, key))
    return found


def clean_title(text: str) -> str:
    title = re.sub(r"^[\s✨]+", "", str(text or ""))
    return re.sub(r"\s+", " ", title).strip()


def parse_duration(text: str) -> int:
    bits = [int(part) for part in str(text or "").split(":") if part.isdigit()]
    if not bits:
        return 0
    total = 0
    for part in bits:
        total = total * 60 + part
    return total


def parse_count(text: str) -> int:
    raw = str(text or "").replace(",", "").strip().upper()
    if not raw:
        return 0
    multiplier = 1
    if raw.endswith("K"):
        multiplier, raw = 1_000, raw[:-1]
    elif raw.endswith("M"):
        multiplier, raw = 1_000_000, raw[:-1]
    elif raw.endswith("B"):
        multiplier, raw = 1_000_000_000, raw[:-1]
    try:
        return int(float(raw) * multiplier)
    except ValueError:
        return 0


def relative_time(text: str, now: datetime) -> Optional[str]:
    match = re.match(r"^(\d+)\s*(h|hour|d|day|w|week|mo|month)s?\s+ago$",
                     str(text or "").strip(), re.I)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2).lower()
    if unit.startswith("h"):
        delta = timedelta(hours=amount)
    elif unit.startswith("d"):
        delta = timedelta(days=amount)
    elif unit.startswith("w"):
        delta = timedelta(weeks=amount)
    else:
        delta = timedelta(days=30 * amount)
    return (now - delta).isoformat(timespec="seconds")


def rss_dates(now: datetime) -> Dict[str, str]:
    root = ET.fromstring(fetch(RSS_URL))
    dates: Dict[str, str] = {}
    for entry in root.findall("atom:entry", NS):
        vid = (entry.findtext("yt:videoId", default="", namespaces=NS) or "").strip()
        published = (entry.findtext("atom:published", default="", namespaces=NS) or "").strip()
        if vid and published:
            dates[vid] = published
    return dates


def parse_items(data: Dict[str, Any], now: datetime,
                dates: Dict[str, str]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen = set()
    for lockup in walk_key(data, "lockupViewModel"):
        video_id = str(lockup.get("contentId") or "").strip()
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)

        meta = (lockup.get("metadata") or {}).get("lockupMetadataViewModel") or {}
        title = clean_title((meta.get("title") or {}).get("content", ""))
        rows = ((meta.get("metadata") or {}).get("contentMetadataViewModel")
                or {}).get("metadataRows") or []
        parts: List[str] = []
        badges: List[str] = []
        for row in rows:
            for part in row.get("metadataParts") or []:
                text = (part.get("text") or {}).get("content") or ""
                if text:
                    parts.append(str(text).strip())
            for badge in row.get("badges") or []:
                badge_view = badge.get("badgeViewModel") or {}
                text = badge_view.get("badgeText") or ""
                if text:
                    badges.append(str(text).strip())

        duration_text = ""
        for overlay in (((lockup.get("contentImage") or {}).get("thumbnailViewModel")
                         or {}).get("overlays") or []):
            bottom = overlay.get("thumbnailBottomOverlayViewModel") or {}
            for badge in bottom.get("badges") or []:
                text = str((badge.get("thumbnailBadgeViewModel") or {}).get("text") or "")
                if DURATION_RE.match(text):
                    duration_text = text
                    break
            if duration_text:
                break

        views = 0
        age_text = ""
        for text in parts:
            if COUNT_RE.match(text):
                views = max(views, parse_count(text))
            elif text.lower().endswith("ago"):
                age_text = text
        published_at = dates.get(video_id) or relative_time(age_text, now) or ""
        lower_title = title.lower()
        items.append({
            "id": video_id,
            "title": title,
            "channel": CHANNEL_NAME,
            "channel_id": CHANNEL_ID,
            "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hq720.jpg",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "duration": parse_duration(duration_text),
            "duration_text": duration_text,
            "views": views,
            "published_at": published_at,
            "members_only": any("members only" in badge.lower() for badge in badges),
            "members_first": any("members first" in badge.lower() for badge in badges),
            "preview": "preview" in lower_title,
        })
    return items


def channel_meta(data: Dict[str, Any]) -> Dict[str, Any]:
    renderer = find_key(data, "channelMetadataRenderer") or {}
    page = find_key(data, "pageHeaderViewModel") or {}
    avatar = ""
    for thumb in ((renderer.get("avatar") or {}).get("thumbnails") or []):
        url = str(thumb.get("url") or "")
        if url:
            # Prefer the compact 120px square over the 900px original.
            avatar = re.sub(r"=s\d+", "=s120", url)
            break
    rows = ((page.get("metadata") or {}).get("contentMetadataViewModel")
            or {}).get("metadataRows") or []
    stats: List[str] = []
    for row in rows:
        for part in row.get("metadataParts") or []:
            text = (part.get("text") or {}).get("content") or ""
            if text:
                stats.append(str(text).strip())
    description = str(renderer.get("description") or "").strip()
    tagline = next((line.strip() for line in description.splitlines() if line.strip()), "")
    return {
        "id": CHANNEL_ID,
        "name": CHANNEL_NAME,
        "handle": CHANNEL_HANDLE,
        "url": CHANNEL_URL,
        "avatar": avatar,
        "subscribers_text": next((s for s in stats if "subscriber" in s.lower()), ""),
        "videos_text": next((s for s in stats if "video" in s.lower()), ""),
        "description": description,
        "tagline": tagline,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", help="Parse a saved channel HTML file instead of fetching")
    args = parser.parse_args()

    html = Path(args.html).read_text(encoding="utf-8") if args.html else fetch(VIDEOS_URL)
    data = initial_data(html)
    now = datetime.now(timezone.utc)
    try:
        dates = rss_dates(now)
    except Exception as exc:
        print(f"warning: could not read RSS timestamps: {exc}", file=sys.stderr)
        dates = {}

    payload = {
        "source": "bundled",
        "fetched_at": now.isoformat(timespec="seconds"),
        "channel": channel_meta(data),
        "items": parse_items(data, now, dates),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} with {len(payload['items'])} videos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
