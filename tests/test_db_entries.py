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
        self.rowcount = len(self._flags) or 1

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


class ArchiveSyncTests(unittest.TestCase):
    """Statuses follow the files on disk, never the other way round."""

    def _sync(self, save_dir, files, episodes, archive_lines=()):
        """Run sync_series_with_archive against a mocked series row."""
        cursor = FakeCursor([])
        connection = FakeConnection(cursor)
        with open(os.path.join(save_dir, "downloaded.txt"), "w",
                  encoding="utf-8") as handle:
            handle.write("\n".join(archive_lines))
        for name, size in files:
            with open(os.path.join(save_dir, name), "wb") as handle:
                handle.write(b"x" * size)

        with mock.patch.object(db, "get_series",
                               return_value={"id": 3, "save_dir": save_dir}), \
                mock.patch.object(db, "get_episodes",
                                  return_value=episodes), \
                mock.patch.object(db, "get_archive_downloaded_ids",
                                  return_value=set(archive_lines and
                                                   [l.split()[-1] for l in archive_lines])), \
                mock.patch.object(db, "get_connection",
                                  return_value=connection):
            changed = db.sync_series_with_archive(3)
        return changed, cursor.executed

    def test_repair_only_creates_the_archive_file(self):
        with tempfile.TemporaryDirectory() as save_dir:
            with mock.patch.object(db, "get_all_series",
                                   return_value=[{"id": 1, "save_dir": save_dir}]), \
                    mock.patch.object(db, "get_episodes", return_value=[
                        {"video_id": "dhs-abc", "status": "downloaded",
                         "title": "Some Episode 1"}]):
                db.repair_archives()

            with open(os.path.join(save_dir, "downloaded.txt"),
                      encoding="utf-8") as handle:
                content = handle.read()
        # A phantom "downloaded" DB row must NOT re-enter the archive.
        self.assertEqual(content, "")

    def test_finished_file_marks_episode_downloaded(self):
        with tempfile.TemporaryDirectory() as save_dir:
            changed, executed = self._sync(
                save_dir,
                files=[("Tales of herding gods Episode 104 Multiple "
                        "Subtitles.mp4", 200_000)],
                episodes=[{"video_id": "dhs-abc", "status": "pending",
                           "title": "Tales of herding gods Episode 104 "
                                    "Multiple Subtitles"}],
            )
        self.assertEqual(changed, 1)
        # One upgrade UPDATE, no downgrade.
        self.assertEqual(len(executed), 1)
        self.assertIn("status = 'downloaded'", executed[0][0])
        self.assertEqual(executed[0][1][1], ["dhs-abc"])

    def test_fragments_and_format_streams_are_not_evidence(self):
        with tempfile.TemporaryDirectory() as save_dir:
            changed, executed = self._sync(
                save_dir,
                files=[
                    ("Tales of herding gods Episode 105 Multiple "
                     "Subtitles.fhls-720.mp4", 200_000),
                    ("Tales of herding gods Episode 105 Multiple "
                     "Subtitles.fhls-720.mp4.part-Frag16.part", 200_000),
                    ("Tales of herding gods Episode 105 Multiple "
                     "Subtitles.temp.webm", 200_000),
                    ("tiny.mp4", 32),
                ],
                episodes=[{"video_id": "dhs-abc", "status": "downloaded",
                           "title": "Tales of herding gods Episode 105 "
                                    "Multiple Subtitles"}],
            )
        # No finished file -> the phantom "downloaded" row falls back to
        # pending so the download can actually restart.
        self.assertEqual(changed, 1)
        self.assertIn("status = 'pending'", executed[0][0])
        self.assertEqual(executed[0][1][1], ["dhs-abc"])

    def test_verified_archive_line_still_counts_as_evidence(self):
        with tempfile.TemporaryDirectory() as save_dir:
            changed, executed = self._sync(
                save_dir,
                files=[],  # legacy collection file deleted by the user
                episodes=[{"video_id": "ytid1234567", "status": "pending",
                           "title": "Old collection episode"}],
                archive_lines=["youtube ytid1234567"],
            )
        self.assertEqual(changed, 1)
        self.assertIn("status = 'downloaded'", executed[0][0])


if __name__ == "__main__":
    unittest.main()
