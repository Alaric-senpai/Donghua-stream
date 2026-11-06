"""Quota-free default Explore feed for the Anime Box YouTube channel.

The desktop app ships a small snapshot so opening Explore is instant and does
not spend YouTube Data API quota.  The optional refresh reads YouTube's public
RSS feed, which is also quota-free; only explicit searches use the Data API.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from youtube_api import format_duration, format_views, human_age

BUNDLED_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "gui", "assets", "animebox_feed.json")
RSS_URL = (
    "https://www.youtube.com/feeds/videos.xml?channel_id="
    "UCCjDVYW8t7cEC-IQY55JFQg")
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}

CHANNEL_ID = "UCCjDVYW8t7cEC-IQY55JFQg"
CHANNEL_NAME = "Anime Box"

FILTERS = [
    ("all", "All"),
    ("full", "Full episodes"),
    ("previews", "Previews"),
    ("members", "Members"),
    ("Soul Land", "Soul Land"),
    ("Swallowed Star", "Swallowed Star"),
    ("Renegade Immortal", "Renegade Immortal"),
]


def _count(text: Any) -> int:
    raw = str(text or "").replace(",", "").strip()
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _published(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat(timespec="seconds")


def _normalize(item: Dict[str, Any], channel: Dict[str, Any]) -> Dict[str, Any]:
    video = dict(item or {})
    video_id = str(video.get("id") or "").strip()
    video["id"] = video_id
    video["url"] = video.get("url") or (
        f"https://www.youtube.com/watch?v={video_id}" if video_id else "")
    video["thumbnail"] = video.get("thumbnail") or (
        f"https://i.ytimg.com/vi/{video_id}/hq720.jpg" if video_id else "")
    video["channel"] = video.get("channel") or channel.get("name") or "YouTube"
    video["channel_id"] = video.get("channel_id") or channel.get("id") or ""
    views = _count(video.get("views"))
    video["views"] = views
    video["views_text"] = format_views(views) if views > 0 else ""
    video["age_text"] = human_age(video.get("published_at"))
    duration = _count(video.get("duration"))
    video["duration"] = duration
    video["duration_text"] = (
        str(video.get("duration_text") or "").strip()
        or (format_duration(duration) if duration else ""))
    title = str(video.get("title") or "").lower()
    video["preview"] = bool(video.get("preview")) or "preview" in title
    if video["channel_id"] == channel.get("id"):
        video["channel_avatar"] = channel.get("avatar") or ""
    return video


def _decorate(payload: Dict[str, Any]) -> Dict[str, Any]:
    channel = dict(payload.get("channel") or {})
    items = [_normalize(item, channel) for item in payload.get("items") or []]
    return {
        "source": payload.get("source") or "bundled",
        "fetched_at": payload.get("fetched_at") or "",
        "channel": channel,
        "items": items,
    }


def load_bundled() -> Dict[str, Any]:
    """Load the shipped Anime Box snapshot without any network access."""
    with open(BUNDLED_PATH, "r", encoding="utf-8") as handle:
        return _decorate(json.load(handle))


def matches_filter(item: Dict[str, Any], key: str) -> bool:
    if not key or key == "all":
        return True
    title = str(item.get("title") or "").lower()
    duration = int(item.get("duration") or 0)
    if key == "full":
        return not item.get("preview") and (
            duration >= 600 or "full" in title)
    if key == "previews":
        return bool(item.get("preview")) or 0 < duration < 120
    if key == "members":
        return bool(item.get("members_only") or item.get("members_first"))
    return key.lower() in title


def filtered(payload: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    return [item for item in payload.get("items") or [] if matches_filter(item, key)]


def _parse_rss(xml_text: str) -> List[Dict[str, Any]]:
    root = ET.fromstring(xml_text)
    items: List[Dict[str, Any]] = []
    for entry in root.findall("atom:entry", NS):
        video_id = (entry.findtext("yt:videoId", default="", namespaces=NS) or "").strip()
        if not video_id:
            continue
        group = entry.find("media:group", NS)
        media = group if group is not None else entry
        title = (media.findtext("media:title", default="", namespaces=NS)
                 or entry.findtext("atom:title", default="", namespaces=NS)
                 or "").strip()
        thumbnail_node = media.find("media:thumbnail", NS)
        thumbnail = ""
        if thumbnail_node is not None:
            thumbnail = str(thumbnail_node.attrib.get("url") or "").strip()
        stats = media.find("media:community/media:statistics", NS)
        views = _count(stats.attrib.get("views")) if stats is not None else 0
        published = _published(entry.findtext("atom:published", default="", namespaces=NS))
        items.append({
            "id": video_id,
            "title": re.sub(r"^[\s✨]+", "", title) or "Untitled video",
            "channel": CHANNEL_NAME,
            "channel_id": CHANNEL_ID,
            "thumbnail": thumbnail or f"https://i.ytimg.com/vi/{video_id}/hq720.jpg",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "duration": 0,
            "duration_text": "",
            "views": views,
            "published_at": published,
            "preview": "preview" in title.lower(),
            "members_only": False,
            "members_first": False,
        })
    return items


def refresh(current: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch the channel RSS and merge it with the bundled/cached feed.

    RSS is quota-free and returns the latest public uploads.  Existing entries
    keep their duration and membership flags; new entries are prepended.
    """
    request = urllib.request.Request(
        RSS_URL, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(request, timeout=20) as response:
        fresh = _parse_rss(response.read().decode("utf-8", errors="replace"))

    channel = dict(current.get("channel") or {})
    existing = {str(item.get("id")): dict(item) for item in current.get("items") or []}
    merged: List[Dict[str, Any]] = []
    seen = set()
    for item in fresh:
        video_id = str(item.get("id") or "")
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        old = existing.get(video_id) or {}
        merged.append({**old, **item, **{
            "duration": old.get("duration") or item.get("duration") or 0,
            "duration_text": old.get("duration_text") or item.get("duration_text") or "",
            "members_only": old.get("members_only", item.get("members_only", False)),
            "members_first": old.get("members_first", item.get("members_first", False)),
        }})
    for video_id, item in existing.items():
        if video_id and video_id not in seen:
            merged.append(item)

    return _decorate({
        "source": "rss",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "channel": channel,
        "items": merged[:60],
    })


def channel_url(payload: Optional[Dict[str, Any]] = None) -> str:
    channel = (payload or {}).get("channel") or {}
    return str(channel.get("url") or "https://www.youtube.com/@AnimeBox666")
