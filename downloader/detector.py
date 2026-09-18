import re

PLATFORM_PATTERNS = {
    "spotify": re.compile(r"https?://(?:open\.spotify\.com|spotify\.link)/[^\s]+", re.IGNORECASE),
    "youtube": re.compile(r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)/[^\s]+", re.IGNORECASE),
    "tiktok": re.compile(r"https?://(?:www\.|v[mt]\.)?tiktok\.com/[^\s]+", re.IGNORECASE),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/(?:p|reel|tv|stories)/[^\s]+", re.IGNORECASE),
    "soundcloud": re.compile(r"https?://(?:www\.|on\.)?soundcloud\.com/[^\s]+", re.IGNORECASE),
    "pinterest": re.compile(r"https?://(?:[a-z]{2}\.)?(?:pinterest\.(?:com|[a-z]{2,3})|pin\.it)/[^\s]+", re.IGNORECASE),
    "twitter": re.compile(r"https?://(?:www\.)?(?:twitter\.com|x\.com)/[^\s]+", re.IGNORECASE),
    "reddit": re.compile(r"https?://(?:www\.|v\.)?reddit\.com/[^\s]+", re.IGNORECASE)
}

GENERAL_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)

def detect_url(text: str) -> tuple[str, str] | None:
    """
    Finds the first supported URL in the text and returns (platform_name, url).
    If it's a URL not in our named patterns, returns ('generic', url).
    If no URL is found, returns None.
    """
    if not text:
        return None

    for platform, pattern in PLATFORM_PATTERNS.items():
        match = pattern.search(text)
        if match:
            return platform, match.group(0)

    # Any other valid URL fallback to generic yt-dlp
    generic_match = GENERAL_URL_PATTERN.search(text)
    if generic_match:
        return "generic", generic_match.group(0)

    return None
