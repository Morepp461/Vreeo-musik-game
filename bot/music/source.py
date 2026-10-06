import asyncio
from urllib.parse import urlparse
import yt_dlp

BASE={
    "quiet":True,
    "no_warnings":True,
    "noplaylist":True,
    "format":"bestaudio/best",
    "skip_download":True,
}

def _extract(query,opts):
    return yt_dlp.YoutubeDL(opts).extract_info(query,download=False)

async def _run(query,opts,timeout=25):
    return await asyncio.wait_for(asyncio.to_thread(_extract,query,opts),timeout=timeout)

def is_spotify(query:str)->bool:
    try:
        return urlparse(query).hostname in {"open.spotify.com","spotify.com","www.spotify.com"}
    except Exception:
        return False

async def resolve(query:str,requested_by:int):
    if is_spotify(query):
        raise ValueError("Spotify audio belum di-rip. Gunakan URL Spotify sebagai metadata setelah Spotify API dikonfigurasi.")
    parsed=urlparse(query)
    is_url=bool(parsed.scheme and parsed.netloc)
    opts={**BASE}
    if not is_url:
        opts["default_search"]="ytsearch1"
    info=await _run(query,opts)
    if info.get("entries"):
        info=next((x for x in info["entries"] if x),None)
    if not info:
        raise ValueError("Track tidak ditemukan.")
    return {
        "title":info.get("title","Unknown"),
        "webpage_url":info.get("webpage_url") or info.get("original_url") or query,
        "stream_url":info.get("url"),
        "duration":info.get("duration"),
        "thumbnail":info.get("thumbnail"),
        "uploader":info.get("uploader"),
        "requested_by":requested_by,
    }

async def search(query:str,limit:int=5):
    if is_spotify(query):
        return []
    opts={"quiet":True,"no_warnings":True,"default_search":f"ytsearch{min(max(limit,1),10)}","skip_download":True,"extract_flat":"discard_in_playlist"}
    info=await _run(query,opts,20)
    out=[]
    for item in info.get("entries") or []:
        if not item: continue
        out.append({
            "title":item.get("title","Unknown"),
            "webpage_url":item.get("webpage_url") or item.get("url"),
            "duration":item.get("duration"),
            "thumbnail":item.get("thumbnail"),
            "uploader":item.get("uploader"),
        })
    return out[:limit]

async def resolve_playlist(url:str,requested_by:int,limit:int=100):
    if is_spotify(url):
        raise ValueError("Spotify playlist rich metadata requires Spotify API credentials.")
    opts={**BASE,"noplaylist":False,"extract_flat":"in_playlist"}
    info=await _run(url,opts,40)
    entries=[]
    for item in info.get("entries") or []:
        if not item: continue
        entries.append(TrackData(item,requested_by))
        if len(entries)>=limit: break
    if not entries:
        return [await resolve(url,requested_by)]
    return entries

def TrackData(info,requested_by):
    from .queue import Track
    return Track(
        title=info.get("title","Unknown"),
        webpage_url=info.get("webpage_url") or info.get("url"),
        duration=info.get("duration"),
        thumbnail=info.get("thumbnail"),
        uploader=info.get("uploader"),
        requested_by=requested_by,
    )
