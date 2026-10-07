import discord
from ..database import supabase
from .player import get_character, money

def jobs_embed():
    rows=supabase.table("game_jobs").select("job_key,job_name,sector,base_salary,min_skill").eq("active",True).order("base_salary").execute().data or []
    e=discord.Embed(title="💼 Bursa Kerja",description="Pilih pekerjaan. Gaji dasar mengikuti data ekonomi game.",color=discord.Color.blurple())
    for j in rows[:10]:
        e.add_field(name=j["job_name"],value=f"{j['sector']} • Gaji Rp{j['base_salary']:,}\nSkill minimum: {j['min_skill']}/100",inline=True)
    return e

class JobView(discord.ui.View):
    def __init__(self,character_id):
        super().__init__(timeout=300); self.character_id=character_id
        rows=supabase.table("game_jobs").select("job_key,job_name").eq("active",True).order("job_name").execute().data or []
        for j in rows[:25]:
            b=discord.ui.Button(label=j["job_name"],style=discord.ButtonStyle.primary)
            b.callback=self._cb(j["job_key"],j["job_name"]); self.add_item(b)
    def _cb(self,key,name):
        async def cb(interaction):
            c=get_character(interaction.user.id,interaction.guild.id)
            if not c or c["id"]!=self.character_id: return await interaction.response.send_message("❌ Ini bukan karaktermu.",ephemeral=True)
            try:
                data=supabase.rpc("game_apply_for_job",{"p_character_id":self.character_id,"p_job_key":key}).execute().data
                row=data[0] if isinstance(data,list) else data
                await interaction.response.edit_message(embed=discord.Embed(title="✅ Diterima Kerja",description=f"Kamu sekarang bekerja sebagai **{row['job_name']}**.\nGaji dasar: **Rp{row['salary']:,}**",color=discord.Color.green()),view=None)
            except Exception as exc:
                s=str(exc)
                msg=("Kamu sudah memiliki pekerjaan aktif." if "ALREADY_EMPLOYED" in s else "Pekerjaan tidak tersedia." if "JOB_NOT_FOUND" in s else "Skill belum cukup." if "SKILL_TOO_LOW" in s else "Karakter tidak ditemukan." if "CHARACTER_NOT_FOUND" in s else "Karakter tidak aktif." if "CHARACTER_NOT_ACTIVE" in s else f"Error sistem: {s[:180]}")
                await interaction.response.send_message("❌ "+msg,ephemeral=True)
        return cb

class CareerHubView(discord.ui.View):
    def __init__(self,character_id):
        super().__init__(timeout=300); self.character_id=character_id
    @discord.ui.button(label="Lihat Lowongan",emoji="💼",style=discord.ButtonStyle.primary)
    async def listings(self,i,b): await i.response.edit_message(embed=jobs_embed(),view=JobView(self.character_id))
    @discord.ui.button(label="Kembali",emoji="↩️",style=discord.ButtonStyle.secondary)
    async def back(self,i,b):
        c=get_character(i.user.id,i.guild.id)
        if not c or c["id"]!=self.character_id: return await i.response.send_message("❌ Ini bukan dashboard karaktermu.",ephemeral=True)
        from .commands import profile_embed, PlayerView
        await i.response.edit_message(embed=profile_embed(c),view=PlayerView(c))
