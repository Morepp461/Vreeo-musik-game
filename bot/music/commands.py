import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from .source import resolve,search,resolve_playlist
from .queue import Track
from .player import MusicPlayer
from . import favorites,history,playlist
from .controls import NowPlayingView
from .guard import reject_channel,reject_manager,in_music_channel
from . import settings
from ..config import MAX_QUEUE_SIZE,MAX_PLAYLIST_SIZE

class SearchView(discord.ui.View):
    def __init__(self,cog,interaction,results):
        super().__init__(timeout=60)
        self.cog=cog
        self.user_id=interaction.user.id
        self.results=results
        for n,result in enumerate(results):
            b=discord.ui.Button(label=str(n+1),style=discord.ButtonStyle.primary,row=n//5)
            b.callback=self.pick(n)
            self.add_item(b)
    def pick(self,index):
        async def callback(interaction):
            if interaction.user.id!=self.user_id:
                return await interaction.response.send_message("Ini bukan search kamu.",ephemeral=True)
            if not in_music_channel(interaction):
                return await interaction.response.send_message("🎵 Gunakan channel musik.",ephemeral=True)
            v=await self.cog.voice(interaction)
            if not v:
                return await interaction.response.send_message("Masuk voice channel dulu.",ephemeral=True)
            r=self.results[index]
            q=self.cog.player.queue_for(interaction.guild.id)
            if len(q.tracks)>=MAX_QUEUE_SIZE:
                return await interaction.response.send_message("Queue sudah penuh.",ephemeral=True)
            q.add(Track(title=r["title"],webpage_url=r["webpage_url"],duration=r.get("duration"),thumbnail=r.get("thumbnail"),uploader=r.get("uploader"),requested_by=interaction.user.id))
            await interaction.response.send_message(f"▶️ Ditambahkan: **{r['title']}**",ephemeral=True)
            if not interaction.guild.voice_client.is_playing():
                await self.cog.player.play_next(interaction.guild)
        return callback

class Music(commands.Cog):
    def __init__(self,bot):
        self.bot=bot
        self.player=MusicPlayer(bot)
        bot.music_player=self.player

    async def voice(self,i):
        if not i.user.voice: return None
        ch=i.user.voice.channel
        v=i.guild.voice_client
        if v and v.channel!=ch: await v.move_to(ch)
        return v or await ch.connect()

    async def add_query(self,i,query):
        if await reject_channel(i): return
        v=await self.voice(i)
        if not v: raise ValueError("Masuk voice channel dulu.")
        await i.response.defer()
        if "youtube.com/playlist" in query or "list=" in query:
            tracks=await resolve_playlist(query,i.user.id)
            q=self.player.queue_for(i.guild.id)
            tracks=tracks[:max(0,MAX_QUEUE_SIZE-len(q.tracks))]
            for t in tracks: q.add(t)
            text=f"📚 **{len(tracks)}** track masuk queue."
            if not v.is_playing(): await self.player.play_next(i.guild)
        else:
            data=await resolve(query,i.user.id)
            q=self.player.queue_for(i.guild.id)
            if len(q.tracks)>=MAX_QUEUE_SIZE: raise ValueError("Queue sudah penuh.")
            q.add(Track(**data))
            text=f"▶️ **{data['title']}** ditambahkan."
            if not v.is_playing(): await self.player.play_next(i.guild)
        await i.followup.send(text)

    @app_commands.command(name="play",description="Putar lagu dari URL atau pencarian")
    async def play(self,i,query:str):
        try: await self.add_query(i,query)
        except Exception as e:
            if i.response.is_done(): await i.followup.send(f"❌ {e}")
            else: await i.response.send_message(f"❌ {e}",ephemeral=True)

    @app_commands.command(name="search",description="Cari lagu dan pilih hasil")
    async def search_cmd(self,i,query:str):
        if await reject_channel(i): return
        await i.response.defer(ephemeral=True)
        try:
            results=await search(query,5)
            if not results: return await i.followup.send("❌ Tidak ada hasil.")
            text="\n".join(f"**{n}.** {r['title']}" for n,r in enumerate(results,1))
            await i.followup.send(text,view=SearchView(self,i,results))
        except Exception as e: await i.followup.send(f"❌ {e}")

    @app_commands.command(name="nowplaying",description="Tampilkan lagu yang sedang diputar")
    async def nowplaying(self,i):
        if await reject_channel(i): return
        q=self.player.queue_for(i.guild.id)
        if not q.current:return await i.response.send_message("Tidak ada lagu.")
        t=q.current
        emb=discord.Embed(title="🎵 Now Playing",description=f"**{t.title}**",url=t.webpage_url)
        if t.thumbnail: emb.set_thumbnail(url=t.thumbnail)
        emb.add_field(name="Request",value=f"<@{t.requested_by}>" if t.requested_by else "-",inline=True)
        emb.add_field(name="Volume",value=f"{int(q.volume*100)}%",inline=True)
        emb.add_field(name="Loop",value=q.loop,inline=True)
        await i.response.send_message(embed=emb,view=NowPlayingView(self.player,i.guild.id))

    @app_commands.command(name="pause",description="Pause")
    async def pause(self,i): self.player.pause(i.guild); await i.response.send_message("⏸️")

    @app_commands.command(name="resume",description="Resume")
    async def resume(self,i): self.player.resume(i.guild); await i.response.send_message("▶️")

    @app_commands.command(name="skip",description="Skip")
    async def skip(self,i):
        if await reject_manager(i): return
        self.player.skip(i.guild); await i.response.send_message("⏭️")

    @app_commands.command(name="previous",description="Putar lagu sebelumnya")
    async def previous(self,i):
        if await reject_manager(i): return
        await i.response.send_message("⏮️" if self.player.previous(i.guild) else "Tidak ada lagu sebelumnya.")

    @app_commands.command(name="stop",description="Stop dan kosongkan player")
    async def stop(self,i):
        if await reject_manager(i): return
        await self.player.disconnect(i.guild); await i.response.send_message("⏹️")

    @app_commands.command(name="shuffle",description="Acak queue")
    async def shuffle(self,i):
        if await reject_manager(i): return
        self.player.queue_for(i.guild.id).shuffle(); await i.response.send_message("🔀 Queue diacak.")

    @app_commands.command(name="loop",description="Atur loop")
    @app_commands.choices(mode=[app_commands.Choice(name=x,value=x) for x in ("off","track","queue")])
    async def loop(self,i,mode:app_commands.Choice[str]):
        self.player.queue_for(i.guild.id).loop=mode.value
        await i.response.send_message(f"🔁 Loop: **{mode.value}**")

    @app_commands.command(name="volume",description="Atur volume 0-150%")
    async def volume(self,i,value:app_commands.Range[int,0,150]):
        if await reject_manager(i): return
        v=self.player.set_volume(i.guild,value)
        await i.response.send_message(f"🔊 Volume: **{v}%**")

    @app_commands.command(name="seek",description="Loncat ke posisi, contoh 1:30 atau +30/-15")
    async def seek(self,i,position:str):
        if await reject_manager(i): return
        q=self.player.queue_for(i.guild.id)
        if not q.current:return await i.response.send_message("Tidak ada lagu.")
        try:
            if position.startswith(("+","-")): seconds=max(0,q.position+float(position))
            elif ":" in position:
                m,s=position.split(":",1); seconds=int(m)*60+float(s)
            else: seconds=float(position)
            self.player.seek(i.guild,seconds)
            await i.response.send_message(f"⏩ Seek ke **{int(seconds)//60}:{int(seconds)%60:02d}**")
        except ValueError: await i.response.send_message("Format seek tidak valid.")

    @app_commands.command(name="filter",description="Atur audio filter")
    @app_commands.choices(name=[app_commands.Choice(name=x,value=x) for x in ("off","bassboost","nightcore","vaporwave","karaoke","8d","tremolo","rotation")])
    async def filter_cmd(self,i,name:app_commands.Choice[str]):
        if await reject_manager(i): return
        self.player.queue_for(i.guild.id).filter=name.value
        await i.response.send_message(f"🎚️ Filter: **{name.value}**")

    @app_commands.command(name="speed",description="Atur kecepatan 0.5x-2x")
    async def speed(self,i,value:app_commands.Range[float,0.5,2.0]):
        if await reject_manager(i): return
        q=self.player.queue_for(i.guild.id)
        q.speed=float(value)
        await i.response.send_message(f"⏩ Speed: **{q.speed:.2f}x**")

    @app_commands.command(name="autoplay",description="Nyalakan/matikan autoplay")
    async def autoplay(self,i,enabled:bool):
        if await reject_manager(i): return
        self.player.queue_for(i.guild.id).autoplay=enabled
        await i.response.send_message(f"🤖 Autoplay: **{'on' if enabled else 'off'}**")

    @app_commands.command(name="247",description="Pertahankan bot di voice channel")
    async def always(self,i,enabled:bool):
        if await reject_manager(i): return
        self.player.queue_for(i.guild.id).always_connected=enabled
        await i.response.send_message(f"🔒 24/7: **{'on' if enabled else 'off'}**")

    queue=app_commands.Group(name="queue",description="Kelola queue")

    @queue.command(name="show",description="Lihat queue")
    async def queue_show(self,i):
        if await reject_channel(i): return
        q=self.player.queue_for(i.guild.id)
        lines=[f"▶️ **{q.current.title}**"] if q.current else []
        lines += [f"{n}. {t.title}" for n,t in enumerate(q.tracks[:25],1)]
        await i.response.send_message("\n".join(lines) or "Queue kosong.")

    @queue.command(name="remove",description="Hapus track dari queue")
    async def queue_remove(self,i,position:app_commands.Range[int,1,100]):
        if await reject_manager(i): return
        q=self.player.queue_for(i.guild.id)
        if position>len(q.tracks): return await i.response.send_message("Posisi tidak ada.")
        t=q.remove(position-1); await i.response.send_message(f"🗑️ {t.title}")

    @queue.command(name="move",description="Pindahkan track")
    async def queue_move(self,i,from_position:int,to_position:int):
        if await reject_manager(i): return
        q=self.player.queue_for(i.guild.id)
        if not (1<=from_position<=len(q.tracks) and 1<=to_position<=len(q.tracks)): return await i.response.send_message("Posisi tidak valid.")
        q.move(from_position-1,to_position-1); await i.response.send_message("↕️ Dipindahkan.")

    @queue.command(name="clear",description="Kosongkan queue")
    async def queue_clear(self,i):
        if await reject_manager(i): return
        self.player.queue_for(i.guild.id).clear(); await i.response.send_message("🧹 Queue dikosongkan.")

    @queue.command(name="jump",description="Lompat ke track")
    async def queue_jump(self,i,position:int):
        if await reject_manager(i): return
        q=self.player.queue_for(i.guild.id)
        if not (1<=position<=len(q.tracks)): return await i.response.send_message("Posisi tidak valid.")
        for _ in range(position-1): q.played.append(q.tracks.pop(0))
        self.player.skip(i.guild); await i.response.send_message("⏭️ Jump.")

    favorite=app_commands.Group(name="favorite",description="Kelola favorit")

    @favorite.command(name="add",description="Simpan lagu ke favorit")
    async def favorite_add(self,i,query:str):
        if await reject_channel(i): return
        try:
            t=Track(**(await resolve(query,i.user.id)))
            favorites.add(i.user.id,t); await i.response.send_message(f"⭐ {t.title} disimpan.")
        except Exception as e: await i.response.send_message(f"❌ {e}",ephemeral=True)

    @favorite.command(name="remove",description="Hapus favorit berdasarkan URL")
    async def favorite_remove(self,i,url:str):
        if await reject_channel(i): return
        favorites.remove(i.user.id,url); await i.response.send_message("⭐ Dihapus.")

    @favorite.command(name="list",description="Lihat favorit")
    async def favorite_list(self,i):
        if await reject_channel(i): return
        rows=favorites.list_all(i.user.id)
        await i.response.send_message("\n".join(f"{n}. {r['title']}" for n,r in enumerate(rows,1))[:1900] or "Favorit kosong.")

    @favorite.command(name="play",description="Putar semua favorit")
    async def favorite_play(self,i):
        if await reject_channel(i): return
        rows=favorites.list_all(i.user.id)
        if not rows:return await i.response.send_message("Favorit kosong.")
        v=await self.voice(i)
        if not v:return await i.response.send_message("Masuk voice channel dulu.",ephemeral=True)
        q=self.player.queue_for(i.guild.id)
        for r in rows[:max(0,MAX_QUEUE_SIZE-len(q.tracks))]:q.add(Track(title=r["title"],webpage_url=r["source_url"],requested_by=i.user.id))
        if not v.is_playing():await self.player.play_next(i.guild)
        await i.response.send_message(f"⭐ {len(rows)} favorit masuk queue.")

    settings_group=app_commands.Group(name="settings",description="Pengaturan musik")

    @settings_group.command(name="music-channel",description="Set channel khusus musik")
    @app_commands.describe(channel="Channel teks untuk command musik")
    async def music_channel(self,i,channel:discord.TextChannel|None=None):
        if await reject_manager(i): return
        settings.set_channel(channel.id if channel else None)
        await i.response.send_message(f"🎵 Music channel: {channel.mention if channel else 'semua channel'}")

    history=app_commands.Group(name="history",description="Riwayat musik")

    @history.command(name="show",description="Lihat riwayat")
    async def history_show(self,i):
        if await reject_channel(i): return
        rows=history.list_recent(i.user.id)
        await i.response.send_message("\n".join(f"{n}. {r['title']}" for n,r in enumerate(rows,1))[:1900] or "History kosong.")

    @history.command(name="clear",description="Hapus riwayat")
    async def history_clear(self,i):
        if await reject_channel(i): return
        history.clear(i.user.id); await i.response.send_message("🧹 History dihapus.")

    playlist=app_commands.Group(name="playlist",description="Playlist pribadi")

    @playlist.command(name="create",description="Buat playlist")
    async def playlist_create(self,i,name:str):
        if await reject_channel(i): return
        playlist.create(i.user.id,name); await i.response.send_message(f"📚 Playlist **{name}** dibuat.")

    @playlist.command(name="list",description="Daftar playlist")
    async def playlist_list(self,i):
        if await reject_channel(i): return
        rows=playlist.list_all(i.user.id)
        await i.response.send_message("\n".join(f"• {r['name']}" for r in rows)[:1900] or "Belum ada playlist.")

    @playlist.command(name="delete",description="Hapus playlist")
    async def playlist_delete(self,i,name:str):
        if await reject_channel(i): return
        ok=playlist.delete(i.user.id,name); await i.response.send_message("🗑️ Dihapus." if ok else "Playlist tidak ditemukan.")

    @playlist.command(name="rename",description="Ganti nama playlist")
    async def playlist_rename(self,i,old:str,new:str):
        if await reject_channel(i): return
        ok=playlist.rename(i.user.id,old,new); await i.response.send_message("✏️ Diganti." if ok else "Playlist tidak ditemukan.")

    @playlist.command(name="add",description="Tambah lagu ke playlist")
    async def playlist_add(self,i,name:str,query:str):
        if await reject_channel(i): return
        try:
            t=Track(**(await resolve(query,i.user.id)))
            ok=playlist.add_track(i.user.id,name,t)
            await i.response.send_message("➕ Ditambahkan." if ok else "Playlist tidak ditemukan.")
        except Exception as e: await i.response.send_message(f"❌ {e}",ephemeral=True)

    @playlist.command(name="remove",description="Hapus track playlist berdasarkan posisi")
    async def playlist_remove(self,i,name:str,position:int):
        if await reject_channel(i): return
        ok=playlist.remove_track(i.user.id,name,position); await i.response.send_message("🗑️ Dihapus." if ok else "Track/playlist tidak ditemukan.")

    @playlist.command(name="play",description="Putar playlist")
    async def playlist_play(self,i,name:str):
        if await reject_channel(i): return
        rows=playlist.tracks(i.user.id,name)
        if not rows:return await i.response.send_message("Playlist kosong/tidak ditemukan.")
        v=await self.voice(i)
        if not v:return await i.response.send_message("Masuk voice channel dulu.",ephemeral=True)
        q=self.player.queue_for(i.guild.id)
        for r in rows:q.add(Track(title=r["title"],webpage_url=r["source_url"],requested_by=i.user.id))
        if not v.is_playing():await self.player.play_next(i.guild)
        await i.response.send_message(f"📚 {len(rows)} track masuk queue.")

async def setup(bot):
    await bot.add_cog(Music(bot))
