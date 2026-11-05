"""Unit tests for the YouTube Data API client (stdlib unittest)."""
import io
import json
import os
import tempfile
import unittest
import urllib.error
from unittest import mock

import youtube_api as yt


SEARCH_PAYLOAD = {
    "items": [{
        "id": {"videoId": "abc12345678"},
        "snippet": {
            "title": "Battle Through the Heavens Ep 1",
            "channelTitle": "Donghua Studio",
            "channelId": "chan-1",
            "publishedAt": "2026-10-01T00:00:00Z",
            "description": "Pilot episode",
            "thumbnails": {"high": {"url": "https://img.example/high.jpg"}},
            "liveBroadcastContent": "none",
        },
    }],
}

DETAILS_PAYLOAD = {
    "items": [{
        "id": "abc12345678",
        "snippet": {
            "title": "Battle Through the Heavens Ep 1",
            "channelTitle": "Donghua Studio",
            "publishedAt": "2026-10-01T00:00:00Z",
            "thumbnails": {"maxres": {"url": "https://img.example/max.jpg"}},
        },
        "contentDetails": {"duration": "PT24M10S"},
        "statistics": {"viewCount": "1234567", "likeCount": "2000"},
    }],
}

TRENDING_PAYLOAD = {
    "items": [{
        "id": "trend123456",
        "snippet": {
            "title": "Trending animation",
            "channelTitle": "Studio",
            "publishedAt": "2026-11-01T00:00:00Z",
            "thumbnails": {"medium": {"url": "https://img.example/med.jpg"}},
        },
        "contentDetails": {"duration": "PT3M"},
        "statistics": {"viewCount": "42"},
    }],
}


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class YouTubeParsingTests(unittest.TestCase):
    def test_duration_parsing_and_formatting(self):
        self.assertEqual(yt.duration_seconds("PT24M10S"), 1450)
        self.assertEqual(yt.duration_seconds("PT1H2M3S"), 3723)
        self.assertEqual(yt.duration_seconds("P1DT2S"), 86402)
        self.assertEqual(yt.duration_seconds("bogus"), 0)
        self.assertEqual(yt.format_duration(1450), "24:10")
        self.assertEqual(yt.format_duration(3723), "1:02:03")
        self.assertEqual(yt.format_duration(0), "—")

    def test_view_formatting(self):
        self.assertEqual(yt.format_views(999), "999 views")
        self.assertEqual(yt.format_views(1500), "1.5K views")
        self.assertEqual(yt.format_views(2_500_000), "2.5M views")
        self.assertEqual(yt.format_views(0), "no views yet")

    def test_normalize_video_merges_details(self):
        video = yt.normalize_video(SEARCH_PAYLOAD["items"][0],
                                   DETAILS_PAYLOAD["items"][0])
        self.assertEqual(video["id"], "abc12345678")
        self.assertEqual(video["duration"], 1450)
        self.assertEqual(video["duration_text"], "24:10")
        self.assertEqual(video["thumbnail"], "https://img.example/max.jpg")
        self.assertEqual(video["views"], 1234567)
        self.assertEqual(video["url"],
                         "https://www.youtube.com/watch?v=abc12345678")


class YouTubeClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.calls = []

    def fake_open(self, request, timeout=0):
        self.calls.append(request.full_url)
        if "/search?" in request.full_url:
            return FakeResponse(SEARCH_PAYLOAD)
        if "/videos?" in request.full_url:
            return FakeResponse(DETAILS_PAYLOAD)
        raise AssertionError(request.full_url)

    def test_missing_key_never_opens_a_connection(self):
        client = yt.YouTubeClient(api_key="", cache_dir=self.tmp.name)
        with mock.patch.object(yt.urllib.request, "urlopen",
                               side_effect=AssertionError("network")):
            with self.assertRaises(yt.YouTubeNotConfigured):
                client.search("donghua")

    def test_search_merges_details_and_caches(self):
        client = yt.YouTubeClient(api_key="AIza-secret", cache_dir=self.tmp.name,
                                  cache_minutes=30)
        with mock.patch.object(yt.urllib.request, "urlopen", self.fake_open):
            items = client.search("donghua", max_results=1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["duration_text"], "24:10")
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(any("/search?" in url for url in self.calls))
        self.assertTrue(any("/videos?" in url for url in self.calls))
        self.assertFalse(any("AIza-secret" in name
                             for name in os.listdir(self.tmp.name)))
        # A second call is served entirely from the disk cache.
        with mock.patch.object(yt.urllib.request, "urlopen",
                               side_effect=AssertionError("cache miss")):
            cached = client.search("donghua", max_results=1)
        self.assertEqual(cached, items)

    def test_trending_returns_normalized_items(self):
        def opener(request, timeout=0):
            return FakeResponse(TRENDING_PAYLOAD)

        client = yt.YouTubeClient(api_key="key", cache_dir=self.tmp.name)
        with mock.patch.object(yt.urllib.request, "urlopen", opener):
            items = client.trending(max_results=1)
        self.assertEqual(items[0]["id"], "trend123456")
        self.assertEqual(items[0]["duration_text"], "3:00")

    def test_http_error_is_friendly_and_redacts_the_key(self):
        body = json.dumps({
            "error": {
                "message": "The request cannot be completed because you have "
                           "exceeded your quota.",
                "errors": [{"reason": "quotaExceeded"}],
            }
        }).encode("utf-8")
        error = urllib.error.HTTPError(
            "https://www.googleapis.com/youtube/v3/search?key=AIza-secret",
            403, "Forbidden", {}, io.BytesIO(body))
        client = yt.YouTubeClient(api_key="AIza-secret", cache_dir=self.tmp.name)
        with mock.patch.object(yt.urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(yt.YouTubeError) as ctx:
                client.search("donghua")
        report = ctx.exception.report()
        self.assertIn("quota", str(ctx.exception).lower())
        self.assertNotIn("AIza-secret", report)
        self.assertIn("redacted", report)

    def test_network_error_is_wrapped(self):
        client = yt.YouTubeClient(api_key="key", cache_dir=self.tmp.name)
        with mock.patch.object(
                yt.urllib.request, "urlopen",
                side_effect=urllib.error.URLError("boom")):
            with self.assertRaises(yt.YouTubeError) as ctx:
                client.trending()
        self.assertIn("network", str(ctx.exception).lower())


class DummyClient:
    def __init__(self, *, fail_trending=False, fail_search=False):
        self.fail_trending = fail_trending
        self.fail_search = fail_search

    def trending(self, **_kwargs):
        if self.fail_trending:
            raise yt.YouTubeError("trending failed")
        return [{"id": "t1"}]

    def search(self, *_args, **_kwargs):
        if self.fail_search:
            raise yt.YouTubeError("search failed")
        return [{"id": "s1"}]


class DiscoverTests(unittest.TestCase):
    def test_discover_returns_two_rails(self):
        result = yt.discover(DummyClient())
        self.assertEqual([r["key"] for r in result["rails"]],
                         ["trending", "curated"])
        self.assertEqual(result["errors"], [])

    def test_discover_keeps_partial_results(self):
        result = yt.discover(DummyClient(fail_search=True))
        self.assertEqual(len(result["rails"]), 1)
        self.assertEqual(result["rails"][0]["key"], "trending")
        self.assertTrue(result["errors"])

    def test_discover_raises_when_everything_fails(self):
        with self.assertRaises(yt.YouTubeError):
            yt.discover(DummyClient(fail_trending=True, fail_search=True))


if __name__ == "__main__":
    unittest.main()
