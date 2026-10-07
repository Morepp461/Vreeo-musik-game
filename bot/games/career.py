import discord
from ..database import supabase
from .player import get_character, money, CITIES

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
        "WORKPLACE_UNAVAILABLE":"Belum ada tempat kerja yang sesuai di kotamu.",
        "QUEST_NOT_FOUND":"Quest sudah tidak tersedia.",
        "JOB_NOT_ACTIVE":"Pekerjaan sudah tidak aktif.",
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
                role = discord.utils.get(i.guild.roles, name=f"WNI | Job | {r['job_name']}")
                if role is None:
                    role = await i.guild.create_role(name=f"WNI | Job | {r['job_name']}", reason="WNI job assignment")
                if role not in i.user.roles:
                    await i.user.add_roles(role, reason="WNI job assignment")
                await i.response.edit_message(embed=discord.Embed(title="✅ Diterima Kerja",description=f"Kamu sekarang bekerja sebagai **{r['job_name']}**.\\nGaji: **Rp{r['salary']:,}**\\n🏢 Tempat kerja: **{r.get('workplace_name','Ditentukan engine')}**",color=discord.Color.green()),view=CareerHubView(self.character_id))
            except Exception as e: await i.response.send_message("❌ "+_err(e),ephemeral=True)
        return cb


class CompanyModal(discord.ui.Modal, title='🏢 Daftar Perusahaan'):
    name=discord.ui.TextInput(label='Nama perusahaan',max_length=60)
    sector=discord.ui.TextInput(label='Bidang usaha',placeholder='Contoh: Restoran, Teknologi, Konstruksi',max_length=40)
    city=discord.ui.TextInput(label='Kota',placeholder='Contoh: Malang',max_length=30)
    capital=discord.ui.TextInput(label='Modal awal',placeholder='Minimal Rp1.000.000',max_length=15)
    async def on_submit(self,interaction):
        c=get_character(interaction.user.id,interaction.guild.id)
        if not c:return await interaction.response.send_message('❌ Kamu belum memiliki karakter.',ephemeral=True)
        city=self.city.value.strip()
        if city.lower() not in {x[1].lower() for x in CITIES}:return await interaction.response.send_message('❌ Kota belum tersedia di dunia.',ephemeral=True)
        try:
            capital=int(self.capital.value.replace('.','').replace(',','').replace('Rp','').strip())
            key='company-%s-%s-%s'%(interaction.guild.id,interaction.user.id,abs(hash(self.name.value.strip().lower()))%100000000)
            d=supabase.rpc('game_register_company',{'p_owner_character_id':c['id'],'p_application_key':key,'p_name':self.name.value.strip(),'p_sector':self.sector.value.strip(),'p_city_key':city.lower().replace(' ','-'),'p_capital':capital}).execute().data
            await interaction.response.send_message('🏢 Pendaftaran perusahaan diterima.\nNama: **%s**\nKota: **%s**\nModal: **Rp%s**\n\n📋 Menunggu pemeriksaan polisi → persetujuan wali kota.'%(self.name.value.strip(),city,f'{capital:,}'),ephemeral=True)
        except Exception as e:await interaction.response.send_message('❌ '+_err(e),ephemeral=True)

class CompanyView(discord.ui.View):
    def __init__(self,character_id):super().__init__(timeout=300);self.character_id=character_id
    @discord.ui.button(label='Daftar Perusahaan',emoji='🏢',style=discord.ButtonStyle.success)
    async def register(self,i,b):
        c=get_character(i.user.id,i.guild.id)
        if not c or c['id']!=self.character_id:return await i.response.send_message('❌ Ini bukan karaktermu.',ephemeral=True)
        await i.response.send_modal(CompanyModal())
    @discord.ui.button(label='Status Pengajuan',emoji='📋',style=discord.ButtonStyle.primary)
    async def status(self,i,b):
        rows=supabase.table('game_company_applications').select('company_name,police_status,mayor_status,final_status').eq('owner_character_id',self.character_id).order('created_at',desc=True).limit(5).execute().data or []
        desc='Belum ada pengajuan perusahaan.' if not rows else '\n'.join('**%s** — Polisi: `%s` • Wali kota: `%s` • Final: `%s`'%(x['company_name'],x['police_status'],x['mayor_status'],x['final_status']) for x in rows)
        await i.response.edit_message(embed=discord.Embed(title='🏢 Perusahaan',description=desc,color=discord.Color.gold()),view=self)
    @discord.ui.button(label='Kembali',emoji='↩️',style=discord.ButtonStyle.secondary)
    async def back(self,i,b):
        c=get_character(i.user.id,i.guild.id)
        if not c or c['id']!=self.character_id:return await i.response.send_message('❌ Ini bukan dashboard karaktermu.',ephemeral=True)
        await i.response.edit_message(embed=discord.Embed(title='💼 Karier',description='Bangun kehidupan profesionalmu.',color=discord.Color.blurple()),view=CareerHubView(self.character_id))

class QuestView(discord.ui.View):
    def __init__(self,character_id):
        super().__init__(timeout=300); self.character_id=character_id
    async def render(self,interaction):
        job=supabase.table("game_character_jobs").select("id").eq("character_id",self.character_id).eq("status","active").limit(1).execute().data or []
        if not job:
            return await interaction.response.edit_message(embed=discord.Embed(title="🎯 Quest Profesi",description="Belum memiliki pekerjaan aktif.",color=discord.Color.orange()),view=CareerHubView(self.character_id))
        rows=supabase.table("game_job_quests").select("id,title,description,trigger_type").eq("character_job_id",job[0]["id"]).eq("status","open").order("assigned_at",desc=True).limit(5).execute().data or []
        e=discord.Embed(title="🎯 Quest Profesi",description="Quest muncul dari kondisi nyata dunia/tempat kerja. Tidak ada pembayaran cash langsung.",color=discord.Color.blurple())
        v=discord.ui.View(timeout=300)
        for q in rows:
            e.add_field(name=q["title"],value=q["description"],inline=False)
            b=discord.ui.Button(label="Selesaikan",style=discord.ButtonStyle.success)
            async def done(i,qid=q["id"],jid=job[0]["id"]):
                try:
                    r=supabase.rpc("game_complete_job_quest",{"p_character_job_id":jid,"p_quest_id":qid}).execute().data
                    await i.response.edit_message(embed=discord.Embed(title="✅ Quest Selesai",description="Performa dan XP karier bertambah.",color=discord.Color.green()),view=self)
                except Exception as ex: await i.response.send_message("❌ "+_err(ex),ephemeral=True)
            b.callback=done; v.add_item(b)
        if not rows: e.description="Belum ada quest aktif. Quest akan muncul ketika kondisi profesimu benar-benar terjadi di dunia."
        await interaction.response.edit_message(embed=e,view=v if rows else self)
    @discord.ui.button(label="🔄 Refresh",style=discord.ButtonStyle.secondary)
    async def refresh(self,i,b): await self.render(i)
    @discord.ui.button(label="↩️ Karier",style=discord.ButtonStyle.primary)
    async def back(self,i,b): await i.response.edit_message(embed=discord.Embed(title="💼 Karier",description="Bangun kehidupan profesionalmu.",color=discord.Color.blurple()),view=CareerHubView(self.character_id))

class CareerHubView(discord.ui.View):
    def __init__(self,character_id):
        super().__init__(timeout=300);self.character_id=character_id
    @discord.ui.button(label="Lihat Lowongan",emoji="💼",style=discord.ButtonStyle.primary)
    async def listings(self,i,b):await i.response.edit_message(embed=jobs_embed(),view=JobView(self.character_id))
    @discord.ui.button(label='Perusahaan',emoji='🏢',style=discord.ButtonStyle.success,row=1)
    async def company(self,i,b):
        c=get_character(i.user.id,i.guild.id)
        if not c or c['id']!=self.character_id:return await i.response.send_message('❌ Ini bukan dashboard karaktermu.',ephemeral=True)
        await i.response.edit_message(embed=discord.Embed(title='🏢 Perusahaan',description='Bangun perusahaan melalui alur polisi → wali kota → legalitas.',color=discord.Color.gold()),view=CompanyView(self.character_id))

    @discord.ui.button(label="Quest Profesi",emoji="🎯",style=discord.ButtonStyle.primary,row=2)
    async def quest(self,i,b):
        c=get_character(i.user.id,i.guild.id)
        if not c or c["id"]!=self.character_id:return await i.response.send_message("❌ Ini bukan dashboard karaktermu.",ephemeral=True)
        await i.response.edit_message(embed=discord.Embed(title="🎯 Quest Profesi",description="Memuat kondisi dunia...",color=discord.Color.blurple()),view=QuestView(self.character_id))
\n    @discord.ui.button(label="Status Kerja",emoji="📋",style=discord.ButtonStyle.success)
    async def status(self,i,b):
        try:
            rows=supabase.table("game_character_jobs").select("id,job_id,salary,skill,status,started_at,performance,position_level,career_xp,employer_institution_id,position_title").eq("character_id",self.character_id).eq("status","active").limit(1).execute().data or []
            if not rows:return await i.response.edit_message(embed=discord.Embed(title="📋 Status Kerja",description="Belum punya pekerjaan aktif.",color=discord.Color.orange()),view=self)
            j=supabase.table("game_jobs").select("job_name,sector").eq("id",rows[0]["job_id"]).limit(1).execute().data
            x=rows[0]
            e=discord.Embed(title="📋 Status Kerja",color=discord.Color.green())
            e.add_field(name="Pekerjaan",value=j[0]["job_name"] if j else "—",inline=True)
            e.add_field(name="Gaji",value=f"Rp{x['salary']:,}",inline=True)
            e.add_field(name="Skill",value=f"{x['skill']}/100",inline=True)
            e.add_field(name="Mulai",value=str(x["started_at"])[:10],inline=True)
            e.add_field(name="Performa",value=f"{x.get('performance',50)}/100",inline=True)
            e.add_field(name="Level Karier",value=str(x.get("position_level",1)),inline=True)
            e.add_field(name="XP Karier",value=str(x.get("career_xp",0)),inline=True)
            inst=supabase.table("game_institutions").select("name,institution_type").eq("id",x.get("employer_institution_id")).limit(1).execute().data if x.get("employer_institution_id") else []
            if inst: e.add_field(name="Tempat Kerja",value=f"{inst[0]['name']} ({inst[0]['institution_type']})",inline=False)
            await i.response.edit_message(embed=e,view=CareerHubView(self.character_id))
        except Exception as e:await i.response.send_message("❌ "+_err(e),ephemeral=True)
    @discord.ui.button(label="Pemerintahan Kota",emoji="🏛️",style=discord.ButtonStyle.secondary,row=1)
    async def citygov(self,i,b):
        rows=supabase.table("game_city_governments").select("city_id,mayor_name,approval,budget,tax_rate,revenue_monthly,expense_monthly,policy_key,term_ends_at").limit(20).execute().data or []
        city=get_character(i.user.id,i.guild.id)
        row=None
        if city:
            c=supabase.table("game_cities").select("id").eq("name",city["city"]).limit(1).execute().data
            if c: row=next((x for x in rows if x["city_id"]==c[0]["id"]),None)
        if not row:return await i.response.send_message("❌ Data pemerintahan kota belum tersedia.",ephemeral=True)
        e=discord.Embed(title=f"🏛️ Pemerintahan {city['city']}",color=discord.Color.dark_red())
        e.add_field(name="Wali Kota",value=row["mayor_name"] or "Belum ditentukan",inline=True)
        e.add_field(name="Approval",value=f"{row['approval']}/100",inline=True)
        e.add_field(name="Pajak",value=f"{float(row['tax_rate'])*100:.2f}%",inline=True)
        e.add_field(name="Anggaran",value=money(row["budget"]),inline=True)
        e.add_field(name="Pendapatan/bln",value=money(row["revenue_monthly"]),inline=True)
        e.add_field(name="Belanja/bln",value=money(row["expense_monthly"]),inline=True)
        e.add_field(name="Kebijakan",value=row["policy_key"] or "Belum ada",inline=True)
        await i.response.edit_message(embed=e,view=CareerHubView(self.character_id))
    @discord.ui.button(label="Resign",emoji="📤",style=discord.ButtonStyle.danger)
    async def resign(self,i,b):
        c=get_character(i.user.id,i.guild.id)
        if not c or c["id"]!=self.character_id:return await i.response.send_message("❌ Ini bukan karaktermu.",ephemeral=True)
        try:
            supabase.rpc("game_resign_job",{"p_character_id":self.character_id}).execute()
            role_names=[r.name for r in i.user.roles if r.name.startswith("WNI | Job | ")]
            for role_name in role_names:
                role=discord.utils.get(i.guild.roles,name=role_name)
                if role:
                    try: await i.user.remove_roles(role, reason="WNI job resignation")
                    except Exception: pass
            await i.response.edit_message(embed=discord.Embed(title="📤 Resign Berhasil",description="Pekerjaan aktifmu telah diakhiri.",color=discord.Color.orange()),view=self)
        except Exception as e:await i.response.send_message("❌ "+_err(e),ephemeral=True)
    @discord.ui.button(label="Kembali",emoji="↩️",style=discord.ButtonStyle.secondary)
    async def back(self,i,b):
        c=get_character(i.user.id,i.guild.id)
        if not c or c["id"]!=self.character_id:return await i.response.send_message("❌ Ini bukan karaktermu.",ephemeral=True)
        from .commands import profile_embed,PlayerView
        await i.response.edit_message(embed=profile_embed(c),view=PlayerView(c))
