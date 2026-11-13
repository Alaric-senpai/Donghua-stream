"""Offscreen tests for the per-source Explore screens and show details."""
import os
import time
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

import sources
from gui.infrastructure.thumbnails import ThumbnailStore
from gui.pages.explore_host import ExploreHost
from gui.pages.source_detail import SourceDetailView
from gui.pages.source_explore import SourceExploreView

CATALOG = [
    {"slug": "alpha", "title": "Alpha", "genres": ["Action"],
     "coverImage": "https://img.example/alpha.jpg", "rating": 9.7,
     "latestSeasonTitle": "Season 1", "latestEpisodeDisplay": "12",
     "latestQuality": "4K", "lastEpisodeAddedAt": "2026-11-01T00:00:00Z"},
    {"slug": "beta", "title": "Beta", "genres": ["Fantasy"],
     "coverImage": "https://img.example/beta.jpg", "rating": 9.2,
     "latestSeasonTitle": "Season 2", "latestEpisodeDisplay": "5",
     "latestQuality": "1080p", "lastEpisodeAddedAt": "2026-10-01T00:00:00Z"},
]

DETAILS = {
    "source": "animecube",
    "kind": "series",
    "id": "alpha",
    "title": "Alpha",
    "description": "A story about alpha.",
    "thumbnail": "https://img.example/alpha.jpg",
    "url": "https://animecube.live/anime/alpha",
    "channel": "AnimeCube",
    "channel_id": "animecube",
    "genres": ["Action", "Adventure"],
    "year": 2026,
    "episode_count": 2,
    "episodes": [
        {"id": "alpha-ep-1", "url": "https://animecube.live/anime/alpha"
         "?season=s1&episode=alpha-ep-1",
         "title": "Episode 1", "episode_number": 1},
        {"id": "alpha-ep-2", "url": "https://animecube.live/anime/alpha"
         "?season=s1&episode=alpha-ep-2",
         "title": "Episode 2", "episode_number": 2},
    ],
    "recommendations": [
        {"id": "beta", "title": "Beta", "source": "animecube",
         "channel": "AnimeCube", "url": "https://animecube.live/anime/beta",
         "thumbnail": "https://img.example/beta.jpg", "episode_count": 5},
    ],
}


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.thumbs = ThumbnailStore()
        patch = mock.patch.object(self.thumbs, "get_url", return_value=None)
        patch.start()
        self.addCleanup(patch.stop)

    def _wait(self, view, timeout: float = 5.0) -> None:
        deadline = time.time() + timeout
        while view._busy and time.time() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        for _ in range(20):
            self.app.processEvents()
            time.sleep(0.005)


class SourceExploreTests(_Base):
    def test_trending_grid_is_shown_by_default(self):
        view = SourceExploreView("animecube", self.thumbs)
        self.addCleanup(view.shutdown)
        with mock.patch.object(
                sources.SOURCES["animecube"], "_catalog",
                return_value=CATALOG):
            view.ensure_loaded()
            self._wait(view)

        self.assertEqual(view._mode, "trending")
        self.assertEqual(len(view._cards), 2)
        self.assertEqual(view.section_title.text(), "Trending Series")
        self.assertIn("ANIMECUBE", view.eyebrow_label.text())

    def test_search_replaces_the_grid_with_results(self):
        view = SourceExploreView("animecube", self.thumbs)
        self.addCleanup(view.shutdown)
        card = {
            "id": "alpha", "title": "Alpha", "source": "animecube",
            "kind": "series", "url": "https://animecube.live/anime/alpha",
            "thumbnail": "", "episode_count": 12,
        }
        with mock.patch.object(
                sources.SOURCES["animecube"], "search",
                return_value=[card]) as search:
            view.search_input.setText("alpha")
            view._submit_search()
            self._wait(view)

        search.assert_called_once()
        self.assertEqual(view._mode, "search")
        self.assertEqual(len(view._cards), 1)
        self.assertIn("alpha", view.section_title.text())

    def test_clicking_a_card_emits_series_selected(self):
        view = SourceExploreView("animecube", self.thumbs)
        self.addCleanup(view.shutdown)
        received = []
        view.series_selected.connect(
            lambda key, data: received.append((key, data)))
        with mock.patch.object(
                sources.SOURCES["animecube"], "_catalog",
                return_value=CATALOG):
            view.ensure_loaded()
            self._wait(view)

        view._cards[0].selected.emit(dict(CATALOG[0]))
        self.assertTrue(received)
        self.assertEqual(received[0][0], "animecube")
        self.assertEqual(received[0][1]["title"], "Alpha")


class SourceDetailTests(_Base):
    def _load(self, view):
        with mock.patch.object(
                sources.SOURCES["animecube"], "details",
                return_value=DETAILS) as details, mock.patch(
                    "gui.pages.source_detail.db.get_episodes_by_ids",
                    return_value=[]):
            view.load("animecube", "https://animecube.live/anime/alpha")
            self._wait(view)
        return details

    def test_details_page_lists_episodes_and_recommendations(self):
        view = SourceDetailView(self.thumbs)
        self.addCleanup(view.shutdown)
        self._load(view)

        self.assertEqual(view.title.text(), "Alpha")
        self.assertEqual(view.chip_eps.text(), "2 EPS")
        self.assertEqual(len(view.rows_host.items), 2)
        self.assertIn("RECOMMENDED", view.rec_eyebrow.text())
        self.assertEqual(view.rec_layout.count(), 2)  # one tile + stretch

    def test_episode_selection_helpers(self):
        view = SourceDetailView(self.thumbs)
        self.addCleanup(view.shutdown)
        self._load(view)

        self.assertEqual(len(view._selected_episodes()), 2)
        view._check_latest()
        self.assertEqual(len(view._selected_episodes()), 1)
        view._check_none()
        self.assertEqual(view._selected_episodes(), [])
        view._check_all()
        self.assertEqual(len(view._selected_episodes()), 2)

    def test_add_button_offers_existing_and_new_series(self):
        view = SourceDetailView(self.thumbs)
        self.addCleanup(view.shutdown)
        self._load(view)

        labels = [action.text() for action in view.add_menu.actions()]
        self.assertEqual(len(labels), 2)
        self.assertIn("existing", labels[0].lower())
        self.assertIn("new", labels[1].lower())

        seen = []

        def _capture(details, series_list, download_now=False,
                     target_mode="any", parent=None):
            seen.append(target_mode)
            return None

        with mock.patch("gui.pages.source_detail.prompt_source_episodes",
                        side_effect=_capture):
            view._add_series("existing")
            view._add_series("new")

        self.assertEqual(seen, ["existing", "new"])

    def test_saving_emits_a_library_refresh(self):
        view = SourceDetailView(self.thumbs)
        self.addCleanup(view.shutdown)
        self._load(view)

        changed = []
        view.library_changed.connect(lambda sid: changed.append(sid))

        payload = {
            "series_id": 31, "new_name": "", "download_now": False,
            "episodes": DETAILS["episodes"], "source": "animecube",
            "source_url": DETAILS["url"], "title": DETAILS["title"],
        }
        with mock.patch(
                "gui.pages.source_detail.prompt_source_episodes",
                return_value=payload), mock.patch(
                    "gui.pages.source_detail.db.add_episode_entries",
                    return_value={"added": 2, "updated": 0, "total": 2}):
            view._add_series("existing")

        self.assertEqual(changed, [31])

    def test_adding_the_series_saves_entries_and_can_queue_downloads(self):
        view = SourceDetailView(self.thumbs)
        self.addCleanup(view.shutdown)
        self._load(view)

        queued = []
        view.download_requested.connect(
            lambda sid, urls: queued.append((sid, urls)))
        toasts = []
        view.toast.connect(lambda msg, ok: toasts.append((msg, ok)))

        payload = {
            "series_id": 12,
            "new_name": "",
            "download_now": True,
            "episodes": DETAILS["episodes"],
            "source": "animecube",
            "source_url": DETAILS["url"],
            "title": DETAILS["title"],
        }
        with mock.patch(
                "gui.pages.source_detail.prompt_source_episodes",
                return_value=payload), mock.patch(
                    "gui.pages.source_detail.db.add_episode_entries",
                    return_value={"added": 2, "updated": 0, "total": 2}):
            view._add_series("existing")

        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0][0], 12)
        self.assertEqual(len(queued[0][1]), 2)
        self.assertTrue(toasts)


class ExploreHostTests(_Base):
    def test_each_source_has_its_own_screen(self):
        host = ExploreHost(self.thumbs)
        self.addCleanup(host.shutdown)

        self.assertIn("animecube", host.source_views)
        self.assertIn("donghuastream", host.source_views)
        self.assertIs(host.stack.currentWidget(), host.youtube_view)

        host.select("animecube")
        self.assertIs(host.stack.currentWidget(),
                      host.source_views["animecube"])
        self.assertEqual(host.current_key, "animecube")
        self.assertTrue(host.tab_buttons["animecube"].isChecked())

        host.select("donghuastream")
        self.assertIs(host.stack.currentWidget(),
                      host.source_views["donghuastream"])
        self.assertFalse(host.tab_buttons["animecube"].isChecked())


if __name__ == "__main__":
    unittest.main()
