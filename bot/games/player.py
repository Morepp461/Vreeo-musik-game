from datetime import date
import discord
from ..database import supabase

STARTING_CASH=250_000
CITIES=[('DKI Jakarta','Jakarta'),('Jawa Barat','Bandung'),('Jawa Tengah','Semarang'),('DI Yogyakarta','Yogyakarta'),('Jawa Timur','Surabaya'),('Jawa Timur','Malang'),('Banten','Tangerang'),('Sumatera Utara','Medan'),('Sumatera Selatan','Palembang'),('Riau','Pekanbaru'),('Bali','Denpasar'),('Kalimantan Timur','Balikpapan'),('Sulawesi Selatan','Makassar'),('Papua','Jayapura')]

def get_character(user_id,guild_id):
    r=supabase.table('game_characters').select('*').eq('discord_user_id',str(user_id)).eq('guild_id',str(guild_id)).limit(1).execute()
    return r.data[0] if r.data else None
def get_wallet(character_id):
    r=supabase.table('game_wallets').select('*').eq('character_id',character_id).limit(1).execute()
    return r.data[0] if r.data else None
def get_needs(character_id):
    r=supabase.table('game_needs').select('*').eq('character_id',character_id).limit(1).execute()
    return r.data[0] if r.data else None
def get_inventory(character_id):
    return supabase.table('game_inventory').select('*').eq('character_id',character_id).order('item_name').execute().data or []
def get_assets(character_id):
    return supabase.table('game_owned_assets').select('*, game_asset_templates(name,category,base_price)').eq('character_id',character_id).eq('status','owned').execute().data or []
def money(value): return 'Rp'+f'{int(value or 0):,}'.replace(',','.')

class CharacterModal(discord.ui.Modal,title='🪪 Daftar WNI SIMULATOR'):
    name=discord.ui.TextInput(label='Nama karakter',placeholder='Contoh: Andi Pratama',min_length=1,max_length=32)
    gender=discord.ui.TextInput(label='Jenis kelamin',placeholder='Laki-laki / Perempuan',max_length=12)
    birth_year=discord.ui.TextInput(label='Tahun lahir',placeholder='Contoh: 2000',min_length=4,max_length=4)
    city=discord.ui.TextInput(label='Kota awal',placeholder='Contoh: Malang',max_length=30)
    background=discord.ui.TextInput(label='Latar belakang',placeholder='Contoh: Keluarga sederhana',max_length=80,required=False)
    async def on_submit(self,interaction):
        try:
            gender=self.gender.value.strip().title()
            if gender not in ('Laki-Laki','Perempuan'): raise ValueError('Jenis kelamin harus Laki-laki atau Perempuan.')
            gender='Laki-laki' if gender=='Laki-Laki' else gender
            matches=[(p,c) for p,c in CITIES if c.lower()==self.city.value.strip().lower()]
            if not matches: raise ValueError('Kota awal belum tersedia di daftar dunia tahap ini.')
            province,city=matches[0]; year=int(self.birth_year.value)
            world=supabase.table('game_world_state').select('world_time').eq('id',1).limit(1).execute()
            current_year=date.fromisoformat((world.data[0]['world_time'] if world.data else date.today().isoformat())[:10]).year
            if year<current_year-100 or year>current_year-13: raise ValueError('Usia karakter harus minimal 13 tahun.')
            supabase.rpc('game_create_character',{'p_discord_user_id':str(interaction.user.id),'p_guild_id':str(interaction.guild.id),'p_name':self.name.value.strip(),'p_gender':gender,'p_birth_date':f'{year:04d}-01-01','p_background':self.background.value.strip() or 'Umum','p_province':province,'p_city':city}).execute()
            await interaction.response.send_message(f'🇮🇩 **Selamat datang, {self.name.value.strip()}!**\n📍 Domisili awal: **{city}, {province}**\n💵 Modal awal: **{money(STARTING_CASH)}**\n📱 Ponsel standar: **1**\n\nGunakan `/game` untuk membuka dashboard.',ephemeral=True)
        except ValueError as exc: await interaction.response.send_message(f'❌ {exc}',ephemeral=True)
        except Exception as exc:
            msg='❌ Pendaftaran gagal. Coba lagi.'
            if 'CHARACTER_EXISTS' in str(exc): msg='❌ Kamu sudah memiliki karakter di server ini.'
            await interaction.response.send_message(msg,ephemeral=True)

class RegisterView(discord.ui.View):
    def __init__(self): super().__init__(timeout=180)
    @discord.ui.button(label='Daftar & Buat Karakter',emoji='🪪',style=discord.ButtonStyle.success)
    async def register(self,interaction,button):
        if get_character(interaction.user.id,interaction.guild.id): return await interaction.response.send_message('❌ Kamu sudah memiliki karakter.',ephemeral=True)
        await interaction.response.send_modal(CharacterModal())

def profile_embed(character):
    wallet=get_wallet(character['id']) or {}; needs=get_needs(character['id']) or {}
    e=discord.Embed(title='🇮🇩 '+character['name'],color=discord.Color.dark_red())
    e.add_field(name='📍 Domisili',value=f"{character['city']}, {character['province']}",inline=True)
    e.add_field(name='🎂 Tahun lahir',value=str(character['birth_date'])[:4],inline=True)
    e.add_field(name='💼 Status',value=character['status'].title(),inline=True)
    e.add_field(name='💵 Tunai',value=money(wallet.get('cash')),inline=True); e.add_field(name='🏦 Bank',value=money(wallet.get('bank')),inline=True); e.add_field(name='💳 Utang',value=money(wallet.get('debt')),inline=True)
    e.add_field(name='❤️ Kesehatan',value=f"{needs.get('health',0)}/100",inline=True); e.add_field(name='🍚 Lapar',value=f"{needs.get('hunger',0)}/100",inline=True); e.add_field(name='💧 Haus',value=f"{needs.get('thirst',0)}/100",inline=True); e.add_field(name='⚡ Energi',value=f"{needs.get('energy',0)}/100",inline=True); e.add_field(name='😊 Bahagia',value=f"{needs.get('happiness',0)}/100",inline=True); e.add_field(name='😵 Stres',value=f"{needs.get('stress',0)}/100",inline=True)
    return e
def inventory_text(character_id):
    items=get_inventory(character_id)
    return 'Inventaris kosong.' if not items else '\n'.join(f"• {x['item_name']} × {x['quantity']}" for x in items[:25])
def assets_text(character_id):
    assets=get_assets(character_id)
    if not assets: return 'Belum memiliki aset.'
    return '\n'.join(f"• {(x.get('game_asset_templates') or {}).get('name','Aset')} — {money(x.get('purchase_price'))}" for x in assets[:20])
