"""Stable media IDs and archive tags for every supported source."""
import unittest

import media_ids


class MediaIdTests(unittest.TestCase):
    def test_youtube_keeps_the_historic_bare_id(self):
        cases = [
            "https://www.youtube.com/watch?v=abc12345678",
            "https://youtu.be/abc12345678",
            "https://www.youtube.com/shorts/abc12345678",
            "https://www.youtube.com/live/abc12345678",
            "https://www.youtube.com/embed/abc12345678",
        ]
        for url in cases:
            self.assertEqual(media_ids.extract_video_id(url), "abc12345678")

    def test_animecube_id_is_stable_and_fits_the_column(self):
        url = ("https://animecube.live/anime/battle-through-the-heavens"
               "?season=tab-1&episode=btth-tab-1-ep-218")
        first = media_ids.extract_video_id(url)
        second = media_ids.extract_video_id(url)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("ac-"))
        self.assertLessEqual(len(first), 50)
        self.assertNotEqual(
            first,
            media_ids.extract_video_id(url.replace("ep-218", "ep-219")))

    def test_donghuastream_id_uses_its_own_prefix(self):
        url = ("https://donghuastream.org/"
               "apotheosis-season-3-episode-1-multiple-subtitles/")
        value = media_ids.extract_video_id(url)
        self.assertTrue(value.startswith("dhs-"))
        self.assertLessEqual(len(value), 50)

    def test_dailymotion_and_generic_urls(self):
        self.assertEqual(
            media_ids.extract_video_id(
                "https://www.dailymotion.com/video/k69vTxDr2f4A22MukEq"),
            "dm-k69vTxDr2f4A22MukEq")
        self.assertEqual(
            media_ids.extract_video_id("https://dai.ly/x7abcde"),
            "dm-x7abcde")
        generic = media_ids.extract_video_id("https://example.com/watch/1")
        self.assertTrue(generic.startswith("web-"))
        self.assertLessEqual(len(generic), 50)

    def test_archive_tags_round_trip_from_ids(self):
        self.assertEqual(media_ids.archive_tag("https://youtu.be/abc12345678"),
                         "youtube")
        self.assertEqual(
            media_ids.archive_tag("https://animecube.live/anime/x"),
            "animecube")
        self.assertEqual(
            media_ids.archive_tag("https://donghuastream.org/anime/x/"),
            "donghuastream")
        self.assertEqual(
            media_ids.archive_tag("https://www.dailymotion.com/video/abc"),
            "dailymotion")
        self.assertEqual(media_ids.archive_tag("https://example.com/v"),
                         "web")

        self.assertEqual(media_ids.archive_tag_for_id("abc12345678"), "youtube")
        self.assertEqual(media_ids.archive_tag_for_id("ac-123"), "animecube")
        self.assertEqual(media_ids.archive_tag_for_id("dhs-123"),
                         "donghuastream")
        self.assertEqual(media_ids.archive_tag_for_id("dm-123"),
                         "dailymotion")
        self.assertEqual(media_ids.archive_tag_for_id("web-123"), "web")

    def test_archive_key_pairs_the_tag_and_id(self):
        tag, vid = media_ids.archive_key(
            "https://animecube.live/anime/x?season=s&episode=e")
        self.assertEqual(tag, "animecube")
        self.assertTrue(vid.startswith("ac-"))


if __name__ == "__main__":
    unittest.main()
