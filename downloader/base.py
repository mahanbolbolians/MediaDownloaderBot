from dataclasses import dataclass, field
from typing import List

@dataclass
class MediaResult:
    media_type: str  # "video", "audio", "photo", "album"
    file_path: str = ""
    file_paths: List[str] = field(default_factory=list)  # for albums / carousels
    title: str = ""
    artist: str = ""
    duration: int = 0  # seconds
    width: int = 0
    height: int = 0
    thumbnail_path: str | None = None
    caption: str = ""
