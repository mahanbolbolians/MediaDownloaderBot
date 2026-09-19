import unittest
from downloader.spotify import parse_spotify_html
from downloader.generic import ensure_ffmpeg, get_js_runtimes_config

class TestSpotifyAndFFmpeg(unittest.TestCase):
    def test_ffmpeg_engine_active(self):
        ff = ensure_ffmpeg()
        self.assertIsNotNone(ff, "FFmpeg binary must be discovered and operational")

    def test_js_runtimes_discovery(self):
        js = get_js_runtimes_config()
        # On dev or CI with node installed, js will be dict; otherwise None
        self.assertTrue(js is None or isinstance(js, dict))

    def test_spotify_html_parsing_standard(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="twitter:title" content="FE!N (feat. Playboi Carti)">
            <meta name="music:musician_description" content="Travis Scott">
            <meta property="og:image" content="https://i.scdn.co/image/test_cover.jpg">
        </head>
        <body></body>
        </html>
        """
        meta = parse_spotify_html(html)
        self.assertEqual(meta["title"], "FE!N (feat. Playboi Carti)")
        self.assertEqual(meta["artist"], "Travis Scott")
        self.assertEqual(meta["thumbnail_url"], "https://i.scdn.co/image/test_cover.jpg")

    def test_spotify_html_parsing_opengraph_fallback(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta property="og:title" content="New Person, Same Old Mistakes">
            <meta property="og:description" content="Tame Impala · Currents · Song · 2015">
            <meta property="og:image" content="https://i.scdn.co/image/tame_cover.jpg">
        </head>
        <body></body>
        </html>
        """
        meta = parse_spotify_html(html)
        self.assertEqual(meta["title"], "New Person, Same Old Mistakes")
        self.assertEqual(meta["artist"], "Tame Impala")
        self.assertEqual(meta["thumbnail_url"], "https://i.scdn.co/image/tame_cover.jpg")

    def test_spotify_html_parsing_json_ld(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@type": "MusicRecording",
                "name": "Starboy",
                "byArtist": [{"@type": "MusicGroup", "name": "The Weeknd"}],
                "image": "https://i.scdn.co/image/starboy.jpg"
            }
            </script>
        </head>
        <body></body>
        </html>
        """
        meta = parse_spotify_html(html)
        self.assertEqual(meta["title"], "Starboy")
        self.assertEqual(meta["artist"], "The Weeknd")
        self.assertEqual(meta["thumbnail_url"], "https://i.scdn.co/image/starboy.jpg")

    def test_spotify_html_parsing_title_fallback(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Blinding Lights - song and lyrics by The Weeknd | Spotify</title>
        </head>
        <body></body>
        </html>
        """
        meta = parse_spotify_html(html)
        self.assertEqual(meta["title"], "Blinding Lights")
        self.assertEqual(meta["artist"], "The Weeknd")

if __name__ == "__main__":
    unittest.main()
