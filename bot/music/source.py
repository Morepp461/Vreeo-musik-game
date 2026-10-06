import asyncio
import base64
import html
import os
import re
import json
import time
from urllib.parse import urlparse
import aiohttp
import yt_dlp
from .queue import Track
from ..config import SPOTIFY_CLIENT_ID,SPOTIFY_CLIENT_SECRET

POT_PROVIDER_URL=os.getenv("YTDL_POT_PROVIDER_URL","").rstrip("/")
BASE={
    "quiet":True,
    "no_warnings":True,
    "noplaylist":True,
    "format":"bestaudio/best",
    "skip_download":True,
    "extractor_args":{
        "youtube":{"player_client":["android_vr","web_embedded","tv"]}
    },
}
if POT_PROVIDER_URL:
    BASE["extractor_args"]["youtubepot-bgutilhttp"]={"base_url":[POT_PROVIDER_URL]}
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
                try:
                    body=await r.json(content_type=None)
                    detail=body.get("error",{}) if isinstance(body,dict) else {}
                    message=detail.get("message") or detail.get("status") or str(body)
                except Exception:
                    message=(await r.text())[:300]
                raise ValueError(f"Spotify API error ({r.status}): {message}")
            return await r.json()

def _spotify_url(kind,item_id):
    return f"https://open.spotify.com/{kind}/{item_id}"

def _track_query(item):
    artists=", ".join(a.get("name","") for a in item.get("artists",[]) if a.get("name"))
    name=item.get("name","")
    return f"{artists} - {name}" if artists else name

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

async def _spotify_oembed_track(url):
    timeout=aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get("https://open.spotify.com/oembed",params={"url":url}) as r:
            if r.status >= 400:
                raise ValueError(f"Spotify oEmbed error ({r.status}).")
            data=await r.json(content_type=None)
    title=(data.get("title") or "").strip()
    if not title:
        raise ValueError("Spotify track metadata tidak ditemukan.")
    return {
        "name":title,
        "artists":[{"name":""}],
        "album":{"images":[{"url":data.get("thumbnail_url")}]} if data.get("thumbnail_url") else {"images":[]},
    }

async def _spotify_track_from_url(url):
    item_id=urlparse(url).path.rstrip("/").split("/")[-1]
    try:
        return await _spotify_api(f"tracks/{item_id}", {"market":"ID"})
    except ValueError as e:
        if "403" not in str(e) or "Active premium subscription required" not in str(e):
            raise
        return await _spotify_oembed_track(url)

async def _spotify_embed_track_ids(url):
    item_id=urlparse(url).path.rstrip("/").split("/")[-1]
    kind="playlist" if "/playlist/" in url else "album"
    embed_url=f"https://open.spotify.com/embed/{kind}/{item_id}"
    timeout=aiohttp.ClientTimeout(total=15)
    headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36"}
    async with aiohttp.ClientSession(timeout=timeout,headers=headers) as session:
        async with session.get(embed_url) as r:
            if r.status >= 400:
                raise ValueError(f"Spotify embed error ({r.status}).")
            page=html.unescape(await r.text())

    match=re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',page,re.S)
    if match:
        try:
            data=json.loads(match.group(1))
            found=[]
            def walk(value):
                if isinstance(value,dict):
                    track_list=value.get("trackList")
                    if isinstance(track_list,list):
                        found.extend(track_list)
                    for child in value.values():
                        walk(child)
                elif isinstance(value,list):
                    for child in value:
                        walk(child)
            walk(data)
            ids=[]
            for item in found:
                uri=item.get("uri") if isinstance(item,dict) else None
                if isinstance(uri,str) and uri.startswith("spotify:track:"):
                    track_id=uri.rsplit(":",1)[-1]
                    if track_id not in ids:
                        ids.append(track_id)
            if ids:
                return ids
        except Exception:
            pass

    patterns=(r"spotify:track:([A-Za-z0-9]{22})",r"/track/([A-Za-z0-9]{22})")
    ids=[]
    for pattern in patterns:
        for track_id in re.findall(pattern,page):
            if track_id not in ids:
                ids.append(track_id)
    return ids

async def _spotify_items_from_embed(url,limit):
    item_id=urlparse(url).path.rstrip("/").split("/")[-1]
    kind="playlist" if "/playlist/" in url else "album"
    embed_url=f"https://open.spotify.com/embed/{kind}/{item_id}"
    timeout=aiohttp.ClientTimeout(total=15)
    headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36"}
    async with aiohttp.ClientSession(timeout=timeout,headers=headers) as session:
        async with session.get(embed_url) as r:
            if r.status >= 400:
                raise ValueError(f"Spotify embed error ({r.status}).")
            page=html.unescape(await r.text())

    match=re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',page,re.S)
    if not match:
        raise ValueError("Spotify playlist tidak bisa dibaca tanpa metadata track.")

    try:
        data=json.loads(match.group(1))
    except Exception as exc:
        raise ValueError("Metadata Spotify playlist rusak.") from exc

    found=[]
    def walk(value):
        if isinstance(value,dict):
            track_list=value.get("trackList")
            if isinstance(track_list,list):
                found.extend(track_list)
            for child in value.values():
                walk(child)
        elif isinstance(value,list):
            for child in value:
                walk(child)
    walk(data)

    results=[]
    seen=set()
    for item in found:
        if not isinstance(item,dict):
            continue
        uri=item.get("uri") or ""
        if not isinstance(uri,str) or not uri.startswith("spotify:track:"):
            continue
        track_id=uri.rsplit(":",1)[-1]
        if track_id in seen:
            continue
        title=(item.get("title") or item.get("name") or "").strip()
        if not title:
            continue
        seen.add(track_id)
        subtitle=(item.get("subtitle") or "").strip()
        duration=item.get("duration")
        if isinstance(duration,(int,float)):
            duration=float(duration)/1000 if duration>10000 else float(duration)
        results.append({
            "name":title,
            "artists":[{"name":subtitle}] if subtitle else [],
            "album":{"images":[]},
            "duration":duration,
            "_spotify_id":track_id,
        })
        if len(results)>=min(limit,100):
            break

    if results:
        return results

    raise ValueError("Spotify playlist tidak bisa dibaca tanpa metadata track.")

async def _spotify_items_from_collection(url,kind,limit):
    # Playlist API Spotify saat ini bisa menolak public playlist untuk app
    # client-credentials. Langsung pakai public embed agar tidak buang waktu
    # menunggu request API yang memang akan gagal.
    if kind=="playlist":
        return await _spotify_items_from_embed(url,limit)

    item_id=urlparse(url).path.rstrip("/").split("/")[-1]
    endpoint=f"{kind}/{item_id}/tracks"
    try:
        out=[]
        offset=0
        while len(out)<limit:
            data=await _spotify_api(endpoint,{"limit":50,"offset":offset,"market":"ID"})
            items=data.get("items",[])
            if not items: break
            for item in items:
                track=item.get("item",item.get("track",item))
                if track and track.get("type","track")=="track": out.append(track)
                if len(out)>=limit: break
            if len(items)<50: break
            offset+=50
        if out:
            return out[:limit]
    except ValueError as e:
        if "410" not in str(e) and "403" not in str(e):
            raise
    return await _spotify_items_from_embed(url,limit)

async def resolve_spotify(query,requested_by):
    parsed=urlparse(query)
    path=parsed.path.strip("/").split("/")
    if len(path)>=2 and path[0]=="track":
        item=await _spotify_track_from_url(query)
    else:
        raise ValueError("Spotify URL harus berupa track untuk /play langsung.")
    artist_names=", ".join(a.get("name","") for a in item.get("artists",[]) if a.get("name"))
    display_title=f"{item.get('name','Unknown')}" + (f" — {artist_names}" if artist_names else "")
    yt=await resolve(_track_query(item),requested_by)
    yt["title"]=display_title
    yt["thumbnail"]=((item.get("album",{}).get("images") or [{}])[0].get("url")) or yt.get("thumbnail")
    return yt

async def resolve(query:str,requested_by:int):
    if is_spotify(query):
        return await resolve_spotify(query,requested_by)
    parsed=urlparse(query)
    is_url=bool(parsed.scheme and parsed.netloc)
    opts={**BASE,"extractor_args":{k:dict(v) if isinstance(v,dict) else v for k,v in BASE["extractor_args"].items()}}
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
    opts={"quiet":True,"no_warnings":True,"default_search":f"ytsearch{min(max(limit,1),10)}","skip_download":True,"extract_flat":"discard_in_playlist","extractor_args":{"youtube":{"player_client":["android_vr","web_embedded","tv"]}}}
    if POT_PROVIDER_URL:
        opts["extractor_args"]["youtubepot-bgutilhttp"]={"base_url":[POT_PROVIDER_URL]}
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

        items=await asyncio.wait_for(
            _spotify_items_from_collection(url,kind,limit),
            timeout=20,
        )
        tracks=[]
        for item in items:
            track_id=item.get("_spotify_id")
            if not track_id:
                continue
            tracks.append(Track(
                title=item.get("name","Unknown"),
                webpage_url=_spotify_url("track",track_id),
                duration=item.get("duration"),
                thumbnail=((item.get("album",{}).get("images") or [{}])[0].get("url")),
                uploader=", ".join(
                    a.get("name","") for a in item.get("artists",[]) if a.get("name")
                ),
                requested_by=requested_by,
            ))
        if not tracks:
            raise ValueError("Spotify playlist kosong atau metadata track tidak tersedia.")
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
