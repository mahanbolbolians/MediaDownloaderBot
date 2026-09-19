import os
import shutil
import uuid
import time
import logging
import asyncio
from hydrogram import Client, filters
from hydrogram.types import (
    Message,
    InputMediaPhoto,
    InputMediaVideo,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

# Optimization & Network Patches
import crypto_patch
import net_patch
net_patch.apply_net_patch()

from config import config
from downloader import download_media
from downloader.detector import detect_url
from utils.progress import ProgressTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s"
)
logger = logging.getLogger("MediaDownloaderBot")

app = Client(
    "media_downloader_bot",
    api_id=config["api_id"],
    api_hash=config["api_hash"],
    bot_token=config["bot_token"],
    in_memory=True
)

ALLOWED_USERS = set(config.get("allowed_users", []))

# In-memory store for pending YouTube quality choices: {job_id: (url, timestamp)}
PENDING_JOBS: dict[str, tuple[str, float]] = {}

def cleanup_pending_jobs():
    """Purge pending selection jobs older than 1 hour."""
    now = time.time()
    expired = [k for k, (_, ts) in PENDING_JOBS.items() if now - ts > 3600]
    for k in expired:
        PENDING_JOBS.pop(k, None)

def is_authorized(user_id: int) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS

@app.on_message(filters.command(["start", "help"]))
async def start_handler(client: Client, message: Message):
    welcome_text = (
        "👋 **Welcome to Universal Media Downloader Bot!**\n\n"
        "Just send or forward any link here and I will upload the media directly into this chat:\n\n"
        "✨ **Supported Platforms:**\n"
        "• 🟢 **Spotify** (Tracks, Albums with high-res cover & tags)\n"
        "• 📺 **YouTube** (Quality Selector: 1080p, 720p, 480p, 360p or MP3)\n"
        "• 🎵 **SoundCloud** (High quality 320kbps MP3)\n"
        "• 📱 **TikTok** (Watermark-free HD videos)\n"
        "• 📸 **Instagram** (Reels, Posts, Carousels & Photos)\n"
        "• 📌 **Pinterest** (Videos & high-res image Pins)\n"
        "• 🐦 **Twitter / X & Reddit**\n\n"
        "💡 **Quick Shortcuts:**\n"
        "• Send a YouTube link to pick quality interactively\n"
        "• `/720 <link>` or `/1080 <link>` to download in that quality directly\n"
        "• `/audio <link>` or `/mp3 <link>` to convert any video into an MP3"
    )
    await message.reply_text(welcome_text)

async def process_and_upload(
    client: Client,
    target_chat_id: int,
    original_message: Message,
    status_msg: Message,
    url: str,
    force_audio: bool = False,
    target_quality: int | None = None
):
    """Handles the full download, progress tracking, upload, and cleanup pipeline."""
    session_id = f"job_{uuid.uuid4().hex[:8]}"
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp", session_id)

    try:
        quality_str = f" [{target_quality}p]" if target_quality else ""
        mode_str = " [MP3 Audio]" if force_audio else quality_str
        await status_msg.edit_text(f"⏳ **Downloading media{mode_str}...**")

        result = await download_media(
            url,
            temp_dir,
            force_audio=force_audio,
            target_quality=target_quality
        )

        await status_msg.edit_text("📤 **Uploading directly to Telegram...**")
        upload_tracker = ProgressTracker(status_msg, action="Uploading to Telegram")

        async def upload_progress(current, total):
            await upload_tracker.update(current, total)

        if result.media_type == "audio":
            await original_message.reply_audio(
                audio=result.file_path,
                title=result.title,
                performer=result.artist,
                duration=result.duration,
                thumb=result.thumbnail_path if result.thumbnail_path and os.path.exists(result.thumbnail_path) else None,
                caption=result.caption,
                progress=upload_progress
            )
        elif result.media_type == "video":
            await original_message.reply_video(
                video=result.file_path,
                caption=result.caption,
                duration=result.duration,
                width=result.width,
                height=result.height,
                thumb=result.thumbnail_path if result.thumbnail_path and os.path.exists(result.thumbnail_path) else None,
                supports_streaming=True,
                progress=upload_progress
            )
        elif result.media_type == "photo":
            await original_message.reply_photo(
                photo=result.file_path,
                caption=result.caption
            )
        elif result.media_type == "album":
            # Send up to 10 media items per album (Telegram limit)
            for chunk_start in range(0, len(result.file_paths), 10):
                chunk = result.file_paths[chunk_start:chunk_start+10]
                media_group = []
                for i, p in enumerate(chunk):
                    cap = result.caption if (chunk_start == 0 and i == 0) else ""
                    if p.lower().endswith((".mp4", ".mkv", ".webm", ".mov")):
                        media_group.append(InputMediaVideo(p, caption=cap))
                    else:
                        media_group.append(InputMediaPhoto(p, caption=cap))
                await client.send_media_group(chat_id=target_chat_id, media=media_group)
        elif result.media_type == "document":
            await original_message.reply_document(
                document=result.file_path,
                caption=result.caption
            )

        # Delete status message on success
        try:
            await status_msg.delete()
        except Exception:
            pass

    except Exception as e:
        logger.exception(f"Error processing {url}: {e}")
        error_text = f"❌ **Download failed**: `{str(e)[:250]}`"
        try:
            await status_msg.edit_text(error_text)
        except Exception:
            await original_message.reply_text(error_text)

    finally:
        # Zero Disk Bloat: Clean up all temporary files immediately
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to cleanup {temp_dir}: {e}")

@app.on_callback_query(filters.regex(r"^yt_"))
async def youtube_quality_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id if callback_query.from_user else 0
    if not is_authorized(user_id):
        await callback_query.answer("⛔ Unauthorized", show_alert=True)
        return

    data_parts = callback_query.data.split("_")
    if len(data_parts) < 3:
        await callback_query.answer("Invalid request.", show_alert=True)
        return

    job_id = data_parts[1]
    choice = data_parts[2]

    if job_id not in PENDING_JOBS:
        await callback_query.answer("⚠️ This link selection expired. Please send the link again.", show_alert=True)
        return

    url, _ = PENDING_JOBS.pop(job_id)
    await callback_query.answer("Starting download...")

    force_audio = (choice == "audio")
    target_quality = int(choice) if choice.isdigit() else None

    # Use the message where buttons were attached as the status message
    status_msg = callback_query.message
    await process_and_upload(
        client=client,
        target_chat_id=status_msg.chat.id,
        original_message=status_msg,
        status_msg=status_msg,
        url=url,
        force_audio=force_audio,
        target_quality=target_quality
    )

@app.on_message(filters.text & filters.private)
async def media_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_authorized(user_id):
        await message.reply_text("⛔ You are not authorized to use this bot.")
        return

    text = message.text.strip()
    force_audio = False
    target_quality = None

    # Direct quality commands: /1080, /720, /480, /360, /audio, /mp3
    if text.startswith(("/audio", "/mp3")):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            text = parts[1].strip()
            force_audio = True
        else:
            await message.reply_text("ℹ️ Please provide a link after the command, e.g.:\n`/audio https://youtu.be/...`")
            return
    elif text.startswith(("/1080", "/720", "/480", "/360")):
        cmd = text.split()[0][1:]
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            text = parts[1].strip()
            target_quality = int(cmd)
        else:
            await message.reply_text(f"ℹ️ Please provide a link after the command, e.g.:\n`/{cmd} https://youtu.be/...`")
            return

    # Check if text contains http
    if "http://" not in text and "https://" not in text:
        return

    cleanup_pending_jobs()
    detection = detect_url(text)
    if not detection:
        await message.reply_text("❌ No supported link detected.")
        return

    platform, clean_url = detection

    # If YouTube and no explicit quality specified, present interactive quality buttons
    if platform == "youtube" and not force_audio and target_quality is None:
        job_id = uuid.uuid4().hex[:8]
        PENDING_JOBS[job_id] = (clean_url, time.time())

        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎬 1080p (Full HD)", callback_data=f"yt_{job_id}_1080"),
                InlineKeyboardButton("🎬 720p (HD)", callback_data=f"yt_{job_id}_720")
            ],
            [
                InlineKeyboardButton("🎬 480p (SD)", callback_data=f"yt_{job_id}_480"),
                InlineKeyboardButton("🎬 360p (Low)", callback_data=f"yt_{job_id}_360")
            ],
            [
                InlineKeyboardButton("🎵 MP3 Audio (320kbps)", callback_data=f"yt_{job_id}_audio")
            ]
        ])

        await message.reply_text(
            "🎬 **YouTube Video Detected**\n"
            f"🔗 `{clean_url}`\n\n"
            "Choose your preferred download quality:",
            reply_markup=buttons
        )
        return

    # For all other platforms or direct commands, start download immediately
    status_msg = await message.reply_text("⏳ **Analyzing link and preparing download...**")
    await process_and_upload(
        client=client,
        target_chat_id=message.chat.id,
        original_message=message,
        status_msg=status_msg,
        url=clean_url,
        force_audio=force_audio,
        target_quality=target_quality
    )

if __name__ == "__main__":
    logger.info("Starting MediaDownloaderBot...")
    app.run()
