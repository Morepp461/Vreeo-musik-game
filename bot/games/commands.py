import discord
from discord.ext import commands
from discord import app_commands

from .world import bootstrap_guild, GAME_NAME
from ..database import supabase

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._bootstrapped = set()

    async def bootstrap(self):
        for guild in self.bot.guilds:
            if guild.id in self._bootstrapped:
                continue
            try:
                result = await bootstrap_guild(guild)
                if result:
                    self._bootstrapped.add(guild.id)
                    print(f"WNI SIMULATOR bootstrap: {result}")
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "WNI SIMULATOR bootstrap gagal untuk guild %s", guild.id
                )

    @app_commands.command(name="game", description="Buka dashboard WNI SIMULATOR.")
    async def game(self, interaction: discord.Interaction):
        state = supabase.table("game_world_state").select("*").eq("id", 1).limit(1).execute()
        ai = supabase.table("game_ai_characters").select("id", count="exact").execute()
        events = supabase.table("game_events").select("id", count="exact").execute()
        row = state.data[0] if state.data else {}
        embed = discord.Embed(
            title=f"🇮🇩 {GAME_NAME}",
            description="Simulasi kehidupan Indonesia yang berjalan persisten.",
            color=discord.Color.dark_red(),
        )
        embed.add_field(name="🕐 Waktu dunia", value=str(row.get("world_time", "belum dimulai")), inline=False)
        embed.add_field(name="👥 Populasi AI", value=str(ai.count or 0), inline=True)
        embed.add_field(name="📰 Event dunia", value=str(events.count or 0), inline=True)
        embed.add_field(name="⏯️ Simulasi", value="PAUSE" if row.get("paused") else "AKTIF", inline=True)
        embed.add_field(name="💱 Ekonomi", value=f"x{row.get('economy_multiplier', 1)}", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="godmode", description="Dashboard kontrol God Mode WNI SIMULATOR.")
    @app_commands.checks.has_permissions(administrator=True)
    async def godmode(self, interaction: discord.Interaction):
        state = supabase.table("game_world_state").select("*").eq("id", 1).limit(1).execute()
        row = state.data[0] if state.data else {}
        embed = discord.Embed(
            title="👑 WNI SIMULATOR — GOD MODE",
            description="Kontrol dunia melalui engine + database, dengan audit.",
            color=discord.Color.gold(),
        )
        embed.add_field(name="World Speed", value=f"{row.get('real_seconds_per_game_day', 604800)} detik/game-day", inline=True)
        embed.add_field(name="AI Target", value=str(row.get("ai_population_target", 250)), inline=True)
        embed.add_field(name="Economy Multiplier", value=str(row.get("economy_multiplier", 1)), inline=True)
        embed.add_field(name="Inflasi", value=str(row.get("inflation_rate", 0)), inline=True)
        embed.add_field(name="Simulasi", value="PAUSED" if row.get("paused") else "RUNNING", inline=True)
        embed.set_footer(text="God Mode hanya untuk administrator server.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @godmode.error
    async def godmode_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "❌ God Mode hanya untuk administrator server.", ephemeral=True
            )
        else:
            raise error

async def setup(bot):
    await bot.add_cog(Games(bot))
