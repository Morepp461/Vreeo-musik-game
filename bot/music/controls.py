import discord

class NowPlayingView(discord.ui.View):
    def __init__(self,player,guild_id:int):
        super().__init__(timeout=900)
        self.player=player
        self.guild_id=guild_id

    @property
    def guild(self):
        return self.player.bot.get_guild(self.guild_id)

    @discord.ui.button(emoji="⏮️",style=discord.ButtonStyle.secondary)
    async def previous(self,interaction:discord.Interaction,button:discord.ui.Button):
        self.player.previous(self.guild)
        await interaction.response.send_message("⏮️ Previous.",ephemeral=True)

    @discord.ui.button(emoji="⏯️",style=discord.ButtonStyle.primary)
    async def pause_resume(self,interaction:discord.Interaction,button:discord.ui.Button):
        v=self.guild.voice_client
        if v and v.is_paused(): self.player.resume(self.guild)
        elif v and v.is_playing(): self.player.pause(self.guild)
        await interaction.response.send_message("⏯️",ephemeral=True)

    @discord.ui.button(emoji="⏭️",style=discord.ButtonStyle.secondary)
    async def skip(self,interaction:discord.Interaction,button:discord.ui.Button):
        self.player.skip(self.guild)
        await interaction.response.send_message("⏭️ Skip.",ephemeral=True)

    @discord.ui.button(emoji="🔀",style=discord.ButtonStyle.secondary)
    async def shuffle(self,interaction:discord.Interaction,button:discord.ui.Button):
        self.player.queue_for(self.guild_id).shuffle()
        await interaction.response.send_message("🔀 Queue diacak.",ephemeral=True)

    @discord.ui.button(emoji="🔁",style=discord.ButtonStyle.secondary)
    async def loop(self,interaction:discord.Interaction,button:discord.ui.Button):
        q=self.player.queue_for(self.guild_id)
        q.loop={"off":"queue","queue":"track","track":"off"}[q.loop]
        await interaction.response.send_message(f"🔁 Loop: **{q.loop}**",ephemeral=True)

    @discord.ui.button(emoji="⏹️",style=discord.ButtonStyle.danger,row=1)
    async def stop(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.player.disconnect(self.guild)
        await interaction.response.send_message("⏹️ Stop.",ephemeral=True)

    @discord.ui.button(emoji="📜",style=discord.ButtonStyle.secondary,row=1)
    async def queue(self,interaction:discord.Interaction,button:discord.ui.Button):
        q=self.player.queue_for(self.guild_id)
        text="\n".join(f"{n}. {t.title}" for n,t in enumerate(q.tracks[:20],1)) or "Queue kosong."
        await interaction.response.send_message(text[:1900],ephemeral=True)
