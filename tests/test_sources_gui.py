"""Offscreen tests for the source selector and series episode dialog."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from gui.dialogs.source_episodes import SourceEpisodesDialog


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


if __name__ == "__main__":
    unittest.main()
