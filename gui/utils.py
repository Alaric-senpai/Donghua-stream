"""Pure, UI-free helpers: formatting, paths, URL parsing, persisted settings."""
import os
import re
import shutil
from typing import Any, Dict, List, Optional

import db


def human_size(n: Optional[float]) -> str:
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        n = 0.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return (f"{n:.1f} {unit}" if unit not in ("B",) else f"{int(n)} {unit}")
        n /= 1024.0
    return f"{n:.1f} TB"


def speed_text(bps: Optional[float]) -> str:
    try:
        return f"{human_size(float(bps or 0))}/s"
    except (TypeError, ValueError):
        return "0 B/s"


def format_eta(seconds: Optional[float]) -> str:
    try:
        s = int(float(seconds or 0))
    except (TypeError, ValueError):
        s = 0
    if s <= 0:
        return "--:--"
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def disk_free(path: str) -> Optional[int]:
    try:
        return shutil.disk_usage(os.path.expanduser(path)).free
    except OSError:
        return None


def resolve_path(raw: str, base_dir: Optional[str] = None) -> str:
    p = os.path.expanduser(raw.strip())
    if base_dir and not os.path.isabs(p):
        p = os.path.join(os.path.expanduser(base_dir), p)
    return p


URL_RE = re.compile(r"https?://\S+")


def parse_bulk_urls(text: str) -> List[Dict[str, str]]:
    """Parse pasted text into episode entries.

    Accepts one URL per line, optionally `URL   # Episode title`.
    Lines starting with '#' or '//' are comments.
    Returns [{'url', 'title', 'vid', 'dup'}]; 'dup' == "1" when video id repeats.
    """
    items: List[Dict[str, str]] = []
    seen = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        m = re.match(r"^(.*?)(?:\s*#\s*(.+))?$", line)
        url = URL_RE.search(m.group(1))
        if not url:
            continue
        url = url.group(0).strip()
        title = (m.group(2) or "").strip()
        vid = db.extract_video_id(url)
        dup = vid in seen
        seen.add(vid)
        items.append({"url": url, "title": title, "vid": vid, "dup": "1" if dup else ""})
    return items


QUALITY_OPTIONS = [("480p", "480p (Fast)"), ("720p", "720p (HD)"),
                   ("1080p", "1080p (Full HD)"), ("2160p", "4K (2160p)"), ("best", "Best Available")]


CONTAINER_OPTIONS = [("mp4", "MP4  - max compatibility"),
                     ("mkv", "MKV  - best quality muxing"),
                     ("webm", "WebM  - open codecs")]


BROWSER_OPTIONS = [("brave", "Brave"), ("chrome", "Chrome"), ("chromium", "Chromium"),
                   ("firefox", "Firefox"), ("edge", "Edge"), ("opera", "Opera"),
                   ("vivaldi", "Vivaldi"), ("safari", "Safari"), ("none", "No cookies")]


def quality_label(q: Any) -> str:
    for val, lab in QUALITY_OPTIONS:
        if str(val) == str(q):
            return lab
    return f"{q}p"


def pct(part: int, whole: int) -> int:
    return int(round(100.0 * part / whole)) if whole else 0


def load_settings() -> Dict[str, str]:
    try:
        return db.get_all_settings()
    except Exception:
        return dict(db.DEFAULT_SETTINGS)


def set_setting(key: str, value: str) -> bool:
    try:
        return db.set_setting(key, str(value))
    except Exception:
        return False

