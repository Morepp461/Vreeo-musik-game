import discord
from ..config import MUSIC_CHANNEL_ID
from . import settings

def in_music_channel(interaction):
    channel_id=MUSIC_CHANNEL_ID
    if not channel_id:
        try:
            channel_id=settings.get_channel()
        except Exception:
            channel_id=None
    return not channel_id or interaction.channel_id==int(channel_id)

def is_manager(member):
    if not isinstance(member,discord.Member):
        return False
    return bool(member.guild_permissions.administrator or member.guild_permissions.manage_guild)

def can_control(member):
    # Semua member server boleh mengontrol player.
    return isinstance(member,discord.Member)

async def reject_channel(interaction):
    if in_music_channel(interaction):
        return False
    await interaction.response.send_message("🎵 Gunakan music command di channel musik yang sudah disetel.",ephemeral=True)
    return True

async def reject_manager(interaction):
    # Nama fungsi dipertahankan agar command lama tetap kompatibel.
    # Semua member boleh menjalankan command musik; pembatasan hanya channel.
    return await reject_channel(interaction)
