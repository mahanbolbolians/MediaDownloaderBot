import os
import shutil
import asyncio
import logging
import yt_dlp
from downloader.base import MediaResult
from downloader.instagram_patch import apply_instagram_patch
from utils.media_tagger import generate_video_thumbnail

logger = logging.getLogger(__name__)

# Apply Instagram photo patch
apply_instagram_patch()

async def download_generic(url: str, output_dir: str, is_audio_only: bool = False) -> MediaResult:
    """
    Downloads media using yt-dlp (supports YouTube, TikTok, Instagram, SoundCloud, Pinterest, X, Reddit, etc.)
    """
    os.makedirs(output_dir, exist_ok=True)
    out_template = os.path.join(output_dir, "%(title).50s_%(id)s.%(ext)s")

    has_ffmpeg = shutil.which("ffmpeg") is not None

    if is_audio_only:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": out_template,
            "writethumbnail": True,
            "quiet": True,
            "no_warnings": True,
        }
        if has_ffmpeg:
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }]
    else:
        if has_ffmpeg:
            format_selector = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best/photo/all"
            ydl_opts = {
                "format": format_selector,
                "outtmpl": out_template,
                "merge_output_format": "mp4",
                "writethumbnail": True,
                "quiet": True,
                "no_warnings": True,
            }
        else:
            format_selector = "best[ext=mp4]/best/photo/all"
            ydl_opts = {
                "format": format_selector,
                "outtmpl": out_template,
                "writethumbnail": True,
                "quiet": True,
                "no_warnings": True,
            }

    loop = asyncio.get_running_loop()

    def _extract_and_download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=True)

    info = await loop.run_in_executor(None, _extract_and_download)

    title = info.get("title") or "Media"
    duration = int(info.get("duration") or 0)
    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    artist = info.get("uploader") or info.get("artist") or ""

    # Find all downloaded files
    downloaded_files = [
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if not f.endswith((".part", ".ytdl")) and os.path.isfile(os.path.join(output_dir, f))
    ]

    if not downloaded_files:
        raise RuntimeError("Download completed but no output file was found.")

    video_files = [f for f in downloaded_files if f.lower().endswith((".mp4", ".mkv", ".webm", ".mov"))]
    audio_files = [f for f in downloaded_files if f.lower().endswith((".mp3", ".m4a", ".flac", ".ogg", ".opus", ".aac"))]
    photo_files = [f for f in downloaded_files if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]

    if video_files:
        main_file = video_files[0]
        thumb_path = photo_files[0] if photo_files else None
        if not thumb_path and has_ffmpeg:
            new_thumb = os.path.join(output_dir, "thumb.jpg")
            thumb_path = generate_video_thumbnail(main_file, new_thumb)

        return MediaResult(
            media_type="video",
            file_path=main_file,
            title=title,
            artist=artist,
            duration=duration,
            width=width,
            height=height,
            thumbnail_path=thumb_path,
            caption=f"🎬 **{title}**"
        )
    elif audio_files or is_audio_only:
        main_file = audio_files[0] if audio_files else downloaded_files[0]
        thumb_path = photo_files[0] if photo_files else None
        return MediaResult(
            media_type="audio",
            file_path=main_file,
            title=title,
            artist=artist,
            duration=duration,
            thumbnail_path=thumb_path,
            caption=f"🎵 **{title}** - `{artist}`"
        )
    elif photo_files:
        if len(photo_files) == 1:
            return MediaResult(
                media_type="photo",
                file_path=photo_files[0],
                title=title,
                caption=f"🖼️ **{title}**"
            )
        else:
            return MediaResult(
                media_type="album",
                file_paths=photo_files,
                title=title,
                caption=f"🖼️ **{title}** ({len(photo_files)} photos)"
            )
    else:
        return MediaResult(
            media_type="document",
            file_path=downloaded_files[0],
            title=title,
            caption=f"📁 **{title}**"
        )
