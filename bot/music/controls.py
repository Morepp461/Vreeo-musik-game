import discord
import time
def _fmt(s):
    s=max(0,int(s or 0)); return f"{s//60}:{s%60:02d}"

def build_now_playing_embed(q):
    t=q.current
    if not t:
        return discord.Embed(title="✦ VREEO MUSIC",description="**Nothing is playing.**\nUse `/play` to start.")
    now=time.monotonic()
    elapsed=max(0,q.started_offset+(q.paused_at or now)-q.started_at) if q.started_at else q.started_offset
    duration=t.duration or 0
    if duration:
        ratio=min(1,max(0,elapsed/duration)); filled=round(ratio*18)
        progress=f"`{_fmt(elapsed)}` {'━'*filled+'●'+'━'*(17-filled)} `{_fmt(duration)}`"
    else: progress=f"`{_fmt(elapsed)}`"
    status="⏸ PAUSED" if q.paused else "▶ PLAYING"
    e=discord.Embed(title="✦ VREEO MUSIC  •  NOW PLAYING",description=f"### [{t.title}]({t.webpage_url})\n{progress}\n\n**{status}**")
    if t.thumbnail: e.set_image(url=t.thumbnail)
    e.add_field(name="ARTIST / SOURCE",value=f"`{(t.uploader or 'Unknown')[:80]}`",inline=True)
    e.add_field(name="REQUESTED BY",value=f"<@{t.requested_by}>" if t.requested_by else "-",inline=True)
    e.add_field(name="QUEUE",value=f"`{len(q.tracks)}`",inline=True)
    e.add_field(name="VOLUME",value=f"`{int(q.volume*100)}%`",inline=True)
    e.add_field(name="LOOP",value=f"`{q.loop.upper()}`",inline=True)
    e.add_field(name="MODE",value=f"`{q.filter.upper()}` • `{q.speed:.2f}x`",inline=True)
    e.set_footer(text="VREEO MUSIC  •  Premium Player")
    return e

from . import favorites
from .guard import can_control

class QueueJumpView(discord.ui.View):
    def __init__(self, player, guild_id:int):
        super().__init__(timeout=90)
        self.player=player
        self.guild_id=guild_id
        q=player.queue_for(guild_id)
        options=[]
        for index, track in enumerate(q.tracks[:25]):
            options.append(discord.SelectOption(label=f"{index+1}. {track.title}"[:100], value=str(index)))
        if not options:
            self.add_item(discord.ui.Button(label="Queue kosong", disabled=True))
            return
        select=discord.ui.Select(placeholder="Pilih lagu untuk langsung jump...", options=options)
        select.callback=self.jump
        self.add_item(select)

    @property
    def guild(self):
        return self.player.bot.get_guild(self.guild_id)

    async def jump(self, interaction:discord.Interaction):
        if not can_control(interaction.user):
            return await interaction.response.send_message("🔒 Kamu tidak punya akses kontrol player.",ephemeral=True)
        q=self.player.queue_for(self.guild_id)
        try:
            position=int(interaction.data["values"][0])
        except Exception:
            return await interaction.response.send_message("❌ Pilihan queue tidak valid.",ephemeral=True)
        if position < 0 or position >= len(q.tracks):
            return await interaction.response.send_message("❌ Lagu itu sudah tidak ada di queue.",ephemeral=True)
        target=q.tracks[position]
        for _ in range(position):
            q.played.append(q.tracks.pop(0))
        self.player.skip(self.guild)
        await interaction.response.send_message(f"⏭️ Jump ke **{target.title}**",ephemeral=True)

class NowPlayingView(discord.ui.View):
    def __init__(self,player,guild_id:int):
        super().__init__(timeout=900)
        self.player=player
        self.guild_id=guild_id

    @property
    def guild(self):
        return self.player.bot.get_guild(self.guild_id)

    async def guard(self,interaction):
        if not can_control(interaction.user):
            await interaction.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
            return False
        if not self.guild:
            await interaction.response.send_message("Guild tidak ditemukan.",ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="⏮️",style=discord.ButtonStyle.secondary)
    async def previous(self,interaction:discord.Interaction,button:discord.ui.Button):
        if not await self.guard(interaction): return
        await interaction.response.send_message("⏮️ Previous." if self.player.previous(self.guild) else "Tidak ada lagu sebelumnya.",ephemeral=True)

    @discord.ui.button(emoji="⏯️",style=discord.ButtonStyle.primary)
    async def pause_resume(self,interaction:discord.Interaction,button:discord.ui.Button):
        if not await self.guard(interaction): return
        v=self.guild.voice_client
        if v and v.is_paused(): self.player.resume(self.guild)
        elif v and v.is_playing(): self.player.pause(self.guild)
        await interaction.response.send_message("⏯️",ephemeral=True)

    @discord.ui.button(emoji="⏭️",style=discord.ButtonStyle.secondary)
    async def skip(self,interaction:discord.Interaction,button:discord.ui.Button):
        if not await self.guard(interaction): return
        self.player.skip(self.guild)
        await interaction.response.send_message("⏭️ Skip.",ephemeral=True)

    @discord.ui.button(emoji="🔀",style=discord.ButtonStyle.secondary)
    async def shuffle(self,interaction:discord.Interaction,button:discord.ui.Button):
        if not await self.guard(interaction): return
        self.player.queue_for(self.guild_id).shuffle()
        await interaction.response.send_message("🔀 Queue diacak.",ephemeral=True)

    @discord.ui.button(emoji="🔁",style=discord.ButtonStyle.secondary)
    async def loop(self,interaction:discord.Interaction,button:discord.ui.Button):
        if not await self.guard(interaction): return
        q=self.player.queue_for(self.guild_id)
        q.loop={"off":"queue","queue":"track","track":"off"}[q.loop]
        await interaction.response.send_message(f"🔁 Loop: **{q.loop}**",ephemeral=True)

    @discord.ui.button(emoji="⭐",style=discord.ButtonStyle.secondary,row=1)
    async def favorite(self,interaction:discord.Interaction,button:discord.ui.Button):
        q=self.player.queue_for(self.guild_id)
        if not q.current:
            return await interaction.response.send_message("Tidak ada lagu.",ephemeral=True)
        try:
            favorites.add(interaction.user.id,q.current)
            await interaction.response.send_message("⭐ Disimpan ke favorit.",ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(f"❌ Gagal simpan favorit: {exc}",ephemeral=True)

    @discord.ui.button(emoji="⏹️",style=discord.ButtonStyle.danger,row=1)
    async def stop(self,interaction:discord.Interaction,button:discord.ui.Button):
        if not await self.guard(interaction): return
        await self.player.disconnect(self.guild)
        await interaction.response.send_message("⏹️ Stop.",ephemeral=True)

    @discord.ui.button(emoji="📜",style=discord.ButtonStyle.secondary,row=1)
    async def queue(self,interaction:discord.Interaction,button:discord.ui.Button):
        q=self.player.queue_for(self.guild_id)
        text="\n".join(f"{n}. {t.title}" for n,t in enumerate(q.tracks[:20],1)) or "Queue kosong."
        await interaction.response.send_message(text[:1900],ephemeral=True)
