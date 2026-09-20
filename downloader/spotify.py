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
    """Extracts title, artist, and cover thumbnail from Spotify HTML or embed page."""
    meta = {
        "title": "Unknown Title",
        "artist": "Unknown Artist",
        "thumbnail_url": None,
        "duration": 0
    }

    # 1. Try __NEXT_DATA__ JSON from Embed page
    m_json = re.search(r'<script\s+id="__NEXT_DATA__"\s+type="application/json">([^<]+)</script>', html, re.IGNORECASE)
    if m_json:
        try:
            data = json.loads(m_json.group(1))
            entity = data.get("props", {}).get("pageProps", {}).get("state", {}).get("data", {}).get("entity", {})
            if entity:
                meta["title"] = entity.get("name") or entity.get("title") or meta["title"]
                artists = entity.get("artists", [])
                if artists:
                    meta["artist"] = ", ".join(a["name"] for a in artists if "name" in a)
                elif "subtitle" in entity:
                    meta["artist"] = entity["subtitle"]

                images = entity.get("visualIdentity", {}).get("image", [])
                if images:
                    meta["thumbnail_url"] = images[-1].get("url")

                dur = entity.get("duration", 0)
                if dur:
                    meta["duration"] = int(dur / 1000)

                if meta["title"] != "Unknown Title" and meta["artist"] != "Unknown Artist":
                    return meta
        except Exception as e:
            logger.debug(f"__NEXT_DATA__ parse failed: {e}")

    # 2. OpenGraph / Twitter meta tags
    m_title = re.search(r'<meta\s+name="twitter:title"\s+content="([^"]+)"', html, re.IGNORECASE) or \
              re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html, re.IGNORECASE)
    if m_title:
        meta["title"] = m_title.group(1).strip()

    m_artist = re.search(r'<meta\s+name="music:musician_description"\s+content="([^"]+)"', html, re.IGNORECASE) or \
               re.search(r'<meta\s+name="twitter:audio:artist_name"\s+content="([^"]+)"', html, re.IGNORECASE)
    if m_artist:
        meta["artist"] = m_artist.group(1).strip()

    if meta["artist"] == "Unknown Artist":
        m_desc = re.search(r'<meta\s+name="twitter:description"\s+content="([^"]+)"', html, re.IGNORECASE) or \
                 re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html, re.IGNORECASE)
        if m_desc:
            parts = m_desc.group(1).split("·")
            if parts and parts[0].strip():
                meta["artist"] = parts[0].strip()

    m_img = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html, re.IGNORECASE) or \
            re.search(r'<meta\s+name="twitter:image"\s+content="([^"]+)"', html, re.IGNORECASE)
    if m_img and not meta["thumbnail_url"]:
        meta["thumbnail_url"] = m_img.group(1).strip()

    # 3. JSON-LD fallback
    if meta["title"] == "Unknown Title" or meta["artist"] == "Unknown Artist":
        m_ld = re.search(r'<script\s+type="application/ld\+json">([^<]+)</script>', html, re.IGNORECASE)
        if m_ld:
            try:
                ld_data = json.loads(m_ld.group(1))
                if meta["title"] == "Unknown Title":
                    meta["title"] = ld_data.get("name", meta["title"])
                if meta["artist"] == "Unknown Artist" and "byArtist" in ld_data and isinstance(ld_data["byArtist"], list) and ld_data["byArtist"]:
                    meta["artist"] = ld_data["byArtist"][0].get("name", meta["artist"])
                if not meta["thumbnail_url"] and "image" in ld_data and isinstance(ld_data["image"], str):
                    meta["thumbnail_url"] = ld_data["image"]
            except Exception:
                pass

    # 4. HTML <title> tag fallback
    if meta["title"] == "Unknown Title" or meta["artist"] == "Unknown Artist":
        m_pt = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if m_pt:
            t = m_pt.group(1).strip()
            match = re.match(r'^(.*?)\s*-\s*song and lyrics by\s*(.*?)\s*\|\s*Spotify', t, re.IGNORECASE)
            if match:
                if meta["title"] == "Unknown Title":
                    meta["title"] = match.group(1).strip()
                if meta["artist"] == "Unknown Artist":
                    meta["artist"] = match.group(2).strip()
            else:
                simple_match = re.match(r'^(.*?)\s*\|\s*Spotify', t, re.IGNORECASE)
                if simple_match and meta["title"] == "Unknown Title":
                    meta["title"] = simple_match.group(1).strip()

    return meta

def get_itunes_metadata(title: str, artist: str = "") -> dict:
    """
    Fetches rich song metadata (artist, album, 1000x1000 artwork, duration)
    from Apple's iTunes Search API as a 100% free, unblocked fallback.
    """
    query = f"{artist} {title}".strip() if artist and artist != "Unknown Artist" else title
    url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&entity=song&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("results"):
                item = data["results"][0]
                art = item.get("artworkUrl100")
                if art:
                    art = art.replace("100x100bb.jpg", "1000x1000bb.jpg")
                return {
                    "title": item.get("trackName") or title,
                    "artist": item.get("artistName") or artist,
                    "album": item.get("collectionName"),
                    "thumbnail_url": art,
                    "duration": int(item.get("trackTimeMillis", 0) / 1000)
                }
    except Exception as e:
        logger.debug(f"iTunes metadata lookup failed: {e}")
    return {}

def search_youtube_music(query: str) -> str | None:
    """
    Directly queries YouTube Music's InnerTube API (WEB_REMIX client)
    to find the official videoId for a song query.
    Bypasses datacenter bot blocks without login or cookies.
    """
    url = "https://music.youtube.com/youtubei/v1/search?prettyPrint=false"
    data = {
        "context": {
            "client": {
                "clientName": "WEB_REMIX",
                "clientVersion": "1.20240101.01.00",
                "hl": "en",
                "gl": "US"
            }
        },
        "query": query
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Origin": "https://music.youtube.com",
        "Referer": "https://music.youtube.com/",
    }
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            match = re.search(r'"videoId":\s*"([a-zA-Z0-9_-]{11})"', raw)
            if match:
                return match.group(1)
    except Exception as e:
        logger.warning(f"InnerTube YouTube Music search failed for '{query}': {e}")
    return None

async def get_spotify_metadata(spotify_url: str) -> dict:
    """Extract metadata (title, artist, thumbnail) from Spotify URL using multi-tier fallback."""
    clean_url = spotify_url.split("?")[0].strip()
    m_id = re.search(r"/(track|album|playlist)/([a-zA-Z0-9]+)", clean_url)
    loop = asyncio.get_running_loop()

    # Tier 1: Embed Page (most reliable, unblocked, contains __NEXT_DATA__ JSON)
    if m_id:
        media_type = m_id.group(1)
        media_id = m_id.group(2)
        embed_url = f"https://open.spotify.com/embed/{media_type}/{media_id}"

        def _fetch_embed():
            try:
                req = urllib.request.Request(
                    embed_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    return resp.read().decode("utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Spotify embed fetch failed for {embed_url}: {e}")
                return None

        embed_html = await loop.run_in_executor(None, _fetch_embed)
        if embed_html:
            meta = parse_spotify_html(embed_html)
            if meta["title"] != "Unknown Title" and meta["artist"] != "Unknown Artist":
                return meta

    # Tier 2: Standard Track HTML Page
    def _fetch_html():
        try:
            req = urllib.request.Request(
                clean_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Spotify HTML fetch error for {clean_url}: {e}")
            return None

    html = await loop.run_in_executor(None, _fetch_html)
    meta = parse_spotify_html(html) if html else {"title": "Unknown Title", "artist": "Unknown Artist", "thumbnail_url": None, "duration": 0}

    # Tier 3: OEmbed Fallback
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

    # Tier 4: Apple iTunes Search API enrichment
    if meta["title"] != "Unknown Title":
        itunes_meta = await loop.run_in_executor(None, lambda: get_itunes_metadata(meta["title"], meta["artist"]))
        if itunes_meta:
            if meta["artist"] == "Unknown Artist" and itunes_meta.get("artist"):
                meta["artist"] = itunes_meta["artist"]
            if not meta["thumbnail_url"] and itunes_meta.get("thumbnail_url"):
                meta["thumbnail_url"] = itunes_meta["thumbnail_url"]
            if not meta.get("duration") and itunes_meta.get("duration"):
                meta["duration"] = itunes_meta["duration"]
            if itunes_meta.get("album"):
                meta["album"] = itunes_meta["album"]

    return meta

async def download_spotify(spotify_url: str, output_dir: str) -> MediaResult:
    """
    Downloads Spotify track by matching metadata with YouTube Music/SoundCloud
    and tagging the resulting 320kbps MP3 with ID3 tags and album cover art.
    """
    os.makedirs(output_dir, exist_ok=True)
    meta = await get_spotify_metadata(spotify_url)

    title = meta["title"]
    artist = meta["artist"]
    album = meta.get("album", "")
    thumb_url = meta["thumbnail_url"]
    expected_duration = meta.get("duration", 0)

    if title == "Unknown Title" and artist == "Unknown Artist":
        raise RuntimeError("Unable to extract song metadata from Spotify URL.")

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

    extractor_args = {
        "youtube": {
            "player_client": ["ios", "visionos", "web_embedded", "tv_downgraded"]
        }
    }

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "extractor_args": extractor_args,
    }

    proxy = os.environ.get("YTDLP_PROXY") or os.environ.get("PROXY")
    if proxy:
        ydl_opts["proxy"] = proxy

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

    def _download(target: str):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(target, download=True)

    def _has_audio(d: str) -> bool:
        return any(
            f.lower().endswith((".mp3", ".m4a", ".webm", ".opus", ".ogg", ".aac"))
            for f in os.listdir(d)
        )

    # Strategy 1: High-Speed InnerTube YouTube Music direct video lookup
    # Bypasses datacenter bot challenge by converting query into direct YouTube video URL
    search_candidates = []
    search_query = f"{artist} {title}".strip() if artist != "Unknown Artist" else title
    logger.info(f"Resolving YouTube Music direct stream for: {search_query}")
    
    ytm_video_id = await loop.run_in_executor(None, lambda: search_youtube_music(search_query))
    if ytm_video_id:
        logger.info(f"Found YouTube Music videoId: {ytm_video_id}")
        search_candidates.append(f"https://www.youtube.com/watch?v={ytm_video_id}")

    # Strategy 2: SoundCloud Search fallback
    search_candidates.append(f"scsearch1:{search_query}")

    # Strategy 3: Standard ytsearch fallback
    search_candidates.append(f"ytsearch1:{search_query}")

    info = None
    last_err = None
    for target in search_candidates:
        logger.info(f"Attempting Spotify audio download via: {target}")
        try:
            cur_info = await loop.run_in_executor(None, lambda t=target: _download(t))
            if _has_audio(output_dir):
                info = cur_info
                logger.info(f"Successfully downloaded audio stream via: {target}")
                break
        except Exception as e:
            last_err = e
            logger.warning(f"Audio target '{target}' failed: {e}")

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
        err_msg = f": {last_err}" if last_err else f" (no audio found for '{artist} - {title}')"
        raise RuntimeError(f"Spotify audio download failed{err_msg}")

    main_file = mp3_files[0]
    duration = expected_duration
    if info and "entries" in info and info["entries"]:
        duration = int(info["entries"][0].get("duration") or duration)
    elif info and "duration" in info and info["duration"]:
        duration = int(info["duration"])

    # Download high-res cover art
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
    tag_mp3(
        main_file,
        title=title,
        artist=artist,
        album=album,
        cover_path=cover_path if os.path.exists(cover_path) else None
    )

    return MediaResult(
        media_type="audio",
        file_path=main_file,
        title=title,
        artist=artist,
        duration=duration,
        thumbnail_path=cover_path if os.path.exists(cover_path) else None,
        caption=f"🎵 **{artist} - {title}**\n✨ High-Quality 320kbps MP3"
    )
