import asyncio
import discord
class MusicPlayer:
    def __init__(self,bot): self.bot=bot; self.queues={}
    def queue_for(self,guild_id):
        from .queue import GuildQueue
        return self.queues.setdefault(guild_id,GuildQueue())
    async def play_next(self,guild):
        voice=guild.voice_client; q=self.queue_for(guild.id)
        if not voice or voice.is_playing(): return
        track=q.next()
        if not track: q.current=None; return
        q.current=track
        source=discord.FFmpegPCMAudio(track.stream_url,before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',options=f'-vn -af volume={q.volume}')
        def after(error):
            self.bot.loop.call_soon_threadsafe(asyncio.create_task,self.play_next(guild))
        voice.play(source,after=after)
    async def disconnect(self,guild):
        if guild.voice_client: await guild.voice_client.disconnect(force=True)
        self.queues.pop(guild.id,None)
    def skip(self,guild):
        v=guild.voice_client
        if v and (v.is_playing() or v.is_paused()): v.stop()
    def pause(self,guild):
        v=guild.voice_client
        if v and v.is_playing(): v.pause()
    def resume(self,guild):
        v=guild.voice_client
        if v and v.is_paused(): v.resume()
