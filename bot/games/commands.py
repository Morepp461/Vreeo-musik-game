import random
import discord
from discord.ext import commands
from discord import app_commands

class Games(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="coinflip", description="Flip a virtual coin.")
    async def coinflip(self, interaction: discord.Interaction):
        await interaction.response.send_message("Coin: " + random.choice(["Heads", "Tails"]))

    @app_commands.command(name="dice", description="Roll a six-sided die.")
    async def dice(self, interaction: discord.Interaction):
        await interaction.response.send_message("Dice: " + str(random.randint(1, 6)))

    @app_commands.command(name="rps", description="Play rock paper scissors.")
    @app_commands.describe(choice="rock, paper, or scissors")
    async def rps(self, interaction: discord.Interaction, choice: str):
        choice = choice.lower().strip()
        choices = ["rock", "paper", "scissors"]
        if choice not in choices:
            await interaction.response.send_message("Choose rock, paper, or scissors.", ephemeral=True)
            return
        bot_choice = random.choice(choices)
        if choice == bot_choice:
            result = "Draw."
        elif (choice, bot_choice) in {("rock","scissors"),("paper","rock"),("scissors","paper")}:
            result = "You win!"
        else:
            result = "You lose."
        await interaction.response.send_message(
            f"You: {choice} | Vreeo: {bot_choice} | {result}"
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Games(bot))
