import logging
import json
import yt_dlp
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.extractor.instagram import InstagramIE, InstagramBaseIE
from yt_dlp.extractor.pinterest import PinterestIE
from yt_dlp.utils import traverse_obj, ExtractorError

logger = logging.getLogger(__name__)

_patched = False

def populate_photo_formats(info_dict):
    """
    Universally synthesizes a valid 'photo' format for any media entry
    (Instagram, Pinterest, Twitter/X, Reddit, etc.) that contains image thumbnails
    but has no video stream.
    """
    if not isinstance(info_dict, dict):
        return

    # If it's a playlist / multi-item carousel, populate each entry recursively
    if info_dict.get("_type") in ("playlist", "multi_video") and info_dict.get("entries"):
        for entry in info_dict["entries"]:
            populate_photo_formats(entry)
        return

    # If formats already exist, nothing to do
    if info_dict.get("formats"):
        return

    # Gather potential image sources
    thumbs = info_dict.get("thumbnails") or []
    if not thumbs and info_dict.get("thumbnail"):
        thumbs = [{"url": info_dict["thumbnail"]}]

    if not thumbs and info_dict.get("url"):
        raw_url = info_dict["url"].split("?")[0].lower()
        if any(raw_url.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
            thumbs = [{"url": info_dict["url"]}]

    if thumbs:
        best_thumb = max(thumbs, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0)) if thumbs else thumbs[0]
        thumb_url = best_thumb.get("url")
        if thumb_url:
            ext = "jpg"
            clean_url = thumb_url.split("?")[0].lower()
            for e in ("png", "webp", "jpeg", "jpg", "gif"):
                if clean_url.endswith("." + e):
                    ext = "jpg" if e == "jpeg" else e
                    break

            info_dict["formats"] = [{
                "url": thumb_url,
                "ext": ext,
                "format_id": "photo",
                "vcodec": "none",
                "acodec": "none",
                "width": best_thumb.get("width"),
                "height": best_thumb.get("height"),
                "protocol": "https",
            }]

def apply_universal_patch():
    """
    Applies universal photo & video fixes across all extractors and yt-dlp core.
    """
    global _patched
    if _patched:
        return

    # --- 1. Universal Core Patches on YoutubeDL ---
    orig_process_ie = yt_dlp.YoutubeDL.process_ie_result
    def patched_process_ie(self, ie_result, download=True, extra_info=None):
        populate_photo_formats(ie_result)
        return orig_process_ie(self, ie_result, download=download, extra_info=extra_info)
    yt_dlp.YoutubeDL.process_ie_result = patched_process_ie

    orig_process_video = yt_dlp.YoutubeDL.process_video_result
    def patched_process_video(self, info_dict, download=True):
        populate_photo_formats(info_dict)
        return orig_process_video(self, info_dict, download=download)
    yt_dlp.YoutubeDL.process_video_result = patched_process_video

    orig_raise_no_formats = InfoExtractor.raise_no_formats
    def patched_common_raise_no_formats(self, msg="No video formats found!", expected=False, video_id=None):
        if "No video formats found" in str(msg) or "There is no video in this post" in str(msg):
            # Suppress exception if thumbnails/images might be present
            return
        orig_raise_no_formats(self, msg=msg, expected=expected, video_id=video_id)
    InfoExtractor.raise_no_formats = patched_common_raise_no_formats

    # --- 2. Pinterest Specific Patch (extracts original full-res 'orig' image) ---
    orig_pinterest_extract_video = PinterestIE._extract_video
    def patched_pinterest_extract_video(self, data, extract_formats=True):
        res = orig_pinterest_extract_video(self, data, extract_formats=extract_formats)
        if not res.get("formats"):
            images = data.get("images") or {}
            orig_img = images.get("orig") if isinstance(images, dict) else None
            thumbs = res.get("thumbnails") or []
            if orig_img and orig_img.get("url"):
                res["formats"] = [{
                    "url": orig_img["url"],
                    "ext": "jpg",
                    "format_id": "photo",
                    "width": orig_img.get("width"),
                    "height": orig_img.get("height"),
                    "vcodec": "none",
                    "acodec": "none",
                    "protocol": "https",
                }]
            elif thumbs:
                best = max(thumbs, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0))
                res["formats"] = [{
                    "url": best["url"],
                    "ext": "jpg",
                    "format_id": "photo",
                    "width": best.get("width"),
                    "height": best.get("height"),
                    "vcodec": "none",
                    "acodec": "none",
                    "protocol": "https",
                }]
        return res
    PinterestIE._extract_video = patched_pinterest_extract_video

    # --- 3. Instagram Specific Patch (carousels & photo posts) ---
    orig_ig_extract_product_media = InstagramBaseIE._extract_product_media
    def patched_ig_extract_product_media(self, product_media):
        res = orig_ig_extract_product_media(self, product_media)
        formats = res.get("formats") or []
        if not formats:
            thumbs = res.get("thumbnails") or []
            if not thumbs:
                thumbs = traverse_obj(product_media, (
                    "image_versions2", "candidates",
                    lambda _, v: v.get("url"), {
                        "url": "url",
                        "width": ("width", int),
                        "height": ("height", int),
                    }
                )) or []
            if not thumbs:
                thumbs = traverse_obj(product_media, (
                    "display_resources", ..., {
                        "url": "src",
                        "width": ("config_width", int),
                        "height": ("config_height", int),
                    }
                )) or []
            if not thumbs:
                durl = traverse_obj(product_media, ("display_url", str))
                if durl:
                    thumbs = [{"url": durl}]

            if thumbs:
                best_thumb = max(thumbs, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0)) if thumbs else thumbs[0]
                res["thumbnails"] = thumbs
                res["formats"] = [{
                    "url": best_thumb["url"],
                    "ext": "jpg",
                    "format_id": "photo",
                    "vcodec": "none",
                    "acodec": "none",
                    "width": best_thumb.get("width"),
                    "height": best_thumb.get("height"),
                    "protocol": "https",
                }]
        return res
    InstagramBaseIE._extract_product_media = patched_ig_extract_product_media

    # --- 4. YouTube iOS Client Anti-Bot Patch ---
    try:
        from yt_dlp.extractor.youtube._base import INNERTUBE_CLIENTS
        ios_cfg = INNERTUBE_CLIENTS.get("ios", {})
        if ios_cfg and "INNERTUBE_CONTEXT" in ios_cfg:
            ios_cfg["INNERTUBE_CONTEXT"]["client"]["clientVersion"] = "20.03.02"
            ios_cfg["INNERTUBE_CONTEXT"]["client"]["userAgent"] = "com.google.ios.youtube/20.03.02 (iPhone16,2; U; CPU iOS 18_2_1 like Mac OS X;)"
        logger.info("[+] YouTube iOS client anti-bot patch applied.")
    except Exception as e:
        logger.warning(f"[-] Could not patch YouTube iOS client: {e}")

    _patched = True
    logger.info("[+] Universal photo & video patch applied successfully across all platforms.")
