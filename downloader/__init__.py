import logging
from downloader.detector import detect_url
from downloader.generic import download_generic
from downloader.spotify import download_spotify
from downloader.base import MediaResult

logger = logging.getLogger(__name__)

async def download_media(url: str, output_dir: str, force_audio: bool = False) -> MediaResult:
    """
    Identifies the URL platform and downloads media in the optimal format.
    """
    detection = detect_url(url)
    if not detection:
        raise ValueError("No supported URL detected in the message.")

    platform, clean_url = detection
    logger.info(f"Detected platform: {platform} for URL: {clean_url}")

    if platform == "spotify":
        return await download_spotify(clean_url, output_dir)
    elif platform == "soundcloud" or force_audio:
        return await download_generic(clean_url, output_dir, is_audio_only=True)
    else:
        # YouTube, TikTok, Instagram, Pinterest, Twitter, Reddit, etc.
        return await download_generic(clean_url, output_dir, is_audio_only=False)
