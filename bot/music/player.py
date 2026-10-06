import asyncio
import discord
import time
import logging
from .queue import Track
from .source import resolve,search
from . import history
from .controls import NowPlayingView,build_now_playing_embed

log=logging.getLogger(__name__)

FILTERS={"off":None,"bassboost":"bass=g=10","nightcore":"asetrate=44100*1.25,aresample=44100,atempo=1.25","vaporwave":"asetrate=44100*0.8,aresample=44100,atempo=1.25","karaoke":"stereotools=mlev=0.03","8d":"apulsator=hz=0.09","tremolo":"tremolo=f=8:d=0.7","rotation":"apulsator=hz=0.125"}

class MusicPlayer:
    def __init__(self,bot):
        self.bot=bot
        self.queues={}

    def queue_for(self,guild_id):
        from .queue import GuildQueue
        return self.queues.setdefault(guild_id,GuildQueue())

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
        if q.replay_current and q.current:
            track=q.current; q.replay_current=False
        else: track=q.pop_next()
        if not track and q.autoplay and q.current:
            try:
                results=await search(q.current.title,5)
                recent={t.webpage_url for t in q.played[-10:]}; recent.add(q.current.webpage_url)
                candidate=next((r for r in results if r["webpage_url"] not in recent),None)
                if candidate:
                    track=Track(title=candidate["title"],webpage_url=candidate["webpage_url"],duration=candidate.get("duration"),thumbnail=candidate.get("thumbnail"),uploader=candidate.get("uploader"),requested_by=q.current.requested_by)
            except Exception: track=None
        if not track:
            q.current=None; q.position=0
            await self.refresh_now_playing(guild)
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
        af=[]
        if FILTERS.get(q.filter): af.append(FILTERS[q.filter])
        if q.speed!=1.0: af.append("atempo=%.2f"%q.speed)
        af.append("volume=%.2f"%q.volume); q.effects_dirty=False
        source=discord.FFmpegPCMAudio(track.stream_url,before_options="-ss %.2f -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"%seek_offset,options="-vn -af %s"%",".join(af))
        try: history.record(track.requested_by or 0,track.title,track.webpage_url)
        except Exception: pass
        await self.ensure_now_playing(guild)
        def after(error):
            if error:
                log.error("Voice player ended with error for %s: %r",track.title,error)
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
