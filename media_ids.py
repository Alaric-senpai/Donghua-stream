"""Stable media identifiers and yt-dlp archive tags for supported sources.

The downloader keeps its own ``downloaded.txt`` archive and PostgreSQL keeps a
``video_id`` per episode.  Both need one short, stable token per URL.  YouTube
IDs stay exactly as they always were (the bare 11-character ID) so existing
databases and archives keep working.  Every other supported site gets a short
prefixed hash of the canonical URL, which fits the ``VARCHAR(50)`` column and
is stable across runs.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

_YOUTUBE_RE = re.compile(
    r"(?:v=|youtu\.be/|/embed/|/v/|/shorts/|/live/)([0-9A-Za-z_-]{11})")
_DAILYMOTION_RE = re.compile(
    r"(?:dailymotion\.com/(?:video|embed/video)/|dai\.ly/)([0-9A-Za-z]+)")

ANIMECUBE_HOSTS = ("animecube.live", "www.animecube.live")
DONGHUASTREAM_HOSTS = ("donghuastream.org", "www.donghuastream.org")


def _host(url: str) -> str:
    try:
        return (urlparse(str(url or "").strip()).hostname or "").lower()
    except ValueError:
        return ""


def is_youtube(url: str) -> bool:
    host = _host(url)
    return host == "youtu.be" or host.endswith("youtube.com")


def is_animecube(url: str) -> bool:
    return _host(url) in ANIMECUBE_HOSTS


def is_donghuastream(url: str) -> bool:
    return _host(url) in DONGHUASTREAM_HOSTS


def is_dailymotion(url: str) -> bool:
    host = _host(url)
    return host == "dai.ly" or host.endswith("dailymotion.com")


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def extract_video_id(url: str) -> str:
    """Return a short stable ID for any URL used by the download pipeline.

    * YouTube keeps the historic bare 11-character ID.
    * AnimeCube and DonghuaStream episode URLs become ``ac-…`` / ``dhs-…``.
    * Dailymotion URLs become ``dm-<video id>``.
    * Any other HTTP(S) URL becomes ``web-<hash>`` instead of a URL that would
      overflow the database column.
    """
    text = str(url or "").strip()
    if not text:
        return ""
    if is_youtube(text):
        match = _YOUTUBE_RE.search(text)
        if match:
            return match.group(1)
    if is_animecube(text):
        return f"ac-{_digest(text)}"
    if is_donghuastream(text):
        return f"dhs-{_digest(text)}"
    if is_dailymotion(text):
        match = _DAILYMOTION_RE.search(text)
        if match:
            return f"dm-{match.group(1)}"
    if text.startswith(("http://", "https://")):
        return f"web-{_digest(text)}"
    return text


# ---------------------------------------------------------------------------
# Output-file helpers (shared by the downloader and the database scanner)
# ---------------------------------------------------------------------------
MEDIA_EXTENSIONS = (".mp4", ".mkv", ".webm", ".mov", ".m4v")

# yt-dlp writes throw-away files next to the real output while it works:
#   NAME.part / NAME.mp4.part-Frag12.part   (in-progress fragments)
#   NAME.temp.webm                          (a failed merge)
#   NAME.fhls-720.mp4 / NAME.f137.mp4       (separate audio/video streams)
# None of these is a finished episode, so the scanner must ignore them.
_INTERMEDIATE_MARKERS = (".part", ".ytdl", ".temp.")
_FORMAT_SUFFIX_RE = re.compile(r"\.f[a-z0-9_-]+$", re.IGNORECASE)


def is_intermediate_media_name(name: str) -> bool:
    """True when a file is a work-in-progress, not a finished episode."""
    text = str(name or "")
    if not text:
        return True
    lowered = text.lower()
    if any(marker in lowered for marker in _INTERMEDIATE_MARKERS):
        return True
    stem, _, ext = text.rpartition(".")
    if not stem:
        return True
    # "NAME.fhls-720.mp4" -> the format id marks it as a separate stream.
    if _FORMAT_SUFFIX_RE.search(stem):
        return True
    return False


def media_stem(name: str) -> str:
    """Return the file name without its media extension, normalised."""
    text = str(name or "")
    lowered = text.lower()
    for ext in MEDIA_EXTENSIONS:
        if lowered.endswith(ext):
            return text[: -len(ext)]
    return text


def normalize_stem(text: str) -> str:
    """Compare file names and episode titles without case or spacing noise."""
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


_UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_title(title: str, limit: int = 150) -> str:
    """Turn a page title into a single, portable filename component."""
    text = _UNSAFE_FILENAME.sub("-", str(title or ""))
    text = re.sub(r"\s+", " ", text).strip(" .")
    if len(text) > limit:
        text = text[:limit].rstrip(" .")
    return text


def archive_tag(url: str) -> str:
    """Return the extractor-style tag used on the archive line."""
    if is_youtube(url):
        return "youtube"
    if is_animecube(url):
        return "animecube"
    if is_donghuastream(url):
        return "donghuastream"
    if is_dailymotion(url):
        return "dailymotion"
    return "web"


def archive_tag_for_id(video_id: str) -> str:
    """Return the archive tag that belongs to a stored ``video_id``.

    Archive repair only has the ID column, not the original URL, so the
    source is recovered from the stable prefix.  Bare IDs are legacy YouTube
    entries and keep their historic ``youtube <id>`` line.
    """
    value = str(video_id or "").strip()
    if value.startswith("ac-"):
        return "animecube"
    if value.startswith("dhs-"):
        return "donghuastream"
    if value.startswith("dm-"):
        return "dailymotion"
    if value.startswith("web-"):
        return "web"
    return "youtube"


def archive_key(url: str) -> tuple[str, str]:
    """Return ``(tag, id)`` for writing a yt-dlp download-archive line."""
    return archive_tag(url), extract_video_id(url)
