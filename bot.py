import os
import shutil
import uuid
import logging
import asyncio
from hydrogram import Client, filters
from hydrogram.types import Message

# Optimization & Network Patches
import crypto_patch
import net_patch
net_patch.apply_net_patch()

from config import config
from downloader import download_media
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
        "• 📺 **YouTube** (Videos & Shorts up to 1080p)\n"
        "• 🎵 **SoundCloud** (High quality 320kbps MP3)\n"
        "• 📱 **TikTok** (Watermark-free HD videos)\n"
        "• 📸 **Instagram** (Reels & Posts)\n"
        "• 📌 **Pinterest** (Videos & Pins)\n"
        "• 🐦 **Twitter / X & Reddit**\n\n"
        "💡 **Pro-Tip:** Send `/audio <link>` or `/mp3 <link>` to convert any YouTube or video link into an MP3 song!"
    )
    await message.reply_text(welcome_text)

@app.on_message(filters.text & filters.private)
async def media_handler(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_authorized(user_id):
        await message.reply_text("⛔ You are not authorized to use this bot.")
        return

    text = message.text.strip()
    force_audio = False

    if text.startswith(("/audio", "/mp3")):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            text = parts[1].strip()
            force_audio = True
        else:
            await message.reply_text("ℹ️ Please provide a link after the command, e.g.:\n`/audio https://youtu.be/...`")
            return

    # Check if text contains http
    if "http://" not in text and "https://" not in text:
        return

    status_msg = await message.reply_text("⏳ **Analyzing link and preparing download...**")
    session_id = f"job_{uuid.uuid4().hex[:8]}"
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp", session_id)

    try:
        await status_msg.edit_text("⏳ **Downloading media...**")
        result = await download_media(text, temp_dir, force_audio=force_audio)

        await status_msg.edit_text("📤 **Uploading directly to Telegram...**")
        upload_tracker = ProgressTracker(status_msg, action="Uploading to Telegram")

        async def upload_progress(current, total):
            await upload_tracker.update(current, total)

        if result.media_type == "audio":
            await message.reply_audio(
                audio=result.file_path,
                title=result.title,
                performer=result.artist,
                duration=result.duration,
                thumb=result.thumbnail_path if result.thumbnail_path and os.path.exists(result.thumbnail_path) else None,
                caption=result.caption,
                progress=upload_progress
            )
        elif result.media_type == "video":
            await message.reply_video(
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
            await message.reply_photo(
                photo=result.file_path,
                caption=result.caption
            )

        # Delete status message on success
        try:
            await status_msg.delete()
        except Exception:
            pass

    except Exception as e:
        logger.exception(f"Error processing {text}: {e}")
        error_text = f"❌ **Download failed**: `{str(e)[:200]}`"
        try:
            await status_msg.edit_text(error_text)
        except Exception:
            await message.reply_text(error_text)

    finally:
        # Zero Disk Bloat: Clean up all temporary files immediately
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to cleanup {temp_dir}: {e}")

if __name__ == "__main__":
    logger.info("Starting MediaDownloaderBot...")
    app.run()
