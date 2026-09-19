import os
import re
import urllib.request
import urllib.parse
import json
import asyncio
import logging
import subprocess
import yt_dlp
from downloader.base import MediaResult
from downloader.generic import ensure_ffmpeg, get_js_runtimes_config
from utils.media_tagger import tag_mp3

logger = logging.getLogger(__name__)

def parse_spotify_html(html: str) -> dict:
    """Extracts title, artist, and cover thumbnail from Spotify HTML."""
    title = None
    artist = None
    cover_url = None

    # 1. OpenGraph / Twitter meta tags
    m_title = re.search(r'<meta\s+name="twitter:title"\s+content="([^"]+)"', html, re.IGNORECASE) or \
              re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html, re.IGNORECASE)
    if m_title:
        title = m_title.group(1).strip()

    m_artist = re.search(r'<meta\s+name="music:musician_description"\s+content="([^"]+)"', html, re.IGNORECASE) or \
               re.search(r'<meta\s+name="twitter:audio:artist_name"\s+content="([^"]+)"', html, re.IGNORECASE)
    if m_artist:
        artist = m_artist.group(1).strip()

    if not artist:
        m_desc = re.search(r'<meta\s+name="twitter:description"\s+content="([^"]+)"', html, re.IGNORECASE) or \
                 re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html, re.IGNORECASE)
        if m_desc:
            parts = m_desc.group(1).split("·")
            if parts and parts[0].strip():
                artist = parts[0].strip()

    m_img = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html, re.IGNORECASE) or \
            re.search(r'<meta\s+name="twitter:image"\s+content="([^"]+)"', html, re.IGNORECASE)
    if m_img:
        cover_url = m_img.group(1).strip()

    # 2. JSON-LD fallback
    if not title or not artist:
        m_ld = re.search(r'<script\s+type="application/ld\+json">([^<]+)</script>', html, re.IGNORECASE)
        if m_ld:
            try:
                data = json.loads(m_ld.group(1))
                if not title:
                    title = data.get("name")
                if not artist and "byArtist" in data and isinstance(data["byArtist"], list) and data["byArtist"]:
                    artist = data["byArtist"][0].get("name")
                if not cover_url and "image" in data and isinstance(data["image"], str):
                    cover_url = data["image"]
            except Exception:
                pass

    # 3. HTML <title> tag fallback
    if not title or not artist:
        m_pt = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if m_pt:
            t = m_pt.group(1).strip()
            match = re.match(r'^(.*?)\s*-\s*song and lyrics by\s*(.*?)\s*\|\s*Spotify', t, re.IGNORECASE)
            if match:
                if not title:
                    title = match.group(1).strip()
                if not artist:
                    artist = match.group(2).strip()
            else:
                simple_match = re.match(r'^(.*?)\s*\|\s*Spotify', t, re.IGNORECASE)
                if simple_match and not title:
                    title = simple_match.group(1).strip()

    return {
        "title": title or "Unknown Title",
        "artist": artist or "Unknown Artist",
        "thumbnail_url": cover_url
    }

async def get_spotify_metadata(spotify_url: str) -> dict:
    """Extract metadata (title, artist, thumbnail) from Spotify URL using multi-tier fallback."""
    clean_url = spotify_url.split("?")[0].strip()
    loop = asyncio.get_running_loop()

    # Tier 1: HTML Scrape
    def _fetch_html():
        try:
            req = urllib.request.Request(
                clean_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Spotify HTML fetch error for {clean_url}: {e}")
            return None

    html = await loop.run_in_executor(None, _fetch_html)
    meta = parse_spotify_html(html) if html else {"title": "Unknown Title", "artist": "Unknown Artist", "thumbnail_url": None}

    # Tier 2: OEmbed Fallback if title or artist is unknown
    if meta["title"] == "Unknown Title" or meta["artist"] == "Unknown Artist":
        def _fetch_oembed():
            try:
                oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
                req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                logger.warning(f"Spotify oembed error: {e}")
                return None

        oembed_data = await loop.run_in_executor(None, _fetch_oembed)
        if oembed_data:
            if meta["title"] == "Unknown Title" and "title" in oembed_data:
                meta["title"] = oembed_data["title"]
            if not meta["thumbnail_url"] and "thumbnail_url" in oembed_data:
                meta["thumbnail_url"] = oembed_data["thumbnail_url"]

    return meta

async def download_spotify(spotify_url: str, output_dir: str) -> MediaResult:
    """
    Downloads Spotify track by matching metadata with YouTube/YouTube Music
    and tagging the resulting 320kbps MP3 with ID3 tags and album cover art.
    """
    os.makedirs(output_dir, exist_ok=True)
    meta = await get_spotify_metadata(spotify_url)

    title = meta["title"]
    artist = meta["artist"]
    thumb_url = meta["thumbnail_url"]

    if title == "Unknown Title" and artist == "Unknown Artist":
        raise RuntimeError("Unable to extract song metadata from Spotify URL.")

    search_query = f"ytsearch1:{artist} - {title} audio"
    out_template = os.path.join(output_dir, f"{artist} - {title}.%(ext)s")

    ffmpeg_bin = ensure_ffmpeg()
    js_cfg = get_js_runtimes_config()

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
        "quiet": True,
        "no_warnings": True,
    }

    if ffmpeg_bin:
        ydl_opts["ffmpeg_location"] = ffmpeg_bin
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }]

    if js_cfg:
        ydl_opts["js_runtimes"] = js_cfg

    if cookie_file and os.path.exists(cookie_file):
        ydl_opts["cookiefile"] = cookie_file

    loop = asyncio.get_running_loop()

    def _download(query: str):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(query, download=True)

    info = None
    last_err = None
    try:
        info = await loop.run_in_executor(None, lambda: _download(search_query))
    except Exception as e:
        last_err = e
        logger.warning(f"Primary Spotify query failed: {e}. Trying secondary search without 'audio'...")
        try:
            fallback_query = f"ytsearch1:{artist} - {title}"
            info = await loop.run_in_executor(None, lambda: _download(fallback_query))
        except Exception as e2:
            last_err = e2

    # Check for downloaded mp3 files
    mp3_files = [
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.lower().endswith(".mp3")
    ]

    # Defense-in-depth: if postprocessor didn't produce .mp3 but an audio stream was downloaded (.m4a, .webm, .opus)
    if not mp3_files:
        other_audio = [
            os.path.join(output_dir, f)
            for f in os.listdir(output_dir)
            if f.lower().endswith((".m4a", ".webm", ".opus", ".ogg", ".aac"))
        ]
        if other_audio and ffmpeg_bin:
            in_file = other_audio[0]
            target_mp3 = os.path.splitext(in_file)[0] + ".mp3"
            cmd = [ffmpeg_bin, "-y", "-i", in_file, "-vn", "-ab", "320k", "-ar", "44100", target_mp3]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0 and os.path.exists(target_mp3):
                mp3_files = [target_mp3]
                try:
                    os.remove(in_file)
                except Exception:
                    pass

    if not mp3_files:
        err_msg = f": {last_err}" if last_err else ""
        raise RuntimeError(f"Spotify audio download failed{err_msg}")

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

    # Embed ID3 Tags & Album Cover
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
