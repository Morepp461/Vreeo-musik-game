from __future__ import annotations

import math
import random
import discord
from discord import app_commands
from discord.ext import commands
from bot.database import supabase
from .tournament_engine import next_round_pairings, round_robin_pairings, standings


def rows(table, **filters):
    q = supabase.table(table).select("*")
    for key, value in filters.items():
        q = q.eq(key, value)
    return q.execute().data or []


def tournament(tid):
    data = rows("tournaments", id=tid)
    return data[0] if data else None


async def reply(interaction, text, ephemeral=True):
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=ephemeral)
    else:
        await interaction.response.send_message(text, ephemeral=ephemeral)


def can_manage(interaction, t):
    return interaction.user.id == t["organizer_id"] or interaction.user.guild_permissions.manage_guild


async def embed(t):
    ps = rows("tournament_participants", tournament_id=t["id"])
    ms = rows("tournament_matches", tournament_id=t["id"])
    done = sum(m["status"] == "completed" for m in ms)
    e = discord.Embed(title="🏆 " + t["name"], color=discord.Color.from_rgb(17, 17, 17))
    e.description = "**" + t["format"].title() + "** • **" + t["status"].title() + "**\nParticipants: **" + str(len(ps)) + "/" + str(t["max_participants"]) + "**"
    e.add_field(name="Progress", value=str(done) + "/" + str(len(ms)) + " matches completed" if ms else "Schedule belum dibuat.", inline=False)
    if t["format"] == "league":
        e.add_field(name="Scoring", value="Win 3 • Draw 1 • Loss 0", inline=False)
    return e


async def start_tournament(t):
    participants = rows("tournament_participants", tournament_id=t["id"])
    ids = [p["user_id"] for p in participants]
    if len(ids) < 2:
        raise ValueError("Minimal 2 participants.")
    supabase.table("tournament_matches").delete().eq("tournament_id", t["id"]).execute()
    if t["format"] == "league":
        rounds = round_robin_pairings(ids)
        for rn, pairs in enumerate(rounds, 1):
            for mn, pair in enumerate(pairs, 1):
                supabase.table("tournament_matches").insert({
                    "tournament_id": t["id"], "round_number": rn, "match_number": mn,
                    "home_team_id": pair[0], "away_team_id": pair[1], "status": "scheduled"
                }).execute()
    else:
        random.shuffle(ids)
        size = 2 ** math.ceil(math.log2(len(ids)))
        ids += [None] * (size - len(ids))
        pairs = [(ids[i], ids[i + 1]) for i in range(0, size, 2)]
        for mn, pair in enumerate(pairs, 1):
            home, away = pair
            data = {"tournament_id": t["id"], "round_number": 1, "match_number": mn,
                    "home_team_id": home, "away_team_id": away, "status": "scheduled"}
            if home is None or away is None:
                data.update({"home_score": 0, "away_score": 0, "status": "completed"})
            supabase.table("tournament_matches").insert(data).execute()
        await create_next_knockout_round(t, 1)
    supabase.table("tournaments").update({"status": "active"}).eq("id", t["id"]).execute()


async def create_next_knockout_round(t, round_number):
    current = sorted(rows("tournament_matches", tournament_id=t["id"], round_number=round_number), key=lambda x: x["match_number"])
    if not current or not all(m["status"] == "completed" for m in current):
        return
    winners = [m["home_team_id"] or m["away_team_id"] for m in current]
    if len(winners) == 1:
        supabase.table("tournaments").update({"status": "completed"}).eq("id", t["id"]).execute()
        return
    next_round = round_number + 1
    if rows("tournament_matches", tournament_id=t["id"], round_number=next_round):
        return
    for mn, pair in enumerate(next_round_pairings(winners), 1):
        supabase.table("tournament_matches").insert({
            "tournament_id": t["id"], "round_number": next_round, "match_number": mn,
            "home_team_id": pair[0], "away_team_id": pair[1], "status": "scheduled"
        }).execute()


class ScoreModal(discord.ui.Modal, title="Input Skor"):
    home = discord.ui.TextInput(label="Skor Home", placeholder="0", max_length=3)
    away = discord.ui.TextInput(label="Skor Away", placeholder="0", max_length=3)

    def __init__(self, match_id, tournament_id):
        super().__init__()
        self.match_id = match_id
        self.tournament_id = tournament_id

    async def on_submit(self, interaction):
        t = tournament(self.tournament_id)
        if not t or not can_manage(interaction, t):
            return await reply(interaction, "❌ Hanya organizer / Manage Server yang bisa input skor.")
        try:
            hs, ass = int(self.home.value), int(self.away.value)
            if hs < 0 or ass < 0:
                raise ValueError
        except ValueError:
            return await reply(interaction, "❌ Skor harus angka 0 atau lebih.")
        match = rows("tournament_matches", id=self.match_id)
        if not match:
            return await reply(interaction, "❌ Match tidak ditemukan.")
        if t["format"] == "knockout" and hs == ass:
            return await reply(interaction, "⚠️ Knock-out tidak boleh seri. Masukkan skor final setelah extra time/penalty.")
        supabase.table("tournament_matches").update({"home_score": hs, "away_score": ass, "status": "completed"}).eq("id", self.match_id).execute()
        if t["format"] == "knockout":
            await create_next_knockout_round(t, match[0]["round_number"])
        await interaction.response.send_message("✅ Skor tersimpan. Standings/bracket diperbarui.", ephemeral=True)


class ScoreButton(discord.ui.Button):
    def __init__(self, match_id, tournament_id):
        super().__init__(label="Input Score", emoji="📝", style=discord.ButtonStyle.primary)
        self.match_id = match_id
        self.tournament_id = tournament_id

    async def callback(self, interaction):
        await interaction.response.send_modal(ScoreModal(self.match_id, self.tournament_id))


class Dashboard(discord.ui.View):
    def __init__(self, t):
        super().__init__(timeout=900)
        self.t = t
        self.add_item(RefreshButton(t["id"]))
        self.add_item(ParticipantsButton(t["id"]))
        self.add_item(ScheduleButton(t["id"]))
        self.add_item(ResultsButton(t["id"]))
        if t["format"] == "league":
            self.add_item(StandingsButton(t["id"]))
        else:
            self.add_item(BracketButton(t["id"]))
        scheduled = [m for m in rows("tournament_matches", tournament_id=t["id"]) if m["status"] == "scheduled" and m["home_team_id"] and m["away_team_id"]]
        if len(scheduled) <= 19:
            for m in scheduled:
                self.add_item(ScoreButton(m["id"], t["id"]))


class RefreshButton(discord.ui.Button):
    def __init__(self, tid):
        super().__init__(label="Refresh", emoji="🔄", style=discord.ButtonStyle.secondary)
        self.tid = tid
    async def callback(self, interaction):
        t = tournament(self.tid)
        await interaction.response.edit_message(embed=await embed(t), view=Dashboard(t))


class ParticipantsButton(discord.ui.Button):
    def __init__(self, tid):
        super().__init__(label="Participants", emoji="👥", style=discord.ButtonStyle.secondary)
        self.tid = tid
    async def callback(self, interaction):
        ps = rows("tournament_participants", tournament_id=self.tid)
        await reply(interaction, "👥 Participants\n" + ("\n".join("• <@" + str(p["user_id"]) + ">" for p in ps) or "Belum ada peserta."))


class ScheduleButton(discord.ui.Button):
    def __init__(self, tid):
        super().__init__(label="Schedule", emoji="📅", style=discord.ButtonStyle.secondary)
        self.tid = tid
    async def callback(self, interaction):
        ms = sorted(rows("tournament_matches", tournament_id=self.tid), key=lambda m: (m["round_number"], m["match_number"]))
        lines = []
        for m in ms[:50]:
            h = "<@" + str(m["home_team_id"]) + ">" if m["home_team_id"] else "BYE/TBD"
            a = "<@" + str(m["away_team_id"]) + ">" if m["away_team_id"] else "BYE/TBD"
            score = str(m["home_score"]) + "-" + str(m["away_score"]) if m["status"] == "completed" else "vs"
            lines.append("R" + str(m["round_number"]) + " M" + str(m["match_number"]) + ": " + h + " " + score + " " + a)
        await reply(interaction, "📅 Schedule\n" + ("\n".join(lines) or "Belum ada jadwal."))


class StandingsButton(discord.ui.Button):
    def __init__(self, tid):
        super().__init__(label="Standings", emoji="🏆", style=discord.ButtonStyle.primary)
        self.tid = tid
    async def callback(self, interaction):
        ps = rows("tournament_participants", tournament_id=self.tid)
        ms = rows("tournament_matches", tournament_id=self.tid)
        table = standings([p["user_id"] for p in ps], ms)
        lines = ["Pos • Participant • P • W-D-L • GF:GA • Pts"]
        for pos, r in enumerate(table, 1):
            lines.append(str(pos) + ". <@" + str(r["team_id"]) + "> • " + str(r["played"]) + " • " + str(r["wins"]) + "-" + str(r["draws"]) + "-" + str(r["losses"]) + " • " + str(r["for"]) + ":" + str(r["against"]) + " • **" + str(r["points"]) + "**")
        await reply(interaction, "\n".join(lines))


class BracketButton(discord.ui.Button):
    def __init__(self, tid):
        super().__init__(label="Bracket", emoji="🧩", style=discord.ButtonStyle.primary)
        self.tid = tid
    async def callback(self, interaction):
        ms = sorted(rows("tournament_matches", tournament_id=self.tid), key=lambda m: (m["round_number"], m["match_number"]))
        lines = []
        for m in ms:
            h = "<@" + str(m["home_team_id"]) + ">" if m["home_team_id"] else "TBD"
            a = "<@" + str(m["away_team_id"]) + ">" if m["away_team_id"] else "TBD"
            result = " `" + str(m["home_score"]) + "-" + str(m["away_score"]) + "`" if m["status"] == "completed" else ""
            lines.append("R" + str(m["round_number"]) + " M" + str(m["match_number"]) + ": " + h + " vs " + a + result)
        await reply(interaction, "🧩 Bracket\n" + ("\n".join(lines) or "Bracket belum dibuat."))


class ResultsButton(discord.ui.Button):
    def __init__(self, tid):
        super().__init__(label="Results", emoji="📊", style=discord.ButtonStyle.secondary)
        self.tid = tid
    async def callback(self, interaction):
        ms = rows("tournament_matches", tournament_id=self.tid)
        done = [m for m in ms if m["status"] == "completed"]
        lines = []
        for m in done[-30:]:
            lines.append("R" + str(m["round_number"]) + " M" + str(m["match_number"]) + ": <@" + str(m["home_team_id"]) + "> **" + str(m["home_score"]) + "-" + str(m["away_score"]) + "** <@" + str(m["away_team_id"]) + ">")
        await reply(interaction, "📊 Results\n" + ("\n".join(lines) or "Belum ada hasil."))


class JoinView(discord.ui.View):
    def __init__(self, tid):
        super().__init__(timeout=None)
        self.add_item(JoinButton(tid))


class JoinButton(discord.ui.Button):
    def __init__(self, tid):
        super().__init__(label="Join Tournament", emoji="🎟️", style=discord.ButtonStyle.success)
        self.tid = tid
    async def callback(self, interaction):
        t = tournament(self.tid)
        if not t or t["status"] != "registration":
            return await reply(interaction, "❌ Pendaftaran sudah ditutup.")
        ps = rows("tournament_participants", tournament_id=self.tid)
        if len(ps) >= t["max_participants"]:
            return await reply(interaction, "❌ Slot tournament sudah penuh.")
        if rows("tournament_participants", tournament_id=self.tid, user_id=interaction.user.id):
            return await reply(interaction, "ℹ️ Lu sudah terdaftar.")
        supabase.table("tournament_participants").insert({"tournament_id": self.tid, "user_id": interaction.user.id}).execute()
        await reply(interaction, "✅ Lu berhasil masuk tournament.")


class Tournament(commands.Cog):
    tournament = app_commands.Group(name="tournament", description="Tournament Maker")

    @tournament.command(name="create", description="Buat League atau Knock-out tournament.")
    @app_commands.describe(name="Nama tournament", format="Format", max_participants="Maksimal peserta")
    @app_commands.choices(format=[app_commands.Choice(name="League", value="league"), app_commands.Choice(name="Knock-out", value="knockout")])
    async def create(self, interaction, name: str, format: app_commands.Choice[str], max_participants: app_commands.Range[int, 2, 64]):
        if not interaction.user.guild_permissions.manage_guild:
            return await reply(interaction, "❌ Butuh Manage Server untuk membuat tournament.")
        data = supabase.table("tournaments").insert({"guild_id": interaction.guild_id, "organizer_id": interaction.user.id, "name": name[:80], "format": format.value, "max_participants": max_participants, "status": "registration"}).execute().data[0]
        await interaction.response.send_message(embed=await embed(data), view=JoinView(data["id"]))

    @tournament.command(name="start", description="Tutup pendaftaran dan auto-generate jadwal/bracket.")
    async def start(self, interaction, tournament_id: int):
        t = tournament(tournament_id)
        if not t or t["guild_id"] != interaction.guild_id:
            return await reply(interaction, "❌ Tournament tidak ditemukan.")
        if not can_manage(interaction, t):
            return await reply(interaction, "❌ Hanya organizer / Manage Server.")
        if t["status"] != "registration":
            return await reply(interaction, "❌ Tournament ini bukan fase pendaftaran.")
        try:
            await start_tournament(t)
        except ValueError as exc:
            return await reply(interaction, "❌ " + str(exc))
        t = tournament(tournament_id)
        await interaction.response.send_message(embed=await embed(t), view=Dashboard(t))

    @tournament.command(name="score", description="Input skor berdasarkan Match ID.")
    async def score(self, interaction, tournament_id: int, match_id: int, home_score: int, away_score: int):
        t = tournament(tournament_id)
        if not t or t["guild_id"] != interaction.guild_id:
            return await reply(interaction, "❌ Tournament tidak ditemukan.")
        if not can_manage(interaction, t):
            return await reply(interaction, "❌ Hanya organizer / Manage Server.")
        match = rows("tournament_matches", id=match_id, tournament_id=tournament_id)
        if not match:
            return await reply(interaction, "❌ Match tidak ditemukan.")
        if match[0]["status"] != "scheduled":
            return await reply(interaction, "❌ Match sudah selesai.")
        if home_score < 0 or away_score < 0:
            return await reply(interaction, "❌ Skor tidak boleh negatif.")
        if t["format"] == "knockout" and home_score == away_score:
            return await reply(interaction, "⚠️ Knock-out tidak boleh seri. Masukkan skor final setelah extra time/penalty.")
        supabase.table("tournament_matches").update({"home_score": home_score, "away_score": away_score, "status": "completed"}).eq("id", match_id).execute()
        if t["format"] == "knockout":
            await create_next_knockout_round(t, match[0]["round_number"])
        await interaction.response.send_message("✅ Skor tersimpan dan logic tournament diperbarui.", ephemeral=True)

    @tournament.command(name="panel", description="Buka dashboard tournament.")
    async def panel(self, interaction, tournament_id: int):
        t = tournament(tournament_id)
        if not t or t["guild_id"] != interaction.guild_id:
            return await reply(interaction, "❌ Tournament tidak ditemukan.")
        await interaction.response.send_message(embed=await embed(t), view=Dashboard(t))


async def setup(bot):
    await bot.add_cog(Tournament(bot))
