import aiohttp
import logging
from urllib.parse import quote

log=logging.getLogger(__name__)

async def fetch(title,artist=None):
    title=(title or "").strip()
    artist=(artist or "").strip()
    if not title:
        return None
    params={"track_name":title}
    if artist and len(artist)<120:
        params["artist_name"]=artist
    try:
        timeout=aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout,headers={"User-Agent":"Vreeo-Music/1.0"}) as session:
            async with session.get("https://lrclib.net/api/get",params=params) as r:
                if r.status==404:
                    q=" ".join(x for x in (artist,title) if x)
                    async with session.get("https://lrclib.net/api/search",params={"q":q,"limit":5}) as sr:
                        if sr.status>=400: return None
                        data=await sr.json(content_type=None)
                        if isinstance(data,list) and data:
                            best=data[0]
                        else: return None
                elif r.status>=400:
                    return None
                else:
                    best=await r.json(content_type=None)
        synced=(best.get("syncedLyrics") or "").strip()
        plain=(best.get("plainLyrics") or "").strip()
        if not synced and not plain:
            return None
        return {"title":best.get("trackName") or title,"artist":best.get("artistName") or artist,"synced":synced,"plain":plain}
    except Exception as exc:
        log.warning("Lyrics lookup failed for %r: %s",title,exc)
        return None
