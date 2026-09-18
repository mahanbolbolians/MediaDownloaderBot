import os
import unittest
import subprocess
from PIL import Image
from mutagen.id3 import ID3
from utils.media_tagger import tag_mp3

class TestMediaTagger(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(os.path.dirname(__file__), "tmp_test")
        os.makedirs(self.test_dir, exist_ok=True)
        self.mp3_path = os.path.join(self.test_dir, "test_song.mp3")
        self.cover_path = os.path.join(self.test_dir, "test_cover.jpg")

        # Generate 1 sec silent mp3 with ffmpeg
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", "1", "-q:a", "9", "-acodec", "libmp3lame", self.mp3_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Generate dummy image
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(self.cover_path, "JPEG")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_tagging(self):
        tag_mp3(
            self.mp3_path,
            title="Sample Title",
            artist="Sample Artist",
            album="Sample Album",
            cover_path=self.cover_path
        )

        tags = ID3(self.mp3_path)
        self.assertEqual(tags["TIT2"].text[0], "Sample Title")
        self.assertEqual(tags["TPE1"].text[0], "Sample Artist")
        self.assertEqual(tags["TALB"].text[0], "Sample Album")
        self.assertIn("APIC:Cover", tags)

if __name__ == "__main__":
    unittest.main()
