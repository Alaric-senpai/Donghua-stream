"""Source clients for AnimeCube and DonghuaStream.

The desktop Explore page treats every source the same way: ``search`` returns
series cards, ``details`` lists the episodes of one series, and ``resolve``
turns an episode page URL into a direct media URL that yt-dlp understands.

Both sites are ordinary public web pages; no DRM or paywall is bypassed.  The
AnimeCube API responses are AES-GCM encrypted with a per-request key, which is
implemented here with the ``cryptography`` package.  Responses are cached on
disk under ``~/.cache/donghua-stream/sources`` so repeated searches and page
visits do not hammer the sites.
"""
from __future__ import annotations

import base64
import hashlib
import html as html_lib
import json
import os
import re
import secrets
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import app_config
from media_ids import extract_video_id, is_animecube, is_donghuastream
from youtube_api import human_age

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
CACHE_DIR = os.path.join(
    os.path.expanduser("~"), ".cache", "donghua-stream", "sources")

ANIMECUBE_BASE = "https://animecube.live"
DONGHUASTREAM_BASE = "https://donghuastream.org"


class SourceError(RuntimeError):
    """A user-readable source/network failure with safe diagnostics."""

    def __init__(self, message: str, *, source: str = "",
                 details: str = ""):
        super().__init__(message)
        self.message = message
        self.source = source
        self.details = details or message

    def report(self) -> str:
        header = f"source: {self.source}" if self.source else ""
        return f"{header}\n\n{self.details}".strip()


# ---------------------------------------------------------------------------
# Small transport / cache helpers
# ---------------------------------------------------------------------------
def _cache_seconds() -> int:
    try:
        minutes = int(app_config.explore_config().get("cache_minutes") or 20)
    except Exception:
        minutes = 20
    return max(0, minutes) * 60


def _read_cache(path: str, ttl: int) -> Optional[Any]:
    if ttl <= 0:
        return None
    try:
        if (datetime.now().timestamp() - os.stat(path).st_mtime) > ttl:
            return None
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _write_cache(path: str, data: Any) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True, mode=0o700)
        fd, tmp = tempfile.mkstemp(
            prefix=".src-", suffix=".json", dir=os.path.dirname(path))
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
        # A read-only cache must never break Explore.
        pass


def _cached(namespace: str, key: str, loader: Callable[[], Any], *,
            ttl: Optional[int] = None, refresh: bool = False) -> Any:
    ttl = _cache_seconds() if ttl is None else ttl
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    path = os.path.join(CACHE_DIR, namespace, f"{digest}.json")
    if not refresh:
        cached = _read_cache(path, ttl)
        if cached is not None:
            return cached
    data = loader()
    _write_cache(path, data)
    return data


def _header(headers: Dict[str, str], name: str) -> str:
    lower = name.lower()
    for key, value in headers.items():
        if key.lower() == lower:
            return str(value)
    return ""


def _request(url: str, *, headers: Optional[Dict[str, str]] = None,
             timeout: int = 30) -> Tuple[bytes, Dict[str, str]]:
    merged = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    merged.update(headers or {})
    request = urllib.request.Request(url, headers=merged)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(), dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            body = ""
        raise SourceError(
            f"The site returned HTTP {exc.code}. It may be temporarily "
            "unavailable or blocking automated requests.",
            details=f"URL: {url}\nHTTP {exc.code}\n{body}") from None
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise SourceError(
            "The site could not be reached. Check your network connection.",
            details=f"URL: {url}\n{type(exc).__name__}: {reason}") from None
    except TimeoutError:
        raise SourceError(
            "The site took too long to respond.",
            details=f"URL: {url}\nNo response after {timeout}s.") from None


def _get_text(url: str, *, headers: Optional[Dict[str, str]] = None) -> str:
    body, _ = _request(url, headers=headers)
    return body.decode("utf-8", errors="replace")


def _strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _episode_number(value: Any, fallback_text: str = "") -> Optional[int]:
    number = _int(value)
    if number > 0:
        return number
    match = re.search(r"\d+", str(fallback_text or ""))
    return int(match.group(0)) if match else None


def _series_card(*, source: str, source_label: str, slug: str, title: str,
                 url: str, thumbnail: str, description: str = "",
                 season_title: str = "", latest_episode: str = "",
                 quality: str = "", episode_count: Optional[int] = None,
                 updated_at: str = "") -> Dict[str, Any]:
    meta = [bit for bit in (season_title, quality) if bit]
    if latest_episode:
        meta.append(f"Latest EP {latest_episode}")
    if episode_count:
        meta.append(f"{episode_count} episodes")
    duration_text = (
        f"EP {latest_episode}" if latest_episode
        else (f"{episode_count} EPS" if episode_count else "SERIES"))
    return {
        "id": slug,
        "title": title or "Untitled series",
        "description": description,
        "channel": source_label,
        "channel_id": source,
        "published_at": updated_at,
        "thumbnail": thumbnail,
        "url": url,
        "duration": 0,
        "duration_text": duration_text,
        "views": 0,
        "likes": 0,
        "comments": 0,
        "views_text": "  ·  ".join(meta),
        "age_text": human_age(updated_at),
        "live": False,
        "source": source,
        "kind": "series",
        "episode_count": episode_count,
    }


# ---------------------------------------------------------------------------
# AnimeCube
# ---------------------------------------------------------------------------
_NEXT_PUSH_RE = re.compile(
    r"self\.__next_f\.push\(\[1,(\"(?:[^\"\\]|\\.)*\")\]\)</script>", re.S)


def _rsc_text(page: str) -> str:
    """Join the React Server Component flight payload embedded in the HTML."""
    parts: List[str] = []
    for raw in _NEXT_PUSH_RE.findall(page or ""):
        try:
            parts.append(json.loads(raw))
        except ValueError:
            continue
    return "".join(parts)


def _json_after(text: str, marker: str) -> Any:
    index = text.find(marker)
    if index < 0:
        raise ValueError(f"marker not found: {marker}")
    start = index + len(marker)
    while start < len(text) and text[start].isspace():
        start += 1
    value, _ = json.JSONDecoder().raw_decode(text[start:])
    return value


def _find_anime_object(rsc: str) -> Dict[str, Any]:
    for match in re.finditer(r'"anime"\s*:\s*\{', rsc):
        start = match.end() - 1
        try:
            value, _ = json.JSONDecoder().raw_decode(rsc[start:])
        except ValueError:
            continue
        if (isinstance(value, dict) and value.get("slug")
                and ("primaryTabs" in value or "seasons" in value)):
            return value
    raise ValueError("anime payload not found in the RSC stream")


def _decrypt_payload(blob: str, key_material: str) -> Dict[str, Any]:
    """Decrypt an AnimeCube ``d`` payload (base64 IV + AES-GCM ciphertext)."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise SourceError(
            "AnimeCube playback needs the 'cryptography' package.",
            source="animecube",
            details=f"{type(exc).__name__}: {exc}") from None
    raw = base64.b64decode(str(blob or ""))
    if len(raw) <= 12:
        raise SourceError(
            "AnimeCube returned an invalid encrypted payload.",
            source="animecube")
    key = hashlib.sha256(key_material.encode("utf-8")).digest()
    plain = AESGCM(key).decrypt(raw[:12], raw[12:], None)
    return json.loads(plain.decode("utf-8"))


_QUALITY_RANK = {"4K": 5, "2K": 4, "1080p": 3, "720p": 2, "480p": 1}
_PLATFORM_RANK = {"dailymotion": 5, "youtube": 4, "vimeo": 3, "rumble": 2}


def _animecube_source_url(source: Dict[str, Any]) -> str:
    platform = str(source.get("platform") or "").strip().lower()
    # AnimeCube stores the playable Dailymotion identifier in ``privateId``
    # when the upload is unlisted; the public ``videoId`` is not playable.
    video = str(source.get("privateId") or source.get("videoId") or "").strip()
    if platform == "dailymotion" and video:
        return f"https://www.dailymotion.com/video/{video}"
    if platform == "youtube" and video:
        return f"https://www.youtube.com/watch?v={video}"
    if platform == "vimeo" and video:
        return f"https://vimeo.com/{video}"
    if platform == "rumble" and video:
        publisher = str(source.get("publisherId") or "").strip()
        return f"https://rumble.com/embed/{video}/" + (
            f"?pub={publisher}" if publisher else "")
    for key in ("url", "embedUrl", "embed_url", "src"):
        value = str(source.get(key) or "").strip()
        if value.startswith(("http://", "https://")):
            return value
    return ""


def _pick_source(sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    playable = []
    for source in sources or []:
        url = _animecube_source_url(source)
        if not url:
            continue
        platform = str(source.get("platform") or "").lower()
        quality = str(source.get("quality") or "")
        score = (
            _PLATFORM_RANK.get(platform, 1),
            _QUALITY_RANK.get(quality, 0),
            1 if source.get("goodSub") else 0,
        )
        playable.append((score, source, url))
    if not playable:
        raise SourceError(
            "AnimeCube did not return a playable source for this episode.",
            source="animecube")
    playable.sort(key=lambda item: item[0], reverse=True)
    best = dict(playable[0][1])
    best["url"] = playable[0][2]
    return best


class AnimeCubeSource:
    key = "animecube"
    label = "AnimeCube"
    home_url = ANIMECUBE_BASE + "/"

    # ---- search -----------------------------------------------------------
    def search(self, query: str, *, max_results: int = 18,
               refresh: bool = False) -> List[Dict[str, Any]]:
        text = str(query or "").strip().lower()
        if not text:
            return []
        catalog = self._catalog(refresh=refresh)
        tokens = [token for token in re.split(r"\s+", text) if token]
        scored: List[Tuple[int, Dict[str, Any]]] = []
        for item in catalog:
            title = str(item.get("title") or "").lower()
            slug = str(item.get("slug") or "").lower()
            aliases = " ".join(
                str(alias) for alias in item.get("aliases") or []).lower()
            genres = " ".join(
                str(genre) for genre in item.get("genres") or []).lower()
            haystack = " ".join((title, slug, aliases, genres))
            if tokens and not all(token in haystack for token in tokens):
                continue
            if text == title:
                score = 100
            elif title.startswith(text):
                score = 80
            elif text in title:
                score = 60
            elif text in slug:
                score = 50
            elif text in aliases:
                score = 40
            else:
                score = 10
            scored.append((score, item))
        scored.sort(key=lambda pair: (-pair[0],
                                      str(pair[1].get("title") or "").lower()))
        limit = max(1, int(max_results or 18))
        return [self._card(item) for _, item in scored[:limit]]

    def _card(self, item: Dict[str, Any]) -> Dict[str, Any]:
        slug = str(item.get("slug") or "").strip()
        return _series_card(
            source=self.key,
            source_label=self.label,
            slug=slug,
            title=str(item.get("title") or "").strip(),
            url=f"{ANIMECUBE_BASE}/anime/{urllib.parse.quote(slug)}",
            thumbnail=str(item.get("coverImage") or "").strip(),
            season_title=str(item.get("latestSeasonTitle") or "").strip(),
            latest_episode=str(item.get("latestEpisodeDisplay") or "").strip(),
            quality=str(item.get("latestQuality") or "").strip(),
            episode_count=None,
            updated_at=str(item.get("lastEpisodeAddedAt") or "").strip(),
        )

    def _catalog(self, *, refresh: bool = False) -> List[Dict[str, Any]]:
        def load() -> List[Dict[str, Any]]:
            page = _get_text(self.home_url)
            rsc = _rsc_text(page)
            try:
                catalog = _json_after(rsc, '"fallbackData":')
            except ValueError as exc:
                raise SourceError(
                    "AnimeCube's home page did not contain its catalog. The "
                    "site layout may have changed.",
                    source=self.key, details=str(exc)) from None
            if not isinstance(catalog, list):
                raise SourceError(
                    "AnimeCube returned an unexpected catalog payload.",
                    source=self.key)
            return [item for item in catalog
                    if isinstance(item, dict) and item.get("slug")
                    and item.get("title")]
        return _cached("animecube", "catalog", load, refresh=refresh)

    # ---- details ----------------------------------------------------------
    def _anime(self, slug: str, *, refresh: bool = False) -> Dict[str, Any]:
        slug = str(slug or "").strip()
        if not slug:
            raise SourceError("AnimeCube series URL has no slug.",
                              source=self.key)

        def load() -> Dict[str, Any]:
            url = f"{ANIMECUBE_BASE}/anime/{urllib.parse.quote(slug)}"
            page = _get_text(url)
            rsc = _rsc_text(page)
            try:
                return _find_anime_object(rsc)
            except ValueError as exc:
                raise SourceError(
                    "AnimeCube's series page did not contain episode data.",
                    source=self.key,
                    details=f"{url}\n{exc}") from None
        return _cached("animecube", f"anime:{slug}", load, refresh=refresh)

    @staticmethod
    def slug_from_url(url: str) -> str:
        text = str(url or "").strip()
        parsed = urllib.parse.urlparse(text)
        match = re.search(r"/anime/([^/?#]+)", parsed.path or text)
        if match:
            return urllib.parse.unquote(match.group(1)).strip("/")
        return text.strip("/").split("/")[-1]

    def details(self, url: str, *, refresh: bool = False) -> Dict[str, Any]:
        slug = self.slug_from_url(url)
        anime = self._anime(slug, refresh=refresh)
        episodes: List[Dict[str, Any]] = []
        seen = set()

        def add_episode(tab: Dict[str, Any], season: Dict[str, Any],
                        episode: Dict[str, Any]) -> None:
            episode_id = str(episode.get("id") or "").strip()
            season_id = str(season.get("id") or "").strip()
            if not episode_id or not season_id:
                return
            episode_url = (
                f"{ANIMECUBE_BASE}/anime/{urllib.parse.quote(slug)}"
                f"?season={urllib.parse.quote(season_id)}"
                f"&episode={urllib.parse.quote(episode_id)}")
            if episode_url in seen:
                return
            seen.add(episode_url)
            number = _episode_number(
                episode.get("number"), str(episode.get("numberDisplay") or ""))
            title = str(episode.get("title") or "").strip()
            if not title:
                display = str(episode.get("numberDisplay") or number or "")
                title = f"Episode {display}".strip()
            episodes.append({
                "id": episode_id,
                "url": episode_url,
                "title": title,
                "episode_number": number,
                "season_id": season_id,
                "primary_tab_id": str(tab.get("id") or ""),
                "season_title": str(
                    season.get("customName") or season.get("title") or ""),
            })

        tabs = anime.get("primaryTabs") or []
        if tabs:
            for tab in tabs:
                for season in tab.get("seasons") or []:
                    for episode in season.get("episodes") or []:
                        add_episode(tab, season, episode)
        else:
            for season in anime.get("seasons") or []:
                for episode in season.get("episodes") or []:
                    add_episode({}, season, episode)

        episodes.sort(key=lambda ep: (
            ep.get("episode_number") or 0, ep.get("id") or ""))

        title = str(anime.get("title") or slug).strip()
        return {
            "source": self.key,
            "kind": "series",
            "id": slug,
            "title": title,
            "description": str(anime.get("description") or "").strip(),
            "thumbnail": str(anime.get("coverImage") or "").strip(),
            "url": f"{ANIMECUBE_BASE}/anime/{urllib.parse.quote(slug)}",
            "channel": self.label,
            "channel_id": self.key,
            "genres": list(anime.get("genres") or []),
            "year": anime.get("year"),
            "episode_count": len(episodes),
            "episodes": episodes,
        }

    # ---- resolve ----------------------------------------------------------
    def _versions(self, *, refresh: bool = False) -> Dict[str, Any]:
        def load() -> Dict[str, Any]:
            obf = secrets.token_hex(16)
            body, headers = _request(
                f"{ANIMECUBE_BASE}/api/anime-sources-versions",
                headers={"Accept": "application/json", "X-Obf": obf})
            etag = _header(headers, "X-Registry-ETag") or _header(
                headers, "ETag")
            if not etag:
                raise SourceError(
                    "AnimeCube did not return a source registry version.",
                    source=self.key)
            try:
                payload = json.loads(body.decode("utf-8", errors="replace"))
                data = _decrypt_payload(payload["d"], f"{obf}|{etag}")
            except (ValueError, KeyError, TypeError) as exc:
                raise SourceError(
                    "AnimeCube returned an unreadable source registry.",
                    source=self.key, details=f"{type(exc).__name__}: {exc}") \
                    from None
            return data.get("bySeason") or {}
        # The registry changes whenever an episode is added, so keep it short.
        return _cached("animecube", "versions", load, ttl=180, refresh=refresh)

    @staticmethod
    def _primary_tab(anime: Dict[str, Any], season_id: str) -> str:
        for tab in anime.get("primaryTabs") or []:
            for season in tab.get("seasons") or []:
                if str(season.get("id") or "") == season_id:
                    return str(tab.get("id") or "")
        return ""

    @staticmethod
    def _episode_title(anime: Dict[str, Any], episode_id: str,
                       season_id: str) -> str:
        series_title = str(anime.get("title") or "").strip()
        for tab in anime.get("primaryTabs") or []:
            for season in tab.get("seasons") or []:
                if str(season.get("id") or "") != season_id:
                    continue
                for episode in season.get("episodes") or []:
                    if str(episode.get("id") or "") != episode_id:
                        continue
                    title = str(episode.get("title") or "").strip()
                    if title:
                        return f"{series_title} - {title}" if series_title else title
                    number = str(episode.get("numberDisplay")
                                 or episode.get("number") or "").strip()
                    title = f"Episode {number}".strip()
                    return f"{series_title} - {title}" if series_title else title
        return series_title or "AnimeCube episode"

    def resolve(self, url: str, *, refresh: bool = False) -> Dict[str, Any]:
        slug = self.slug_from_url(url)
        parsed = urllib.parse.urlparse(str(url or ""))
        query = urllib.parse.parse_qs(parsed.query)
        episode_id = str((query.get("episode") or [""])[0]).strip()
        season_id = str((query.get("season") or [""])[0]).strip()
        if not episode_id:
            raise SourceError(
                "AnimeCube episode URL is missing its episode identifier.",
                source=self.key, details=str(url))
        if not season_id:
            match = re.match(
                rf"^{re.escape(slug)}-(.+)-ep-[^-]+$", episode_id)
            if match:
                season_id = match.group(1)
        if not season_id:
            raise SourceError(
                "AnimeCube episode URL is missing its season identifier.",
                source=self.key, details=str(url))

        anime = self._anime(slug, refresh=refresh)
        tab_id = self._primary_tab(anime, season_id)
        if not tab_id:
            raise SourceError(
                "The season for this AnimeCube episode could not be found.",
                source=self.key, details=f"slug={slug} season={season_id}")

        versions = self._versions(refresh=refresh)
        version = (
            versions.get(slug, {}).get(tab_id, {}).get(season_id)
            if isinstance(versions, dict) else None)
        if not version:
            raise SourceError(
                "AnimeCube has not published a source version for this "
                "episode yet.",
                source=self.key,
                details=f"slug={slug}\ntab={tab_id}\nseason={season_id}")

        obf = secrets.token_hex(16)
        query_string = urllib.parse.urlencode({
            "v": version,
            "primaryTabId": tab_id,
            "seasonId": season_id,
        })
        api_url = (
            f"{ANIMECUBE_BASE}/api/anime/{urllib.parse.quote(slug)}"
            f"/episode/{urllib.parse.quote(episode_id)}/sources?"
            f"{query_string}")
        body, _ = _request(api_url, headers={
            "Accept": "application/json",
            "X-Obf": obf,
            "Referer": f"{ANIMECUBE_BASE}/anime/{urllib.parse.quote(slug)}",
        })
        try:
            payload = json.loads(body.decode("utf-8", errors="replace"))
            data = _decrypt_payload(payload["d"], f"{obf}|{version}")
        except (ValueError, KeyError, TypeError) as exc:
            raise SourceError(
                "AnimeCube returned unreadable episode sources.",
                source=self.key, details=f"{type(exc).__name__}: {exc}") \
                from None
        best = _pick_source(data.get("sources") or [])
        return {
            "url": best["url"],
            "title": self._episode_title(anime, episode_id, season_id),
            "source": self.key,
            "video_id": extract_video_id(url),
            "quality": str(best.get("quality") or ""),
            "platform": str(best.get("platform") or ""),
        }


# ---------------------------------------------------------------------------
# DonghuaStream
# ---------------------------------------------------------------------------
def _dhs_series_url(url: str) -> str:
    text = str(url or "").strip()
    parsed = urllib.parse.urlparse(text)
    match = re.search(r"/anime/([^/?#]+)", parsed.path or text)
    if match:
        return (f"{DONGHUASTREAM_BASE}/anime/"
                f"{urllib.parse.quote(match.group(1).strip('/'))}/")
    return text


def _dhs_episode_url(url: str) -> str:
    text = str(url or "").strip()
    parsed = urllib.parse.urlparse(text)
    path = parsed.path or text
    if not path.startswith("/"):
        path = "/" + path.lstrip("/")
    return DONGHUASTREAM_BASE + path


def _dailymotion_direct(url: str) -> str:
    parsed = urllib.parse.urlparse(str(url or ""))
    host = (parsed.hostname or "").lower()
    if host.endswith("dailymotion.com"):
        query = urllib.parse.parse_qs(parsed.query)
        video = str((query.get("video") or [""])[0]).strip()
        if video:
            return f"https://www.dailymotion.com/video/{video}"
        match = re.search(r"/(?:embed/)?video/([0-9A-Za-z]+)", parsed.path)
        if match:
            return f"https://www.dailymotion.com/video/{match.group(1)}"
    if host == "dai.ly":
        video = parsed.path.strip("/").split("/")[0]
        if video:
            return f"https://www.dailymotion.com/video/{video}"
    return ""


class DonghuaStreamSource:
    key = "donghuastream"
    label = "DonghuaStream"
    home_url = DONGHUASTREAM_BASE + "/"

    # ---- search -----------------------------------------------------------
    def search(self, query: str, *, max_results: int = 18,
               refresh: bool = False) -> List[Dict[str, Any]]:
        text = str(query or "").strip()
        if not text:
            return []
        url = f"{DONGHUASTREAM_BASE}/?s={urllib.parse.quote_plus(text)}"

        def load() -> List[Dict[str, Any]]:
            return self._parse_search(_get_text(url))

        results = _cached(
            "donghuastream", f"search:{text.lower()}", load, refresh=refresh)
        limit = max(1, int(max_results or 18))
        return list(results or [])[:limit]

    def _parse_search(self, page: str) -> List[Dict[str, Any]]:
        block = re.search(
            r'<div class="listupd">(.*?)</div>\s*</div>', page, re.S)
        body = block.group(1) if block else page
        cards: List[Dict[str, Any]] = []
        seen = set()
        for article in re.findall(
                r'<article class="bs".*?</article>', body, re.S):
            link = re.search(
                r'<a href="([^"]+)"[^>]*itemprop="url"[^>]*title="([^"]*)"',
                article, re.S)
            if not link:
                link = re.search(
                    r'<a href="([^"]+)"[^>]*class="tip"[^>]*title="([^"]*)"',
                    article, re.S)
            if not link:
                continue
            series_url = html_lib.unescape(link.group(1)).strip()
            if "/anime/" not in series_url or series_url in seen:
                continue
            seen.add(series_url)
            title = _strip_tags(link.group(2))
            title_match = re.search(
                r'<div class="tt">\s*(?:<a[^>]*>)?([^<]+)', article, re.S)
            if title_match:
                title = _strip_tags(title_match.group(1)) or title
            image = re.search(r'<img[^>]+src="([^"]+)"', article)
            slug = series_url.rstrip("/").split("/")[-1]
            cards.append(_series_card(
                source=self.key,
                source_label=self.label,
                slug=slug,
                title=title,
                url=series_url,
                thumbnail=html_lib.unescape(image.group(1)).strip()
                if image else "",
            ))
        return cards

    # ---- details ----------------------------------------------------------
    def details(self, url: str, *, refresh: bool = False) -> Dict[str, Any]:
        series_url = _dhs_series_url(url)

        def load() -> Dict[str, Any]:
            return self._parse_series(_get_text(series_url), series_url)

        return _cached(
            "donghuastream", f"series:{series_url}", load, refresh=refresh)

    def _parse_series(self, page: str, series_url: str) -> Dict[str, Any]:
        title_match = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
        title = _strip_tags(title_match.group(1)) if title_match else ""
        if not title:
            og_title = re.search(
                r'<meta property="og:title" content="([^"]+)"', page)
            title = _strip_tags(og_title.group(1)) if og_title else ""
        if not title:
            title = series_url.rstrip("/").split("/")[-1].replace("-", " ").title()

        image = re.search(
            r'<meta property="og:image" content="([^"]+)"', page)
        thumbnail = html_lib.unescape(image.group(1)).strip() if image else ""

        description = ""
        desc_match = re.search(
            r'<div class="entry-content"[^>]*>(.*?)</div>', page, re.S)
        if desc_match:
            description = _strip_tags(desc_match.group(1))
        if not description:
            meta = re.search(
                r'<meta name="description" content="([^"]+)"', page)
            description = _strip_tags(meta.group(1)) if meta else ""

        episodes: List[Dict[str, Any]] = []
        seen = set()
        start = page.find('class="eplister"')
        if start >= 0:
            end = page.find('<div class="bixbox">', start)
            chunk = page[start:end if end > start else len(page)]
            for link in re.finditer(
                    r'<a href="([^"]+)"[^>]*>(.*?)</a>', chunk, re.S):
                episode_url = html_lib.unescape(link.group(1)).strip()
                if "-episode-" not in episode_url or episode_url in seen:
                    continue
                inner = link.group(2)
                num_match = re.search(
                    r'<div class="epl-num">(.*?)</div>', inner, re.S)
                title_match = re.search(
                    r'<div class="epl-title">(.*?)</div>', inner, re.S)
                num_text = _strip_tags(num_match.group(1)) if num_match else ""
                number = _episode_number(None, num_text)
                if number is None:
                    url_match = re.search(
                        r"-episode-(\d+)-", episode_url, re.I)
                    number = int(url_match.group(1)) if url_match else None
                if number is None:
                    continue
                seen.add(episode_url)
                episode_title = _strip_tags(
                    title_match.group(1)) if title_match else ""
                if not episode_title:
                    episode_title = f"Episode {number}"
                episodes.append({
                    "id": episode_url,
                    "url": episode_url,
                    "title": episode_title,
                    "episode_number": number,
                })
        episodes.sort(key=lambda ep: (
            ep.get("episode_number") or 0, ep.get("url") or ""))

        slug = series_url.rstrip("/").split("/")[-1]
        return {
            "source": self.key,
            "kind": "series",
            "id": slug,
            "title": title,
            "description": description,
            "thumbnail": thumbnail,
            "url": series_url,
            "channel": self.label,
            "channel_id": self.key,
            "episode_count": len(episodes),
            "episodes": episodes,
        }

    # ---- resolve ----------------------------------------------------------
    def resolve(self, url: str, *, refresh: bool = False) -> Dict[str, Any]:
        episode_url = _dhs_episode_url(url)
        page = _get_text(episode_url)

        players: List[str] = []
        for tag in re.findall(r"<iframe[^>]*>", page, re.I | re.S):
            for attribute in ("data-litespeed-src", "data-src", "src"):
                match = re.search(
                    rf'{attribute}="([^"]+)"', tag, re.I)
                if not match:
                    continue
                value = html_lib.unescape(match.group(1)).strip()
                if value and value != "about:blank":
                    players.append(value)
                    break
        for tag in re.findall(r"<(?:video|source)[^>]*>", page, re.I | re.S):
            match = re.search(r'src="([^"]+)"', tag, re.I)
            if match:
                value = html_lib.unescape(match.group(1)).strip()
                if value and value != "about:blank":
                    players.append(value)

        if not players:
            raise SourceError(
                "DonghuaStream did not expose a playable video on this "
                "episode page.",
                source=self.key, details=episode_url)

        direct = ""
        for player in players:
            direct = _dailymotion_direct(player)
            if direct:
                break
        if not direct:
            for player in players:
                path = urllib.parse.urlparse(player).path.lower()
                if path.endswith((".mp4", ".m3u8", ".webm")):
                    direct = player
                    break
        if not direct:
            direct = players[0]

        title = ""
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
        if h1:
            title = _strip_tags(h1.group(1))
        if not title:
            page_title = re.search(r"<title>(.*?)</title>", page, re.S)
            if page_title:
                title = _strip_tags(page_title.group(1))
                title = re.split(r"\s+[|–-]\s+", title)[0].strip()

        return {
            "url": direct,
            "title": title or "DonghuaStream episode",
            "source": self.key,
            "video_id": extract_video_id(url),
            "quality": "",
            "platform": "dailymotion" if _dailymotion_direct(direct) else "",
        }


# ---------------------------------------------------------------------------
# Registry / public helpers
# ---------------------------------------------------------------------------
SOURCES: Dict[str, Any] = {
    AnimeCubeSource.key: AnimeCubeSource(),
    DonghuaStreamSource.key: DonghuaStreamSource(),
}

SOURCE_CHOICES: List[Tuple[str, str]] = [
    ("youtube", "YouTube"),
    (AnimeCubeSource.key, AnimeCubeSource.label),
    (DonghuaStreamSource.key, DonghuaStreamSource.label),
]


def get_source(key: str):
    """Return a source client by key, or ``None`` for YouTube/unknown keys."""
    return SOURCES.get(str(key or "").strip().lower())


def source_for_url(url: str) -> Optional[str]:
    if is_animecube(url):
        return AnimeCubeSource.key
    if is_donghuastream(url):
        return DonghuaStreamSource.key
    return None


def supports(url: str) -> bool:
    return source_for_url(url) is not None


def resolve_for_download(url: str) -> Optional[Dict[str, Any]]:
    """Resolve a supported episode page URL, or return ``None`` for others."""
    source = get_source(source_for_url(url) or "")
    if source is None:
        return None
    return source.resolve(url)
