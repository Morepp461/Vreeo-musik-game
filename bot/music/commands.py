import asyncio
import time
import logging
import discord
from discord.ext import commands
from discord import app_commands
from .source import resolve,search,resolve_playlist,is_spotify
from .queue import Track
from .player import MusicPlayer
from . import favorites,history,playlist
from .controls import NowPlayingView,AutoplayView
from .guard import reject_channel,reject_manager,in_music_channel,can_control
from . import settings
from ..config import MAX_QUEUE_SIZE,MAX_PLAYLIST_SIZE

log=logging.getLogger(__name__)

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
            await interaction.response.defer(ephemeral=True)
            try:
                v=await asyncio.wait_for(self.cog.voice(interaction),timeout=12)
            except asyncio.TimeoutError:
                return await interaction.edit_original_response(content="❌ Koneksi ke voice channel timeout. Coba lagi.")
            if not v:
                return await interaction.edit_original_response(content="Masuk voice channel dulu.")
            r=self.results[index]
            q=self.cog.player.queue_for(interaction.guild.id)
            q.panel_channel_id=interaction.channel.id
            if len(q.tracks)>=MAX_QUEUE_SIZE:
                return await interaction.edit_original_response(content="Queue sudah penuh.")
            if (q.current and q.current.webpage_url==r["webpage_url"]) or any(t.webpage_url==r["webpage_url"] for t in q.tracks):
                return await interaction.edit_original_response(content="Track itu sudah ada di queue.")
            q.add(Track(title=r["title"],webpage_url=r["webpage_url"],duration=r.get("duration"),thumbnail=r.get("thumbnail"),uploader=r.get("uploader"),requested_by=interaction.user.id))
            if not interaction.guild.voice_client or not interaction.guild.voice_client.is_playing():
                ok=await self.cog.player.play_next(interaction.guild)
                if ok:
                    await interaction.edit_original_response(content=f"▶️ Memutar: **{r['title']}**")
                else:
                    await interaction.edit_original_response(content=f"⚠️ **{r['title']}** masuk queue, tapi gagal mulai playback.")
            else:
                await interaction.edit_original_response(content=f"▶️ Ditambahkan: **{r['title']}** ke queue")
        return callback

class Music(commands.Cog):
    def __init__(self,bot):
        self.bot=bot
        self.player=MusicPlayer(bot)
        bot.music_player=self.player
        self.cooldowns={}
        self._247_locks={}
        self._247_task=asyncio.create_task(self._247_watchdog())

    async def _247_watchdog(self):
        while True:
            try:
                await asyncio.sleep(15)
                for guild_id,q in list(self.player.queues.items()):
                    if not q.always_connected:
                        continue
                    guild=self.bot.get_guild(guild_id)
                    if not guild:
                        continue
                    voice=guild.voice_client
                    if voice and voice.is_connected():
                        if q.always_channel_id is None and voice.channel:
                            q.always_channel_id=voice.channel.id
                        continue
                    channel=None
                    if q.always_channel_id:
                        channel=guild.get_channel(q.always_channel_id)
                    if channel is None and voice and voice.channel:
                        channel=voice.channel
                        q.always_channel_id=channel.id
                    if channel is None:
                        continue
                    lock=self._247_locks.setdefault(guild_id,asyncio.Lock())
                    if lock.locked():
                        continue
                    async with lock:
                        try:
                            current=guild.voice_client
                            if current and current.is_connected():
                                continue
                            if current:
                                try:
                                    await current.disconnect(force=True)
                                except Exception:
                                    pass
                            await channel.connect()
                            log.info("24/7 watchdog reconnected voice for guild %s",guild_id)
                        except Exception as exc:
                            log.warning("24/7 reconnect failed for guild %s: %s",guild_id,exc)
            except asyncio.CancelledError:
                return
            except Exception:
                log.exception("24/7 watchdog error")

    def cog_unload(self):
        if self._247_task:
            self._247_task.cancel()

    @commands.Cog.listener()
    async def on_voice_state_update(self,member,before,after):
        if not self.bot.user or member.id!=self.bot.user.id:
            return
        if after.channel is None and before.channel:
            q=self.player.queues.get(member.guild.id)
            if q and q.always_connected:
                q.always_channel_id=before.channel.id
                await asyncio.sleep(2)
                if member.guild.voice_client is None:
                    try:
                        await before.channel.connect()
                        await self.player.play_next(member.guild)
                    except Exception:
                        pass

    def rate_limited(self,user_id,command,seconds=2.0):
        now=time.monotonic()
        key=(user_id,command)
        last=self.cooldowns.get(key,0.0)
        if now-last<seconds: return seconds-(now-last)
        self.cooldowns[key]=now
        return 0.0

    async def voice(self,i):
        member=getattr(i,"user",None) or getattr(i,"author",None)
        if not member or not member.voice: return None
        ch=member.voice.channel
        v=i.guild.voice_client
        if v and v.channel!=ch:
            await asyncio.wait_for(v.move_to(ch),timeout=12)
            return v
        if v:
            return v
        return await asyncio.wait_for(ch.connect(),timeout=12)

    async def add_query(self,i,query):
        if await reject_channel(i): return
        await i.response.defer()
        try:
            v=await self.voice(i)
        except asyncio.TimeoutError:
            raise ValueError("Koneksi ke voice channel timeout. Coba lagi.")
        if not v: raise ValueError("Masuk voice channel dulu.")
        if "youtube.com/playlist" in query or "list=" in query or (is_spotify(query) and any(f"/{kind}/" in query for kind in ("playlist","album"))):
            tracks=await resolve_playlist(query,i.user.id,MAX_PLAYLIST_SIZE)
            q=self.player.queue_for(i.guild.id)
            q.panel_channel_id=i.channel.id
            tracks=tracks[:max(0,MAX_QUEUE_SIZE-len(q.tracks))]
            for t in tracks: q.add(t)
            text=f"📚 **{len(tracks)}** track masuk queue."
        else:
            data=await resolve(query,i.user.id)
            q=self.player.queue_for(i.guild.id)
            q.panel_channel_id=i.channel.id
            if len(q.tracks)>=MAX_QUEUE_SIZE: raise ValueError("Queue sudah penuh.")
            if (q.current and q.current.webpage_url==data["webpage_url"]) or any(t.webpage_url==data["webpage_url"] for t in q.tracks):
                raise ValueError("Track itu sudah ada di queue.")
            q.add(Track(**data))
            text=f"▶️ **{data['title']}** ditambahkan."
        await i.followup.send(text)
        if not v.is_playing():
            asyncio.create_task(self.player.play_next(i.guild))

    @commands.command(name="play")
    async def prefix_play(self,ctx,*,query:str):
        if not ctx.guild:
            return
        if not in_music_channel(ctx):
            return await ctx.send("🎵 Gunakan channel musik.")
        remaining=self.rate_limited(ctx.author.id,"prefix_play")
        if remaining:
            return await ctx.send(f"⏳ Tunggu {remaining:.1f} detik.")
        try:
            v=await self.voice(ctx)
            if not v:
                return await ctx.send("Masuk voice channel dulu.")
            q=self.player.queue_for(ctx.guild.id)
            q.panel_channel_id=ctx.channel.id
            if "youtube.com/playlist" in query or "list=" in query or (is_spotify(query) and any(f"/{kind}/" in query for kind in ("playlist","album"))):
                tracks=await resolve_playlist(query,ctx.author.id,MAX_PLAYLIST_SIZE)
                room=max(0,MAX_QUEUE_SIZE-len(q.tracks))
                tracks=tracks[:room]
                for track in tracks:
                    q.add(track)
                if not tracks:
                    return await ctx.send("⚠️ Queue sudah penuh atau playlist kosong.")
                await ctx.send(f"📚 **{len(tracks)}** track masuk queue.")
            else:
                results=await search(query,1)
                if not results:
                    return await ctx.send("❌ Lagu tidak ditemukan.")
                r=results[0]
                if len(q.tracks)>=MAX_QUEUE_SIZE:
                    return await ctx.send("❌ Queue sudah penuh.")
                if (q.current and q.current.webpage_url==r["webpage_url"]) or any(t.webpage_url==r["webpage_url"] for t in q.tracks):
                    return await ctx.send("❌ Track itu sudah ada di queue.")
                track=Track(title=r["title"],webpage_url=r["webpage_url"],duration=r.get("duration"),thumbnail=r.get("thumbnail"),uploader=r.get("uploader"),requested_by=ctx.author.id)
                q.add(track)
                await ctx.send(f"🎵 **{track.title}** masuk queue.")
            if not v.is_playing() and not v.is_paused():
                ok=await self.player.play_next(ctx.guild)
                if not ok:
                    await ctx.send("⚠️ Track masuk queue, tapi gagal mulai playback.")
        except asyncio.TimeoutError:
            await ctx.send("❌ Koneksi ke voice channel timeout. Coba lagi.")
        except Exception as e:
            await ctx.send(f"❌ {e}")

    @app_commands.command(name="play",description="Putar lagu dari URL atau pencarian")
    async def play(self,i,query:str):
        remaining=self.rate_limited(i.user.id,"play")
        if remaining: return await i.response.send_message(f"⏳ Tunggu {remaining:.1f} detik.",ephemeral=True)
        try: await self.add_query(i,query)
        except Exception as e:
            if i.response.is_done(): await i.followup.send(f"❌ {e}")
            else: await i.response.send_message(f"❌ {e}",ephemeral=True)

    @app_commands.command(name="search",description="Cari lagu dan pilih hasil")
    async def search_cmd(self,i,query:str):
        if await reject_channel(i): return
        remaining=self.rate_limited(i.user.id,"search")
        if remaining: return await i.response.send_message(f"⏳ Tunggu {remaining:.1f} detik.",ephemeral=True)
        await i.response.defer(ephemeral=True)
        try:
            results=await search(query,5)
            if not results: return await i.followup.send("❌ Tidak ada hasil.")
            text="\n".join(f"**{n}.** {r['title']}" for n,r in enumerate(results,1))
            await i.followup.send(text,view=SearchView(self,i,results))
        except Exception as e: await i.followup.send(f"❌ {e}")

    @app_commands.command(name="autoplay",description="Atur mode autoplay")
    async def autoplay(self,i,enabled:bool):
        if await reject_manager(i): return
        q=self.player.queue_for(i.guild.id)
        if not enabled:
            q.autoplay=False
            q.autoplay_mode="random"
            q.autoplay_genre="random"
            q.autoplay_artist=None
            return await i.response.send_message("🤖 Autoplay: **off**")
        q.autoplay=True
        await i.response.send_message(
            "🤖 **Autoplay ON**\\nPilih sumber autoplay:",
            view=AutoplayView(self.player,i.guild.id),
            ephemeral=True
        )

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
        added=rows[:max(0,MAX_QUEUE_SIZE-len(q.tracks))]
        for r in added:q.add(Track(title=r["title"],webpage_url=r["source_url"],requested_by=i.user.id))
        if not v.is_playing():await self.player.play_next(i.guild)
        await i.response.send_message(f"⭐ {len(added)} favorit masuk queue.")

    settings_group=app_commands.Group(name="settings",description="Pengaturan musik")

    @settings_group.command(name="music-channel",description="Set channel khusus musik")
    @app_commands.describe(channel="Channel teks untuk command musik")
    async def music_channel(self,i,channel:discord.TextChannel|None=None):
        if not can_control(i.user):
            return await i.response.send_message("🔒 Fitur ini khusus DJ/Admin.",ephemeral=True)
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
            ok=playlist.add_track(i.user.id,name,t,MAX_PLAYLIST_SIZE)
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
        added=rows[:max(0,MAX_QUEUE_SIZE-len(q.tracks))]
        for r in added:q.add(Track(title=r["title"],webpage_url=r["source_url"],requested_by=i.user.id))
        if not v.is_playing():await self.player.play_next(i.guild)
        await i.response.send_message(f"📚 {len(added)} track masuk queue.")

async def setup(bot):
    await bot.add_cog(Music(bot))
