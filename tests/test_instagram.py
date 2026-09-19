import os
import unittest
from yt_dlp.extractor.instagram import InstagramIE, InstagramBaseIE
from downloader.instagram_patch import apply_instagram_patch

class TestInstagramPatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        apply_instagram_patch()

    def test_single_photo_post(self):
        prod = {
            'pk': '12345678',
            'user': {'username': 'testcreator'},
            'image_versions2': {
                'candidates': [
                    {'url': 'https://instagram.com/small.jpg', 'width': 320, 'height': 320},
                    {'url': 'https://instagram.com/large.jpg', 'width': 1080, 'height': 1080},
                ]
            }
        }
        ie = InstagramIE()
        extracted = ie._extract_product_media(prod)
        formats = extracted.get('formats') or []
        self.assertTrue(len(formats) > 0, "Formats should not be empty for photo post")
        self.assertEqual(formats[0]['format_id'], 'photo')
        self.assertEqual(formats[0]['url'], 'https://instagram.com/large.jpg')
        self.assertEqual(formats[0]['width'], 1080)

    def test_carousel_album_extraction(self):
        carousel_post = {
            'pk': '999999',
            'user': {'username': 'testcreator'},
            'carousel_media': [
                {'pk': '111', 'image_versions2': {'candidates': [{'url': 'https://instagram.com/slide1.jpg', 'width': 1080, 'height': 1080}]}},
                {'pk': '222', 'image_versions2': {'candidates': [{'url': 'https://instagram.com/slide2.jpg', 'width': 1080, 'height': 1080}]}},
            ]
        }
        ie = InstagramIE()
        info = ie._extract_product(carousel_post, video_id='999999', get_comments=False)
        self.assertEqual(info.get('_type'), 'playlist')
        entries = info.get('entries', [])
        self.assertEqual(len(entries), 2)
        for entry in entries:
            formats = entry.get('formats') or []
            self.assertTrue(len(formats) > 0)
            self.assertEqual(formats[0]['format_id'], 'photo')

if __name__ == '__main__':
    unittest.main()
