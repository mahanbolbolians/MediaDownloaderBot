import time
import math
import logging

logger = logging.getLogger(__name__)

def human_bytes(size: int | float) -> str:
    if not size or math.isnan(size):
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.1f} {units[i]}"

class ProgressTracker:
    def __init__(self, message, action: str = "Downloading"):
        self.message = message
        self.action = action
        self.last_update_time = 0
        self.update_interval = 3.5  # seconds (respect Telegram edit message rate limit)

    async def update(self, current: int, total: int):
        now = time.time()
        if now - self.last_update_time < self.update_interval:
            return

        if not total or total <= 0:
            text = f"⏳ **{self.action}...**\n📦 `{human_bytes(current)}`"
        else:
            percentage = min(100.0, (current / total) * 100)
            completed_bars = int(percentage / 10)
            progress_bar = "█" * completed_bars + "░" * (10 - completed_bars)
            text = (
                f"⏳ **{self.action}...**\n"
                f"`[{progress_bar}]` {percentage:.1f}%\n"
                f"📦 `{human_bytes(current)}` / `{human_bytes(total)}`"
            )

        try:
            self.last_update_time = now
            await self.message.edit_text(text)
        except Exception:
            pass
