import random
import discord
from discord.ext import commands
from discord import app_commands
class Games(commands.Cog):
    @app_commands.command(name="coinflip",description="Flip a virtual coin.")
    async def coinflip(self,interaction): await interaction.response.send_message(random.choice(["Heads","Tails"]))
    @app_commands.command(name="dice",description="Roll a six-sided die.")
    async def dice(self,interaction): await interaction.response.send_message(str(random.randint(1,6)))
async def setup(bot): await bot.add_cog(Games(bot))
