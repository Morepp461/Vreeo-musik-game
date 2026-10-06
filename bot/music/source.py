import asyncio
import yt_dlp
from urllib.parse import urlparse
BASE={"quiet":True,"no_warnings":True,"noplaylist":True,"format":"bestaudio/best","skip_download":True}
async def resolve(query,requested_by):
    parsed=urlparse(query); is_url=bool(parsed.scheme and parsed.netloc)
    opts={**BASE,**({} if is_url else {"default_search":"ytsearch"})}
    info=await asyncio.to_thread(lambda:yt_dlp.YoutubeDL(opts).extract_info(query,download=False))
    if info.get("entries"): info=next((x for x in info["entries"] if x),None)
    if not info: raise ValueError("Track tidak ditemukan")
    return {"title":info.get("title","Unknown"),"webpage_url":info.get("webpage_url") or info.get("original_url"),"stream_url":info.get("url"),"duration":info.get("duration"),"thumbnail":info.get("thumbnail"),"uploader":info.get("uploader"),"requested_by":requested_by}
