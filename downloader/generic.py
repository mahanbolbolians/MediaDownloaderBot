import os
import shutil
import asyncio
import logging
import yt_dlp
from downloader.base import MediaResult
from downloader.universal_patch import apply_universal_patch
from utils.media_tagger import generate_video_thumbnail

logger = logging.getLogger(__name__)

# Apply Universal photo & platform patches
apply_universal_patch()

def _get_cookiefile(output_dir: str) -> str | None:
    """Check for local cookies.txt or YOUTUBE_COOKIES environment variable."""
    if os.path.exists("cookies.txt"):
        return os.path.abspath("cookies.txt")
    
    cookies_env = os.environ.get("YOUTUBE_COOKIES")
    if cookies_env:
        cookie_path = os.path.join(output_dir, "cookies.txt")
        try:
            with open(cookie_path, "w", encoding="utf-8") as f:
                f.write(cookies_env)
            return cookie_path
        except Exception as e:
            logger.warning(f"Failed to write cookies from environment: {e}")
    return None

async def download_generic(
    url: str,
    output_dir: str,
    is_audio_only: bool = False,
    target_quality: int | None = None
) -> MediaResult:
    """
    Downloads media using yt-dlp with support for all platforms, dynamic video quality, and photos.
    """
    os.makedirs(output_dir, exist_ok=True)
    out_template = os.path.join(output_dir, "%(title).50s_%(id)s.%(ext)s")

    has_ffmpeg = shutil.which("ffmpeg") is not None
    cookie_file = _get_cookiefile(output_dir)

    extractor_args = {
        "youtube": {
            "player_client": ["android", "ios", "mweb"]
        }
    }

    if is_audio_only:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": out_template,
            "writethumbnail": True,
            "quiet": True,
            "no_warnings": True,
            "extractor_args": extractor_args,
        }
        if has_ffmpeg:
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }]
    else:
        max_q = target_quality or 1080
        if has_ffmpeg:
            format_selector = (
                f"bestvideo[height<={max_q}][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={max_q}]+bestaudio/"
                f"best[height<={max_q}][ext=mp4]/"
                f"best[height<={max_q}]/"
                f"best/photo"
            )
            ydl_opts = {
                "format": format_selector,
                "outtmpl": out_template,
                "merge_output_format": "mp4",
                "writethumbnail": True,
                "quiet": True,
                "no_warnings": True,
                "extractor_args": extractor_args,
            }
        else:
            format_selector = f"best[height<={max_q}][ext=mp4]/best[height<={max_q}]/best/photo"
            ydl_opts = {
                "format": format_selector,
                "outtmpl": out_template,
                "writethumbnail": True,
                "quiet": True,
                "no_warnings": True,
                "extractor_args": extractor_args,
            }

    if cookie_file and os.path.exists(cookie_file):
        ydl_opts["cookiefile"] = cookie_file

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
        if not f.endswith((".part", ".ytdl", ".txt")) and os.path.isfile(os.path.join(output_dir, f))
    ]

    if not downloaded_files:
        raise RuntimeError("Download completed but no output file was found.")

    video_files = sorted([f for f in downloaded_files if f.lower().endswith((".mp4", ".mkv", ".webm", ".mov"))])
    audio_files = sorted([f for f in downloaded_files if f.lower().endswith((".mp3", ".m4a", ".flac", ".ogg", ".opus", ".aac"))])
    photo_files = sorted([f for f in downloaded_files if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))])

    video_basenames = {os.path.splitext(v)[0] for v in video_files}
    standalone_photos = [p for p in photo_files if os.path.splitext(p)[0] not in video_basenames]

    # Single video case
    if len(video_files) == 1 and not standalone_photos:
        main_file = video_files[0]
        thumb_candidates = [p for p in photo_files if os.path.splitext(p)[0] in video_basenames]
        thumb_path = thumb_candidates[0] if thumb_candidates else None
        if not thumb_path and has_ffmpeg:
            new_thumb = os.path.join(output_dir, "thumb.jpg")
            thumb_path = generate_video_thumbnail(main_file, new_thumb)

        quality_badge = f" [{height}p]" if height else ""
        return MediaResult(
            media_type="video",
            file_path=main_file,
            title=title,
            artist=artist,
            duration=duration,
            width=width,
            height=height,
            thumbnail_path=thumb_path,
            caption=f"🎬 **{title}**{quality_badge}"
        )

    # Audio only or audio file returned
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

    # Carousel or multiple media items (photos or videos)
    elif len(video_files) > 1 or (video_files and standalone_photos) or len(standalone_photos) > 1:
        album_files = standalone_photos + video_files
        return MediaResult(
            media_type="album",
            file_paths=album_files,
            title=title,
            caption=f"🖼️ **{title}** ({len(album_files)} items)"
        )

    # Single standalone photo
    elif len(standalone_photos) == 1:
        return MediaResult(
            media_type="photo",
            file_path=standalone_photos[0],
            title=title,
            caption=f"🖼️ **{title}**"
        )

    # Fallback to single photo if any photo exists
    elif photo_files:
        return MediaResult(
            media_type="photo",
            file_path=photo_files[0],
            title=title,
            caption=f"🖼️ **{title}**"
        )

    else:
        return MediaResult(
            media_type="document",
            file_path=downloaded_files[0],
            title=title,
            caption=f"📁 **{title}**"
        )
