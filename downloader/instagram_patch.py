import logging
import yt_dlp
from yt_dlp.extractor.instagram import InstagramIE
from yt_dlp.utils import traverse_obj
import json

logger = logging.getLogger(__name__)

_patched = False

def apply_instagram_patch():
    global _patched
    if _patched:
        return

    orig_real_extract = InstagramIE._real_extract

    def patched_real_extract(self, url):
        try:
            return orig_real_extract(self, url)
        except yt_dlp.utils.ExtractorError as e:
            if "There is no video in this post" in str(e):
                logger.info("[+] Instagram photo post detected, extracting image format...")
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
                    
                    # If it's a carousel / album of multiple items
                    if info.get('_type') == 'playlist' and 'entries' in info:
                        for entry in info['entries']:
                            thumbs = entry.get('thumbnails') or []
                            if not entry.get('formats') and thumbs:
                                best = thumbs[-1]
                                entry['formats'] = [{
                                    'url': best['url'],
                                    'ext': 'jpg',
                                    'format_id': 'photo',
                                    'vcodec': 'none',
                                    'acodec': 'none',
                                    'width': best.get('width'),
                                    'height': best.get('height'),
                                }]
                    else:
                        thumbs = info.get('thumbnails') or []
                        if thumbs:
                            best = thumbs[-1]
                            info['formats'] = [{
                                'url': best['url'],
                                'ext': 'jpg',
                                'format_id': 'photo',
                                'vcodec': 'none',
                                'acodec': 'none',
                                'width': best.get('width'),
                                'height': best.get('height'),
                            }]
                    return info
            raise e

    InstagramIE._real_extract = patched_real_extract
    _patched = True
    logger.info("[+] Instagram photo patch applied successfully.")
