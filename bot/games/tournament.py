from __future__ import annotations

import math
import random
import logging
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import io
from bot.database import supabase
from .tournament_engine import next_round_pairings, round_robin_pairings, standings


def rows(table, **filters):
    q = supabase.table(table).select("*")
    for key, value in filters.items():
        q = q.eq(key, value)
    return q.execute().data or []


def insert_match(tournament_id, round_number, match_number, home_team_id=None, away_team_id=None, status="scheduled", home_score=None, away_score=None):
    payload = {
        "tournament_id": tournament_id,
        "round_number": round_number,
        "match_number": match_number,
        "home_team_id": str(home_team_id) if home_team_id is not None else None,
        "away_team_id": str(away_team_id) if away_team_id is not None else None,
        "status": status,
        "home_score": home_score,
        "away_score": away_score,
    }
    return supabase.table("tournament_matches").insert(payload).execute()


def update_match(match_id, **fields):
    return supabase.table("tournament_matches").update(fields).eq("id", match_id).execute()

def tournament(tid):
    data = rows("tournaments", id=tid)
    return data[0] if data else None


async def reply(interaction, text, ephemeral=True):
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=ephemeral)
    else:
        await interaction.response.send_message(text, ephemeral=ephemeral)


def can_manage(interaction, t):
    return str(interaction.user.id) == str(t["organizer_id"]) or interaction.user.guild_permissions.manage_guild


async def embed(t):
    ps = rows("tournament_participants", tournament_id=t["id"])
    ms = rows("tournament_matches", tournament_id=t["id"])
    done = sum(m["status"] == "completed" for m in ms)
    e = discord.Embed(title="🏆 " + t["name"], color=discord.Color.from_rgb(17, 17, 17))
    e.description = "**" + t["format"].title() + "** • **" + t["status"].title() + "**\nParticipants: **" + str(len(ps)) + "/" + str(t["max_participants"]) + "**"
    e.add_field(name="Progress", value=str(done) + "/" + str(len(ms)) + " matches completed" if ms else "Schedule belum dibuat.", inline=False)
    if t["format"] == "league":
        e.add_field(name="Scoring", value="Win 3 • Draw 1 • Loss 0", inline=False)
    e.add_field(name="Tournament ID", value="`" + str(t["id"]) + "`", inline=False)
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
                    "home_team_id": str(pair[0]), "away_team_id": str(pair[1]), "status": "scheduled"
                }).execute()
    else:
        random.shuffle(ids)
        size = 2 ** math.ceil(math.log2(len(ids)))
        ids += [None] * (size - len(ids))
        upper_rounds = int(math.log2(size))
        for rn in range(1, upper_rounds + 1):
            count = size // (2 ** rn)
            for mn in range(1, count + 1):
                home = away = None
                if rn == 1:
                    home, away = ids[(mn - 1) * 2], ids[(mn - 1) * 2 + 1]
                if rn == 1 and (home is None or away is None):
                    insert_match(t["id"], rn, mn, home, away, "completed", 0, 0)
                else:
                    insert_match(t["id"], rn, mn, home, away)
        lower_rounds = max(1, upper_rounds * 2 - 2)
        for lr in range(1, lower_rounds + 1):
            count = size // (2 ** math.ceil((lr + 2) / 2))
            for mn in range(1, count + 1):
                insert_match(t["id"], -lr, mn)
        insert_match(t["id"], 0, 1)
        await advance_double_elimination(t)

    supabase.table("tournaments").update({"status": "active"}).eq("id", t["id"]).execute()


async def advance_double_elimination(t):
    ps=rows("tournament_participants",tournament_id=t["id"]); size=2**math.ceil(math.log2(len(ps))); ur=int(math.log2(size)); lrt=max(1,ur*2-2)
    def win(m):
        if m["status"] not in ("completed","bye"): return None
        h,a=m["home_team_id"],m["away_team_id"]
        if not h or not a: return h or a
        return h if int(m["home_score"])>int(m["away_score"]) else a
    def lose(m):
        if m["status"]!="completed" or not m["home_team_id"] or not m["away_team_id"]: return None
        return m["away_team_id"] if win(m)==m["home_team_id"] else m["home_team_id"]
    for _ in range(ur+lrt+2):
        changed=False
        for r in range(1,ur):
            cur=sorted(rows("tournament_matches",tournament_id=t["id"],round_number=r),key=lambda x:x["match_number"]); nxt=sorted(rows("tournament_matches",tournament_id=t["id"],round_number=r+1),key=lambda x:x["match_number"])
            if not cur or not nxt or not all(m["status"] in ("completed","bye") for m in cur): continue
            ws=[win(m) for m in cur]
            for i,m in enumerate(nxt):
                p=ws[i*2:i*2+2]; v={}
                if len(p)>0 and p[0] and not m["home_team_id"]: v["home_team_id"]=str(p[0])
                if len(p)>1 and p[1] and not m["away_team_id"]: v["away_team_id"]=str(p[1])
                if v: update_match(m["id"],**v); changed=True
        for r in range(1,lrt+1):
            tg=sorted(rows("tournament_matches",tournament_id=t["id"],round_number=-r),key=lambda x:x["match_number"])
            if not tg: continue
            if r==1:
                src=sorted(rows("tournament_matches",tournament_id=t["id"],round_number=1),key=lambda x:x["match_number"])
                if not src or not all(m["status"] in ("completed","bye") for m in src): continue
                inc=[lose(m) for m in src]
            elif r%2==0:
                su=sorted(rows("tournament_matches",tournament_id=t["id"],round_number=r//2+1),key=lambda x:x["match_number"]); sl=sorted(rows("tournament_matches",tournament_id=t["id"],round_number=-(r-1)),key=lambda x:x["match_number"])
                if not su or not sl or not all(m["status"] in ("completed","bye") for m in su+sl): continue
                inc=[win(m) for m in sl]+[lose(m) for m in su]
            else:
                sl=sorted(rows("tournament_matches",tournament_id=t["id"],round_number=-(r-1)),key=lambda x:x["match_number"])
                if not sl or not all(m["status"] in ("completed","bye") for m in sl): continue
                inc=[win(m) for m in sl]
            inc=[x for x in inc if x]
            for i,m in enumerate(tg):
                p=inc[i*2:i*2+2]; v={}
                if len(p)>0 and p[0] and not m["home_team_id"]: v["home_team_id"]=str(p[0])
                if len(p)>1 and p[1] and not m["away_team_id"]: v["away_team_id"]=str(p[1])
                if v: update_match(m["id"],**v); changed=True
                h=v.get("home_team_id",m["home_team_id"]); a=v.get("away_team_id",m["away_team_id"])
                if h and not a and m["status"]=="scheduled": update_match(m["id"],status="bye",home_score=0,away_score=0); changed=True
        uf=rows("tournament_matches",tournament_id=t["id"],round_number=ur); lf=rows("tournament_matches",tournament_id=t["id"],round_number=-lrt); gf=rows("tournament_matches",tournament_id=t["id"],round_number=0)
        if uf and lf and gf:
            v={}; uw,lw=win(uf[0]),win(lf[0])
            if uw and not gf[0]["home_team_id"]: v["home_team_id"]=str(uw)
            if lw and not gf[0]["away_team_id"]: v["away_team_id"]=str(lw)
            if v: update_match(gf[0]["id"],**v); changed=True
        if not changed: break

async def create_next_knockout_round(t, round_number):
    if t["format"]=="knockout": await advance_double_elimination(t)


class ScoreModal(discord.ui.Modal, title="Input Skor"):
    home = discord.ui.TextInput(label="Skor Home", placeholder="0", max_length=3)
    away = discord.ui.TextInput(label="Skor Away", placeholder="0", max_length=3)

    def __init__(self, match_id, tournament_id):
        super().__init__()
        self.match_id = match_id
        self.tournament_id = tournament_id

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True)
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
        await interaction.followup.send("✅ Skor tersimpan. Standings/bracket diperbarui.", ephemeral=True)


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
        await interaction.response.defer()
        t = tournament(self.tid)
        await interaction.edit_original_response(embed=await embed(t), view=Dashboard(t))


class ParticipantsButton(discord.ui.Button):
    def __init__(self, tid):
        super().__init__(label="Participants", emoji="👥", style=discord.ButtonStyle.secondary)
        self.tid = tid
    async def callback(self, interaction):
        await interaction.response.defer(ephemeral=True)
        ps = rows("tournament_participants", tournament_id=self.tid)
        await reply(interaction, "👥 Participants\n" + ("\n".join("• <@" + str(p["user_id"]) + ">" for p in ps) or "Belum ada peserta."))


async def participant_names(interaction, tid):
    ps = rows("tournament_participants", tournament_id=tid)
    names = {}
    for p in ps:
        uid = str(p["user_id"])
        if p.get("participant_name"):
            names[uid] = str(p["participant_name"])
            continue
        member = interaction.guild.get_member(int(uid))
        if member is None:
            try:
                member = await interaction.guild.fetch_member(int(uid))
            except (discord.NotFound, discord.HTTPException):
                member = None
        names[uid] = member.display_name if member else "Unknown"
    return names


def _render_schedule(t,names=None):
    names=names or {}
    ms=sorted(rows("tournament_matches",tournament_id=t["id"]),key=lambda m:(m["round_number"],m["match_number"]))
    if not ms: return None
    items=ms[:50]; rows_per=7; cols=max(1,min(2,math.ceil(len(items)/rows_per)))
    cell_w,cell_h=500,82; width=cols*cell_w+60; height=125+math.ceil(len(items)/cols)*cell_h
    img=Image.new("RGB",(width,height),(12,12,15)); d=ImageDraw.Draw(img)
    tf,nf,bf=_font(28,True),_font(15),_font(16,True)
    d.text((30,25),f"{t['name']} • SCHEDULE",fill=(245,245,245),font=tf)
    for i,m in enumerate(items):
        col=i//rows_per; row=i%rows_per; x=30+col*cell_w; y=85+row*cell_h
        d.rounded_rectangle((x,y,x+cell_w-20,y+66),radius=9,outline=(70,70,80),width=2)
        d.text((x+12,y+7),f"R{m['round_number']} • M{m['match_number']}",fill=(170,170,180),font=nf)
        h=names.get(str(m["home_team_id"]),"TBD") if m["home_team_id"] else "TBD"
        a=names.get(str(m["away_team_id"]),"TBD") if m["away_team_id"] else "TBD"
        score=f"{m['home_score']} - {m['away_score']}" if m["status"] in ("completed","bye") else "VS"
        d.text((x+12,y+31),h[:22],fill=(245,245,245),font=bf)
        d.text((x+245,y+31),score,fill=(210,210,220),font=bf)
        d.text((x+330,y+31),a[:22],fill=(205,205,215),font=nf)
    buf=io.BytesIO(); img.save(buf,"PNG"); buf.seek(0); return discord.File(buf,filename="tournament-schedule.png")


class ScheduleButton(discord.ui.Button):
    def __init__(self, tid):
        super().__init__(label="Schedule", emoji="📅", style=discord.ButtonStyle.secondary)
        self.tid = tid
    async def callback(self, interaction):
        await interaction.response.defer(ephemeral=True)
        t=tournament(self.tid)
        names = await participant_names(interaction, self.tid)
        f=_render_schedule(t,names)
        e=discord.Embed(title=f"📅 {t['name']} — Schedule",color=discord.Color.from_rgb(17,17,17))
        if f: e.set_image(url="attachment://tournament-schedule.png")
        await interaction.followup.send(embed=e,file=f,ephemeral=True)


class StandingsButton(discord.ui.Button):
    def __init__(self, tid):
        super().__init__(label="Standings", emoji="🏆", style=discord.ButtonStyle.primary)
        self.tid = tid
    async def callback(self, interaction):
        await interaction.response.defer(ephemeral=True)
        ps = rows("tournament_participants", tournament_id=self.tid)
        ms = rows("tournament_matches", tournament_id=self.tid)
        table = standings([p["user_id"] for p in ps], ms)
        lines = ["Pos • Participant • P • W-D-L • GF:GA • Pts"]
        for pos, r in enumerate(table, 1):
            lines.append(str(pos) + ". <@" + str(r["team_id"]) + "> • " + str(r["played"]) + " • " + str(r["wins"]) + "-" + str(r["draws"]) + "-" + str(r["losses"]) + " • " + str(r["for"]) + ":" + str(r["against"]) + " • **" + str(r["points"]) + "**")
        await reply(interaction, "\n".join(lines))


def _font(size,bold=False):
    p="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try: return ImageFont.truetype(p,size)
    except OSError: return ImageFont.load_default()

def _render_bracket(t,section,names=None):
    names = names or {}
    ms=rows("tournament_matches",tournament_id=t["id"])
    if section=="upper": sel=[m for m in ms if m["round_number"]>0]; title="UPPER BRACKET"; key=lambda m:m["round_number"]
    elif section=="lower": sel=[m for m in ms if m["round_number"]<0]; title="LOWER BRACKET"; key=lambda m:abs(m["round_number"])
    else: sel=[m for m in ms if m["round_number"]==0]; title="GRAND FINAL"; key=lambda m:1
    if not sel: return None
    groups={}
    for m in sel: groups.setdefault(key(m),[]).append(m)
    groups=sorted(groups.items()); width=max(1000,330*len(groups)); top=105; bh=62; height=max(480,top+max(len(v) for _,v in groups)*90+70)
    img=Image.new("RGB",(width,height),(12,12,15)); d=ImageDraw.Draw(img); tf,rf,nf,bf=_font(28,True),_font(19,True),_font(14),_font(14,True)
    d.text((30,25),f"{t['name']} • {title}",fill=(245,245,245),font=tf); boxes=[]; gap=width//len(groups)
    for c,(rn,mm) in enumerate(groups):
        x=c*gap+30; d.text((x,75),f"ROUND {rn}",fill=(180,180,190),font=rf)
        for i,m in enumerate(mm):
            y=top+i*90; bw=min(280,gap-60); d.rounded_rectangle((x,y,x+bw,y+bh),radius=9,outline=(85,85,95),width=2)
            h=names.get(str(m["home_team_id"]), "TBD") if m["home_team_id"] else "TBD"; a=names.get(str(m["away_team_id"]), "TBD") if m["away_team_id"] else "TBD"; hs=str(m["home_score"]) if m["status"] in ("completed","bye") else ""; ass=str(m["away_score"]) if m["status"] in ("completed","bye") else ""
            d.text((x+10,y+7),h[:20],fill=(245,245,245),font=bf); d.text((x+10,y+33),a[:20],fill=(195,195,205),font=nf); d.text((x+bw-45,y+7),hs,fill=(245,245,245),font=bf); d.text((x+bw-45,y+33),ass,fill=(195,195,205),font=nf); boxes.append((c,x,y,bw,bh))
    for c in range(len(groups)-1):
        left=[b for b in boxes if b[0]==c]; right=[b for b in boxes if b[0]==c+1]
        for j,r in enumerate(right):
            a=left[min(j*2,len(left)-1)]; b=left[min(j*2+1,len(left)-1)]; y1=a[2]+bh//2; y2=b[2]+bh//2; yr=r[2]+bh//2; x1=a[1]+a[3]; x2=r[1]; mid=(x1+x2)//2
            d.line((x1,y1,mid,y1),fill=(95,95,105),width=2); d.line((x1,y2,mid,y2),fill=(95,95,105),width=2); d.line((mid,y1,mid,y2),fill=(95,95,105),width=2); d.line((mid,yr,x2,yr),fill=(95,95,105),width=2)
    buf=io.BytesIO(); img.save(buf,"PNG"); buf.seek(0); return discord.File(buf,filename="tournament-bracket.png")

class BracketView(discord.ui.View):
    def __init__(self,tid,section="upper"):
        super().__init__(timeout=900); self.tid=tid
        for k,l in (("upper","⬆️ Upper"),("lower","⬇️ Lower"),("grand","🏆 Grand")):
            b=BracketSectionButton(tid,k,l); b.disabled=k==section; self.add_item(b)

class BracketSectionButton(discord.ui.Button):
    def __init__(self,tid,section,label):
        super().__init__(label=label,style=discord.ButtonStyle.primary); self.tid=tid; self.section=section
    async def callback(self,interaction):
        await interaction.response.defer(); t=tournament(self.tid)
        names = await participant_names(interaction, self.tid)
        f=_render_bracket(t,self.section,names); e=discord.Embed(title=f"🧩 {t['name']} — {self.section.title()} Bracket",color=discord.Color.from_rgb(17,17,17))
        if f: e.set_image(url="attachment://tournament-bracket.png")
        await interaction.edit_original_response(embed=e,attachments=[f] if f else [],view=BracketView(self.tid,self.section))

class BracketButton(discord.ui.Button):
    def __init__(self,tid):
        super().__init__(label="Bracket",emoji="🧩",style=discord.ButtonStyle.primary); self.tid=tid
    async def callback(self,interaction):
        await interaction.response.defer(ephemeral=True); t=tournament(self.tid)
        names = await participant_names(interaction, self.tid)
        f=_render_bracket(t,"upper",names); e=discord.Embed(title=f"🧩 {t['name']} — Upper Bracket",color=discord.Color.from_rgb(17,17,17))
        if f: e.set_image(url="attachment://tournament-bracket.png")
        await interaction.followup.send(embed=e,file=f,view=BracketView(self.tid,"upper"),ephemeral=True)


class ResultsButton(discord.ui.Button):
    def __init__(self, tid):
        super().__init__(label="Results", emoji="📊", style=discord.ButtonStyle.secondary)
        self.tid = tid
    async def callback(self, interaction):
        await interaction.response.defer(ephemeral=True)
        ms = rows("tournament_matches", tournament_id=self.tid)
        done = [m for m in ms if m["status"] == "completed"]
        lines = []
        for m in done[-30:]:
            lines.append("R" + str(m["round_number"]) + " M" + str(m["match_number"]) + ": <@" + str(m["home_team_id"]) + "> **" + str(m["home_score"]) + "-" + str(m["away_score"]) + "** <@" + str(m["away_team_id"]) + ">")
        await reply(interaction, "📊 Results\n" + ("\n".join(lines) or "Belum ada hasil."))


class TournamentNameModal(discord.ui.Modal, title="Nama Peserta"):
    participant_name = discord.ui.TextInput(
        label="Nama",
        placeholder="Masukkan nama peserta (maks. 12 karakter)",
        min_length=1,
        max_length=12,
        required=True,
    )

    def __init__(self, tid):
        super().__init__()
        self.tid = tid

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True)
        t = tournament(self.tid)
        if not t or t["status"] != "registration":
            return await reply(interaction, "❌ Pendaftaran sudah ditutup.")

        name = str(self.participant_name.value).strip()
        if not name:
            return await reply(interaction, "❌ Nama tidak boleh kosong.")
        if len(name) > 12:
            return await reply(interaction, "❌ Nama maksimal 12 karakter termasuk spasi.")
        if any(ch != " " and not ch.isalpha() for ch in name):
            return await reply(interaction, "❌ Nama hanya boleh berisi huruf dan spasi. Angka, simbol, dan emote tidak diperbolehkan.")

        ps = rows("tournament_participants", tournament_id=self.tid)
        if len(ps) >= t["max_participants"]:
            return await reply(interaction, "❌ Slot tournament sudah penuh.")
        if rows("tournament_participants", tournament_id=self.tid, user_id=str(interaction.user.id)):
            return await reply(interaction, "ℹ️ Lu sudah terdaftar.")

        try:
            supabase.table("tournament_participants").insert({
                "tournament_id": self.tid,
                "user_id": str(interaction.user.id),
                "participant_name": name,
            }).execute()
        except Exception:
            logging.exception("Tournament participant join failed")
            return await reply(interaction, "❌ Gagal mendaftarkan nama peserta.")

        ps = rows("tournament_participants", tournament_id=self.tid)
        if len(ps) >= t["max_participants"]:
            try:
                await start_tournament(t)
                await reply(interaction, "✅ Lu berhasil masuk sebagai **" + name + "**. Slot penuh — tournament otomatis dimulai dan jadwal/bracket sudah dibuat.")
            except Exception:
                logging.exception("Auto-start tournament failed")
                await reply(interaction, "✅ Lu berhasil masuk sebagai **" + name + "**, tapi auto-generate jadwal gagal. Organizer bisa jalankan /tournament start.")
        else:
            await reply(interaction, "✅ Lu berhasil masuk sebagai **" + name + "**. (" + str(len(ps)) + "/" + str(t["max_participants"]) + ")")


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
        if rows("tournament_participants", tournament_id=self.tid, user_id=str(interaction.user.id)):
            return await reply(interaction, "ℹ️ Lu sudah terdaftar.")
        await interaction.response.send_modal(TournamentNameModal(self.tid))


class Tournament(commands.Cog):
    tournament = app_commands.Group(name="tournament", description="Tournament Maker")

    @tournament.command(name="create", description="Buat League atau Knock-out tournament.")
    @app_commands.describe(name="Nama tournament", format="Format", max_participants="Maksimal peserta")
    @app_commands.choices(format=[app_commands.Choice(name="League", value="league"), app_commands.Choice(name="Double Elimination", value="knockout")])
    async def create(self, interaction, name: str, format: app_commands.Choice[str], max_participants: app_commands.Range[int, 2, 64]):
        if not interaction.user.guild_permissions.manage_guild:
            return await reply(interaction, "❌ Butuh Manage Server untuk membuat tournament.")
        await interaction.response.defer()
        try:
            result = supabase.table("tournaments").insert({"guild_id": str(interaction.guild_id), "organizer_id": str(interaction.user.id), "name": name[:80], "format": format.value, "max_participants": max_participants, "status": "registration"}).execute()
            data = (result.data or [None])[0]
            if not data:
                raise RuntimeError("Supabase tidak mengembalikan data tournament.")
            await interaction.followup.send(embed=await embed(data), view=JoinView(data["id"]))
        except Exception:
            logging.exception("Tournament create failed")
            await interaction.followup.send("❌ Gagal membuat tournament. Cek koneksi/database Supabase.", ephemeral=True)

    @tournament.command(name="add", description="Tambahkan peserta secara manual.")
    @app_commands.describe(tournament_id="ID tournament", member="Member Discord yang ditambahkan")
    async def add(self, interaction, tournament_id: int, member: discord.Member):
        await interaction.response.defer(ephemeral=True)
        t = tournament(tournament_id)
        if not t or str(t["guild_id"]) != str(interaction.guild_id):
            return await reply(interaction, "❌ Tournament tidak ditemukan.")
        if not can_manage(interaction, t):
            return await reply(interaction, "❌ Hanya organizer / Manage Server.")
        if t["status"] != "registration":
            return await reply(interaction, "❌ Peserta hanya bisa ditambahkan saat fase pendaftaran.")
        ps = rows("tournament_participants", tournament_id=tournament_id)
        if len(ps) >= t["max_participants"]:
            return await reply(interaction, "❌ Slot tournament sudah penuh.")
        if rows("tournament_participants", tournament_id=tournament_id, user_id=str(member.id)):
            return await reply(interaction, "ℹ️ Member itu sudah terdaftar.")
        try:
            supabase.table("tournament_participants").insert({
                "tournament_id": tournament_id,
                "user_id": str(member.id)
            }).execute()
            ps = rows("tournament_participants", tournament_id=tournament_id)
            if len(ps) >= t["max_participants"]:
                await start_tournament(t)
                await reply(interaction, "✅ " + member.mention + " ditambahkan. Slot penuh — tournament otomatis dimulai dan jadwal/bracket sudah dibuat.")
            else:
                await reply(interaction, "✅ " + member.mention + " berhasil ditambahkan. (" + str(len(ps)) + "/" + str(t["max_participants"]) + ")")
        except Exception:
            logging.exception("Tournament add participant failed")
            return await reply(interaction, "❌ Gagal menambahkan peserta.")

    @tournament.command(name="delete", description="Hapus tournament beserta peserta, jadwal, dan hasilnya.")
    async def delete(self, interaction, tournament_id: int):
        await interaction.response.defer(ephemeral=True)
        t = tournament(tournament_id)
        if not t or str(t["guild_id"]) != str(interaction.guild_id):
            return await reply(interaction, "❌ Tournament tidak ditemukan.")
        if not can_manage(interaction, t):
            return await reply(interaction, "❌ Hanya organizer / Manage Server.")
        try:
            supabase.table("tournament_matches").delete().eq("tournament_id", tournament_id).execute()
            supabase.table("tournament_participants").delete().eq("tournament_id", tournament_id).execute()
            supabase.table("tournaments").delete().eq("id", tournament_id).execute()
        except Exception:
            logging.exception("Tournament delete failed")
            return await reply(interaction, "❌ Gagal menghapus tournament.")
        await reply(interaction, "🗑️ Tournament **" + t["name"] + "** (ID `" + str(tournament_id) + "`) berhasil dihapus.")

    @tournament.command(name="start", description="Tutup pendaftaran dan auto-generate jadwal/bracket.")
    async def start(self, interaction, tournament_id: int):
        await interaction.response.defer()
        t = tournament(tournament_id)
        if not t or str(t["guild_id"]) != str(interaction.guild_id):
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
        await interaction.followup.send(embed=await embed(t), view=Dashboard(t))

    @tournament.command(name="score", description="Input skor berdasarkan Match ID.")
    async def score(self, interaction, tournament_id: int, match_id: int, home_score: int, away_score: int):
        await interaction.response.defer(ephemeral=True)
        t = tournament(tournament_id)
        if not t or str(t["guild_id"]) != str(interaction.guild_id):
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
        await interaction.followup.send("✅ Skor tersimpan dan logic tournament diperbarui.", ephemeral=True)

    @tournament.command(name="panel", description="Buka dashboard tournament.")
    async def panel(self, interaction, tournament_id: int):
        await interaction.response.defer()
        t = tournament(tournament_id)
        if not t or str(t["guild_id"]) != str(interaction.guild_id):
            return await reply(interaction, "❌ Tournament tidak ditemukan.")
        await interaction.followup.send(embed=await embed(t), view=Dashboard(t))


async def setup(bot):
    await bot.add_cog(Tournament(bot))
