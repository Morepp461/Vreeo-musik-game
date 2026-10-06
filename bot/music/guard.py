import discord
from ..config import DISCORD_DJ_ROLE_ID,MUSIC_CHANNEL_ID
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
    if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
        return True
    return bool(DISCORD_DJ_ROLE_ID and any(role.id==DISCORD_DJ_ROLE_ID for role in member.roles))

def can_control(member):
    return is_manager(member)

async def reject_channel(interaction):
    if in_music_channel(interaction):
        return False
    await interaction.response.send_message("🎵 Gunakan music command di channel musik yang sudah disetel.",ephemeral=True)
    return True

async def reject_manager(interaction):
    if not in_music_channel(interaction):
        await interaction.response.send_message("🎵 Gunakan music command di channel musik yang sudah disetel.",ephemeral=True)
        return True
    if can_control(interaction.user):
        return False
    await interaction.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
    return True
