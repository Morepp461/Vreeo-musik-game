import discord

class MusicPlayer:
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}

    def queue_for(self, guild_id):
        from .queue import GuildQueue
        return self.queues.setdefault(guild_id, GuildQueue())

    async def disconnect(self, guild):
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)
        self.queues.pop(guild.id, None)

    def skip(self, guild):
        voice = guild.voice_client
        if voice and (voice.is_playing() or voice.is_paused()):
            voice.stop()

    def pause(self, guild):
        voice = guild.voice_client
        if voice and voice.is_playing():
            voice.pause()

    def resume(self, guild):
        voice = guild.voice_client
        if voice and voice.is_paused():
            voice.resume()
