"""downloader.py - Core download engine for YouTube videos using yt-dlp.

Handles video quality resolution (360p to 1080p+), subtitle downloads,
archive tracking, retries with backoff, and progress reporting.
"""

import os
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any, Union
import yt_dlp
import sources
from media_ids import archive_tag_for_id, extract_video_id


# ==============================================================================
# Archive helpers
# ==============================================================================

_ARCHIVE_NAME = "downloaded.txt"
_DISABLED_BROWSERS = {"", "none", "no", "off", "disabled", "false"}


def normalize_browser(browser: Optional[str]) -> Optional[str]:
    """Turn the UI's "No cookies" sentinel into ``None`` for yt-dlp.

    Passing the literal string ``"none"`` to yt-dlp makes it raise
    ``ERROR: unsupported browser: "none"``, so every entry point funnels
    browser values through this helper.
    """
    value = str(browser or "").strip().lower()
    return None if value in _DISABLED_BROWSERS else value


def ensure_archive_file(save_dir: str) -> str:
    """Create the per-directory download archive even before the first save."""
    save_dir = os.path.expanduser(save_dir)
    os.makedirs(save_dir, exist_ok=True)
    archive_path = os.path.join(save_dir, _ARCHIVE_NAME)
    if not os.path.exists(archive_path):
        with open(archive_path, "a", encoding="utf-8"):
            pass
    return archive_path


def read_archive_ids(save_dir: str) -> set:
    """Read the archive as a set of video IDs (last token on each line)."""
    archive_path = os.path.join(os.path.expanduser(save_dir), _ARCHIVE_NAME)
    ids = set()
    if not os.path.exists(archive_path):
        return ids
    try:
        with open(archive_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.strip().split()
                if parts:
                    ids.add(parts[-1])
    except OSError:
        pass
    return ids


def add_archive_id(save_dir: str, video_id: str,
                   tag: Optional[str] = None) -> bool:
    """Append a video ID to ``downloaded.txt`` if it is not recorded yet."""
    video_id = (video_id or "").strip()
    # extract_video_id() returns the raw URL when it cannot find an ID.
    if not video_id or "://" in video_id or " " in video_id:
        return False
    archive_path = ensure_archive_file(save_dir)
    if video_id in read_archive_ids(save_dir):
        return False
    tag = tag or archive_tag_for_id(video_id)
    with open(archive_path, "a", encoding="utf-8") as f:
        f.write(f"{tag} {video_id}\n")
    return True


_UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_title(title: str, limit: int = 150) -> str:
    """Turn a page title into a single, portable filename component."""
    text = _UNSAFE_FILENAME.sub("-", str(title or ""))
    text = re.sub(r"\s+", " ", text).strip(" .")
    if len(text) > limit:
        text = text[:limit].rstrip(" .")
    return text


def output_template(save_dir: str, title: str = "") -> str:
    """Return a yt-dlp output template, optionally pinned to a page title."""
    directory = os.path.expanduser(save_dir)
    clean = safe_title(title)
    if not clean:
        return os.path.join(directory, "%(title)s.%(ext)s")
    # A literal percent sign would otherwise start a yt-dlp format field.
    clean = clean.replace("%", "%%")
    return os.path.join(directory, f"{clean}.%(ext)s")


def final_output_path(info: Any) -> str:
    """Return the final (post-merge) filepath from a yt-dlp info dict.

    ``download()`` discards the info dict, so the engine uses
    ``extract_info(download=True)`` and checks this path before declaring a
    video successful.  This prevents a partially merged multi-stream download
    from being recorded in the archive.
    """
    if not isinstance(info, dict):
        return ""
    if info.get("_type") in ("playlist", "multi_video"):
        for entry in info.get("entries") or []:
            path = final_output_path(entry)
            if path:
                return path
        return ""
    path = str(info.get("filepath") or info.get("_filename") or "").strip()
    if path:
        return path
    for download in reversed(info.get("requested_downloads") or []):
        if isinstance(download, dict):
            path = str(download.get("filepath") or "").strip()
            if path:
                return path
    return ""


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
        return _format_for_height(height), f"{height}p"

    q_str = str(quality).strip().lower()
    if q_str in ("best", "max", "highest", "auto", "none"):
        return "bestvideo+bestaudio/best", "Best Available"

    cleaned = q_str.rstrip("p")
    try:
        height = int(cleaned)
        return _format_for_height(height), f"{height}p"
    except ValueError:
        # Default fallback to 720p
        return _format_for_height(720), "720p (fallback)"


def _format_for_height(height: int) -> str:
    """Prefer the exact height, then the best stream at or below it.

    ``height<=720`` is deliberate: it caps the download at the selected
    quality and picks the highest available stream below that cap.  If the
    source has no 720p rendition, a lower one is used instead of failing.
    The final ``/best`` only runs when no capped format exists at all.
    """
    h = max(1, int(height))
    return (
        f"bestvideo[height={h}]+bestaudio/"
        f"bestvideo[height<={h}]+bestaudio/"
        f"best[height={h}]/"
        f"best[height<={h}]/"
        "best"
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
    vid = extract_video_id(url)
    return bool(vid) and vid in read_archive_ids(save_dir)


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
        # A retry budget below one would skip every attempt and report an
        # empty failure, so keep the loop meaningful for bad settings.
        self.max_retries = max(1, int(max_retries))
        self.browser = normalize_browser(browser)
        self.write_subs = write_subs
        self.on_event = on_event
        self.cancel_check = cancel_check
        self.ydl_logger = ydl_logger
        self.container = container
        self.sub_langs = sub_langs
        self.rate_limit = rate_limit
        self._format_downloaded: Dict[str, int] = {}
        self._format_total: Dict[str, int] = {}
        self._formats_finished: set = set()

    def _notify(self, event: str, **kwargs):
        if self.on_event:
            self.on_event(event, kwargs)

    # ---- multi-stream progress ------------------------------------------------
    def _reset_format_progress(self) -> None:
        self._format_downloaded = {}
        self._format_total = {}
        self._formats_finished = set()

    @staticmethod
    def _format_key(data: Dict[str, Any]) -> str:
        info = data.get("info_dict") or {}
        return str(info.get("format_id") or data.get("filename") or "")

    def _aggregate_progress(
        self, data: Dict[str, Any], downloaded: int, total: int
    ) -> tuple[int, int, int]:
        """Return (downloaded, total, streams_done) across all formats.

        yt-dlp strips ``requested_formats`` from the per-stream hook, so the
        engine cannot know the total stream count in advance.  It therefore
        treats each stream as partial and only reports completion after the
        whole ``extract_info`` call returns.
        """
        key = self._format_key(data)
        if key:
            self._format_downloaded[key] = max(0, int(downloaded))
            if total:
                self._format_total[key] = max(0, int(total))
        done = len(self._formats_finished)
        aggregate_downloaded = sum(self._format_downloaded.values())
        aggregate_total = sum(self._format_total.values())
        return (aggregate_downloaded, max(aggregate_total, aggregate_downloaded),
                done)

    def _emit_final_progress(self, filepath: str) -> None:
        """Emit the one true ``finished`` event after the merge is verified."""
        downloaded = sum(self._format_downloaded.values())
        total = max(downloaded, sum(self._format_total.values()))
        self._notify(
            "progress",
            filename=filepath,
            downloaded_bytes=downloaded,
            total_bytes=total,
            speed=0,
            eta=0,
            status="finished",
            formats_done=len(self._formats_finished),
        )

    def _progress_hook(self, d: Dict[str, Any]):
        """yt-dlp progress hook: forwards live telemetry and honours cancellation."""
        if self.cancel_check and self.cancel_check():
            raise yt_dlp.utils.DownloadCancelled("Download cancelled by user.")
        # Subtitle downloads use the same hook but are not part of the
        # video/audio stream count.
        filename = str(d.get("filename") or "")
        if os.path.splitext(filename)[1].lower() in {
                ".srt", ".vtt", ".ass", ".ssa", ".lrc", ".json3"}:
            return
        status = d.get("status")
        if status == "downloading":
            downloaded = int(d.get("downloaded_bytes") or 0)
            total = int(d.get("total_bytes") or d.get("total_bytes_estimate") or 0)
            agg_done, agg_total, done = self._aggregate_progress(
                d, downloaded, total)
            self._notify(
                "progress",
                filename=filename,
                downloaded_bytes=agg_done,
                total_bytes=agg_total,
                speed=d.get("speed") or 0,
                eta=d.get("eta") or 0,
                status="downloading",
                formats_done=done,
                current_format=str((d.get("info_dict") or {}).get("format_id") or ""),
            )
        elif status == "finished":
            downloaded = int(d.get("downloaded_bytes") or 0)
            total = int(d.get("total_bytes") or downloaded)
            key = self._format_key(d)
            if key:
                self._format_downloaded[key] = max(downloaded, total)
                self._formats_finished.add(key)
            agg_done, agg_total, done = self._aggregate_progress(
                d, max(downloaded, total), total)
            # A per-stream ``finished`` is only partial progress: yt-dlp may
            # still have to fetch another stream, and ffmpeg still has to
            # merge them.  The engine emits the single final ``finished``
            # after extract_info() returns and the merged file is verified.
            self._notify(
                "progress",
                filename=filename,
                downloaded_bytes=agg_done,
                total_bytes=agg_total,
                speed=0,
                eta=0,
                status="stream_finished",
                formats_done=done,
                current_format=str((d.get("info_dict") or {}).get("format_id") or ""),
            )

    def _postprocessor_hook(self, d: Dict[str, Any]):
        """Report ffmpeg merging/post-processing without marking the job done."""
        name = str(d.get("postprocessor") or "")
        status = str(d.get("status") or "")
        self._notify(
            "postprocess",
            postprocessor=name,
            status=status,
            filepath=str(d.get("filepath") or ""),
        )

    def _wait_for_retry(self, seconds: float) -> bool:
        """Cancellation-aware backoff; returns True when cancellation was requested."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.cancel_check and self.cancel_check():
                return True
            time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))
        return bool(self.cancel_check and self.cancel_check())

    def download_urls(
        self,
        urls: List[str],
        save_dir: str,
        quality: Optional[Union[str, int]] = None,
    ) -> DownloadSummary:
        """Download a list of video URLs into the target directory with configured quality."""
        save_dir = os.path.expanduser(save_dir)
        os.makedirs(save_dir, exist_ok=True)
        archive_file = ensure_archive_file(save_dir)
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
            "postprocessor_hooks": [self._postprocessor_hook],
            # Low-bandwidth connections are the main source of failures.
            # Let yt-dlp exhaust its own retries before the outer loop
            # treats an attempt as failed.
            "retries": 10,
            "fragment_retries": 10,
            "extractor_retries": 3,
            "file_access_retries": 3,
            "socket_timeout": 30,
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
                    self._notify("cancelled", url=clean_url,
                                 index=index, total=len(urls))
                    return summary
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
                    self._reset_format_progress()
                    attempt_opts = ydl_opts
                    media_url = clean_url
                    resolved = sources.resolve_for_download(clean_url)
                    if resolved:
                        media_url = resolved["url"]
                        attempt_opts = dict(ydl_opts)
                        # The archive must key off the stable source page URL,
                        # never the transient CDN/extractor ID that the site
                        # happens to embed today.
                        attempt_opts.pop("download_archive", None)
                        attempt_opts["outtmpl"] = output_template(
                            save_dir, resolved.get("title") or "")
                        self._notify(
                            "source",
                            url=clean_url,
                            resolved_url=media_url,
                            source=resolved.get("source") or "",
                            title=resolved.get("title") or "",
                            index=index,
                            total=len(urls),
                        )
                    with yt_dlp.YoutubeDL(params=attempt_opts) as ydl:
                        # extract_info() returns only after yt-dlp has
                        # downloaded every requested stream and run ffmpeg's
                        # merge postprocessor.  Keep the info dict so the
                        # final merged path can be verified below.
                        info = ydl.extract_info(media_url, download=True)

                    final_path = final_output_path(info)
                    if (not final_path or not os.path.isfile(final_path)
                            or os.path.getsize(final_path) <= 0):
                        raise RuntimeError(
                            "yt-dlp finished without a complete merged output "
                            f"file for {clean_url}"
                            + (f" (expected {final_path})" if final_path else ""))

                    # yt-dlp normally writes the archive itself, but a
                    # post-processing failure can leave a finished file
                    # unrecorded.  Always reconcile after a successful run.
                    self._emit_final_progress(final_path)
                    add_archive_id(save_dir, extract_video_id(clean_url))
                    self._notify("success", url=clean_url, index=index, total=len(urls))
                    summary.succeeded.append(clean_url)
                    success = True
                    break
                except yt_dlp.utils.DownloadCancelled:
                    self._notify("cancelled", url=clean_url, index=index, total=len(urls))
                    return summary
                except Exception as exc:
                    last_err = str(exc)
                    if self.cancel_check and self.cancel_check():
                        self._notify("cancelled", url=clean_url,
                                     index=index, total=len(urls))
                        return summary
                    # An exception from one attempt is not a final failure:
                    # yt-dlp may have already tried alternative clients and
                    # the outer retry loop is still going.  Only emit
                    # ``retry_error`` while another attempt will follow, and
                    # wait for the whole budget before reporting ``failure``.
                    if attempt >= self.max_retries:
                        break
                    backoff = min(30.0, 2.0 * attempt)
                    self._notify(
                        "retry_error",
                        url=clean_url,
                        attempt=attempt,
                        max_retries=self.max_retries,
                        error=last_err,
                        will_retry=True,
                        delay=backoff,
                    )
                    if self._wait_for_retry(backoff):
                        self._notify("cancelled", url=clean_url,
                                     index=index, total=len(urls))
                        return summary

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
