"""Offscreen smoke tests for the Explore page (stdlib unittest)."""
import os
import time
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from gui.infrastructure.thumbnails import ThumbnailStore
from gui.components.poster_grid import PosterGrid
from gui.dialogs.add_video import AddVideoDialog
from gui.pages.explore import ExploreView
from PyQt6.QtWidgets import QWidget
import youtube_api


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

    def _wait(self, view: ExploreView, timeout: float = 5.0) -> None:
        deadline = time.time() + timeout
        while view._busy and time.time() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        for _ in range(20):
            self.app.processEvents()
            time.sleep(0.005)

    def test_missing_key_shows_onboarding(self):
        with mock.patch("gui.pages.explore.app_config.youtube_ready",
                        return_value=False):
            view = ExploreView(self.thumbs)
        self.assertEqual(view.state_panel.title.text(), "Connect YouTube")
        self.assertEqual(view.api_chip.text(), "API KEY NEEDED")
        view.shutdown()

    def test_discovery_renders_cards(self):
        data = {
            "rails": [{
                "key": "trending",
                "title": "Trending in Animation",
                "caption": "Popular",
                "items": [_video("a1", "One"), _video("b2", "Two")],
            }],
            "errors": [],
            "fetched_at": "now",
        }
        with mock.patch("gui.pages.explore.app_config.youtube_ready",
                        return_value=True), \
                mock.patch("gui.pages.explore.youtube_api.YouTubeClient",
                           return_value=object()), \
                mock.patch("gui.pages.explore.youtube_api.discover",
                           return_value=data):
            view = ExploreView(self.thumbs)
            view.refresh()
            self._wait(view)
        self.assertEqual(len(view._cards), 2)
        self.assertFalse(view.rails_host.isHidden())
        self.assertIn("YOUTUBE DATA API", view.status_line.text())
        view.shutdown()

    def test_api_error_shows_copyable_state(self):
        error = youtube_api.YouTubeError(
            "The YouTube API quota for this key is exhausted.",
            status=403, reason="quotaExceeded",
            details="HTTP 403\nreason: quotaExceeded")
        with mock.patch("gui.pages.explore.app_config.youtube_ready",
                        return_value=True), \
                mock.patch("gui.pages.explore.youtube_api.YouTubeClient",
                           return_value=object()), \
                mock.patch("gui.pages.explore.youtube_api.discover",
                           side_effect=error):
            view = ExploreView(self.thumbs)
            view.refresh()
            self._wait(view)
        self.assertEqual(view.state_panel.title.text(), "YouTube is not responding")
        self.assertIn("quota", view._last_error.lower())
        self.assertFalse(view.notice.isHidden())
        view.shutdown()

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
