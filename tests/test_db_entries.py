"""Bulk episode metadata inserts and source-aware archive repair."""
import os
import tempfile
import unittest
from unittest import mock

import db
import media_ids


class FakeCursor:
    def __init__(self, inserted_flags):
        self.executed = []
        self._flags = list(inserted_flags)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def fetchone(self):
        return (self._flags.pop(0),)


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True


class EpisodeEntryTests(unittest.TestCase):
    def test_bulk_insert_maps_urls_titles_and_numbers(self):
        url1 = "https://donghuastream.org/apotheosis-season-3-episode-1/"
        url2 = "https://donghuastream.org/apotheosis-season-3-episode-2/"
        cursor = FakeCursor([True, False])
        connection = FakeConnection(cursor)

        with mock.patch.object(db, "get_series",
                               return_value={"id": 4, "save_dir": "/tmp/x"}), \
                mock.patch.object(db, "get_archive_downloaded_ids",
                                  return_value=set()), \
                mock.patch.object(db, "get_connection",
                                  return_value=connection):
            stats = db.add_episode_entries(4, [
                {"url": url1, "title": "Episode 1", "episode_number": 1},
                {"url": url2, "title": "Episode 2", "episode_number": "2"},
                {"url": "", "title": "Ignored"},
            ])

        self.assertEqual(stats, {"added": 1, "updated": 1, "total": 3})
        self.assertTrue(connection.committed)
        self.assertEqual(len(cursor.executed), 2)
        sql, params = cursor.executed[0]
        self.assertIn("INSERT INTO episodes", sql)
        self.assertEqual(params, (
            4, media_ids.extract_video_id(url1), url1, "Episode 1", 1,
            "pending"))
        self.assertEqual(cursor.executed[1][1][4], 2)

    def test_bulk_insert_marks_archived_episodes_downloaded(self):
        url = "https://animecube.live/anime/x?season=s&episode=e"
        vid = media_ids.extract_video_id(url)
        cursor = FakeCursor([True])
        connection = FakeConnection(cursor)

        with mock.patch.object(db, "get_series",
                               return_value={"id": 1, "save_dir": "/tmp/x"}), \
                mock.patch.object(db, "get_archive_downloaded_ids",
                                  return_value={vid}), \
                mock.patch.object(db, "get_connection",
                                  return_value=connection):
            db.add_episode_entries(1, [{"url": url}])

        self.assertEqual(cursor.executed[0][1][-1], "downloaded")


class ArchiveRepairTests(unittest.TestCase):
    def test_repaired_archive_lines_keep_the_source_tag(self):
        with tempfile.TemporaryDirectory() as save_dir:
            added = db._append_archive_ids(
                save_dir, {"ac-abc", "dhs-def", "ytid1234567"})
            self.assertEqual(added, 3)
            with open(os.path.join(save_dir, "downloaded.txt"),
                      encoding="utf-8") as handle:
                lines = [line.strip() for line in handle if line.strip()]
        self.assertEqual(lines, [
            "animecube ac-abc",
            "donghuastream dhs-def",
            "youtube ytid1234567",
        ])


if __name__ == "__main__":
    unittest.main()
