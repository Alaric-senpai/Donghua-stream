"""YouTube Data API v3 client.

Explore uses ``search`` only, and only after an explicit user search: its
default Anime Box feed is bundled with the app and costs zero quota.  The
``trending``, ``video`` and ``discover`` helpers remain available for other
callers and diagnostics.

Responses are cached on disk under ``~/.cache/donghua-stream/youtube`` so
repeating a search does not spend quota.  The module uses ``urllib`` from the
standard library; no new runtime dependency is required.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import app_config

API_ROOT = "https://www.googleapis.com/youtube/v3"
CACHE_DIR = os.path.join(
    os.path.expanduser("~"), ".cache", "donghua-stream", "youtube")
USER_AGENT = "DonghuaStream/1.0 (+PyQt6 desktop client)"
_THUMB_KEYS = ("maxres", "standard", "high", "medium", "default")


class YouTubeError(RuntimeError):
    """A user-readable API/network failure with safe diagnostic details."""

    def __init__(self, message: str, *, status: Optional[int] = None,
                 reason: str = "", details: str = ""):
        super().__init__(message)
        self.message = message
        self.status = status
        self.reason = reason
        self.details = details or message

    def report(self) -> str:
        bits = []
        if self.status:
            bits.append(f"HTTP {self.status}")
        if self.reason:
            bits.append(f"reason: {self.reason}")
        header = "\n".join(bits)
        return f"{header}\n\n{self.details}".strip()


class YouTubeNotConfigured(YouTubeError):
    """Raised when no API key has been saved to the config file."""


# ---------------------------------------------------------------------------
# Formatting / parsing helpers (kept UI-free for unit tests)
# ---------------------------------------------------------------------------
_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$")


def duration_seconds(value: str) -> int:
    """Convert an ISO-8601 YouTube duration (``PT1H2M3S``) to seconds."""
    text = str(value or "").strip()
    if not text:
        return 0
    match = _DURATION_RE.match(text)
    if not match:
        return 0
    parts = match.groupdict()
    days = int(parts.get("days") or 0)
    hours = int(parts.get("hours") or 0)
    minutes = int(parts.get("minutes") or 0)
    seconds = float(parts.get("seconds") or 0)
    return int(days * 86400 + hours * 3600 + minutes * 60 + seconds)


def format_duration(seconds: Any) -> str:
    try:
        total = max(0, int(float(seconds or 0)))
    except (TypeError, ValueError):
        total = 0
    if total <= 0:
        return "—"
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def format_views(value: Any) -> str:
    count = _int(value)
    if count >= 1_000_000_000:
        return f"{count / 1_000_000_000:.1f}B views"
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M views"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K views"
    if count > 0:
        return f"{count:,} views"
    return "no views yet"


def human_age(value: Any) -> str:
    """Return a compact relative age for an ISO-8601 timestamp."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        published = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - published
    days = max(0, delta.days)
    if days == 0:
        hours = max(0, int(delta.total_seconds() // 3600))
        return "today" if hours < 1 else f"{hours}h ago"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    if days < 30:
        weeks = days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    if days < 365:
        months = max(1, days // 30)
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = max(1, days // 365)
    return f"{years} year{'s' if years != 1 else ''} ago"


# ---------------------------------------------------------------------------
# Response normalisation
# ---------------------------------------------------------------------------
def best_thumbnail(snippet: Dict[str, Any]) -> str:
    thumbs = (snippet or {}).get("thumbnails") or {}
    for key in _THUMB_KEYS:
        item = thumbs.get(key) or {}
        url = str(item.get("url") or "").strip()
        if url:
            return url
    return ""


def normalize_video(item: Dict[str, Any],
                    details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Merge a search item with its ``videos.list`` details."""
    snippet = dict(item.get("snippet") or {})
    # videos.list entries carry their own contentDetails/statistics, so they
    # can be normalized without a second payload.
    detail = details or item
    detail_snippet = dict(detail.get("snippet") or {})
    # videos.list is authoritative when both payloads provide a field.
    merged = {**snippet, **detail_snippet}
    video_id = str(item.get("id") or detail.get("id") or "").strip()
    if not video_id or "videoId" in video_id:
        video_id = str((item.get("id") or {}).get("videoId") or "").strip()
    content = detail.get("contentDetails") or {}
    stats = detail.get("statistics") or {}
    duration = duration_seconds(content.get("duration", ""))
    channel = (merged.get("channelTitle") or "").strip()
    return {
        "id": video_id,
        "title": (merged.get("title") or "Untitled video").strip(),
        "description": (merged.get("description") or "").strip(),
        "channel": channel,
        "channel_id": (merged.get("channelId") or "").strip(),
        "published_at": (merged.get("publishedAt") or "").strip(),
        "thumbnail": best_thumbnail(merged),
        "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
        "duration": duration,
        "duration_text": format_duration(duration),
        "views": _int(stats.get("viewCount")),
        "likes": _int(stats.get("likeCount")),
        "comments": _int(stats.get("commentCount")),
        "views_text": format_views(stats.get("viewCount")),
        "age_text": human_age(merged.get("publishedAt")),
        "live": (merged.get("liveBroadcastContent") or "none") != "none",
    }


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
def _cache_key(endpoint: str, params: Dict[str, Any]) -> str:
    clean = {k: str(v) for k, v in params.items() if k != "key"}
    raw = endpoint + "?" + urllib.parse.urlencode(sorted(clean.items()))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _read_cache(path: str, ttl_seconds: int) -> Optional[Dict[str, Any]]:
    if ttl_seconds <= 0:
        return None
    try:
        stat = os.stat(path)
        if (datetime.now().timestamp() - stat.st_mtime) > ttl_seconds:
            return None
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write_cache(path: str, data: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True, mode=0o700)
        fd, tmp = tempfile.mkstemp(
            prefix=".yt-", suffix=".json", dir=os.path.dirname(path))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError:
        # A read-only cache directory must not break Explore.
        pass


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class YouTubeClient:
    """Small, testable wrapper around the YouTube Data API v3."""

    def __init__(self, api_key: Optional[str] = None, *, timeout: int = 15,
                 cache_dir: Optional[str] = None, cache_minutes: Optional[int] = None,
                 now: Optional[float] = None):
        key = app_config.get_youtube_api_key() if api_key is None else api_key
        self.api_key = str(key or "").strip()
        self.timeout = max(3, int(timeout))
        self.cache_dir = cache_dir or CACHE_DIR
        if cache_minutes is None:
            cache_minutes = int(app_config.explore_config().get("cache_minutes") or 20)
        self.cache_seconds = max(0, int(cache_minutes)) * 60
        # `now` is unused at runtime; kept as a seam for deterministic tests.
        self._now = now

    # ---- public API -------------------------------------------------------
    def configured(self) -> bool:
        return bool(self.api_key)

    def trending(self, *, region_code: Optional[str] = None,
                 max_results: int = 12, category_id: Optional[str] = None,
                 refresh: bool = False) -> List[Dict[str, Any]]:
        cfg = app_config.explore_config()
        region = (region_code or app_config.youtube_config().get("region_code")
                  or "US").upper()
        category = str(category_id or cfg.get("trending_category") or "1")
        limit = max(1, min(50, int(max_results or 12)))
        data = self._get("videos", {
            "part": "snippet,contentDetails,statistics",
            "chart": "mostPopular",
            "regionCode": region,
            "videoCategoryId": category,
            "maxResults": limit,
        }, refresh=refresh)
        return [normalize_video(item) for item in data.get("items", [])
                if item.get("id")]

    def search(self, query: str, *, max_results: int = 18,
               order: str = "relevance", region_code: Optional[str] = None,
               refresh: bool = False,
               safe_search: Optional[str] = None) -> List[Dict[str, Any]]:
        text = str(query or "").strip()
        if not text:
            return []
        cfg = app_config.explore_config()
        yt = app_config.youtube_config()
        region = (region_code or yt.get("region_code") or "US").upper()
        limit = max(1, min(50, int(max_results or 18)))
        search_data = self._get("search", {
            "part": "snippet",
            "type": "video",
            "q": text,
            "maxResults": limit,
            "order": order or "relevance",
            "regionCode": region,
            "relevanceLanguage": yt.get("language") or "en",
            "safeSearch": safe_search or cfg.get("safe_search") or "moderate",
            "videoEmbeddable": "true",
        }, refresh=refresh)

        items = [item for item in search_data.get("items", [])
                 if (item.get("id") or {}).get("videoId")]
        ids = [str(item["id"]["videoId"]) for item in items]
        if not ids:
            return []
        detail_by_id = self.details(ids, refresh=refresh)
        return [normalize_video(item, detail_by_id.get(str(item["id"]["videoId"])))
                for item in items]

    def details(self, video_ids: List[str], *,
                refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        ids = [str(v).strip() for v in (video_ids or []) if str(v).strip()]
        if not ids:
            return {}
        # videos.list accepts at most 50 ids; Explore never requests more.
        data = self._get("videos", {
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(ids[:50]),
            "maxResults": min(50, len(ids)),
        }, refresh=refresh)
        return {str(item.get("id")): item for item in data.get("items", [])}

    def video(self, video_id: str, *, refresh: bool = False) -> Optional[Dict[str, Any]]:
        item = self.details([video_id], refresh=refresh).get(str(video_id))
        return normalize_video({"id": video_id}, item) if item else None

    def clear_cache(self) -> int:
        removed = 0
        try:
            for name in os.listdir(self.cache_dir):
                if name.startswith("search-") or name.startswith("videos-"):
                    try:
                        os.unlink(os.path.join(self.cache_dir, name))
                        removed += 1
                    except OSError:
                        pass
        except OSError:
            pass
        return removed

    # ---- transport --------------------------------------------------------
    def _get(self, endpoint: str, params: Dict[str, Any], *,
             refresh: bool = False) -> Dict[str, Any]:
        if not self.api_key:
            raise YouTubeNotConfigured(
                "No YouTube Data API key is configured.",
                details=(f"Add a YouTube Data API v3 key in "
                         f"{app_config.display_path()} or from Settings → "
                         "YouTube Data API."))
        clean = {k: str(v) for k, v in params.items() if v not in (None, "")}
        cache_name = f"{endpoint}-{_cache_key(endpoint, clean)}.json"
        cache_path = os.path.join(self.cache_dir, cache_name)
        if not refresh:
            cached = _read_cache(cache_path, self.cache_seconds)
            if cached is not None:
                return cached

        query = dict(clean)
        query["key"] = self.api_key
        url = f"{API_ROOT}/{endpoint}?" + urllib.parse.urlencode(query)
        request = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc) from None
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise YouTubeError(
                "YouTube could not be reached. Check your network connection.",
                details=f"{type(exc).__name__}: {reason}\nURL host: "
                        f"{urllib.parse.urlparse(API_ROOT).netloc}") from None
        except TimeoutError:
            raise YouTubeError(
                "The YouTube API request timed out.",
                details=f"No response after {self.timeout}s from "
                        f"{urllib.parse.urlparse(API_ROOT).netloc}.") from None

        try:
            data = json.loads(payload)
        except ValueError:
            raise YouTubeError(
                "YouTube returned an unreadable response.",
                details=f"Endpoint: {endpoint}\nBody starts: {payload[:300]!r}") from None
        if not isinstance(data, dict):
            raise YouTubeError(
                "YouTube returned an unexpected response.",
                details=f"Endpoint: {endpoint}\nBody type: {type(data).__name__}")
        _write_cache(cache_path, data)
        return data

    @staticmethod
    def _http_error(exc: urllib.error.HTTPError) -> YouTubeError:
        status = int(getattr(exc, "code", 0) or 0)
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        message = ""
        reasons: List[str] = []
        try:
            parsed = json.loads(body)
            error = parsed.get("error") or {}
            message = str(error.get("message") or "")
            for err in error.get("errors") or []:
                reason = str(err.get("reason") or "").strip()
                if reason:
                    reasons.append(reason)
        except (ValueError, AttributeError):
            pass
        reason = reasons[0] if reasons else ""
        lower = f"{message} {reason}".lower()
        if "quota" in lower:
            friendly = (
                "The YouTube API quota for this key is exhausted. Wait for the "
                "daily reset or use a different Google Cloud project.")
        elif "keyinvalid" in lower or "api key not valid" in lower or "bad request" in lower and "key" in lower:
            friendly = (
                "YouTube rejected the API key. Check that YouTube Data API v3 "
                "is enabled for the key's Google Cloud project.")
        elif status == 403:
            friendly = (
                "YouTube denied this request. The key may be restricted, or "
                "the API may not be enabled for the project.")
        elif status == 404:
            friendly = "YouTube could not find that resource."
        elif status >= 500:
            friendly = "YouTube is having trouble right now. Try again shortly."
        else:
            friendly = f"The YouTube API request failed (HTTP {status})."
        detail = (
            f"HTTP {status}\n"
            f"reason: {reason or 'unknown'}\n"
            f"message: {message or '(no message)'}\n"
            f"endpoint: {getattr(exc, 'url', '')}"
        )
        # Never include the query string: it contains the API key.
        detail = re.sub(r"\?[^\s]*", "?<redacted>", detail)
        return YouTubeError(friendly, status=status, reason=reason,
                            details=detail)


def discover(client: Optional[YouTubeClient] = None, *,
             refresh: bool = False) -> Dict[str, Any]:
    """Legacy two-rail discovery helper retained for diagnostics.

    The desktop Explore page no longer calls this; it opens the bundled Anime
    Box feed instead.  A failure in the 100-unit search still leaves the cheap
    trending rail usable, and total failure raises the first error.
    """
    client = client or YouTubeClient()
    cfg = app_config.explore_config()
    limit = int(cfg.get("result_limit") or 18)
    rails: List[Dict[str, Any]] = []
    errors: List[YouTubeError] = []

    try:
        trending = client.trending(max_results=min(12, limit), refresh=refresh)
        if trending:
            rails.append({
                "key": "trending",
                "title": "Trending in Animation",
                "caption": "Most popular right now on YouTube",
                "items": trending,
            })
    except YouTubeError as exc:
        errors.append(exc)

    try:
        curated = client.search(
            str(cfg.get("curated_query") or "donghua english sub"),
            max_results=limit,
            order=str(cfg.get("curated_order") or "viewCount"),
            refresh=refresh,
        )
        if curated:
            rails.append({
                "key": "curated",
                "title": "Donghua Discoveries",
                "caption": f"Curated search · {cfg.get('curated_query')}",
                "items": curated,
            })
    except YouTubeError as exc:
        errors.append(exc)

    if not rails and errors:
        raise errors[0]
    return {
        "rails": rails,
        "errors": [err.report() for err in errors],
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
