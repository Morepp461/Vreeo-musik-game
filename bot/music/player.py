import asyncio
import discord
import time
import logging
import shlex
import random
from .queue import Track
from .source import resolve,search,music_candidates
from . import history
from .controls import NowPlayingView,build_now_playing_embed

log=logging.getLogger(__name__)

FILTERS={"off":None,"bassboost":"bass=g=10","nightcore":"asetrate=44100*1.25,aresample=44100,atempo=1.25","vaporwave":"asetrate=44100*0.8,aresample=44100,atempo=1.25","karaoke":"stereotools=mlev=0.03","8d":"apulsator=hz=0.09","tremolo":"tremolo=f=8:d=0.7","rotation":"apulsator=hz=0.125"}

class MusicPlayer:
    def __init__(self,bot):
        self.bot=bot
        self.queues={}
        self.stats={}

    def queue_for(self,guild_id):
        from .queue import GuildQueue
        return self.queues.setdefault(guild_id,GuildQueue())

    def record_play(self,guild_id,track):
        bucket=self.stats.setdefault(guild_id,{"plays":0,"seconds":0.0,"songs":{},"artists":{},"users":{}})
        bucket["plays"]+=1
        bucket["seconds"]+=float(track.duration or 0)
        title=track.title or "Unknown"
        bucket["songs"][title]=bucket["songs"].get(title,0)+1
        artist=(track.uploader or "Unknown").strip() or "Unknown"
        bucket["artists"][artist]=bucket["artists"].get(artist,0)+1
        user=str(track.requested_by or 0)
        bucket["users"][user]=bucket["users"].get(user,0)+1

    def stats_for(self,guild_id):
        return self.stats.get(guild_id,{"plays":0,"seconds":0.0,"songs":{},"artists":{},"users":{}})

    async def refresh_now_playing(self,guild):
        q=self.queue_for(guild.id)
        if not q.panel_channel_id or not q.panel_message_id: return
        try:
            channel=self.bot.get_channel(q.panel_channel_id)
            if not channel: return
            msg=await channel.fetch_message(q.panel_message_id)
            await msg.edit(embed=build_now_playing_embed(q),view=NowPlayingView(self,guild.id))
        except Exception:
            q.panel_channel_id=None
            q.panel_message_id=None

    async def ensure_now_playing(self,guild):
        q=self.queue_for(guild.id)
        if not q.panel_channel_id: return
        try:
            channel=self.bot.get_channel(q.panel_channel_id)
            if not channel: return
            if q.panel_message_id:
                try:
                    msg=await channel.fetch_message(q.panel_message_id)
                    await msg.edit(embed=build_now_playing_embed(q),view=NowPlayingView(self,guild.id))
                    return
                except Exception: pass
            msg=await channel.send(embed=build_now_playing_embed(q),view=NowPlayingView(self,guild.id))
            q.panel_message_id=msg.id
        except Exception:
            pass

    async def play_next(self,guild):
        voice=guild.voice_client
        q=self.queue_for(guild.id)
        if not voice or voice.is_playing() or voice.is_paused(): return
        replaying=q.replay_current and q.current is not None
        if replaying:
            track=q.current; q.replay_current=False
        else:
            track=q.pop_next()
        if track is not None and not replaying:
            track.playback_retries=0
        if not track and q.autoplay:
            try:
                genre_queries={
                    "random":("popular songs","latest music","indie music","r&b songs","dance music","chill music","rock songs","electronic music","top songs"),
                    "pop":("pop hits","best pop songs","new pop music","popular pop songs"),
                    "rock":("rock hits","best rock songs","classic rock songs","new rock music"),
                    "rnb":("r&b songs","best r&b music","rnb hits","soul r&b songs"),
                    "hiphop":("hip hop hits","rap songs","best hip hop music","new rap songs"),
                    "edm":("EDM hits","electronic dance music","best EDM songs","dance music"),
                    "lofi":("lofi chill music","lofi beats","chill lofi songs","study lofi"),
                    "jpop":("J-Pop hits","best J-Pop songs","Japanese pop music"),
                    "kpop":("K-Pop hits","best K-Pop songs","Korean pop music"),
                    "indonesia":("lagu Indonesia","Indonesian pop songs","musik Indonesia terbaru"),
                    "classical":("classical music","best classical songs","classical piano music"),
                    "disco":("disco funk hits","best disco songs","funk music"),
                    "jazz":("jazz music","best jazz songs","smooth jazz"),
                    "metal":("metal hits","best metal songs","heavy metal music"),
                }
                mode=q.autoplay_mode or "random"
                if mode=="artist" and q.autoplay_artist:
                    artist=q.autoplay_artist.strip()
                    artist_tokens=[x for x in artist.lower().replace("-"," ").split() if len(x)>2]
                    def artist_match(r):
                        text=f"{r.get('title','')} {r.get('uploader','') or r.get('channel','')}".lower()
                        return bool(artist_tokens) and all(token in text for token in artist_tokens)
                    queries=[f"{artist} songs",f"{artist} official songs",f"{artist} music"]
                    random.shuffle(queries)
                    results=[]
                    for query in queries:
                        found=await search(query,10)
                        results.extend(found)
                        if any(artist_match(r) for r in music_candidates(found)):
                            break
                else:
                    genre=q.autoplay_genre if mode=="genre" else "random"
                    if mode=="random" and q.current:
                        title=q.current.title.strip()
                        artist=(q.current.uploader or "").strip()
                        smart_queries=[
                            f"similar songs to {title}",
                            f"songs like {title}",
                            f"{artist} similar songs" if artist and "topic" not in artist.lower() else f"music similar to {title}",
                        ]
                        queries=[x for x in smart_queries if x]
                        fallback_queries=list(genre_queries["random"])
                        random.shuffle(fallback_queries)
                        queries.extend(fallback_queries[:2])
                    else:
                        queries=list(genre_queries.get(genre,genre_queries["random"]))
                        random.shuffle(queries)
                    results=[]
                    # Try several queries: a single weak/blocked YouTube search must
                    # never make autoplay silently die.
                    for query in queries[:5]:
                        try:
                            found=await search(query,10)
                        except Exception as exc:
                            log.warning("Autoplay search failed for %r: %s",query,exc)
                            continue
                        results.extend(found)
                        if music_candidates(found):
                            break
                recent={t.webpage_url for t in q.played[-20:]}
                if q.current: recent.add(q.current.webpage_url)
                current_title=(q.current.title or "").lower() if q.current else ""
                candidates=music_candidates(results)
                if mode=="artist" and q.autoplay_artist:
                    candidates=[r for r in candidates if artist_match(r)]
                candidates=[r for r in candidates if r.get("webpage_url") and r["webpage_url"] not in recent and r.get("title","").lower()!=current_title]
                # Search metadata can be sparse (especially YouTube's public
                # fallback), so use a safe music-looking result when the scorer
                # rejects everything instead of returning "no track".
                if not candidates:
                    fallback=[]
                    for r in results:
                        title=str(r.get("title") or "").lower()
                        url=r.get("webpage_url")
                        duration=r.get("duration")
                        if not url or url in recent or title==current_title:
                            continue
                        if any(word in title for word in ("reaction","podcast","interview","news","tutorial","gameplay","walkthrough","review","commentary","vlog","shorts","livestream","trailer","teaser")):
                            continue
                        if isinstance(duration,(int,float)) and (duration < 20 or duration > 3600):
                            continue
                        if mode=="artist" and q.autoplay_artist and not artist_match(r):
                            continue
                        fallback.append(r)
                    random.shuffle(fallback)
                    candidates=fallback
                candidate=candidates[0] if candidates else None
                if candidate:
                    track=Track(title=candidate["title"],webpage_url=candidate["webpage_url"],duration=candidate.get("duration"),thumbnail=candidate.get("thumbnail"),uploader=candidate.get("uploader"),requested_by=q.current.requested_by if q.current else 0)
            except Exception as exc:
                log.exception("Autoplay generation failed: %s",exc)
                track=None
        if not track:
            q.current=None; q.position=0
            await self.refresh_now_playing(guild)
            if q.autoplay and guild.voice_client:
                # Keep the 24/7 voice connection alive and retry instead of
                # flashing the player for a moment and then dropping it.
                await asyncio.sleep(3)
                if q.autoplay and guild.voice_client and not guild.voice_client.is_playing() and not guild.voice_client.is_paused():
                    return await self.play_next(guild)
            if not q.always_connected and guild.voice_client:
                await guild.voice_client.disconnect(force=True); self.queues.pop(guild.id,None)
            return
        if q.current is not None and track is not q.current:
            q.played.append(q.current); q.played=q.played[-20:]
        q.current=track; q.paused=False; seek_offset=q.position; q.position=0
        q.started_at=time.monotonic(); q.started_offset=seek_offset; q.paused_at=0.0
        data=None
        if not track.stream_url:
            try:
                data=await asyncio.wait_for(resolve(track.webpage_url,track.requested_by or 0),timeout=25)
            except Exception as exc:
                q.last_error=str(exc)
                log.exception("Failed to resolve track %s (%s)",track.title,track.webpage_url)
                q.tracks=[t for t in q.tracks if t is not track]
                q.current=None
                if q.tracks:
                    return await self.play_next(guild)
                await self.refresh_now_playing(guild)
                return False
            track.stream_url=data.get("stream_url")
            track.stream_headers=data.get("stream_headers") or track.stream_headers
        if not track.stream_url:
            q.last_error="Resolver returned no stream URL."
            log.error("Resolver returned no stream URL for %s (%s)",track.title,track.webpage_url)
            q.tracks=[t for t in q.tracks if t is not track]
            q.current=None
            if q.tracks:
                return await self.play_next(guild)
            await self.refresh_now_playing(guild)
            return False
        if data:
            track.title=data.get("title") or track.title
            track.duration=data.get("duration") or track.duration
            track.thumbnail=data.get("thumbnail") or track.thumbnail
            track.uploader=data.get("uploader") or track.uploader
        if not (replaying and track.playback_retries > 0):
            self.record_play(guild.id,track)
        af=[]
        if FILTERS.get(q.filter): af.append(FILTERS[q.filter])
        if q.speed!=1.0: af.append("atempo=%.2f"%q.speed)
        af.append("volume=%.2f"%q.volume); q.effects_dirty=False
        headers=track.stream_headers or {}
        header_args=""
        if headers:
            header_lines=[]
            for hk,hv in headers.items():
                if hk.lower() in {"user-agent","referer","origin","accept-language"} and hv:
                    header_lines.append(f"{hk}: {hv}")
            if header_lines:
                header_args=" -headers "+shlex.quote("\r\n".join(header_lines)+"\r\n")
        source=discord.FFmpegPCMAudio(track.stream_url,before_options="-ss %.2f -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5%s"%(seek_offset,header_args),options="-vn -af %s"%",".join(af))
        try: history.record(track.requested_by or 0,track.title,track.webpage_url)
        except Exception: pass
        await self.ensure_now_playing(guild)
        def after(error):
            if error:
                log.error("Voice player ended with error for %s: %r",track.title,error)
                if track.playback_retries < 1 and track.stream_url:
                    track.playback_retries += 1
                    track.stream_url=None
                    track.stream_headers=None
                    q.replay_current=True
                    log.warning("Retrying stream resolution for %s after FFmpeg playback error",track.title)
            self.bot.loop.call_soon_threadsafe(lambda: asyncio.create_task(self.play_next(guild)))
        try:
            voice.play(source,after=after)
            q.last_error=None
            if q.tracks:
                asyncio.create_task(self._prefetch_next(guild))
            return True
        except Exception as exc:
            q.last_error=str(exc)
            log.exception("Voice playback failed for %s",track.title)
            source.cleanup()
            q.current=None
            if q.tracks:
                return await self.play_next(guild)
            return False

    async def _prefetch_next(self,guild):
        q=self.queue_for(guild.id)
        if not q.tracks:
            return
        track=q.tracks[0]
        if track.stream_url:
            return
        try:
            data=await asyncio.wait_for(resolve(track.webpage_url,track.requested_by or 0),timeout=18)
            track.stream_url=data.get("stream_url") or track.stream_url
            track.stream_headers=data.get("stream_headers") or track.stream_headers
            track.title=data.get("title") or track.title
            track.duration=data.get("duration") or track.duration
            track.thumbnail=data.get("thumbnail") or track.thumbnail
            track.uploader=data.get("uploader") or track.uploader
        except Exception:
            pass
    async def disconnect(self,guild):
        q=self.queues.get(guild.id)
        if q: q.always_connected=False
        if guild.voice_client: await guild.voice_client.disconnect(force=True)
        self.queues.pop(guild.id,None)

    def skip(self,guild):
        v=guild.voice_client; q=self.queue_for(guild.id); q.paused=False; q.paused_at=0.0
        if v and (v.is_playing() or v.is_paused()): v.stop()

    def pause(self,guild):
        v=guild.voice_client
        if v and v.is_playing():
            v.pause(); q=self.queue_for(guild.id); q.paused=True; q.paused_at=time.monotonic()

    def resume(self,guild):
        v=guild.voice_client
        if v and v.is_paused():
            v.resume(); q=self.queue_for(guild.id)
            if q.paused_at: q.started_at+=time.monotonic()-q.paused_at
            q.paused=False; q.paused_at=0.0
            if q.effects_dirty: self.restart_current(guild)

    def previous(self,guild):
        q=self.queue_for(guild.id)
        if not q.played: return False
        prev=q.played.pop()
        if q.current: q.tracks.insert(0,q.current)
        q.current=prev; q.position=0; q.replay_current=True; self.skip(guild); return True

    def seek(self,guild,seconds):
        q=self.queue_for(guild.id)
        if not q.current: return False
        duration=q.current.duration
        q.position=max(0,min(seconds,(duration-0.5) if duration else seconds)); self.restart_current(guild,preserve_position=False); return True

    def restart_current(self,guild,preserve_position=True):
        q=self.queue_for(guild.id)
        if not q.current: return False
        if preserve_position and q.started_at: q.position=max(0,q.started_offset+(q.paused_at or time.monotonic())-q.started_at)
        q.replay_current=True; v=guild.voice_client
        if v and (v.is_playing() or v.is_paused()): v.stop()
        return True

    def set_volume(self,guild,value):
        value=max(0,min(150,value)); q=self.queue_for(guild.id); q.volume=value/100; q.effects_dirty=True
        if guild.voice_client and guild.voice_client.is_playing(): self.restart_current(guild)
        return value
