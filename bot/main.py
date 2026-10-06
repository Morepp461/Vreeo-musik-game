import logging
import discord
from discord.ext import commands
from .config import DISCORD_TOKEN,DISCORD_GUILD_ID
logging.basicConfig(level=logging.INFO)
class VreeoBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!",intents=discord.Intents.all())
    async def setup_hook(self):
        await self.load_extension("bot.music.commands")
        await self.load_extension("bot.games.commands")
        if DISCORD_GUILD_ID:
            g=discord.Object(id=DISCORD_GUILD_ID); self.tree.copy_global_to(guild=g); await self.tree.sync(guild=g)
        else: await self.tree.sync()
    async def on_ready(self): logging.info("Logged in as %s",self.user)
bot=VreeoBot(); bot.run(DISCORD_TOKEN)
