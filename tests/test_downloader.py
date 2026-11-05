"""Retry/error semantics and multi-stream progress for the download engine."""
import os
import tempfile
import unittest
from unittest import mock

import downloader

VIDEO_ID = "abc12345678"
VIDEO_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"


class FakeYoutubeDL:
    """Minimal stand-in for ``yt_dlp.YoutubeDL`` with scripted outcomes."""

    outcomes = []
    calls = []
    last_params = {}

    def __init__(self, params=None):
        self.params = dict(params or {})
        FakeYoutubeDL.last_params = self.params

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def extract_info(self, url, download=True):
        FakeYoutubeDL.calls.append((url, download))
        outcome = FakeYoutubeDL.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            return outcome(self)
        if outcome is None:
            return self.write_output()
        return outcome

    def output_dir(self):
        return os.path.dirname(self.params.get("outtmpl") or ".") or "."

    def write_output(self):
        path = os.path.join(self.output_dir(), "merged.webm")
        with open(path, "wb") as handle:
            handle.write(b"complete merged output")
        return {"filepath": path}


class VideoDownloaderRetryTests(unittest.TestCase):
    def setUp(self):
        FakeYoutubeDL.outcomes = []
        FakeYoutubeDL.calls = []
        FakeYoutubeDL.last_params = {}

    def _run(self, outcomes, max_retries=3):
        events = []

        def on_event(name, data):
            events.append((name, data))

        with tempfile.TemporaryDirectory() as save_dir, \
                mock.patch.object(downloader.yt_dlp, "YoutubeDL", FakeYoutubeDL), \
                mock.patch.object(downloader.VideoDownloader,
                                  "_wait_for_retry", return_value=False):
            FakeYoutubeDL.outcomes = list(outcomes)
            engine = downloader.VideoDownloader(
                max_retries=max_retries,
                write_subs=False,
                on_event=on_event,
            )
            summary = engine.download_urls([VIDEO_URL], save_dir)
        return events, summary

    @staticmethod
    def _named(events, name):
        return [data for event, data in events if event == name]

    def test_transient_error_is_retried_without_final_failure(self):
        events, summary = self._run([RuntimeError("network reset"), None])

        self.assertEqual([d["attempt"] for d in self._named(events, "attempt")],
                         [1, 2])
        retries = self._named(events, "retry_error")
        self.assertEqual(len(retries), 1)
        self.assertEqual(retries[0]["attempt"], 1)
        self.assertTrue(retries[0]["will_retry"])
        self.assertEqual(retries[0]["delay"], 2.0)
        self.assertEqual(len(self._named(events, "success")), 1)
        self.assertEqual(self._named(events, "failure"), [])
        self.assertEqual(summary.success_count, 1)
        self.assertEqual(summary.failed_count, 0)
        self.assertEqual(events[-1][0], "finish")

    def test_failure_is_reported_only_after_the_retry_budget(self):
        errors = [RuntimeError("timed out")] * 3
        events, summary = self._run(errors, max_retries=3)

        self.assertEqual([d["attempt"] for d in self._named(events, "attempt")],
                         [1, 2, 3])
        # The final attempt must not announce a retry that will never happen.
        self.assertEqual([d["attempt"] for d in self._named(events, "retry_error")],
                         [1, 2])
        failures = self._named(events, "failure")
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["error"], "timed out")
        self.assertEqual(summary.failed_count, 1)
        self.assertEqual(events[-2][0], "failure")
        self.assertEqual(events[-1][0], "finish")

    def test_cancelling_during_retry_does_not_report_failure(self):
        cancelled = {"value": False}

        def on_event(name, data):
            if name == "retry_error":
                cancelled["value"] = True

        with tempfile.TemporaryDirectory() as save_dir, \
                mock.patch.object(downloader.yt_dlp, "YoutubeDL", FakeYoutubeDL), \
                mock.patch.object(downloader.VideoDownloader,
                                  "_wait_for_retry", return_value=False):
            FakeYoutubeDL.outcomes = [RuntimeError("boom"), None]
            engine = downloader.VideoDownloader(
                max_retries=3,
                write_subs=False,
                on_event=on_event,
                cancel_check=lambda: cancelled["value"],
            )
            summary = engine.download_urls([VIDEO_URL], save_dir)

        self.assertEqual(summary.failed_count, 0)
        self.assertEqual(len(summary.succeeded), 0)
        # The cancellation path returns before the success attempt runs.
        self.assertEqual(len(FakeYoutubeDL.calls), 1)

    def test_ytdlp_gets_network_resilience_options(self):
        self._run([None])
        params = FakeYoutubeDL.last_params
        self.assertGreaterEqual(params["retries"], 10)
        self.assertGreaterEqual(params["fragment_retries"], 10)
        self.assertGreaterEqual(params["socket_timeout"], 30)
        self.assertTrue(params["postprocessor_hooks"])

    def test_missing_merged_file_is_not_recorded_as_success(self):
        def missing_output(ydl):
            return {"filepath": os.path.join(ydl.output_dir(), "missing.webm")}

        events, summary = self._run([missing_output, missing_output],
                                    max_retries=2)

        self.assertEqual(self._named(events, "success"), [])
        self.assertEqual(summary.success_count, 0)
        self.assertEqual(summary.failed_count, 1)
        self.assertIn("without a complete merged output",
                      self._named(events, "failure")[0]["error"])

    def test_first_stream_finished_is_not_reported_as_whole_download(self):
        def two_streams(ydl):
            hooks = ydl.params["progress_hooks"]
            requested = [
                {"format_id": "398", "filesize": 1000, "ext": "mp4"},
                {"format_id": "251", "filesize": 200, "ext": "webm"},
            ]
            video = {"format_id": "398", "requested_formats": requested}
            audio = {"format_id": "251", "requested_formats": requested}
            hooks[0]({
                "status": "downloading", "downloaded_bytes": 500,
                "total_bytes": 1000, "filename": "video.f398.mp4",
                "info_dict": video,
            })
            hooks[0]({
                "status": "finished", "downloaded_bytes": 1000,
                "total_bytes": 1000, "filename": "video.f398.mp4",
                "info_dict": video,
            })
            hooks[0]({
                "status": "downloading", "downloaded_bytes": 100,
                "total_bytes": 200, "filename": "audio.f251.webm",
                "info_dict": audio,
            })
            hooks[0]({
                "status": "finished", "downloaded_bytes": 200,
                "total_bytes": 200, "filename": "audio.f251.webm",
                "info_dict": audio,
            })
            return ydl.write_output()

        events, summary = self._run([two_streams])
        progress = self._named(events, "progress")

        self.assertEqual([p["status"] for p in progress],
                         ["downloading", "stream_finished", "downloading",
                          "finished"])
        first_done = progress[1]
        self.assertEqual(first_done["formats_done"], 1)
        self.assertEqual(first_done["formats_total"], 2)
        self.assertEqual(first_done["downloaded_bytes"], 1000)
        self.assertGreater(first_done["total_bytes"],
                           first_done["downloaded_bytes"])
        self.assertEqual(progress[2]["downloaded_bytes"], 1100)
        self.assertEqual(progress[-1]["downloaded_bytes"], 1200)
        self.assertEqual(progress[-1]["total_bytes"], 1200)
        self.assertEqual(summary.success_count, 1)

    def test_subtitle_progress_is_ignored_for_stream_counting(self):
        events = []

        def on_event(name, data):
            events.append((name, data))

        engine = downloader.VideoDownloader(
            max_retries=1, write_subs=False, on_event=on_event)
        engine._progress_hook({
            "status": "finished", "downloaded_bytes": 42, "total_bytes": 42,
            "filename": "video.en.srt",
            "info_dict": {"format_id": "srt"},
        })
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
