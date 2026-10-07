import discord
from discord.ext import commands
from discord import app_commands

from .world import bootstrap_guild, GAME_NAME
from .player import get_character, get_wallet, get_needs, get_inventory, get_assets, profile_embed, inventory_text, assets_text, RegisterView, money
from ..database import supabase
from .gameplay import ActionView, TravelView, ShopView, action_embed
from .career import CareerHubView
from .social import WorldView

GODMODE_OWNER_ID = 1441030290280550513

class PlayerView(discord.ui.View):
    def __init__(self, character):
        super().__init__(timeout=300)
        self.character_id = character["id"]

    @discord.ui.button(label="Profil", emoji="🪪", style=discord.ButtonStyle.primary)
    async def profile(self, interaction, button):
        c = supabase.table("game_characters").select("*").eq("id", self.character_id).limit(1).execute().data
        if not c:
            return await interaction.response.send_message("❌ Karakter tidak ditemukan.", ephemeral=True)
        await interaction.response.edit_message(embed=profile_embed(c[0]), view=self)

    @discord.ui.button(label="Wallet", emoji="💰", style=discord.ButtonStyle.success)
    async def wallet(self, interaction, button):
        w = get_wallet(self.character_id) or {}
        e = discord.Embed(title="💰 Wallet", color=discord.Color.green())
        e.add_field(name="💵 Tunai", value=money(w.get("cash")), inline=True)
        e.add_field(name="🏦 Bank", value=money(w.get("bank")), inline=True)
        e.add_field(name="💳 Utang", value=money(w.get("debt")), inline=True)
        e.set_footer(text="Semua perubahan uang dicatat di ledger transaksi.")
        await interaction.response.edit_message(embed=e, view=self)

    @discord.ui.button(label="Inventaris", emoji="🎒", style=discord.ButtonStyle.secondary)
    async def inventory(self, interaction, button):
        e = discord.Embed(title="🎒 Inventaris", description=inventory_text(self.character_id), color=discord.Color.blurple())
        await interaction.response.edit_message(embed=e, view=self)

    @discord.ui.button(label="Aset", emoji="🏠", style=discord.ButtonStyle.secondary)
    async def assets(self, interaction, button):
        e = discord.Embed(title="🏠 Aset Milikmu", description=assets_text(self.character_id), color=discord.Color.gold())
        await interaction.response.edit_message(embed=e, view=self)

    @discord.ui.button(label="Kebutuhan", emoji="❤️", style=discord.ButtonStyle.danger, row=1)
    async def needs(self, interaction, button):
        n = get_needs(self.character_id) or {}
        e = discord.Embed(title="❤️ Kondisi Karakter", color=discord.Color.red())
        for key,label,emoji in [("health","Kesehatan","❤️"),("hunger","Lapar","🍚"),("thirst","Haus","💧"),("energy","Energi","⚡"),("happiness","Kebahagiaan","😊"),("stress","Stres","😵")]:
            e.add_field(name=f"{emoji} {label}", value=f"{n.get(key,0)}/100", inline=True)
        await interaction.response.edit_message(embed=e, view=self)

    @discord.ui.button(label="Karier", emoji="💼", style=discord.ButtonStyle.success, row=1)
    async def career(self, interaction, button):
        c = get_character(interaction.user.id, interaction.guild.id)
        if not c or c["id"] != self.character_id:
            return await interaction.response.send_message("❌ Ini bukan dashboard karaktermu.", ephemeral=True)
        await interaction.response.edit_message(embed=discord.Embed(title="💼 Karier",description="Bangun kehidupan profesionalmu. Cari kerja dan mulai dari bawah.",color=discord.Color.blurple()),view=CareerHubView(self.character_id))

    @discord.ui.button(label="Dunia", emoji="🌏", style=discord.ButtonStyle.primary, row=2)
    async def world(self, interaction, button):
        await interaction.response.edit_message(embed=discord.Embed(title="🌏 Dunia WNI SIMULATOR",description="Berita, hubungan AI, kriminal, bencana, dan perkembangan masyarakat.",color=discord.Color.dark_red()),view=WorldView(self.character_id))

    @discord.ui.button(label="Kehidupan", emoji="🎮", style=discord.ButtonStyle.primary, row=1)
    async def life(self, interaction, button):
        c = supabase.table("game_characters").select("*").eq("id", self.character_id).limit(1).execute().data
        if not c:
            return await interaction.response.send_message("❌ Karakter tidak ditemukan.", ephemeral=True)
        await interaction.response.edit_message(embed=action_embed(c[0]), view=ActionHubView(self.character_id))

class ActionHubView(discord.ui.View):
    def __init__(self, character_id):
        super().__init__(timeout=300)
        self.character_id = character_id

    @discord.ui.button(label="Aktivitas", emoji="⚡", style=discord.ButtonStyle.success)
    async def activities(self, interaction, button):
        await interaction.response.edit_message(embed=action_embed({"id": self.character_id}), view=ActionView(self.character_id))

    @discord.ui.button(label="Toko", emoji="🛍️", style=discord.ButtonStyle.success)
    async def shop(self, interaction, button):
        e = discord.Embed(title="🛍️ Toko", description="Pilih barang yang ingin dibeli. Pembelian dicatat ke wallet + ledger + inventaris.", color=discord.Color.green())
        await interaction.response.edit_message(embed=e, view=ShopView(self.character_id))

    @discord.ui.button(label="Perjalanan", emoji="🚆", style=discord.ButtonStyle.secondary)
    async def travel(self, interaction, button):
        e = discord.Embed(title="🚆 Perjalanan", description="Pilih kota tujuan. Biaya perjalanan Rp75.000.", color=discord.Color.blurple())
        await interaction.response.edit_message(embed=e, view=TravelView(self.character_id))

    @discord.ui.button(label="Kembali", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def back(self, interaction, button):
        c = get_character(interaction.user.id, interaction.guild.id)
        if not c or c["id"] != self.character_id:
            return await interaction.response.send_message("❌ Ini bukan dashboard karaktermu.", ephemeral=True)
        await interaction.response.edit_message(embed=profile_embed(c), view=PlayerView(c))

class GodModeView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot

    async def _render(self, interaction):
        state = supabase.table("game_world_state").select("*").eq("id", 1).limit(1).execute()
        row = state.data[0] if state.data else {}
        e = discord.Embed(title="👑 WNI SIMULATOR — GOD MODE", description="Kontrol dunia + reconciliation + audit.", color=discord.Color.gold())
        e.add_field(name="World Speed", value=f"{row.get('real_seconds_per_game_day',604800)} detik/game-day", inline=True)
        e.add_field(name="AI Target", value=str(row.get("ai_population_target",250)), inline=True)
        e.add_field(name="Economy", value=str(row.get("economy_multiplier",1)), inline=True)
        e.add_field(name="Inflasi", value=str(row.get("inflation_rate",0)), inline=True)
        e.add_field(name="Simulasi", value="⏸️ PAUSED" if row.get("paused") else "▶️ RUNNING", inline=True)
        e.set_footer(text="Semua aksi God Mode dicatat ke audit log.")
        await interaction.response.edit_message(embed=e, view=self)

    @discord.ui.button(label="Refresh", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction, button):
        await self._render(interaction)

    @discord.ui.button(label="Pause/Resume", emoji="⏯️", style=discord.ButtonStyle.primary)
    async def toggle(self, interaction, button):
        state = supabase.table("game_world_state").select("paused").eq("id",1).limit(1).execute().data
        paused = bool(state[0].get("paused")) if state else False
        supabase.rpc("game_set_world_paused", {"p_paused": not paused, "p_actor_id": str(interaction.user.id)}).execute()
        await self._render(interaction)

    @discord.ui.button(label="Reconcile", emoji="🛠️", style=discord.ButtonStyle.success)
    async def reconcile(self, interaction, button):
        from .world import bootstrap_guild
        result = await bootstrap_guild(interaction.guild)
        supabase.table("game_audit_log").insert({
            "actor_type":"godmode",
            "actor_id":str(interaction.user.id),
            "action":"discord_reconcile",
            "target_type":"guild",
            "target_id":str(interaction.guild.id),
            "metadata":result or {},
        }).execute()
        await interaction.response.send_message("✅ Rekonsiliasi Discord selesai. Role + channel WNI diverifikasi tanpa membuat kategori baru.", ephemeral=True)


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
                logging.getLogger(__name__).exception("WNI SIMULATOR bootstrap gagal untuk guild %s", guild.id)

    @app_commands.command(name="game", description="Buka dashboard WNI SIMULATOR.")
    async def game(self, interaction: discord.Interaction):
        character = get_character(interaction.user.id, interaction.guild.id)
        if not character:
            e = discord.Embed(
                title=f"🇮🇩 {GAME_NAME}",
                description="Dunia sudah online, tapi kamu belum memiliki karakter.\n\nBuat identitasmu untuk mulai menjalani kehidupan.",
                color=discord.Color.dark_red(),
            )
            e.add_field(name="🎒 Yang kamu mulai dengan", value="💵 Rp250.000 tunai\n📱 1 ponsel standar", inline=False)
            e.add_field(name="📍 Pilih kota", value="Jakarta, Bandung, Semarang, Yogyakarta, Surabaya, Malang, Tangerang, Medan, Palembang, Pekanbaru, Denpasar, Balikpapan", inline=False)
            return await interaction.response.send_message(embed=e, view=RegisterView(), ephemeral=True)
        await interaction.response.send_message(embed=profile_embed(character), view=PlayerView(character), ephemeral=True)

    @app_commands.command(name="godmode", description="Dashboard kontrol God Mode WNI SIMULATOR.")
    async def godmode(self, interaction: discord.Interaction):
        if interaction.user.id != GODMODE_OWNER_ID:
            return await interaction.response.send_message("❌ Kamu tidak memiliki akses God Mode.", ephemeral=True)

        state = supabase.table("game_world_state").select("*").eq("id", 1).limit(1).execute()
        row = state.data[0] if state.data else {}
        e = discord.Embed(title="👑 WNI SIMULATOR — GOD MODE", description="Kontrol dunia melalui engine + database, dengan audit.", color=discord.Color.gold())
        e.add_field(name="World Speed", value=f"{row.get('real_seconds_per_game_day',604800)} detik/game-day", inline=True)
        e.add_field(name="AI Target", value=str(row.get("ai_population_target",250)), inline=True)
        e.add_field(name="Economy Multiplier", value=str(row.get("economy_multiplier",1)), inline=True)
        e.add_field(name="Inflasi", value=str(row.get("inflation_rate",0)), inline=True)
        e.add_field(name="Simulasi", value="PAUSED" if row.get("paused") else "RUNNING", inline=True)
        e.set_footer(text="God Mode dikunci ke pemilik bot.")
        await interaction.response.send_message(embed=e, view=GodModeView(self.bot), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Games(bot))
