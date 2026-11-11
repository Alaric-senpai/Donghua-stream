"""Offscreen tests for the source selector and series episode dialog."""
import os
import time
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

import sources
from gui.dialogs.source_episodes import SourceEpisodesDialog
from gui.infrastructure.thumbnails import ThumbnailStore
from gui.pages.explore import ExploreView


DETAILS = {
    "source": "animecube",
    "channel": "AnimeCube",
    "title": "Battle Through the Heavens",
    "year": 2025,
    "description": "Xiao Yan rises.",
    "url": "https://animecube.live/anime/battle-through-the-heavens",
    "episodes": [
        {"url": "https://animecube.live/anime/x?season=s&episode=e1",
         "title": "Episode 1", "episode_number": 1},
        {"url": "https://animecube.live/anime/x?season=s&episode=e2",
         "title": "Episode 2", "episode_number": 2},
    ],
}


class SourceDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_defaults_to_all_episodes_and_a_new_series(self):
        dialog = SourceEpisodesDialog(DETAILS, [], download_now=True)
        self.assertIsNone(dialog._target_id())
        self.assertEqual(len(dialog.selected_episodes()), 2)
        self.assertEqual(dialog.save_btn.text(), "Add & Download")
        payload = dialog.payload()
        self.assertIsNone(payload["series_id"])
        self.assertEqual(payload["new_name"], "Battle Through the Heavens")
        self.assertTrue(payload["download_now"])
        self.assertEqual(len(payload["episodes"]), 2)
        dialog.close()

    def test_latest_and_existing_series_targets(self):
        series = [{"id": 7, "name": "Existing", "downloaded_episodes": 1,
                   "total_episodes": 3}]
        dialog = SourceEpisodesDialog(DETAILS, series)
        self.assertEqual(dialog._target_id(), 7)
        self.assertFalse(dialog.new_name.isVisibleTo(dialog))

        dialog._latest_only()
        selected = dialog.selected_episodes()
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["episode_number"], 2)

        dialog._set_all(False)
        self.assertEqual(dialog.selected_episodes(), [])
        self.assertFalse(dialog.save_btn.isEnabled())

        dialog._set_all(True)
        self.assertTrue(dialog.save_btn.isEnabled())
        payload = dialog.payload()
        self.assertEqual(payload["series_id"], 7)
        self.assertEqual(payload["source"], "animecube")
        dialog.close()


class ExploreSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.thumbs = ThumbnailStore()
        self.thumb_patch = mock.patch.object(
            self.thumbs, "get_url", return_value=None)
        self.thumb_patch.start()
        self.addCleanup(self.thumb_patch.stop)

    def _wait(self, view: ExploreView, timeout: float = 5.0) -> None:
        deadline = time.time() + timeout
        while view._busy and time.time() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        for _ in range(20):
            self.app.processEvents()
            time.sleep(0.005)

    def test_switching_source_updates_the_idle_prompt(self):
        view = ExploreView(self.thumbs)
        self.addCleanup(view.shutdown)
        index = view.source_combo.findData("animecube")
        self.assertGreaterEqual(index, 0)
        with mock.patch(
                "gui.pages.explore.app_config.youtube_ready",
                return_value=False):
            view.source_combo.setCurrentIndex(index)

        self.assertEqual(view._source_key, "animecube")
        self.assertIn("ANIMECUBE", view.eyebrow_label.text())
        self.assertEqual(view.state_panel.title.text(), "Find a donghua series")
        self.assertTrue(view.key_btn.isHidden())
        self.assertEqual(view.api_chip.text(), "ANIMECUBE · PUBLIC")
        self.assertIn("public AnimeCube catalog", view.search_hint.text())

    def test_source_search_needs_no_youtube_key_and_renders_series(self):
        item = {
            "id": "battle-through-the-heavens",
            "title": "Battle Through the Heavens",
            "channel": "AnimeCube",
            "channel_id": "animecube",
            "source": "animecube",
            "kind": "series",
            "url": "https://animecube.live/anime/battle-through-the-heavens",
            "thumbnail": "",
            "duration_text": "EP 218",
            "views_text": "Season 5 · 4K",
            "age_text": "2 days ago",
            "description": "desc",
        }
        view = ExploreView(self.thumbs)
        self.addCleanup(view.shutdown)
        view.source_combo.setCurrentIndex(
            view.source_combo.findData("animecube"))

        with mock.patch(
                "gui.pages.explore.app_config.youtube_ready",
                return_value=False), mock.patch.object(
                    sources.SOURCES["animecube"], "search",
                    return_value=[item]) as search:
            view.search_for("battle")
            self._wait(view)

        search.assert_called_once()
        args, kwargs = search.call_args
        self.assertEqual(args[0], "battle")
        self.assertGreaterEqual(int(kwargs.get("max_results") or 0), 1)
        self.assertEqual(view._mode, "search")
        self.assertEqual(len(view._cards), 1)
        self.assertIn("ANIMECUBE", view.status_line.text())
        self.assertIn("1 series", view.section_caption.text())


if __name__ == "__main__":
    unittest.main()
