import logging
import json
import yt_dlp
from yt_dlp.extractor.instagram import InstagramIE, InstagramBaseIE
from yt_dlp.utils import traverse_obj, ExtractorError

logger = logging.getLogger(__name__)

_patched = False

def apply_instagram_patch():
    global _patched
    if _patched:
        return

    orig_extract_product_media = InstagramBaseIE._extract_product_media
    orig_raise_no_formats = InstagramIE.raise_no_formats
    orig_real_extract = InstagramIE._real_extract

    def patched_extract_product_media(self, product_media):
        res = orig_extract_product_media(self, product_media)
        formats = res.get("formats") or []

        # If formats is empty, it is a photo post or carousel image slide
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
                # Pick the highest-resolution candidate
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

    def patched_raise_no_formats(self, msg="No video formats found!", expected=False):
        if "There is no video in this post" in msg or "No video formats found" in msg:
            return
        orig_raise_no_formats(self, msg=msg, expected=expected)

    def patched_real_extract(self, url):
        try:
            return orig_real_extract(self, url)
        except ExtractorError as e:
            if "There is no video in this post" in str(e) or "No video formats found" in str(e):
                logger.info("[+] Instagram photo post detected in fallback, extracting image format...")
                video_id = self._match_id(url)
                webpage, urlh = self._download_webpage_handle(f"https://www.instagram.com/p/{video_id}", video_id)
                
                media = traverse_obj(webpage, (
                    {self._SJS_RE.findall}, ..., {json.loads},
                    'require', ..., ..., ..., '__bbox', 'require',
                    lambda _, v: v[0] == 'RelayPrefetchedStreamCache', ...,
                    lambda _, v: v['__bbox']['result']['data']['xig_polaris_media'],
                    '__bbox', 'result', 'data', 'xig_polaris_media', {dict}, any))
                product_info = traverse_obj(media, ('if_not_gated_logged_out', {dict}))
                
                if product_info:
                    info = self._extract_product(product_info, video_id=video_id, get_comments=False)
                    return info
            raise e

    InstagramBaseIE._extract_product_media = patched_extract_product_media
    InstagramIE.raise_no_formats = patched_raise_no_formats
    InstagramIE._real_extract = patched_real_extract

    _patched = True
    logger.info("[+] Instagram photo & carousel patch applied successfully.")
