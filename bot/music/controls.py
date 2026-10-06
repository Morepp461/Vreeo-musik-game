import asyncio
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
    if q.autoplay_mode=="artist" and q.autoplay_artist:
        autoplay_label=f"🎤 {q.autoplay_artist[:60]}"
    elif q.autoplay_mode=="genre":
        autoplay_label=f"🎚️ {q.autoplay_genre.upper()}"
    else:
        autoplay_label="🎲 RANDOM"
    e.add_field(name="AUTOPLAY",value=f"`{'ON' if q.autoplay else 'OFF'}` • {autoplay_label}",inline=False)
    e.set_footer(text="VREEO MUSIC  •  Premium Player")
    return e

from . import favorites
from .guard import can_control

class QueueJumpView(discord.ui.View):
    def __init__(self, player, guild_id:int):
        super().__init__(timeout=900)
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
        await interaction.response.defer(ephemeral=True)
        if not can_control(interaction.user):
            return await interaction.edit_original_response(content="🔒 Kamu tidak punya akses kontrol player.")
        guild=self.guild
        if not guild:
            return await interaction.edit_original_response(content="❌ Guild tidak ditemukan.")
        q=self.player.queue_for(self.guild_id)
        try:
            position=int(interaction.data["values"][0])
        except Exception:
            return await interaction.edit_original_response(content="❌ Pilihan queue tidak valid.")
        if position < 0 or position >= len(q.tracks):
            return await interaction.edit_original_response(content="❌ Lagu itu sudah tidak ada di queue.")
        target=q.tracks[position]
        for _ in range(position):
            q.played.append(q.tracks.pop(0))
        voice=guild.voice_client
        if voice and (voice.is_playing() or voice.is_paused()):
            self.player.skip(guild)
        else:
            asyncio.create_task(self.player.play_next(guild))
        await interaction.edit_original_response(content=f"⏭️ Jump ke **{target.title}**")


class ArtistAutoplayModal(discord.ui.Modal, title="🎤 Autoplay by Artist"):
    artist=discord.ui.TextInput(label="Nama artis",placeholder="Contoh: The Weeknd",max_length=100,required=True)

    def __init__(self, player, guild_id):
        super().__init__()
        self.player=player
        self.guild_id=guild_id

    async def on_submit(self, interaction:discord.Interaction):
        if not can_control(interaction.user):
            return await interaction.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
        artist=str(self.artist.value).strip()
        q=self.player.queue_for(self.guild_id)
        q.autoplay=True
        q.autoplay_mode="artist"
        q.autoplay_artist=artist
        await interaction.response.send_message(f"🎤 Autoplay artist: **{artist}**",ephemeral=True)
        guild=self.player.bot.get_guild(self.guild_id)
        if guild: await self.player.refresh_now_playing(guild)


class AutoplayView(discord.ui.View):
    def __init__(self, player, guild_id):
        super().__init__(timeout=180)
        self.player=player
        self.guild_id=guild_id
        options=[
            discord.SelectOption(label="🎲 Random",value="random",description="Autoplay bebas dari semua musik"),
            discord.SelectOption(label="🎚️ Genre",value="genre",description="Pilih genre musik"),
            discord.SelectOption(label="🎤 Artist",value="artist",description="Autoplay dari artis tertentu"),
            discord.SelectOption(label="⛔ Off",value="off",description="Matikan autoplay"),
        ]
        select=discord.ui.Select(placeholder="Pilih mode autoplay...",options=options)
        select.callback=self.select_mode
        self.add_item(select)

    async def select_mode(self, interaction:discord.Interaction):
        if not can_control(interaction.user):
            return await interaction.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
        value=interaction.data["values"][0]
        q=self.player.queue_for(self.guild_id)
        if value=="artist":
            return await interaction.response.send_modal(ArtistAutoplayModal(self.player,self.guild_id))
        if value=="genre":
            return await interaction.response.edit_message(content="🎚️ Pilih genre autoplay:",view=GenreAutoplayView(self.player,self.guild_id))
        if value=="off":
            q.autoplay=False
        else:
            q.autoplay=True
            q.autoplay_mode="random"
            q.autoplay_genre="random"
            q.autoplay_artist=None
        await interaction.response.edit_message(content=f"🤖 Autoplay: **{'ON' if q.autoplay else 'OFF'}**",view=NowPlayingView(self.player,self.guild_id))
        guild=self.player.bot.get_guild(self.guild_id)
        if guild: await self.player.refresh_now_playing(guild)


class GenreAutoplayView(discord.ui.View):
    def __init__(self, player, guild_id):
        super().__init__(timeout=180)
        self.player=player
        self.guild_id=guild_id
        genres=[
            ("Pop","pop"),("Rock","rock"),("R&B / Soul","rnb"),("Hip-Hop / Rap","hiphop"),
            ("EDM / Electronic","edm"),("Lo-fi / Chill","lofi"),("J-Pop","jpop"),("K-Pop","kpop"),
            ("Indonesia","indonesia"),("Classical","classical"),("Disco / Funk","disco"),("Jazz","jazz"),("Metal","metal")
        ]
        select=discord.ui.Select(placeholder="Pilih genre...",options=[discord.SelectOption(label=a,value=b) for a,b in genres])
        select.callback=self.select_genre
        self.add_item(select)
        back=discord.ui.Button(label="← Kembali",style=discord.ButtonStyle.secondary)
        back.callback=self.back
        self.add_item(back)

    async def select_genre(self, interaction:discord.Interaction):
        if not can_control(interaction.user):
            return await interaction.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
        genre=interaction.data["values"][0]
        q=self.player.queue_for(self.guild_id)
        q.autoplay=True
        q.autoplay_mode="genre"
        q.autoplay_genre=genre
        q.autoplay_artist=None
        await interaction.response.edit_message(content=f"🎚️ Genre autoplay: **{genre.upper()}**",view=NowPlayingView(self.player,self.guild_id))
        guild=self.player.bot.get_guild(self.guild_id)
        if guild: await self.player.refresh_now_playing(guild)

    async def back(self, interaction:discord.Interaction):
        if not can_control(interaction.user):
            return await interaction.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
        await interaction.response.edit_message(content="🤖 Pilih mode autoplay:",view=AutoplayView(self.player,self.guild_id))


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

    @discord.ui.button(label="🤖 Autoplay",style=discord.ButtonStyle.secondary,row=2)
    async def autoplay(self,interaction:discord.Interaction,button:discord.ui.Button):
        if not await self.guard(interaction): return
        await interaction.response.send_message("🤖 Pilih mode autoplay:",view=AutoplayView(self.player,self.guild_id),ephemeral=True)

    @discord.ui.button(emoji="📜",style=discord.ButtonStyle.secondary,row=1)
    async def queue(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        q=self.player.queue_for(self.guild_id)
        if not q.tracks:
            return await interaction.edit_original_response(content="Queue kosong.")
        text="\n".join(f"**{n}.** {t.title}" for n,t in enumerate(q.tracks[:25],1))
        await interaction.edit_original_response(content=f"### 📜 Queue\n{text}",view=QueueJumpView(self.player,self.guild_id))
