import logging
import random
from datetime import datetime, timezone

import discord

from ..database import supabase
from ..config import DISCORD_GUILD_ID, GAME_CATEGORY_ID

log = logging.getLogger(__name__)

GAME_NAME = "WNI SIMULATOR🇮🇩🦅"
GENERAL_CHANNEL_KEY = "general"
VOICE_CHANNEL_KEY = "voice-game"

ROLE_DEFINITIONS = [
    ("WNI | Warga", "Warga WNI Simulator"),
    ("WNI | Pemerintah", "Afiliasi pemerintahan"),
    ("WNI | Polisi", "Penegak hukum"),
    ("WNI | Tenaga Kesehatan", "Tenaga kesehatan"),
    ("WNI | Pendidikan", "Tenaga pendidikan"),
    ("WNI | Pengusaha", "Pemilik/pengelola usaha"),
    ("WNI | Karyawan", "Pekerja/karyawan"),
    ("WNI | Pedagang", "Pedagang"),
    ("WNI | Media", "Media dan jurnalis"),
    ("WNI | Organisasi", "Anggota organisasi"),
    ("WNI | Politik", "Afiliasi politik"),
    ("WNI | Admin Dunia", "Kontrol dunia / God Mode"),
]

AI_FIRST_NAMES = [
    "Agus","Budi","Citra","Dewi","Eko","Fajar","Gilang","Hana","Indra","Joko",
    "Kurnia","Laras","Maya","Nadia","Oki","Putri","Raka","Sari","Teguh","Vina",
]
AI_LAST_NAMES = [
    "Pratama","Wijaya","Saputra","Permata","Santoso","Hidayat","Nugroho","Lestari",
    "Ramadhan","Kusuma","Wibowo","Siregar","Setiawan","Maulana","Utami",
]
AI_CITIES = [
    "Jakarta","Surabaya","Bandung","Medan","Semarang","Makassar","Malang",
    "Palembang","Denpasar","Yogyakarta","Balikpapan","Banjarmasin","Padang",
    "Pekanbaru","Manado","Samarinda","Pontianak","Mataram","Solo","Bogor",
]
AI_JOBS = [
    "Karyawan swasta","Pedagang","Guru","Perawat","Polisi","Teknisi",
    "Programmer","Dokter","Petani","Sopir","Wiraswasta","Jurnalis",
    "Akuntan","Arsitek","Montir","Barista","Pengacara","Pegawai pemerintah",
]

def _binding(guild_id: int, entity_type: str, entity_key: str):
    r = supabase.table("game_discord_bindings").select("*").eq(
        "guild_id", str(guild_id)
    ).eq("entity_type", entity_type).eq("entity_key", entity_key).limit(1).execute()
    return r.data[0] if r.data else None

def _save_binding(guild_id: int, entity_type: str, entity_key: str, discord_id: int, name: str):
    supabase.table("game_discord_bindings").upsert({
        "guild_id": str(guild_id),
        "entity_type": entity_type,
        "entity_key": entity_key,
        "discord_id": str(discord_id),
        "discord_name": name,
        "status": "active",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="guild_id,entity_type,entity_key").execute()

def _game_overwrites(guild: discord.Guild, roles, *, voice=False):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True,
            connect=voice,
            speak=voice,
            send_messages=not voice,
        )
    }
    for role in roles:
        overwrites[role] = discord.PermissionOverwrite(
            view_channel=True,
            connect=voice,
            speak=voice,
            send_messages=not voice,
        )
    return overwrites

async def ensure_game_roles(guild: discord.Guild):
    roles = []
    for name, _ in ROLE_DEFINITIONS:
        role = discord.utils.get(guild.roles, name=name)
        if role is None:
            role = await guild.create_role(name=name, reason="WNI SIMULATOR bootstrap")
            log.info("Created game role %s (%s)", name, role.id)
        roles.append(role)
        _save_binding(guild.id, "role", name, role.id, role.name)
    return roles

async def _get_game_category(guild: discord.Guild):
    # HARD RULE: never fallback to another category and never create a category.
    category = guild.get_channel(GAME_CATEGORY_ID)
    if category is None:
        try:
            category = await guild.fetch_channel(GAME_CATEGORY_ID)
        except Exception:
            category = None
    if not isinstance(category, discord.CategoryChannel):
        raise RuntimeError(
            f"WNI SIMULATOR category {GAME_CATEGORY_ID} tidak ditemukan sebagai kategori. "
            "Bot tidak akan membuat/fallback ke kategori lain."
        )
    return category

async def ensure_game_channels(guild: discord.Guild, roles):
    category = await _get_game_category(guild)

    text = None
    voice = None
    for ch in guild.channels:
        if ch.category_id != GAME_CATEGORY_ID:
            continue
        if ch.name == "wni-general" and isinstance(ch, discord.TextChannel):
            text = ch
        elif ch.name == "wni-ngobrol" and isinstance(ch, discord.VoiceChannel):
            voice = ch

    if text is None:
        text = await guild.create_text_channel(
            "wni-general",
            category=category,
            overwrites=_game_overwrites(guild, roles, voice=False),
            reason="WNI SIMULATOR global game channel",
        )
    else:
        await text.edit(
            category=category,
            overwrites=_game_overwrites(guild, roles, voice=False),
            reason="WNI SIMULATOR channel reconciliation",
        )

    if voice is None:
        voice = await guild.create_voice_channel(
            "wni-ngobrol",
            category=category,
            overwrites=_game_overwrites(guild, roles, voice=True),
            reason="WNI SIMULATOR game voice channel",
        )
    else:
        await voice.edit(
            category=category,
            overwrites=_game_overwrites(guild, roles, voice=True),
            reason="WNI SIMULATOR channel reconciliation",
        )

    _save_binding(guild.id, "channel", GENERAL_CHANNEL_KEY, text.id, text.name)
    _save_binding(guild.id, "channel", VOICE_CHANNEL_KEY, voice.id, voice.name)
    return text, voice

def seed_ai_population(target=120):
    existing = supabase.table("game_ai_characters").select("external_key", count="exact").execute()
    current = existing.count or 0
    if current >= target:
        return 0

    rows = []
    used = set()
    for i in range(current, target):
        while True:
            name = f"{random.choice(AI_FIRST_NAMES)} {random.choice(AI_LAST_NAMES)}"
            if name not in used:
                used.add(name)
                break
        rows.append({
            "external_key": f"seed-ai-{i+1:04d}",
            "name": name,
            "age": random.randint(18, 65),
            "gender": random.choice(["Laki-laki", "Perempuan"]),
            "occupation": random.choice(AI_JOBS),
            "city": random.choice(AI_CITIES),
            "personality": {
                "openness": random.randint(20, 90),
                "conscientiousness": random.randint(20, 90),
                "sociability": random.randint(20, 90),
                "risk_tolerance": random.randint(10, 80),
            },
            "goals": random.sample(
                ["menabung","membeli rumah","mengembangkan karier","membangun usaha",
                 "menikah","membantu keluarga","berinvestasi"], k=2
            ),
            "wallet": random.randint(1_500_000, 15_000_000),
        })
    if rows:
        supabase.table("game_ai_characters").upsert(rows, on_conflict="external_key").execute()
    return len(rows)

def seed_world_state():
    supabase.table("game_world_state").upsert({
        "id": 1,
        "world_name": GAME_NAME,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="id").execute()

def create_bootstrap_event(ai_count: int):
    title = "WNI SIMULATOR resmi dimulai"
    description = (
        f"Dunia simulasi Indonesia telah diinisialisasi dengan {ai_count} karakter AI. "
        "Ekonomi, pekerjaan, hubungan sosial, bisnis, pemerintahan, dan peristiwa dunia "
        "akan berkembang berdasarkan state database dan aturan simulasi."
    )
    supabase.table("game_events").insert({
        "event_type": "world_bootstrap",
        "title": title,
        "description": description,
        "severity": 1,
        "metadata": {"ai_population": ai_count, "source": "system"},
    }).execute()
    return title, description

async def bootstrap_guild(guild: discord.Guild):
    if DISCORD_GUILD_ID and guild.id != DISCORD_GUILD_ID:
        return None

    seed_world_state()
    ai_added = seed_ai_population(120)
    roles = await ensure_game_roles(guild)
    text, voice = await ensure_game_channels(guild, roles)

    existing_event = supabase.table("game_events").select("id").eq(
        "event_type", "world_bootstrap"
    ).limit(1).execute()
    if not existing_event.data:
        _, description = create_bootstrap_event(120)
        embed = discord.Embed(
            title=f"🇮🇩 {GAME_NAME}",
            description="**Dunia telah online.**\n\n" + description,
            color=discord.Color.dark_red(),
        )
        embed.add_field(name="👥 Populasi AI", value="120 karakter", inline=True)
        embed.add_field(name="🎭 Role game", value=f"{len(roles)} role", inline=True)
        embed.add_field(name="📡 Kanal global", value="#wni-general + 🔊 wni-ngobrol", inline=True)
        embed.set_footer(text="Database adalah sumber kebenaran dunia.")
        await text.send(embed=embed)

    return {
        "guild_id": guild.id,
        "category_id": GAME_CATEGORY_ID,
        "general_channel_id": text.id,
        "voice_channel_id": voice.id,
        "roles_created_or_verified": len(roles),
        "ai_added": ai_added,
    }
