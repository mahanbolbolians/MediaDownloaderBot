import unittest
from downloader.detector import detect_url

class TestDetector(unittest.TestCase):
    def test_youtube(self):
        self.assertEqual(detect_url("Check this: https://www.youtube.com/watch?v=dQw4w9WgXcQ")[0], "youtube")
        self.assertEqual(detect_url("https://youtu.be/dQw4w9WgXcQ?si=abc")[0], "youtube")
        self.assertEqual(detect_url("https://youtube.com/shorts/1234567890")[0], "youtube")

    def test_spotify(self):
        self.assertEqual(detect_url("https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT")[0], "spotify")
        self.assertEqual(detect_url("listen to https://open.spotify.com/album/12345")[0], "spotify")

    def test_tiktok(self):
        self.assertEqual(detect_url("https://www.tiktok.com/@user/video/123456789")[0], "tiktok")
        self.assertEqual(detect_url("https://vm.tiktok.com/ZM8abc/")[0], "tiktok")

    def test_instagram(self):
        self.assertEqual(detect_url("https://www.instagram.com/reel/C12345/")[0], "instagram")
        self.assertEqual(detect_url("https://instagram.com/p/C12345/")[0], "instagram")

    def test_soundcloud(self):
        self.assertEqual(detect_url("https://soundcloud.com/artist/song-name")[0], "soundcloud")
        self.assertEqual(detect_url("https://on.soundcloud.com/1234")[0], "soundcloud")

    def test_pinterest(self):
        self.assertEqual(detect_url("https://pinterest.com/pin/123456/")[0], "pinterest")
        self.assertEqual(detect_url("https://pin.it/123456")[0], "pinterest")

if __name__ == "__main__":
    unittest.main()
