"""Offscreen checks that retry noise never looks like a final failure."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from gui.infrastructure.download_queue import DownloadManager, QuietYdlLogger
from gui.pages.downloads import DownloadsView, is_progress_line, terminal_html


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

    def test_progress_detection_ignores_destination_and_log_rows(self):
        self.assertTrue(is_progress_line(
            "[download]  10.0% of 10.00MiB at 1.00MiB/s ETA 00:09"))
        self.assertTrue(is_progress_line(
            "[download]  1.00MiB [00:01<00:02, 1.00MiB/s]"))
        self.assertFalse(is_progress_line(
            "[download] Destination: clip.mp4"))
        self.assertFalse(is_progress_line(
            "[download] clip.mp4 has already been downloaded"))

    def test_progress_lines_replace_the_previous_line(self):
        self.view.on_log_line(
            "[download]  10.0% of 10.00MiB at 1.00MiB/s ETA 00:09")
        self.view.on_log_line(
            "[download]  20.0% of 10.00MiB at 1.00MiB/s ETA 00:08")

        text = self.view.terminal.toPlainText()
        self.assertNotIn("10.0%", text)
        self.assertIn("20.0%", text)
        self.assertEqual(self.view.terminal.document().blockCount(), 1)

    def test_normal_line_after_progress_starts_a_new_line(self):
        self.view.on_log_line("[download]  10.0% of 10.00MiB")
        self.view.on_log_line("[download] Destination: clip.mp4")
        self.view.on_log_line("[download]  50.0% of 10.00MiB")

        text = self.view.terminal.toPlainText()
        self.assertIn("10.0%", text)
        self.assertIn("Destination: clip.mp4", text)
        self.assertIn("50.0%", text)
        self.assertEqual(self.view.terminal.document().blockCount(), 3)

    def test_retry_line_is_not_overwritten_by_later_progress(self):
        self._retry()
        self.view.on_log_line("[download]  10.0% of 10.00MiB")
        self.view.on_log_line("[download]  20.0% of 10.00MiB")

        text = self.view.terminal.toPlainText()
        self.assertIn("retrying", text.lower())
        self.assertIn("20.0%", text)

    def test_carriage_return_progress_updates_in_place(self):
        self.view.on_log_line(
            "[download] 1.0%\r[download] 2.0%\r[download] 3.0%")

        text = self.view.terminal.toPlainText()
        self.assertIn("3.0%", text)
        self.assertNotIn("1.0%", text)
        self.assertNotIn("2.0%", text)
        self.assertEqual(self.view.terminal.document().blockCount(), 1)

    def test_copy_console_copies_every_visible_line(self):
        self.view.on_log_line("[download] Destination: clip.mp4")
        self.view.on_log_line("[Merger] Merging formats into clip.mkv")
        QApplication.clipboard().setText("")

        self.view._copy_console()

        self.assertEqual(
            QApplication.clipboard().text(),
            self.view.terminal.toPlainText().strip())

    def test_console_expand_and_restore_toggle_the_other_panels(self):
        self.assertFalse(self.view.npcard.isHidden())

        self.view._toggle_console_expanded()

        self.assertTrue(self.view.npcard.isHidden())
        self.assertTrue(self.view.qcontrols.isHidden())
        self.assertTrue(self.view.qarea.isHidden())
        self.assertEqual(self.view.expand_btn.text(), "Restore")

        self.view._toggle_console_expanded()

        self.assertFalse(self.view.npcard.isHidden())
        self.assertFalse(self.view.qcontrols.isHidden())
        self.assertFalse(self.view.qarea.isHidden())
        self.assertEqual(self.view.expand_btn.text(), "Expand")

    def test_console_is_taller_and_resizable(self):
        self.assertGreaterEqual(self.view.terminal.minimumHeight(), 180)
        self.assertGreater(self.view.console_splitter.handleWidth(), 0)
        self.assertFalse(self.view.console_splitter.childrenCollapsible())

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


class QuietYdlLoggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_existing_tags_are_preserved_and_missing_tags_are_added(self):
        logger = QuietYdlLogger()
        lines = []
        logger.line.connect(lines.append)

        logger.debug("[download]  10.0% of 1.00MiB")
        logger.debug("[youtube] extracting metadata")
        logger.debug("Merging formats")
        logger.warning("slow server")
        logger.info("metadata ready")
        logger.error("boom")

        self.assertEqual(lines, [
            "[download]  10.0% of 1.00MiB",
            "[youtube] extracting metadata",
            "[download] Merging formats",
            "[warning] slow server",
            "[info] metadata ready",
            "[error] boom",
        ])


if __name__ == "__main__":
    unittest.main()
