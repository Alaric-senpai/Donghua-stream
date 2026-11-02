"""downloader.py - Core download engine for YouTube videos using yt-dlp.

Handles video quality resolution (360p to 1080p+), subtitle downloads,
archive tracking, retries with backoff, and progress reporting.
"""

import os
import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any, Union
import yt_dlp
from urls import extract_video_id


# ==============================================================================
# Quality Definitions
# ==============================================================================

QUALITY_PRESETS = {
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
    "best": None,
}

QUALITY_CHOICES = [
    {"name": "1080p  (Full HD - 1920x1080)", "value": "1080p"},
    {"name": "720p   (HD - 1280x720) [Recommended]", "value": "720p"},
    {"name": "480p   (Standard - 854x480)", "value": "480p"},
    {"name": "360p   (Low - 640x360)", "value": "360p"},
    {"name": "Best   (Maximum Available)", "value": "best"},
]


def resolve_format_string(quality: Union[str, int]) -> tuple[str, str]:
    """Convert user quality specification (e.g. '720p', 1080, 'best') into a yt-dlp format string.

    Returns:
        (format_string, display_label)
    """
    if isinstance(quality, int):
        height = quality
        return (
            f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best",
            f"{height}p",
        )

    q_str = str(quality).strip().lower()
    if q_str in ("best", "max", "highest", "auto", "none"):
        return "bestvideo+bestaudio/best", "Best Available"

    cleaned = q_str.rstrip("p")
    try:
        height = int(cleaned)
        return (
            f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best",
            f"{height}p",
        )
    except ValueError:
        # Default fallback to 720p
        return (
            "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "720p (fallback)",
        )


# ==============================================================================
# Download Result Data Structure
# ==============================================================================

@dataclass
class DownloadSummary:
    total: int = 0
    succeeded: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    failed: List[Dict[str, str]] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return len(self.succeeded)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    @property
    def failed_count(self) -> int:
        return len(self.failed)


# ==============================================================================
# Backward Compatibility Helpers
# ==============================================================================

def already_downloaded(save_dir: str, url: str) -> bool:
    """Check if a URL was already recorded in the download archive for save_dir."""
    archive_path = os.path.join(save_dir, "downloaded.txt")
    if not os.path.exists(archive_path):
        return False
    vid = extract_video_id(url)
    try:
        with open(archive_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if vid in line:
                    return True
    except Exception:
        pass
    return False


# ==============================================================================
# VideoDownloader Engine
# ==============================================================================

class VideoDownloader:
    """Core download manager using yt-dlp."""

    def __init__(
        self,
        quality: Union[str, int] = "720p",
        max_retries: int = 3,
        browser: Optional[str] = None,
        write_subs: bool = True,
        on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        ydl_logger: Any = None,
        container: str = "mp4",
        sub_langs: str = "en",
        rate_limit: Optional[float] = None,
    ):
        self.quality = quality
        self.max_retries = max_retries
        self.browser = browser
        self.write_subs = write_subs
        self.on_event = on_event
        self.cancel_check = cancel_check
        self.ydl_logger = ydl_logger
        self.container = container
        self.sub_langs = sub_langs
        self.rate_limit = rate_limit

    def _notify(self, event: str, **kwargs):
        if self.on_event:
            self.on_event(event, kwargs)

    def _progress_hook(self, d: Dict[str, Any]):
        """yt-dlp progress hook: forwards live telemetry and honours cancellation."""
        if self.cancel_check and self.cancel_check():
            raise yt_dlp.utils.DownloadCancelled("Download cancelled by user.")
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            self._notify(
                "progress",
                filename=d.get("filename", ""),
                downloaded_bytes=d.get("downloaded_bytes") or 0,
                total_bytes=total,
                speed=d.get("speed") or 0,
                eta=d.get("eta") or 0,
                status="downloading",
            )
        elif d.get("status") == "finished":
            self._notify(
                "progress",
                filename=d.get("filename", ""),
                downloaded_bytes=d.get("downloaded_bytes") or 0,
                total_bytes=d.get("total_bytes") or d.get("downloaded_bytes") or 0,
                speed=0,
                eta=0,
                status="finished",
            )

    def download_urls(
        self,
        urls: List[str],
        save_dir: str,
        quality: Optional[Union[str, int]] = None,
    ) -> DownloadSummary:
        """Download a list of video URLs into the target directory with configured quality."""
        os.makedirs(save_dir, exist_ok=True)
        archive_file = os.path.join(save_dir, "downloaded.txt")
        chosen_quality = quality if quality is not None else self.quality
        format_str, quality_label = resolve_format_string(chosen_quality)

        summary = DownloadSummary(total=len(urls))

        ydl_opts: Dict[str, Any] = {
            "outtmpl": os.path.join(save_dir, "%(title)s.%(ext)s"),
            "format": format_str,
            "merge_output_format": self.container if self.container in ("mp4", "mkv", "webm", "mov") else "mp4",
            "noplaylist": True,
            "download_archive": archive_file,
            "warn_when_outdated": False,
            "quiet": False,
            "no_warnings": False,
            "progress_hooks": [self._progress_hook],
        }

        if self.rate_limit is not None and self.rate_limit > 0:
            ydl_opts["ratelimit"] = self.rate_limit * 1024 * 1024  # MB/s -> bytes/s

        if self.ydl_logger is not None:
            # Route yt-dlp console output to a custom logger (used by the GUI)
            ydl_opts["logger"] = self.ydl_logger

        if self.write_subs:
            langs = [l.strip() for l in (self.sub_langs or "en").split(",") if l.strip()] or ["en"]
            ydl_opts.update({
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": langs,
                "subtitlesformat": "srt",
            })

        if self.browser:
            ydl_opts["cookiesfrombrowser"] = (self.browser,)

        self._notify(
            "start",
            total=len(urls),
            save_dir=save_dir,
            quality=quality_label,
            format_str=format_str,
        )

        for index, url in enumerate(urls, 1):
            if self.cancel_check and self.cancel_check():
                self._notify("cancelled")
                break

            clean_url = url.strip()
            if not clean_url or clean_url.startswith("#"):
                continue

            # Quick check if already recorded
            if already_downloaded(save_dir, clean_url):
                self._notify("skip", url=clean_url, index=index, total=len(urls))
                summary.skipped.append(clean_url)
                continue

            success = False
            last_err = ""

            for attempt in range(1, self.max_retries + 1):
                if self.cancel_check and self.cancel_check():
                    break
                self._notify(
                    "attempt",
                    url=clean_url,
                    attempt=attempt,
                    max_retries=self.max_retries,
                    index=index,
                    total=len(urls),
                    quality=quality_label,
                )

                try:
                    with yt_dlp.YoutubeDL(params=ydl_opts) as ydl:
                        ydl.download([clean_url])

                    self._notify("success", url=clean_url, index=index, total=len(urls))
                    summary.succeeded.append(clean_url)
                    success = True
                    break
                except yt_dlp.utils.DownloadCancelled:
                    self._notify("cancelled", url=clean_url, index=index, total=len(urls))
                    return summary
                except Exception as exc:
                    last_err = str(exc)
                    self._notify(
                        "retry_error",
                        url=clean_url,
                        attempt=attempt,
                        max_retries=self.max_retries,
                        error=last_err,
                    )
                    if attempt < self.max_retries and not (self.cancel_check and self.cancel_check()):
                        backoff = 2 * attempt
                        time.sleep(backoff)

            if not success:
                self._notify(
                    "failure",
                    url=clean_url,
                    index=index,
                    total=len(urls),
                    error=last_err,
                )
                summary.failed.append({"url": clean_url, "error": last_err})

        self._notify("finish", summary=summary)
        return summary


# ==============================================================================
# Convenience Functions (Drop-in compatibility)
# ==============================================================================

def download_urls(
    urls: List[str],
    save_dir: str,
    quality: Union[str, int] = "720p",
    max_retries: int = 3,
    browser: Optional[str] = None,
) -> DownloadSummary:
    """Drop-in functional replacement for script.py's original download_urls."""
    downloader = VideoDownloader(
        quality=quality,
        max_retries=max_retries,
        browser=browser,
    )
    return downloader.download_urls(urls, save_dir)
