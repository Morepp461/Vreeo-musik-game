import discord
from ..config import DISCORD_DJ_ROLE_ID,MUSIC_CHANNEL_ID

def in_music_channel(interaction):
    return not MUSIC_CHANNEL_ID or interaction.channel_id==MUSIC_CHANNEL_ID

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
    if can_control(interaction.user):
        return False
    await interaction.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
    return True
