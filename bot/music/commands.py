import discord
from discord.ext import commands
from discord import app_commands
from .source import resolve
from .queue import Track
from .player import MusicPlayer
class Music(commands.Cog):
    def __init__(self,bot): self.bot=bot; self.player=MusicPlayer(bot); bot.music_player=self.player
    async def voice(self,i):
        if not i.user.voice:return None
        ch=i.user.voice.channel; v=i.guild.voice_client
        if v and v.channel!=ch: await v.move_to(ch)
        return v or await ch.connect()
    @app_commands.command(name="play",description="Putar lagu dari URL atau pencarian")
    async def play(self,i,query:str):
        v=await self.voice(i)
        if not v:return await i.response.send_message("Masuk voice channel dulu.",ephemeral=True)
        await i.response.defer(); data=await resolve(query,i.user.id); q=self.player.queue_for(i.guild.id); q.add(Track(**data))
        if not v.is_playing(): await self.player.play_next(i.guild)
        await i.followup.send("▶️ "+data["title"])
    @app_commands.command(name="pause",description="Pause")
    async def pause(self,i): self.player.pause(i.guild); await i.response.send_message("⏸️")
    @app_commands.command(name="resume",description="Resume")
    async def resume(self,i): self.player.resume(i.guild); await i.response.send_message("▶️")
    @app_commands.command(name="skip",description="Skip")
    async def skip(self,i): self.player.skip(i.guild); await i.response.send_message("⏭️")
    @app_commands.command(name="stop",description="Stop")
    async def stop(self,i): await self.player.disconnect(i.guild); await i.response.send_message("⏹️")
    @app_commands.command(name="queue",description="Lihat queue")
    async def queue(self,i):
        q=self.player.queue_for(i.guild.id); lines=[f"▶️ {q.current.title}"] if q.current else []
        lines += [f"{n}. {t.title}" for n,t in enumerate(q.tracks[:20],1)]
        await i.response.send_message("\n".join(lines) or "Queue kosong.")
    @app_commands.command(name="shuffle",description="Acak queue")
    async def shuffle(self,i): self.player.queue_for(i.guild.id).shuffle(); await i.response.send_message("🔀")
async def setup(bot): await bot.add_cog(Music(bot))
