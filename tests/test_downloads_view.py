"""Offscreen checks that retry noise never looks like a final failure."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from gui.infrastructure.download_queue import DownloadManager
from gui.pages.downloads import DownloadsView, terminal_html


class DownloadsViewErrorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.manager = DownloadManager()
        self.view = DownloadsView(self.manager)

    def tearDown(self):
        self.view.deleteLater()
        self.manager.deleteLater()
        self.app.processEvents()

    def _retry(self):
        self.view.on_event("retry_error", {
            "url": "https://www.youtube.com/watch?v=abc12345678",
            "attempt": 1,
            "max_retries": 3,
            "error": "ERROR: [youtube] Sign in to confirm you're not a bot.",
            "delay": 2.0,
            "will_retry": True,
        })

    def _failure(self):
        self.view.on_event("failure", {
            "url": "https://www.youtube.com/watch?v=abc12345678",
            "error": "ERROR: [youtube] Sign in to confirm you're not a bot.",
        })

    def test_retry_error_does_not_show_the_failure_banner(self):
        self._retry()
        self.assertTrue(self.view.error_banner.isHidden())
        self.assertIn("Retrying 1/3", self.view.step_chip.text())
        self.assertIn("retrying", self.view.terminal.toPlainText().lower())

    def test_console_tags_are_colorized_and_escaped(self):
        html = terminal_html("[download] 42% <unsafe>")
        self.assertIn("color:#38bdf8", html)
        self.assertIn("&lt;unsafe&gt;", html)
        self.assertNotIn("<unsafe>", html)

    def test_first_stream_does_not_look_complete(self):
        self.view.on_event("progress", {
            "status": "stream_finished",
            "downloaded_bytes": 1000,
            "total_bytes": 1000,
            "formats_done": 1,
            "speed": 0,
            "eta": 0,
        })
        self.assertIn("Stream 1 saved", self.view.step_chip.text())
        self.assertLess(self.view.np_bar.value(), 100)

        self.view.on_event("postprocess", {
            "postprocessor": "Merger", "status": "started"})
        self.assertEqual(self.view.step_chip.text(), "Merging streams")

        self.view.on_event("postprocess", {
            "postprocessor": "MoveFiles", "status": "started"})
        self.assertEqual(self.view.step_chip.text(), "Finalizing")

    def test_exhausted_video_waits_for_the_run_summary_to_show_the_banner(self):
        self._retry()
        self._failure()
        self.assertTrue(self.view.error_banner.isHidden())

        self.view.on_event("summary", {
            "total": 1,
            "succeeded": [],
            "failed": [{
                "url": "https://www.youtube.com/watch?v=abc12345678",
                "error": "ERROR: [youtube] Sign in to confirm you're not a bot.",
            }],
            "skipped": [],
        })

        self.assertFalse(self.view.error_banner.isHidden())
        self.assertIn("1 episode(s) failed", self.view.error_title.text())
        self.assertIn("not a bot", self.view._last_error_details)


if __name__ == "__main__":
    unittest.main()
