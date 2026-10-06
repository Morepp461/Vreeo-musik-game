import logging
import discord
from discord.ext import commands
from .config import DISCORD_TOKEN, DISCORD_GUILD_ID

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

class VreeoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.load_extension("bot.games.commands")
        if DISCORD_GUILD_ID:
            guild = discord.Object(id=DISCORD_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self):
        logging.info("Logged in as %s (%s)", self.user, self.user.id)

bot = VreeoBot()
bot.run(DISCORD_TOKEN)
