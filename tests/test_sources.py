"""Parser and resolver tests for AnimeCube and DonghuaStream clients."""
import base64
import hashlib
import unittest
from unittest import mock

import sources


ANIME = {
    "slug": "battle-through-the-heavens",
    "title": "Battle Through the Heavens",
    "description": "Xiao Yan rises.",
    "coverImage": "https://images.example/btth.jpg",
    "genres": ["Action", "Fantasy"],
    "year": 2025,
    "primaryTabs": [{
        "id": "primary-1",
        "seasons": [{
            "id": "tab-1",
            "customName": "Season 5",
            "episodes": [
                {"id": "btth-tab-1-ep-2", "number": 2,
                 "numberDisplay": "2", "title": "Season 5 Episode 2"},
                {"id": "btth-tab-1-ep-1", "number": 1,
                 "numberDisplay": "1", "title": "Season 5 Episode 1"},
            ],
        }],
    }],
}

CATALOG = [
    {"slug": "battle-through-the-heavens",
     "title": "Battle Through the Heavens",
     "aliases": ["btth"], "genres": ["Action"],
     "coverImage": "https://images.example/btth.jpg",
     "latestSeasonTitle": "Season 5", "latestEpisodeDisplay": "218",
     "latestQuality": "4K", "lastEpisodeAddedAt": "2025-12-16T10:01:31Z"},
    {"slug": "soul-land", "title": "Soul Land", "aliases": ["douluo"],
     "genres": ["Fantasy"], "coverImage": "https://images.example/sl.jpg"},
    {"slug": "swallowed-star", "title": "Swallowed Star", "aliases": [],
     "genres": ["Sci-Fi"], "coverImage": "https://images.example/ss.jpg"},
]


SEARCH_HTML = """
<article class="bs">
  <div class="bsx">
    <a href="https://donghuastream.org/anime/apotheosis-season-3/"
       itemprop="url" title="Apotheosis Season 3" class="tip">
      <div class="limit"><img src="https://cdn.example/ap3.jpg" alt=""></div>
    </a>
    <div class="tt"><a href="https://donghuastream.org/anime/apotheosis-season-3/">
      Apotheosis Season 3</a></div>
  </div>
</article>
<article class="bs">
  <div class="bsx">
    <a href="https://donghuastream.org/anime/battle-through-the-heavens-season-5th/"
       itemprop="url" title="Battle Through the Heavens Season 5" class="tip">
      <div class="limit"><img src="https://cdn.example/btth5.jpg" alt=""></div>
    </a>
    <div class="tt">Battle Through the Heavens Season 5</div>
  </div>
</article>
"""

SERIES_HTML = """
<html><head>
<meta property="og:image" content="https://cdn.example/ap3.jpg">
<meta name="description" content="Third season of Apotheosis.">
<title>Apotheosis Season 3 &raquo; DonghuaStream</title>
</head><body>
<h1>Apotheosis Season 3</h1>
<div class="entry-content">Third season of Apotheosis.</div>
<div class="eplister"><ul>
<li><a href="https://donghuastream.org/apotheosis-season-3-episode-1-multiple-subtitles/">
  <div class="epl-num">1 (Good Sub)(4K)</div>
  <div class="epl-title">Apotheosis Season 3 Episode 1</div></a></li>
<li><a href="https://donghuastream.org/apotheosis-season-3-episode-2-multiple-subtitles/">
  <div class="epl-num">Hiatus</div>
  <div class="epl-title">Apotheosis Season 3 Episode 2</div></a></li>
</ul></div>
<div class="bixbox">footer</div>
</body></html>
"""

EPISODE_HTML = """
<html><head><title>Apotheosis Season 3 Episode 1 &raquo; DonghuaStream</title></head>
<body>
<h1>Apotheosis Season 3 Episode 1</h1>
<iframe data-lazyloaded="1" src="about:blank"
  data-litespeed-src="https://geo.dailymotion.com/player/x19jsm.html?video=k69vTxDr2f4A22MukEq">
</iframe>
</body></html>
"""


class AnimeCubeTests(unittest.TestCase):
    def setUp(self):
        self.client = sources.SOURCES["animecube"]

    def test_catalog_search_matches_titles_and_aliases(self):
        with mock.patch.object(self.client, "_catalog", return_value=CATALOG):
            hits = self.client.search("btth")
            self.assertEqual([hit["title"] for hit in hits],
                             ["Battle Through the Heavens"])
            self.assertTrue(hits[0]["url"].endswith(
                "/anime/battle-through-the-heavens"))
            self.assertEqual(hits[0]["source"], "animecube")

            empty = self.client.search("nothing here")
            self.assertEqual(empty, [])

    def test_details_builds_canonical_episode_urls(self):
        with mock.patch.object(self.client, "_anime", return_value=ANIME):
            details = self.client.details(
                "https://animecube.live/anime/battle-through-the-heavens")

        self.assertEqual(details["title"], "Battle Through the Heavens")
        self.assertEqual(details["episode_count"], 2)
        numbers = [ep["episode_number"] for ep in details["episodes"]]
        self.assertEqual(numbers, [1, 2])
        first = details["episodes"][0]
        self.assertIn("?season=tab-1&episode=btth-tab-1-ep-1", first["url"])
        self.assertEqual(first["season_title"], "Season 5")
        self.assertEqual(first["primary_tab_id"], "primary-1")

    def test_private_dailymotion_id_wins_over_public_video_id(self):
        source = {
            "platform": "dailymotion",
            "videoId": "xbulga2",
            "privateId": "k5AuCQaGBrL0iDMuqSu",
            "quality": "4K",
            "goodSub": True,
        }
        self.assertEqual(
            sources._animecube_source_url(source),
            "https://www.dailymotion.com/video/k5AuCQaGBrL0iDMuqSu")

        best = sources._pick_source([
            source,
            {"platform": "youtube", "videoId": "abc12345678",
             "quality": "4K"},
        ])
        self.assertIn("dailymotion.com", best["url"])

    def test_encrypted_payload_uses_the_documented_key_recipe(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        material = "obf-value|etag-value"
        key = hashlib.sha256(material.encode("utf-8")).digest()
        iv = b"0123456789ab"
        plain = b'{"sources": [{"platform": "dailymotion"}]}'
        blob = base64.b64encode(
            iv + AESGCM(key).encrypt(iv, plain, None)).decode("ascii")
        self.assertEqual(
            sources._decrypt_payload(blob, material),
            {"sources": [{"platform": "dailymotion"}]})

    def test_rsc_helpers_extract_catalog_and_anime_objects(self):
        rsc = (
            'prefix{"fallbackData":[{"slug":"x","title":"X"}]}'
            'middle{"anime":{"slug":"x","primaryTabs":[]}}suffix')
        self.assertEqual(
            sources._json_after(rsc, '"fallbackData":'),
            [{"slug": "x", "title": "X"}])
        self.assertEqual(
            sources._find_anime_object(rsc),
            {"slug": "x", "primaryTabs": []})


class DonghuaStreamTests(unittest.TestCase):
    def setUp(self):
        self.client = sources.SOURCES["donghuastream"]

    def test_search_parses_wordpress_result_cards(self):
        cards = self.client._parse_search(SEARCH_HTML)
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0]["title"], "Apotheosis Season 3")
        self.assertEqual(cards[0]["source"], "donghuastream")
        self.assertEqual(cards[0]["thumbnail"], "https://cdn.example/ap3.jpg")
        self.assertTrue(cards[0]["url"].endswith(
            "/anime/apotheosis-season-3/"))

    def test_series_page_lists_episodes_and_recovers_hiatus_numbers(self):
        details = self.client._parse_series(
            SERIES_HTML,
            "https://donghuastream.org/anime/apotheosis-season-3/")
        self.assertEqual(details["title"], "Apotheosis Season 3")
        self.assertEqual(details["thumbnail"], "https://cdn.example/ap3.jpg")
        self.assertEqual(details["episode_count"], 2)
        self.assertEqual(
            [ep["episode_number"] for ep in details["episodes"]], [1, 2])
        self.assertTrue(details["episodes"][0]["url"].endswith(
            "/apotheosis-season-3-episode-1-multiple-subtitles/"))

    def test_episode_page_resolves_to_a_direct_dailymotion_url(self):
        with mock.patch("sources._get_text", return_value=EPISODE_HTML):
            resolved = self.client.resolve(
                "https://donghuastream.org/"
                "apotheosis-season-3-episode-1-multiple-subtitles/")
        self.assertEqual(
            resolved["url"],
            "https://www.dailymotion.com/video/k69vTxDr2f4A22MukEq")
        self.assertEqual(resolved["platform"], "dailymotion")
        self.assertEqual(resolved["source"], "donghuastream")
        self.assertTrue(resolved["video_id"].startswith("dhs-"))
        self.assertIn("Apotheosis Season 3 Episode 1", resolved["title"])


class SourceRegistryTests(unittest.TestCase):
    def test_registry_and_url_detection(self):
        self.assertEqual(
            sources.source_for_url("https://animecube.live/anime/x"),
            "animecube")
        self.assertEqual(
            sources.source_for_url("https://donghuastream.org/anime/x/"),
            "donghuastream")
        self.assertIsNone(
            sources.source_for_url("https://www.youtube.com/watch?v=abc12345678"))
        self.assertTrue(sources.supports("https://animecube.live/anime/x"))
        self.assertFalse(sources.supports("https://example.com/video"))
        self.assertIsNone(sources.get_source("youtube"))
        self.assertIsNotNone(sources.get_source("animecube"))
        self.assertEqual(
            [key for key, _label in sources.SOURCE_CHOICES],
            ["youtube", "animecube", "donghuastream"])


if __name__ == "__main__":
    unittest.main()
