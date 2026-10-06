import asyncio
import discord
import time
import re
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
    e.add_field(name="CROSSFADE",value=f"`{q.crossfade:.0f}s`",inline=True)
    if q.autoplay_mode=="artist" and q.autoplay_artist:
        autoplay_label=f"🎤 {q.autoplay_artist[:60]}"
    elif q.autoplay_mode=="genre":
        autoplay_label=f"🎚️ {q.autoplay_genre.upper()}"
    else:
        autoplay_label="🎲 RANDOM"
    e.add_field(name="AUTOPLAY",value=f"`{'ON' if q.autoplay else 'OFF'}` • {autoplay_label}",inline=False)
    e.set_footer(text="VREEO MUSIC  •  Premium Player")
    return e

from . import favorites, premium
from .guard import can_control
from .lyrics import fetch as fetch_lyrics
from .source import search
from .queue import Track
from ..config import MAX_QUEUE_SIZE

async def _kick_autoplay(interaction, player, guild_id):
    guild=player.bot.get_guild(guild_id)
    if not guild:
        return False, "Guild tidak ditemukan."
    voice=guild.voice_client
    if not voice:
        member=getattr(interaction,"user",None)
        channel=getattr(getattr(member,"voice",None),"channel",None)
        if not channel:
            return False, "Masuk voice channel dulu supaya autoplay bisa mulai."
        try:
            voice=await channel.connect()
        except Exception as exc:
            return False, f"Gagal masuk voice channel: {exc}"
    if not voice.is_playing() and not voice.is_paused():
        asyncio.create_task(player.play_next(guild))
    return True, None

class QueueJumpView(discord.ui.View):
    def __init__(self, player, guild_id:int, page:int=0):
        super().__init__(timeout=900)
        self.player=player
        self.guild_id=guild_id
        self.page=max(0,page)
        self.page_size=8
        self._build()

    @property
    def guild(self):
        return self.player.bot.get_guild(self.guild_id)

    def _build(self):
        q=self.player.queue_for(self.guild_id)
        self.clear_items()
        total=len(q.tracks)
        pages=max(1,(total+self.page_size-1)//self.page_size)
        self.page=min(self.page,max(0,pages-1))
        start=self.page*self.page_size
        options=[]
        for index,track in enumerate(q.tracks[start:start+self.page_size],start+1):
            options.append(discord.SelectOption(label=f"{index}. {track.title}"[:100],value=str(index-1)))
        if options:
            select=discord.ui.Select(placeholder="Pilih lagu untuk langsung jump...",options=options,row=0)
            select.callback=self.jump
            self.add_item(select)
            delete=discord.ui.Select(placeholder="🗑️ Pilih lagu untuk dihapus...",options=options,row=1)
            delete.callback=self.delete
            self.add_item(delete)
        else:
            self.add_item(discord.ui.Button(label="Queue kosong",disabled=True))
        prev=discord.ui.Button(label="◀️",style=discord.ButtonStyle.secondary,disabled=self.page<=0,row=2)
        next_=discord.ui.Button(label="▶️",style=discord.ButtonStyle.secondary,disabled=self.page>=pages-1,row=2)
        prev.callback=self.previous_page
        next_.callback=self.next_page
        self.add_item(prev)
        self.add_item(next_)
        back=discord.ui.Button(label="↩️ Now Playing",style=discord.ButtonStyle.primary,row=3)
        back.callback=self.back
        self.add_item(back)

    async def back(self,interaction):
        if not can_control(interaction.user):
            return await interaction.response.send_message("🔒 Kamu tidak punya akses kontrol player.",ephemeral=True)
        guild=self.guild
        if not guild:
            return await interaction.response.send_message("Guild tidak ditemukan.",ephemeral=True)
        await interaction.response.edit_message(embed=build_now_playing_embed(self.player.queue_for(self.guild_id)),view=NowPlayingView(self.player,self.guild_id))

    def embed(self):
        q=self.player.queue_for(self.guild_id)
        total=len(q.tracks)
        pages=max(1,(total+self.page_size-1)//self.page_size)
        e=discord.Embed(title="✦ VREEO MUSIC  •  QUEUE",description=f"**{total} lagu** • Halaman {self.page+1}/{pages}")
        start=self.page*self.page_size
        lines=[]
        for index,t in enumerate(q.tracks[start:start+self.page_size],start+1):
            who=f"<@{t.requested_by}>" if t.requested_by else "Autoplay"
            duration=_fmt(t.duration or 0)
            lines.append(f"**{index}.** {t.title[:80]}\n{duration} • {who}")
        e.add_field(name="UP NEXT",value="\n\n".join(lines) or "Queue kosong.",inline=False)
        if q.current:
            e.set_footer(text=f"Now: {q.current.title[:70]}")
        else:
            e.set_footer(text="VREEO MUSIC • Premium Queue")
        return e

    async def _page(self,interaction,page):
        if not can_control(interaction.user):
            return await interaction.response.send_message("🔒 Kamu tidak punya akses kontrol player.",ephemeral=True)
        self.page=max(0,page)
        self._build()
        await interaction.response.edit_message(embed=self.embed(),view=self)

    async def previous_page(self,interaction):
        await self._page(interaction,self.page-1)

    async def next_page(self,interaction):
        await self._page(interaction,self.page+1)

    async def jump(self,interaction:discord.Interaction):
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

    async def delete(self,interaction:discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not can_control(interaction.user):
            return await interaction.edit_original_response(content="🔒 Kamu tidak punya akses kontrol player.")
        q=self.player.queue_for(self.guild_id)
        try:
            position=int(interaction.data["values"][0])
        except Exception:
            return await interaction.edit_original_response(content="❌ Pilihan queue tidak valid.")
        if position < 0 or position >= len(q.tracks):
            return await interaction.edit_original_response(content="❌ Lagu itu sudah tidak ada di queue.")
        removed=q.remove(position)
        self._build()
        await interaction.edit_original_response(content=f"🗑️ **{removed.title}** dihapus dari queue.",embed=self.embed(),view=self)


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
        q.panel_channel_id=interaction.channel.id
        q.autoplay=True
        q.autoplay_mode="artist"
        q.autoplay_artist=artist
        ok,error=await _kick_autoplay(interaction,self.player,self.guild_id)
        if error:
            await interaction.response.send_message(f"⚠️ {error}",ephemeral=True)
            return
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
        q.panel_channel_id=interaction.channel.id
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
        if q.autoplay:
            ok,error=await _kick_autoplay(interaction,self.player,self.guild_id)
            if error:
                await interaction.response.edit_message(content=f"⚠️ {error}",view=AutoplayView(self.player,self.guild_id))
                return
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
        q.panel_channel_id=interaction.channel.id
        q.autoplay=True
        q.autoplay_mode="genre"
        q.autoplay_genre=genre
        q.autoplay_artist=None
        ok,error=await _kick_autoplay(interaction,self.player,self.guild_id)
        if error:
            await interaction.response.edit_message(content=f"⚠️ {error}",view=GenreAutoplayView(self.player,self.guild_id))
            return
        await interaction.response.edit_message(content=f"🎚️ Genre autoplay: **{genre.upper()}**",view=NowPlayingView(self.player,self.guild_id))
        guild=self.player.bot.get_guild(self.guild_id)
        if guild: await self.player.refresh_now_playing(guild)

    async def back(self, interaction:discord.Interaction):
        if not can_control(interaction.user):
            return await interaction.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
        await interaction.response.edit_message(content="🤖 Pilih mode autoplay:",view=AutoplayView(self.player,self.guild_id))


class LyricsView(discord.ui.View):
    def __init__(self,player,guild_id,title,artist,lyrics):
        super().__init__(timeout=900)
        self.player=player
        self.guild_id=guild_id
        self.title=title
        self.artist=artist
        clean=re.sub(r"\[\d{1,3}:\d{2}(?:\.\d+)?\]\s*","",lyrics).strip()
        self.pages=[clean[i:i+3500] for i in range(0,len(clean),3500)] or ["Lirik kosong."]
        self.page=0
        self._build()

    def _build(self):
        self.clear_items()
        prev=discord.ui.Button(label="◀️",style=discord.ButtonStyle.secondary,disabled=self.page<=0,row=1)
        next_=discord.ui.Button(label="▶️",style=discord.ButtonStyle.secondary,disabled=self.page>=len(self.pages)-1,row=1)
        back=discord.ui.Button(label="↩️ Now Playing",style=discord.ButtonStyle.primary,row=1)
        prev.callback=self.previous
        next_.callback=self.next_page
        back.callback=self.back
        self.add_item(prev)
        self.add_item(next_)
        self.add_item(back)

    def embed(self):
        e=discord.Embed(title="🎤 VREEO MUSIC  •  LYRICS",description=self.pages[self.page])
        e.add_field(name="TRACK",value=self.title[:100],inline=True)
        if self.artist: e.add_field(name="ARTIST",value=self.artist[:100],inline=True)
        e.set_footer(text=f"Page {self.page+1}/{len(self.pages)} • VREEO MUSIC")
        return e

    async def previous(self,interaction):
        self.page=max(0,self.page-1)
        self._build()
        await interaction.response.edit_message(embed=self.embed(),view=self)

    async def next_page(self,interaction):
        self.page=min(len(self.pages)-1,self.page+1)
        self._build()
        await interaction.response.edit_message(embed=self.embed(),view=self)

    async def back(self,interaction):
        guild=self.player.bot.get_guild(self.guild_id)
        if not guild:
            return await interaction.response.send_message("Guild tidak ditemukan.",ephemeral=True)
        await interaction.response.edit_message(embed=build_now_playing_embed(self.player.queue_for(self.guild_id)),view=NowPlayingView(self.player,self.guild_id))


class StatsView(discord.ui.View):
    def __init__(self,player,guild_id):
        super().__init__(timeout=600)
        self.player=player
        self.guild_id=guild_id

    def embed(self):
        s=self.player.stats_for(self.guild_id)
        songs=sorted(s["songs"].items(),key=lambda x:x[1],reverse=True)[:5]
        artists=sorted(s["artists"].items(),key=lambda x:x[1],reverse=True)[:5]
        users=sorted(s["users"].items(),key=lambda x:x[1],reverse=True)[:5]
        hours=s["seconds"]/3600
        song_text="\n".join(f"**{i}.** {name[:55]} — {count}x" for i,(name,count) in enumerate(songs,1)) or "Belum ada data."
        artist_text="\n".join(f"**{i}.** {name[:55]} — {count}x" for i,(name,count) in enumerate(artists,1)) or "Belum ada data."
        user_text="\n".join(f"**{i}.** <@{uid}> — {count}x" for i,(uid,count) in enumerate(users,1) if uid!="0") or "Belum ada data."
        e=discord.Embed(title="✦ VREEO MUSIC  •  STATS",description=f"**{s['plays']}** plays • **{hours:.1f} jam** listening time")
        e.add_field(name="🔥 TOP SONGS",value=song_text,inline=False)
        e.add_field(name="🎤 TOP ARTISTS",value=artist_text,inline=False)
        e.add_field(name="👑 TOP REQUESTERS",value=user_text,inline=False)
        e.set_footer(text="VREEO MUSIC • Runtime stats")
        return e


class VolumeModal(discord.ui.Modal, title="🔊 Volume"):
    value=discord.ui.TextInput(label="Volume (0-150%)",placeholder="Contoh: 80",max_length=3,required=True)

    def __init__(self,player,guild_id):
        super().__init__()
        self.player=player
        self.guild_id=guild_id

    async def on_submit(self,interaction):
        if not can_control(interaction.user):
            return await interaction.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
        try:
            value=int(str(self.value.value).strip())
            if not 0 <= value <= 150:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Volume harus 0-150%.",ephemeral=True)
        guild=self.player.bot.get_guild(self.guild_id)
        if not guild:
            return await interaction.response.send_message("❌ Guild tidak ditemukan.",ephemeral=True)
        self.player.set_volume(guild,value)
        await interaction.response.send_message(f"🔊 Volume: **{value}%**",ephemeral=True)
        await self.player.refresh_now_playing(guild)


class SeekModal(discord.ui.Modal, title="⏩ Seek"):
    position=discord.ui.TextInput(label="Posisi",placeholder="1:30 atau +30 atau -15",max_length=20,required=True)

    def __init__(self,player,guild_id):
        super().__init__()
        self.player=player
        self.guild_id=guild_id

    async def on_submit(self,interaction):
        if not can_control(interaction.user):
            return await interaction.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
        guild=self.player.bot.get_guild(self.guild_id)
        q=self.player.queue_for(self.guild_id)
        if not guild or not q.current:
            return await interaction.response.send_message("❌ Tidak ada lagu yang sedang diputar.",ephemeral=True)
        position=str(self.position.value).strip()
        try:
            current_pos=max(0,q.started_offset+(q.paused_at or time.monotonic())-q.started_at) if q.started_at and not q.paused else q.position
            if position.startswith(("+","-")):
                seconds=max(0,current_pos+float(position))
            elif ":" in position:
                m,s=position.split(":",1); seconds=int(m)*60+float(s)
            else:
                seconds=float(position)
            self.player.seek(guild,seconds)
            await interaction.response.send_message(f"⏩ Seek ke **{int(seconds)//60}:{int(seconds)%60:02d}**",ephemeral=True)
            await self.player.refresh_now_playing(guild)
        except (ValueError,TypeError):
            await interaction.response.send_message("❌ Format seek tidak valid.",ephemeral=True)


class FilterPanelView(discord.ui.View):
    def __init__(self,player,guild_id):
        super().__init__(timeout=60)
        self.player=player
        self.guild_id=guild_id
        options=[discord.SelectOption(label=x,value=x) for x in ("off","bassboost","nightcore","vaporwave","karaoke","8d","tremolo","rotation")]
        select=discord.ui.Select(placeholder="Pilih audio filter...",options=options)
        select.callback=self.pick
        self.add_item(select)

    async def pick(self,interaction):
        if not can_control(interaction.user):
            return await interaction.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
        value=interaction.data["values"][0]
        guild=self.player.bot.get_guild(self.guild_id)
        if not guild:
            return await interaction.response.send_message("❌ Guild tidak ditemukan.",ephemeral=True)
        q=self.player.queue_for(self.guild_id)
        q.filter=value
        q.effects_dirty=True
        if guild.voice_client and guild.voice_client.is_playing():
            self.player.restart_current(guild)
        await interaction.response.send_message(f"🎚️ Filter: **{value}**",ephemeral=True)
        await self.player.refresh_now_playing(guild)


class SpeedPanelView(discord.ui.View):
    def __init__(self,player,guild_id):
        super().__init__(timeout=60)
        self.player=player
        self.guild_id=guild_id
        options=[discord.SelectOption(label=f"{x:.2f}x",value=str(x)) for x in (0.5,0.75,1.0,1.25,1.5,1.75,2.0)]
        select=discord.ui.Select(placeholder="Pilih speed...",options=options)
        select.callback=self.pick
        self.add_item(select)

    async def pick(self,interaction):
        if not can_control(interaction.user):
            return await interaction.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
        value=float(interaction.data["values"][0])
        guild=self.player.bot.get_guild(self.guild_id)
        if not guild:
            return await interaction.response.send_message("❌ Guild tidak ditemukan.",ephemeral=True)
        q=self.player.queue_for(self.guild_id)
        q.speed=value
        q.effects_dirty=True
        if guild.voice_client and guild.voice_client.is_playing():
            self.player.restart_current(guild)
        await interaction.response.send_message(f"⏩ Speed: **{value:.2f}x**",ephemeral=True)
        await self.player.refresh_now_playing(guild)


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

    @discord.ui.button(emoji="🎤",label="Lyrics",style=discord.ButtonStyle.secondary,row=3)
    async def lyrics(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        q=self.player.queue_for(self.guild_id)
        if not q.current:
            return await interaction.edit_original_response(content="Tidak ada lagu yang sedang diputar.")
        data=await fetch_lyrics(q.current.title,q.current.uploader)
        if not data:
            return await interaction.edit_original_response(content="🎤 Lirik tidak ditemukan untuk lagu ini.")
        lyrics=data.get("synced") or data.get("plain") or ""
        view=LyricsView(self.player,self.guild_id,data.get("title") or q.current.title,data.get("artist") or q.current.uploader,lyrics)
        await interaction.edit_original_response(embed=view.embed(),view=view)

    @discord.ui.button(emoji="📊",label="Stats",style=discord.ButtonStyle.secondary,row=3)
    async def stats(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        view=StatsView(self.player,self.guild_id)
        await interaction.edit_original_response(embed=view.embed(),view=view)

    @discord.ui.button(label="✨ Premium",style=discord.ButtonStyle.secondary,row=3)
    async def premium_menu(self,interaction:discord.Interaction,button:discord.ui.Button):
        if not await self.guard(interaction): return
        await interaction.response.send_message("✨ Pilih fitur Premium:",view=PremiumView(self.player,self.guild_id),ephemeral=True)

    @discord.ui.button(label="🔊 Volume",style=discord.ButtonStyle.secondary,row=3)
    async def volume_panel(self,interaction:discord.Interaction,button:discord.ui.Button):
        if not await self.guard(interaction): return
        await interaction.response.send_modal(VolumeModal(self.player,self.guild_id))

    @discord.ui.button(label="🎚️ Filter",style=discord.ButtonStyle.secondary,row=3)
    async def filter_panel(self,interaction:discord.Interaction,button:discord.ui.Button):
        if not await self.guard(interaction): return
        await interaction.response.send_message("🎚️ Pilih filter:",view=FilterPanelView(self.player,self.guild_id),ephemeral=True)

    @discord.ui.button(label="⏩ Speed",style=discord.ButtonStyle.secondary,row=4)
    async def speed_panel(self,interaction:discord.Interaction,button:discord.ui.Button):
        if not await self.guard(interaction): return
        await interaction.response.send_message("⏩ Pilih speed:",view=SpeedPanelView(self.player,self.guild_id),ephemeral=True)

    @discord.ui.button(label="⏱️ Seek",style=discord.ButtonStyle.secondary,row=4)
    async def seek_panel(self,interaction:discord.Interaction,button:discord.ui.Button):
        if not await self.guard(interaction): return
        await interaction.response.send_modal(SeekModal(self.player,self.guild_id))

    @discord.ui.button(label="🔒 24/7",style=discord.ButtonStyle.secondary,row=4)
    async def always_panel(self,interaction:discord.Interaction,button:discord.ui.Button):
        if not await self.guard(interaction): return
        q=self.player.queue_for(self.guild_id)
        q.always_connected=not q.always_connected
        await interaction.response.send_message(f"🔒 24/7: **{'ON' if q.always_connected else 'OFF'}**",ephemeral=True)
        await self.player.refresh_now_playing(self.guild)

    @discord.ui.button(emoji="📜",style=discord.ButtonStyle.secondary,row=1)
    async def queue(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        q=self.player.queue_for(self.guild_id)
        if not q.tracks:
            return await interaction.edit_original_response(content="Queue kosong.")
        view=QueueJumpView(self.player,self.guild_id)
        await interaction.edit_original_response(embed=view.embed(),view=view)


class PremiumView(discord.ui.View):
    def __init__(self,player,guild_id):
        super().__init__(timeout=300)
        self.player=player
        self.guild_id=guild_id
        options=[
            discord.SelectOption(label="🎧 Music Discovery",value="discover",description="Temukan musik berdasarkan taste kamu"),
            discord.SelectOption(label="🌙 Mood / Vibes",value="vibes",description="Pilih vibe dan isi queue"),
            discord.SelectOption(label="🧠 Personal Taste Profile",value="taste",description="Lihat profil selera musik"),
            discord.SelectOption(label="📅 Weekly Recap",value="recap",description="Ringkasan musik 7 hari terakhir"),
            discord.SelectOption(label="✨ Crossfade",value="crossfade",description="Atur fade transition antar lagu"),
        ]
        select=discord.ui.Select(placeholder="Pilih fitur premium...",options=options)
        select.callback=self.select_feature
        self.add_item(select)

    async def select_feature(self,interaction):
        if not can_control(interaction.user):
            return await interaction.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
        value=interaction.data["values"][0]
        if value=="vibes":
            return await interaction.response.edit_message(content="🌙 Pilih mood / vibe:",view=VibeView(self.player,self.guild_id))
        if value=="crossfade":
            return await interaction.response.edit_message(content="✨ Pilih durasi crossfade:",view=CrossfadeView(self.player,self.guild_id))
        if value=="taste":
            await interaction.response.defer()
            data=premium.taste(interaction.user.id)
            e=discord.Embed(title="✦ VREEO MUSIC • PERSONAL TASTE",description=f"**{data['plays']}** plays dalam 7 hari terakhir")
            songs="\n".join(f"**{i}.** {n[:65]} — {count}x" for i,(n,count) in enumerate(data["top_songs"],1)) or "Belum cukup data."
            artists="\n".join(f"**{i}.** {n[:65]} — {count}x" for i,(n,count) in enumerate(data["top_artists"],1)) or "Belum cukup data."
            genres="\n".join(f"**{n}** — {count}" for n,count in data["genres"]) or "Belum cukup data."
            e.add_field(name="🔥 TOP SONGS",value=songs,inline=False)
            e.add_field(name="🎤 TOP ARTISTS",value=artists,inline=False)
            e.add_field(name="🎚️ VIBES",value=genres,inline=False)
            e.set_footer(text="VREEO MUSIC • Personal Taste Profile")
            return await interaction.edit_original_response(content=None,embed=e,view=self)
        if value=="recap":
            await interaction.response.defer()
            data=premium.weekly(interaction.user.id)
            e=discord.Embed(title="✦ VREEO MUSIC • WEEKLY RECAP",description=f"**{data['plays']}** plays • 7 hari terakhir")
            songs="\n".join(f"**{i}.** {n[:65]} — {count}x" for i,(n,count) in enumerate(data["songs"].most_common(5),1)) or "Belum ada data."
            artists="\n".join(f"**{i}.** {n[:65]} — {count}x" for i,(n,count) in enumerate(data["artists"].most_common(5),1)) or "Belum ada data."
            e.add_field(name="🔥 MOST PLAYED",value=songs,inline=False)
            e.add_field(name="🎤 TOP ARTISTS",value=artists,inline=False)
            e.set_footer(text="VREEO MUSIC • Weekly Recap")
            return await interaction.edit_original_response(content=None,embed=e,view=self)
        await interaction.response.defer()
        try:
            queries=premium.discovery_queries(interaction.user.id)
            results=[]
            for query in queries:
                try:
                    results.extend(await search(query,5))
                except Exception:
                    continue
                if len(results)>=5: break
            seen=set(); clean=[]
            for r in results:
                url=r.get("webpage_url")
                if url and url not in seen:
                    seen.add(url); clean.append(r)
            filtered=[]
            for r in clean:
                duration=r.get("duration")
                if duration is not None:
                    try:
                        if float(duration) > 480:
                            continue
                    except (TypeError,ValueError):
                        pass
                filtered.append(r)
            clean=filtered[:5]
            if not clean:
                return await interaction.edit_original_response(content="❌ Discovery belum menemukan hasil.",view=self)
            return await interaction.edit_original_response(content="🎧 Pilih hasil discovery untuk masuk queue:",view=DiscoveryView(self.player,self.guild_id,clean))
        except Exception as exc:
            return await interaction.edit_original_response(content=f"❌ Discovery gagal: {exc}",view=self)


class DiscoveryView(discord.ui.View):
    def __init__(self,player,guild_id,results):
        super().__init__(timeout=180)
        self.player=player; self.guild_id=guild_id; self.results=results
        options=[discord.SelectOption(label=f"{i+1}. {r['title']}"[:100],value=str(i)) for i,r in enumerate(results)]
        select=discord.ui.Select(placeholder="Pilih lagu discovery...",options=options)
        select.callback=self.pick
        self.add_item(select)

    async def pick(self,interaction):
        if not can_control(interaction.user):
            return await interaction.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
        idx=int(interaction.data["values"][0]); r=self.results[idx]
        q=self.player.queue_for(self.guild_id)
        if len(q.tracks)>=MAX_QUEUE_SIZE:
            return await interaction.response.send_message("Queue sudah penuh.",ephemeral=True)
        if q.current and q.current.webpage_url==r["webpage_url"] or any(t.webpage_url==r["webpage_url"] for t in q.tracks):
            return await interaction.response.send_message("Track itu sudah ada di queue.",ephemeral=True)
        q.add(Track(title=r["title"],webpage_url=r["webpage_url"],duration=r.get("duration"),thumbnail=r.get("thumbnail"),uploader=r.get("uploader"),requested_by=interaction.user.id))
        if self.player.bot.get_guild(self.guild_id).voice_client and not self.player.bot.get_guild(self.guild_id).voice_client.is_playing():
            await self.player.play_next(self.player.bot.get_guild(self.guild_id))
        await interaction.response.send_message(f"🎧 **{r['title']}** masuk queue.",ephemeral=True)


class VibeView(discord.ui.View):
    def __init__(self,player,guild_id):
        super().__init__(timeout=180)
        self.player=player; self.guild_id=guild_id
        options=[discord.SelectOption(label=label,value=key) for key,(label,_) in premium.MOODS.items()]
        select=discord.ui.Select(placeholder="Pilih vibe...",options=options)
        select.callback=self.pick
        self.add_item(select)

    async def pick(self,interaction):
        if not can_control(interaction.user):
            return await interaction.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
        await interaction.response.defer()
        key=interaction.data["values"][0]
        label,queries=premium.MOODS[key]
        q=self.player.queue_for(self.guild_id)
        room=max(0,MAX_QUEUE_SIZE-len(q.tracks))
        results=[]
        for query in queries:
            try:
                results.extend(await search(query,5))
            except Exception:
                continue
            if len(results)>=room or len(results)>=10: break
        seen=set(); added=0
        for r in results:
            url=r.get("webpage_url")
            if not url or url in seen: continue
            seen.add(url)
            duration=r.get("duration")
            if duration is not None and not (20 <= float(duration) <= 480):
                continue
            if q.current and q.current.webpage_url==url or any(t.webpage_url==url for t in q.tracks): continue
            q.add(Track(title=r["title"],webpage_url=url,duration=duration,thumbnail=r.get("thumbnail"),uploader=r.get("uploader"),requested_by=interaction.user.id))
            added+=1
            if added>=min(room,5): break
        guild=self.player.bot.get_guild(self.guild_id)
        if guild and guild.voice_client and not guild.voice_client.is_playing() and added:
            await self.player.play_next(guild)
        await interaction.edit_original_response(content=f"🌙 **{label}** • {added} lagu masuk queue.",view=PremiumView(self.player,self.guild_id))


class CrossfadeView(discord.ui.View):
    def __init__(self,player,guild_id):
        super().__init__(timeout=180)
        self.player=player; self.guild_id=guild_id
        options=[discord.SelectOption(label="Off",value="0"),*[
            discord.SelectOption(label=f"{x} detik",value=str(x)) for x in (2,4,6,8)
        ]]
        select=discord.ui.Select(placeholder="Durasi transition...",options=options)
        select.callback=self.pick
        self.add_item(select)

    async def pick(self,interaction):
        if not can_control(interaction.user):
            return await interaction.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
        seconds=float(interaction.data["values"][0])
        q=self.player.queue_for(self.guild_id)
        q.crossfade=seconds
        q.effects_dirty=True
        guild=self.player.bot.get_guild(self.guild_id)
        if guild and guild.voice_client and guild.voice_client.is_playing():
            self.player.restart_current(guild)
        label="OFF" if seconds==0 else f"{int(seconds)}s"
        await interaction.response.edit_message(content=f"✨ Crossfade: **{label}**",view=PremiumView(self.player,self.guild_id))
