import asyncio
import base64
import time
from urllib.parse import urlparse
import aiohttp
import yt_dlp
from .queue import Track
from ..config import SPOTIFY_CLIENT_ID,SPOTIFY_CLIENT_SECRET

BASE={
    "quiet":True,
    "no_warnings":True,
    "noplaylist":True,
    "format":"bestaudio/best",
    "skip_download":True,
}
_spotify_token=None
_spotify_expires=0.0

def _extract(query,opts):
    return yt_dlp.YoutubeDL(opts).extract_info(query,download=False)

async def _run(query,opts,timeout=25):
    return await asyncio.wait_for(asyncio.to_thread(_extract,query,opts),timeout=timeout)

def is_spotify(query:str)->bool:
    try:
        return (urlparse(query).hostname or "").lower() in {"open.spotify.com","spotify.com","www.spotify.com"}
    except Exception:
        return False

def _spotify_configured():
    return bool(SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET)

async def _spotify_access_token():
    global _spotify_token,_spotify_expires
    if not _spotify_configured():
        raise ValueError("Spotify API belum dikonfigurasi.")
    if _spotify_token and time.time() < _spotify_expires-30:
        return _spotify_token
    raw=base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
    timeout=aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post("https://accounts.spotify.com/api/token",data={"grant_type":"client_credentials"},headers={"Authorization":f"Basic {raw}"}) as r:
            if r.status != 200:
                raise ValueError("Spotify authentication gagal.")
            data=await r.json()
    _spotify_token=data["access_token"]
    _spotify_expires=time.time()+int(data.get("expires_in",3600))
    return _spotify_token

async def _spotify_api(path,params=None):
    token=await _spotify_access_token()
    timeout=aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get("https://api.spotify.com/v1/"+path,params=params,headers={"Authorization":f"Bearer {token}"}) as r:
            if r.status >= 400:
                raise ValueError(f"Spotify API error ({r.status}).")
            return await r.json()

def _spotify_url(kind,item_id):
    return f"https://open.spotify.com/{kind}/{item_id}"

def _track_query(item):
    artists=", ".join(a["name"] for a in item.get("artists",[]))
    return f"{artists} - {item.get('name','')}"

async def spotify_search(query,limit=5):
    data=await _spotify_api("search",{"q":query,"type":"track","limit":min(max(limit,1),10)})
    out=[]
    for item in data.get("tracks",{}).get("items",[]):
        out.append({
            "title":f"{item.get('name','Unknown')} — {', '.join(a['name'] for a in item.get('artists',[]))}",
            "webpage_url":_spotify_url("track",item["id"]),
            "duration":(item.get("duration_ms") or 0)/1000,
            "thumbnail":((item.get("album",{}).get("images") or [{}])[0].get("url")),
            "uploader":", ".join(a["name"] for a in item.get("artists",[])),
            "spotify_query":_track_query(item),
        })
    return out

async def _spotify_track_from_url(url):
    item_id=urlparse(url).path.rstrip("/").split("/")[-1]
    return await _spotify_api(f"tracks/{item_id}")

async def _spotify_items_from_collection(url,kind,limit):
    item_id=urlparse(url).path.rstrip("/").split("/")[-1]
    endpoint=f"{kind}/{item_id}/tracks"
    out=[]
    offset=0
    while len(out)<limit:
        data=await _spotify_api(endpoint,{"limit":50,"offset":offset})
        items=data.get("items",[])
        if not items: break
        for item in items:
            track=item.get("track",item)
            if track: out.append(track)
            if len(out)>=limit: break
        if len(items)<50: break
        offset+=50
    return out[:limit]

async def resolve_spotify(query,requested_by):
    parsed=urlparse(query)
    path=parsed.path.strip("/").split("/")
    if len(path)>=2 and path[0]=="track":
        item=await _spotify_track_from_url(query)
    else:
        raise ValueError("Spotify URL harus berupa track untuk /play langsung.")
    yt=await resolve(_track_query(item),requested_by)
    yt["title"]=f"{item.get('name','Unknown')} — {', '.join(a['name'] for a in item.get('artists',[]))}"
    yt["thumbnail"]=((item.get("album",{}).get("images") or [{}])[0].get("url")) or yt.get("thumbnail")
    return yt

async def resolve(query:str,requested_by:int):
    if is_spotify(query):
        return await resolve_spotify(query,requested_by)
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
    results=[]
    if _spotify_configured():
        try:
            results.extend(await spotify_search(query,limit))
        except Exception:
            pass
    opts={"quiet":True,"no_warnings":True,"default_search":f"ytsearch{min(max(limit,1),10)}","skip_download":True,"extract_flat":"discard_in_playlist"}
    info=await _run(query,opts,20)
    for item in info.get("entries") or []:
        if not item: continue
        item_url=item.get("webpage_url") or item.get("url")
        if item_url and not str(item_url).startswith(("http://","https://")):
            item_url=f"https://www.youtube.com/watch?v={item_url}"
        results.append({
            "title":item.get("title","Unknown"),
            "webpage_url":item_url,
            "duration":item.get("duration"),
            "thumbnail":item.get("thumbnail"),
            "uploader":item.get("uploader"),
        })
    return results[:limit]

async def resolve_playlist(url:str,requested_by:int,limit:int=100):
    if is_spotify(url):
        parsed=urlparse(url)
        kind=parsed.path.strip("/").split("/")[0]
        if kind not in {"playlist","album"}:
            return [Track(**(await resolve(url,requested_by)))]
        items=await _spotify_items_from_collection(url,kind,limit)
        tracks=[]
        for item in items:
            try:
                data=await resolve(_track_query(item),requested_by)
                data["title"]=f"{item.get('name','Unknown')} — {', '.join(a['name'] for a in item.get('artists',[]))}"
                tracks.append(Track(**data))
            except Exception:
                continue
        return tracks
    opts={**BASE,"noplaylist":False,"extract_flat":"in_playlist"}
    info=await _run(url,opts,40)
    entries=[]
    for item in info.get("entries") or []:
        if not item: continue
        entries.append(TrackData(item,requested_by))
        if len(entries)>=limit: break
    if not entries:
        return [Track(**(await resolve(url,requested_by)))]
    return entries

def TrackData(info,requested_by):
    url=info.get("webpage_url") or info.get("url")
    if url and not str(url).startswith(("http://","https://")):
        url=f"https://www.youtube.com/watch?v={url}"
    return Track(
        title=info.get("title","Unknown"),
        webpage_url=url,
        duration=info.get("duration"),
        thumbnail=info.get("thumbnail"),
        uploader=info.get("uploader"),
        requested_by=requested_by,
    )
