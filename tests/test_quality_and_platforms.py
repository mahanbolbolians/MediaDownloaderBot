import unittest
import yt_dlp
from downloader.universal_patch import apply_universal_patch, populate_photo_formats
from yt_dlp.extractor.pinterest import PinterestIE
from yt_dlp.extractor.instagram import InstagramIE

class TestUniversalPatchesAndQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        apply_universal_patch()

    def test_pinterest_image_pin_extraction(self):
        pin_data = {
            "id": "676032594111061590",
            "title": "Aesthetic Wallpaper",
            "images": {
                "236x": {"url": "https://i.pinimg.com/236x/ab/cd/ef.jpg", "width": 236, "height": 400},
                "orig": {"url": "https://i.pinimg.com/originals/ab/cd/ef.jpg", "width": 1080, "height": 1920},
            }
        }
        ie = PinterestIE()
        res = ie._extract_video(pin_data)
        formats = res.get("formats") or []
        self.assertTrue(len(formats) > 0, "Pinterest photo pin should have formats")
        self.assertEqual(formats[0]["format_id"], "photo")
        self.assertEqual(formats[0]["url"], "https://i.pinimg.com/originals/ab/cd/ef.jpg")
        self.assertEqual(formats[0]["width"], 1080)

    def test_generic_photo_population(self):
        info = {
            "id": "item123",
            "title": "Generic Item",
            "thumbnails": [
                {"url": "https://example.com/thumb_small.jpg", "width": 300, "height": 300},
                {"url": "https://example.com/thumb_large.jpg", "width": 1200, "height": 1200},
            ]
        }
        populate_photo_formats(info)
        formats = info.get("formats") or []
        self.assertTrue(len(formats) > 0)
        self.assertEqual(formats[0]["format_id"], "photo")
        self.assertEqual(formats[0]["url"], "https://example.com/thumb_large.jpg")
        self.assertEqual(formats[0]["width"], 1200)

    def test_quality_format_selectors(self):
        for q in [1080, 720, 480, 360]:
            spec = (
                f"bestvideo[height<={q}][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={q}]+bestaudio/"
                f"best[height<={q}][ext=mp4]/"
                f"best[height<={q}]/"
                f"best/photo"
            )
            ydl = yt_dlp.YoutubeDL({"format": spec})
            sel = ydl.build_format_selector(spec)
            self.assertIsNotNone(sel)

if __name__ == "__main__":
    unittest.main()
