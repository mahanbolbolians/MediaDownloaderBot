import os
import asyncio
import logging
import yt_dlp
from downloader.base import MediaResult
from utils.media_tagger import generate_video_thumbnail

logger = logging.getLogger(__name__)

async def download_generic(url: str, output_dir: str, is_audio_only: bool = False) -> MediaResult:
    """
    Downloads media using yt-dlp (supports YouTube, TikTok, Instagram, SoundCloud, Pinterest, X, Reddit, etc.)
    """
    os.makedirs(output_dir, exist_ok=True)
    out_template = os.path.join(output_dir, "%(title).50s.%(ext)s")

    if is_audio_only:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": out_template,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }],
            "writethumbnail": True,
            "quiet": True,
            "no_warnings": True,
        }
    else:
        ydl_opts = {
            # Highest quality video up to 1080p, remuxed into standard mp4
            "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
            "outtmpl": out_template,
            "merge_output_format": "mp4",
            "writethumbnail": True,
            "quiet": True,
            "no_warnings": True,
        }

    loop = asyncio.get_running_loop()

    def _extract_and_download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info

    info = await loop.run_in_executor(None, _extract_and_download)

    title = info.get("title", "Media")
    duration = int(info.get("duration") or 0)
    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    artist = info.get("uploader") or info.get("artist") or ""

    # Find the downloaded file
    downloaded_files = [
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if not f.endswith((".jpg", ".png", ".webp", ".part", ".ytdl"))
    ]

    if not downloaded_files:
        raise RuntimeError("Download completed but no output file was found.")

    main_file = downloaded_files[0]
    ext = os.path.splitext(main_file)[1].lower()

    # Look for thumbnail
    thumb_path = None
    for f in os.listdir(output_dir):
        if f.endswith((".jpg", ".jpeg", ".png", ".webp")):
            thumb_path = os.path.join(output_dir, f)
            break

    # If it's a video and no thumbnail was saved, generate one frame with ffmpeg
    if ext in [".mp4", ".mkv", ".webm"] and (not thumb_path or thumb_path.endswith(".webp")):
        new_thumb = os.path.join(output_dir, "thumb.jpg")
        generated = generate_video_thumbnail(main_file, new_thumb)
        if generated:
            thumb_path = generated

    media_type = "audio" if is_audio_only or ext in [".mp3", ".m4a", ".flac", ".ogg", ".opus"] else "video"

    return MediaResult(
        media_type=media_type,
        file_path=main_file,
        title=title,
        artist=artist,
        duration=duration,
        width=width,
        height=height,
        thumbnail_path=thumb_path,
        caption=f"🎬 **{title}**" if media_type == "video" else f"🎵 **{title}** - `{artist}`"
    )
