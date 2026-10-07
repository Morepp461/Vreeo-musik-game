import discord
from ..database import supabase
from .player import get_character, money

def _err(exc):
    s=str(exc)
    m={
        "ALREADY_EMPLOYED":"Kamu sudah memiliki pekerjaan aktif.",
        "JOB_NOT_FOUND":"Pekerjaan tidak tersedia.",
        "SKILL_TOO_LOW":"Skill belum cukup.",
        "CHARACTER_NOT_FOUND":"Karakter tidak ditemukan.",
        "CHARACTER_NOT_ACTIVE":"Karakter tidak aktif.",
        "CAPITAL_TOO_LOW":"Modal minimal Rp1.000.000.",
        "BUSINESS_KEY_EXISTS":"Kode bisnis sudah dipakai.",
        "NOT_BUSINESS_OWNER":"Kamu bukan pemilik bisnis ini.",
        "INSUFFICIENT_STOCK":"Stok tidak cukup.",
        "BUSINESS_INSUFFICIENT_CASH":"Kas bisnis tidak cukup.",
        "ALREADY_EMPLOYEE":"Karakter tersebut sudah bekerja di bisnis ini.",
        "EMPLOYEE_NOT_FOUND":"Karyawan tidak ditemukan.",
    }
    for k,v in m.items():
        if k in s:return v
    return f"Error sistem: {s[:180]}"

def jobs_embed():
    rows=supabase.table("game_jobs").select("job_key,job_name,sector,base_salary,min_skill").eq("active",True).order("base_salary").execute().data or []
    e=discord.Embed(title="💼 Bursa Kerja",description="Pilih pekerjaan. Skill dan gaji diproses engine database.",color=discord.Color.blurple())
    for j in rows[:10]:
        e.add_field(name=j["job_name"],value=f"{j['sector']} • Rp{j['base_salary']:,}\nSkill minimum: {j['min_skill']}/100",inline=True)
    return e

class JobView(discord.ui.View):
    def __init__(self,character_id):
        super().__init__(timeout=300);self.character_id=character_id
        rows=supabase.table("game_jobs").select("job_key,job_name").eq("active",True).order("job_name").execute().data or []
        for j in rows[:25]:
            b=discord.ui.Button(label=j["job_name"],style=discord.ButtonStyle.primary)
            b.callback=self._cb(j["job_key"]);self.add_item(b)
    def _cb(self,key):
        async def cb(i):
            c=get_character(i.user.id,i.guild.id)
            if not c or c["id"]!=self.character_id:return await i.response.send_message("❌ Ini bukan karaktermu.",ephemeral=True)
            try:
                d=supabase.rpc("game_apply_for_job",{"p_character_id":self.character_id,"p_job_key":key}).execute().data
                r=d[0] if isinstance(d,list) else d
                await i.response.edit_message(embed=discord.Embed(title="✅ Diterima Kerja",description=f"Kamu sekarang bekerja sebagai **{r['job_name']}**.\nGaji: **Rp{r['salary']:,}**",color=discord.Color.green()),view=CareerHubView(self.character_id))
            except Exception as e: await i.response.send_message("❌ "+_err(e),ephemeral=True)
        return cb

class CareerHubView(discord.ui.View):
    def __init__(self,character_id):
        super().__init__(timeout=300);self.character_id=character_id
    @discord.ui.button(label="Lihat Lowongan",emoji="💼",style=discord.ButtonStyle.primary)
    async def listings(self,i,b):await i.response.edit_message(embed=jobs_embed(),view=JobView(self.character_id))
    @discord.ui.button(label="Status Kerja",emoji="📋",style=discord.ButtonStyle.success)
    async def status(self,i,b):
        try:
            rows=supabase.table("game_character_jobs").select("id,job_id,salary,skill,status,started_at").eq("character_id",self.character_id).eq("status","active").limit(1).execute().data or []
            if not rows:return await i.response.edit_message(embed=discord.Embed(title="📋 Status Kerja",description="Belum punya pekerjaan aktif.",color=discord.Color.orange()),view=self)
            j=supabase.table("game_jobs").select("job_name,sector").eq("id",rows[0]["job_id"]).limit(1).execute().data
            x=rows[0]
            e=discord.Embed(title="📋 Status Kerja",color=discord.Color.green())
            e.add_field(name="Pekerjaan",value=j[0]["job_name"] if j else "—",inline=True)
            e.add_field(name="Gaji",value=f"Rp{x['salary']:,}",inline=True)
            e.add_field(name="Skill",value=f"{x['skill']}/100",inline=True)
            e.add_field(name="Mulai",value=str(x["started_at"])[:10],inline=True)
            await i.response.edit_message(embed=e,view=CareerHubView(self.character_id))
        except Exception as e:await i.response.send_message("❌ "+_err(e),ephemeral=True)
    @discord.ui.button(label="Resign",emoji="📤",style=discord.ButtonStyle.danger)
    async def resign(self,i,b):
        c=get_character(i.user.id,i.guild.id)
        if not c or c["id"]!=self.character_id:return await i.response.send_message("❌ Ini bukan karaktermu.",ephemeral=True)
        try:
            supabase.rpc("game_resign_job",{"p_character_id":self.character_id}).execute()
            await i.response.edit_message(embed=discord.Embed(title="📤 Resign Berhasil",description="Pekerjaan aktifmu telah diakhiri.",color=discord.Color.orange()),view=self)
        except Exception as e:await i.response.send_message("❌ "+_err(e),ephemeral=True)
    @discord.ui.button(label="Kembali",emoji="↩️",style=discord.ButtonStyle.secondary)
    async def back(self,i,b):
        c=get_character(i.user.id,i.guild.id)
        if not c or c["id"]!=self.character_id:return await i.response.send_message("❌ Ini bukan karaktermu.",ephemeral=True)
        from .commands import profile_embed,PlayerView
        await i.response.edit_message(embed=profile_embed(c),view=PlayerView(c))
