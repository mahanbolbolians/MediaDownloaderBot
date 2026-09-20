import unittest
import yt_dlp
from downloader.universal_patch import apply_universal_patch, populate_photo_formats
from downloader.generic import get_ffmpeg_path
from yt_dlp.extractor.pinterest import PinterestIE
from yt_dlp.extractor.instagram import InstagramIE

class TestUniversalPatchesAndQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        apply_universal_patch()

    def test_ffmpeg_detection(self):
        path = get_ffmpeg_path()
        self.assertIsNotNone(path, "FFmpeg should be detected via system or imageio-ffmpeg")

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

    def test_landscape_quality_selection(self):
        landscape_formats = [
            {"format_id": "140", "url": "https://a.m4a", "ext": "m4a", "acodec": "aac", "vcodec": "none", "abr": 128},
            {"format_id": "18", "url": "https://360.mp4", "ext": "mp4", "height": 360, "width": 640, "acodec": "aac", "vcodec": "avc1"},
            {"format_id": "135", "url": "https://480.mp4", "ext": "mp4", "height": 480, "width": 854, "acodec": "none", "vcodec": "avc1"},
            {"format_id": "136", "url": "https://720.mp4", "ext": "mp4", "height": 720, "width": 1280, "acodec": "none", "vcodec": "avc1"},
            {"format_id": "137", "url": "https://1080.mp4", "ext": "mp4", "height": 1080, "width": 1920, "acodec": "none", "vcodec": "avc1"},
        ]
        info = {"id": "land", "title": "Landscape", "extractor": "youtube", "formats": landscape_formats}

        expected = {1080: 1080, 720: 720, 480: 480, 360: 360}
        for q, exp_h in expected.items():
            spec = (
                f"bestvideo[height={q}]+bestaudio/"
                f"bestvideo[width={q}]+bestaudio/"
                f"best[height={q}]/"
                f"best[width={q}]/"
                f"bestvideo[height<={q}]+bestaudio/"
                f"bestvideo[width<={q}]+bestaudio/"
                f"best[height<={q}]/"
                f"best[width<={q}]/"
                f"bestvideo+bestaudio/best/photo"
            )
            ydl = yt_dlp.YoutubeDL({"format": spec})
            fmts = ydl._get_formats(info)
            sel = ydl.build_format_selector(spec)
            chosen = ydl._select_formats(fmts, sel)
            self.assertTrue(len(chosen) > 0)
            self.assertEqual(chosen[0].get("height"), exp_h, f"Quality {q} should select height {exp_h}")

    def test_portrait_quality_selection(self):
        portrait_formats = [
            {"format_id": "140", "url": "https://a.m4a", "ext": "m4a", "acodec": "aac", "vcodec": "none", "abr": 128},
            {"format_id": "v360", "url": "https://v360.mp4", "ext": "mp4", "height": 640, "width": 360, "acodec": "none", "vcodec": "avc1"},
            {"format_id": "v480", "url": "https://v480.mp4", "ext": "mp4", "height": 854, "width": 480, "acodec": "none", "vcodec": "avc1"},
            {"format_id": "v720", "url": "https://v720.mp4", "ext": "mp4", "height": 1280, "width": 720, "acodec": "none", "vcodec": "avc1"},
            {"format_id": "v1080", "url": "https://v1080.mp4", "ext": "mp4", "height": 1920, "width": 1080, "acodec": "none", "vcodec": "avc1"},
        ]
        info = {"id": "port", "title": "Portrait", "extractor": "youtube", "formats": portrait_formats}

        expected = {1080: 1080, 720: 720, 480: 480, 360: 360}
        for q, exp_w in expected.items():
            spec = (
                f"bestvideo[height={q}]+bestaudio/"
                f"bestvideo[width={q}]+bestaudio/"
                f"best[height={q}]/"
                f"best[width={q}]/"
                f"bestvideo[height<={q}]+bestaudio/"
                f"bestvideo[width<={q}]+bestaudio/"
                f"best[height<={q}]/"
                f"best[width<={q}]/"
                f"bestvideo+bestaudio/best/photo"
            )
            ydl = yt_dlp.YoutubeDL({"format": spec})
            fmts = ydl._get_formats(info)
            sel = ydl.build_format_selector(spec)
            chosen = ydl._select_formats(fmts, sel)
            self.assertTrue(len(chosen) > 0)
            self.assertEqual(chosen[0].get("width"), exp_w, f"Quality {q} should select width {exp_w}")

    def test_youtube_ios_patch(self):
        from yt_dlp.extractor.youtube._base import INNERTUBE_CLIENTS
        ios_cfg = INNERTUBE_CLIENTS.get("ios", {})
        self.assertIsNotNone(ios_cfg)
        client_version = ios_cfg.get("INNERTUBE_CONTEXT", {}).get("client", {}).get("clientVersion")
        self.assertEqual(client_version, "20.03.02", "iOS client should be patched to 20.03.02")

if __name__ == "__main__":
    unittest.main()
