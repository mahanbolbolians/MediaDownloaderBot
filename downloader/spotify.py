import os
import re
import urllib.request
import json
import asyncio
import logging
import yt_dlp
from downloader.base import MediaResult
from utils.media_tagger import tag_mp3

logger = logging.getLogger(__name__)

async def get_spotify_metadata(spotify_url: str) -> dict:
    """Extract metadata (title, artist, thumbnail) from Spotify URL without API keys."""
    meta = {
        "title": "Unknown Title",
        "artist": "Unknown Artist",
        "thumbnail_url": None
    }

    # 1. Fetch via Spotify oembed API
    oembed_url = f"https://open.spotify.com/oembed?url={spotify_url}"
    req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
    
    loop = asyncio.get_running_loop()

    def _fetch_oembed():
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except Exception as e:
            logger.warning(f"Spotify oembed error: {e}")
            return None

    data = await loop.run_in_executor(None, _fetch_oembed)
    if data:
        meta["title"] = data.get("title", meta["title"])
        meta["thumbnail_url"] = data.get("thumbnail_url")

    # 2. Fetch page HTML to get exact artist name if missing
    def _fetch_html():
        try:
            h_req = urllib.request.Request(spotify_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(h_req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                
                # Extract artist from og:description: "Artist Name · Song · 2024"
                desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', html)
                if desc_match:
                    parts = desc_match.group(1).split("·")
                    if parts:
                        return parts[0].strip()
                
                # Fallback artist match
                art_match = re.search(r'<meta name="twitter:audio:artist_name" content="([^"]+)"', html)
                if art_match:
                    return art_match.group(1).strip()
        except Exception as e:
            logger.warning(f"Spotify HTML artist parse error: {e}")
        return None

    artist = await loop.run_in_executor(None, _fetch_html)
    if artist:
        meta["artist"] = artist

    return meta

async def download_spotify(spotify_url: str, output_dir: str) -> MediaResult:
    """
    Downloads Spotify track by matching metadata with YouTube Music and tagging the resulting MP3.
    """
    os.makedirs(output_dir, exist_ok=True)
    meta = await get_spotify_metadata(spotify_url)

    title = meta["title"]
    artist = meta["artist"]
    thumb_url = meta["thumbnail_url"]

    search_query = f"ytsearch1:{artist} - {title} audio"
    out_template = os.path.join(output_dir, f"{artist} - {title}.%(ext)s")

    cookie_file = None
    if os.path.exists("cookies.txt"):
        cookie_file = os.path.abspath("cookies.txt")
    elif os.environ.get("YOUTUBE_COOKIES"):
        cookie_path = os.path.join(output_dir, "cookies.txt")
        try:
            with open(cookie_path, "w", encoding="utf-8") as f:
                f.write(os.environ["YOUTUBE_COOKIES"])
            cookie_file = cookie_path
        except Exception:
            pass

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }],
        "quiet": True,
        "no_warnings": True,
    }

    from downloader.generic import get_ffmpeg_path
    ffmpeg_bin = get_ffmpeg_path()
    if ffmpeg_bin:
        ydl_opts["ffmpeg_location"] = ffmpeg_bin

    if cookie_file and os.path.exists(cookie_file):
        ydl_opts["cookiefile"] = cookie_file

    loop = asyncio.get_running_loop()

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(search_query, download=True)

    info = await loop.run_in_executor(None, _download)

    # Find the output mp3
    mp3_files = [
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.endswith(".mp3")
    ]
    if not mp3_files:
        raise RuntimeError("Spotify audio download failed.")

    main_file = mp3_files[0]
    duration = 0
    if info and "entries" in info and info["entries"]:
        duration = int(info["entries"][0].get("duration") or 0)

    # Download Spotify high-res cover art
    cover_path = os.path.join(output_dir, "cover.jpg")
    if thumb_url:
        def _get_cover():
            try:
                urllib.request.urlretrieve(thumb_url, cover_path)
                return cover_path
            except Exception:
                return None
        await loop.run_in_executor(None, _get_cover)

    # Embed ID3 Tags & Cover
    tag_mp3(main_file, title=title, artist=artist, cover_path=cover_path if os.path.exists(cover_path) else None)

    return MediaResult(
        media_type="audio",
        file_path=main_file,
        title=title,
        artist=artist,
        duration=duration,
        thumbnail_path=cover_path if os.path.exists(cover_path) else None,
        caption=f"🎧 **{title}**\n👤 `{artist}`\n🟢 *Source: Spotify*"
    )
