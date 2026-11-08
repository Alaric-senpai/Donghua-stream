"""Offscreen smoke tests for the Explore page (stdlib unittest)."""
import os
import time
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget

import youtube_api
from gui.components.poster_grid import PosterGrid
from gui.dialogs.add_video import AddVideoDialog
from gui.infrastructure.thumbnails import ThumbnailStore
from gui.pages.explore import ExploreView


def _video(vid: str, title: str) -> dict:
    return {
        "id": vid,
        "title": title,
        "channel": "Studio",
        "thumbnail": "",
        "duration_text": "24:00",
        "views_text": "1.2M views",
        "age_text": "3 days ago",
        "url": f"https://www.youtube.com/watch?v={vid}",
        "description": "desc",
    }


class ExploreViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.thumbs = ThumbnailStore()
        self.thumb_patch = mock.patch.object(
            self.thumbs, "get_url", return_value=None)
        self.thumb_patch.start()

    def tearDown(self):
        self.thumb_patch.stop()

    def _wait(self, view: ExploreView, timeout: float = 5.0) -> None:
        deadline = time.time() + timeout
        while view._busy and time.time() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        for _ in range(20):
            self.app.processEvents()
            time.sleep(0.005)

    def _view(self, ready: bool = True) -> ExploreView:
        ready_patch = mock.patch(
            "gui.pages.explore.app_config.youtube_ready",
            return_value=ready)
        ready_patch.start()
        self.addCleanup(ready_patch.stop)
        view = ExploreView(self.thumbs)
        self.addCleanup(view.shutdown)
        return view

    def test_explore_starts_on_a_search_prompt_without_api_calls(self):
        with mock.patch(
                "gui.pages.explore.youtube_api.YouTubeClient",
                side_effect=AssertionError("must not search on load")):
            view = self._view(ready=True)

        self.assertEqual(view._mode, "idle")
        self.assertEqual(view._cards, [])
        self.assertFalse(view.state_panel.isHidden())
        self.assertEqual(view.state_panel.title.text(),
                         "Find something to watch")
        self.assertEqual(view.api_chip.text(), "SEARCH READY")
        self.assertIn("READY", view.status_line.text())

    def test_missing_key_prompts_for_a_key_without_api_calls(self):
        with mock.patch(
                "gui.pages.explore.youtube_api.YouTubeClient",
                side_effect=AssertionError("must not search without a key")):
            view = self._view(ready=False)
            self.assertEqual(view._mode, "idle")
            self.assertFalse(view.key_btn.isHidden())
            self.assertEqual(view.api_chip.text(), "API KEY REQUIRED")

            view.search_for("Soul Land")

            self.assertEqual(view._mode, "idle")
            self.assertIsNone(view._worker)
            self.assertEqual(view.state_panel.title.text(),
                             "Connect YouTube search")
            self.assertFalse(view.state_panel.isHidden())

    def test_saving_a_key_restores_the_search_prompt(self):
        view = self._view(ready=False)
        view.search_for("Soul Land")
        self.assertEqual(view.state_panel.title.text(),
                         "Connect YouTube search")

        with mock.patch(
                "gui.pages.explore.app_config.youtube_ready",
                return_value=True):
            view.reload_credentials()
            view.refresh()

        self.assertEqual(view._mode, "idle")
        self.assertEqual(view.state_panel.title.text(),
                         "Find something to watch")
        self.assertTrue(view.key_btn.isHidden())
        self.assertEqual(view.api_chip.text(), "SEARCH READY")

    def test_explicit_search_uses_youtube_client(self):
        client = mock.Mock()
        client.search.return_value = [
            _video("a1", "One"), _video("b2", "Two")]
        with mock.patch(
                "gui.pages.explore.youtube_api.YouTubeClient",
                return_value=client):
            view = self._view(ready=True)
            view.search_for("Battle Through the Heavens")
            self._wait(view)

        client.search.assert_called_once()
        args, kwargs = client.search.call_args
        self.assertEqual(args[0], "Battle Through the Heavens")
        self.assertGreaterEqual(int(kwargs.get("max_results") or 0), 1)
        self.assertEqual(view._mode, "search")
        self.assertEqual(len(view._cards), 2)
        self.assertEqual(view.api_chip.text(), "100 API UNITS")
        self.assertIn("100 API UNITS", view.status_line.text())

    def test_search_error_shows_copyable_state(self):
        error = youtube_api.YouTubeError(
            "The YouTube API quota for this key is exhausted.",
            status=403, reason="quotaExceeded",
            details="HTTP 403\nreason: quotaExceeded")
        client = mock.Mock()
        client.search.side_effect = error
        with mock.patch(
                "gui.pages.explore.youtube_api.YouTubeClient",
                return_value=client):
            view = self._view(ready=True)
            view.search_for("donghua")
            self._wait(view)

        self.assertEqual(view.state_panel.title.text(),
                         "YouTube is not responding")
        self.assertIn("quota", view._last_error.lower())
        self.assertFalse(view.notice.isHidden())

    def test_no_results_shows_a_clear_search_state(self):
        client = mock.Mock()
        client.search.return_value = []
        with mock.patch(
                "gui.pages.explore.youtube_api.YouTubeClient",
                return_value=client):
            view = self._view(ready=True)
            view.search_for("nothing matches this")
            self._wait(view)

        self.assertEqual(view._mode, "search")
        self.assertEqual(view.state_panel.title.text(), "No videos found")
        self.assertFalse(view.state_panel.isHidden())
        self.assertTrue(view.grid.isHidden())

    def test_clear_search_returns_to_the_prompt(self):
        client = mock.Mock()
        client.search.return_value = [_video("a1", "One")]
        with mock.patch(
                "gui.pages.explore.youtube_api.YouTubeClient",
                return_value=client):
            view = self._view(ready=True)
            view.search_for("One")
            self._wait(view)
            self.assertEqual(len(view._cards), 1)

            view._clear_search()

        self.assertEqual(view._mode, "idle")
        self.assertEqual(view._cards, [])
        self.assertEqual(view.search_input.text(), "")
        self.assertEqual(view.state_panel.title.text(),
                         "Find something to watch")
        self.assertFalse(view.state_panel.isHidden())

    def test_add_video_dialog_starts_on_new_series(self):
        dialog = AddVideoDialog(_video("a1", "One"), [])
        self.assertIsNone(dialog._target_id())
        self.assertTrue(dialog.new_name.isVisibleTo(dialog))
        self.assertEqual(dialog.save_btn.text(), "Add to Library")
        payload = dialog.payload()
        self.assertIsNone(payload["series_id"])
        self.assertTrue(payload["new_name"])
        dialog.close()

    def test_add_video_dialog_targets_existing_series(self):
        series = [{"id": 7, "name": "Existing", "downloaded_episodes": 1,
                   "total_episodes": 3}]
        dialog = AddVideoDialog(_video("a1", "One"), series, download_now=True)
        self.assertEqual(dialog._target_id(), 7)
        self.assertFalse(dialog.new_name.isVisibleTo(dialog))
        self.assertEqual(dialog.save_btn.text(), "Add & Download")
        payload = dialog.payload()
        self.assertEqual(payload["series_id"], 7)
        self.assertTrue(payload["download_now"])
        self.assertEqual(payload["url"], "https://www.youtube.com/watch?v=a1")
        dialog.close()

    def test_poster_grid_keeps_fixed_card_width(self):
        grid = PosterGrid()
        cards = []
        for _ in range(2):
            card = QWidget()
            card.setFixedSize(296, 274)
            cards.append(card)
        grid.set_items(cards)
        grid.resize(900, 400)
        self.app.processEvents()
        self.assertEqual(cards[0].width(), 296)
        self.assertEqual(cards[1].width(), 296)
        self.assertGreaterEqual(cards[1].x(), cards[0].x() + 296)
        grid.deleteLater()


if __name__ == "__main__":
    unittest.main()
