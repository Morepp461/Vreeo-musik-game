import asyncio
import discord
from .source import resolve
from .queue import Track

class MusicPlayer:
    def __init__(self,bot):
        self.bot=bot
        self.queues={}

    def queue_for(self,guild_id):
        from .queue import GuildQueue
        return self.queues.setdefault(guild_id,GuildQueue())

    async def play_next(self,guild):
        voice=guild.voice_client
        q=self.queue_for(guild.id)
        if not voice or voice.is_playing() or voice.is_paused():
            return
        track=q.pop_next()
        if not track:
            q.current=None
            q.position=0
            return
        if q.current is not None and track is not q.current:
            q.played.append(q.current)
            q.played=q.played[-20:]
        q.current=track
        q.position=0
        try:
            data=await resolve(track.webpage_url,track.requested_by or 0)
            track.stream_url=data["stream_url"]
            track.title=data["title"] or track.title
            track.duration=data.get("duration") or track.duration
            track.thumbnail=data.get("thumbnail") or track.thumbnail
        except Exception as exc:
            self.bot.logger.warning("stream resolve failed: %s",exc) if hasattr(self.bot,"logger") else None
            return await self.play_next(guild)
        source=discord.FFmpegPCMAudio(
            track.stream_url,
            before_options=f"-ss {q.position:.2f} -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options=f"-vn -af volume={q.volume:.2f}"
        )
        def after(error):
            self.bot.loop.call_soon_threadsafe(lambda: asyncio.create_task(self.play_next(guild)))
        voice.play(source,after=after)

    async def disconnect(self,guild):
        q=self.queue_for(guild.id)
        q.always_connected=False
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)
        self.queues.pop(guild.id,None)

    def skip(self,guild):
        v=guild.voice_client
        if v and (v.is_playing() or v.is_paused()): v.stop()

    def pause(self,guild):
        v=guild.voice_client
        if v and v.is_playing():
            v.pause()
            self.queue_for(guild.id).paused=True

    def resume(self,guild):
        v=guild.voice_client
        if v and v.is_paused():
            v.resume()
            self.queue_for(guild.id).paused=False

    def previous(self,guild):
        q=self.queue_for(guild.id)
        if not q.played:
            return False
        prev=q.played.pop()
        if q.current:
            q.tracks.insert(0,q.current)
        q.current=prev
        q.position=0
        q.tracks.insert(0,prev)
        self.skip(guild)
        return True

    def seek(self,guild,seconds:float):
        q=self.queue_for(guild.id)
        if not q.current: return False
        duration=q.current.duration or 10**9
        q.position=max(0,min(seconds,duration-0.5 if duration else seconds))
        v=guild.voice_client
        if v and (v.is_playing() or v.is_paused()):
            v.stop()
        return True

    def set_volume(self,guild,value:int):
        value=max(0,min(150,value))
        q=self.queue_for(guild.id)
        q.volume=value/100
        return value
