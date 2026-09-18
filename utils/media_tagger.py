import os
import subprocess
import logging
from PIL import Image
import mutagen
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError
from mutagen.mp3 import MP3

logger = logging.getLogger(__name__)

def generate_video_thumbnail(video_path: str, thumb_path: str) -> str | None:
    """Extract a thumbnail frame from video using ffmpeg."""
    try:
        cmd = [
            "ffmpeg", "-y", "-ss", "00:00:01",
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            thumb_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        if res.returncode == 0 and os.path.exists(thumb_path):
            # Ensure thumbnail is within Telegram specs (JPEG, max 320px dimension)
            with Image.open(thumb_path) as img:
                img.thumbnail((320, 320))
                img.convert("RGB").save(thumb_path, "JPEG")
            return thumb_path
    except Exception as e:
        logger.warning(f"Error generating video thumbnail: {e}")
    return None

def tag_mp3(file_path: str, title: str = "", artist: str = "", album: str = "", cover_path: str = None):
    """Embed ID3 tags and album cover into MP3 file."""
    try:
        try:
            tags = ID3(file_path)
        except ID3NoHeaderError:
            tags = ID3()

        if title:
            tags["TIT2"] = TIT2(encoding=3, text=title)
        if artist:
            tags["TPE1"] = TPE1(encoding=3, text=artist)
        if album:
            tags["TALB"] = TALB(encoding=3, text=album)

        if cover_path and os.path.exists(cover_path):
            try:
                # Resize cover to square if needed
                with Image.open(cover_path) as img:
                    img = img.convert("RGB")
                    img.save(cover_path, "JPEG", quality=95)

                with open(cover_path, "rb") as f:
                    cover_data = f.read()

                tags["APIC"] = APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,  # Cover (front)
                    desc="Cover",
                    data=cover_data
                )
            except Exception as e:
                logger.warning(f"Failed to embed cover art: {e}")

        tags.save(file_path)
    except Exception as e:
        logger.warning(f"Failed to tag MP3 file: {e}")
