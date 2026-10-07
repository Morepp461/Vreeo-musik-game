import random
import discord
from ..database import supabase
from .player import get_character, money

CITIES=["Jakarta","Bandung","Semarang","Yogyakarta","Surabaya","Malang","Tangerang","Medan","Palembang","Pekanbaru","Denpasar","Balikpapan","Makassar","Jayapura"]

ACTIONS={
    "eat":("🍚 Makan","Rp25.000"),
    "drink":("💧 Minum","Rp10.000"),
    "rest":("😴 Istirahat","Gratis"),
    "study":("📚 Belajar","Gratis"),
    "walk":("🚶 Jalan-jalan","Rp15.000"),
    "socialize":("🗣️ Bersosialisasi","Rp10.000"),
}

SHOP_ITEMS=[
    ("nasi_sederhana","Nasi sederhana",25000),
    ("air_mineral","Air mineral",10000),
    ("kaos","Kaos",75000),
    ("sepatu","Sepatu",250000),
]

EVENTS=[
    {
        "key":"teman_baru",
        "title":"🤝 Bertemu orang baru",
        "description":"Saat beraktivitas, kamu berkenalan dengan seseorang yang ramah. Ia mengajakmu ikut kegiatan komunitas kecil.",
        "choices":[
            {"key":"ikut","label":"Ikut kegiatan","outcome":"Kamu ikut dan mendapat pengalaman sosial baru.","happiness_delta":8,"stress_delta":-5},
            {"key":"lewat","label":"Lewatkan","outcome":"Kamu memilih melanjutkan urusanmu sendiri.","happiness_delta":-1},
        ],
    },
    {
        "key":"kesempatan_belajar",
        "title":"📚 Kesempatan belajar",
        "description":"Kamu menemukan kelas gratis yang bisa menambah wawasan. Jadwalnya cukup padat.",
        "choices":[
            {"key":"ambil","label":"Ikut kelas","outcome":"Kamu mengikuti kelas dan merasa lebih percaya diri.","happiness_delta":5,"energy_delta":-5},
            {"key":"nanti","label":"Nanti saja","outcome":"Kamu menyimpan informasi itu untuk kesempatan berikutnya.","stress_delta":-2},
        ],
    },
    {
        "key":"pengeluaran_mendadak",
        "title":"💸 Pengeluaran mendadak",
        "description":"Ada kebutuhan kecil yang tidak kamu rencanakan hari ini.",
        "choices":[
            {"key":"bayar","label":"Bayar Rp20.000","outcome":"Kamu menyelesaikan kebutuhan itu tanpa menundanya.","cash_delta":-20000,"stress_delta":-3},
            {"key":"tunda","label":"Tunda","outcome":"Kamu memilih menunda pengeluaran tersebut.","stress_delta":4},
        ],
    },
]

def _err(exc):
    s=str(exc)
    mapping={
        "INSUFFICIENT_CASH":"Uang tunai tidak cukup.",
        "NOT_ENOUGH_ENERGY":"Energi tidak cukup.",
        "CHARACTER_NOT_ACTIVE":"Karakter sedang tidak aktif.",
        "CHARACTER_NOT_FOUND":"Karakter tidak ditemukan.",
        "EVENT_NOT_FOUND":"Event tidak ditemukan.",
        "EVENT_ALREADY_RESOLVED":"Event itu sudah diselesaikan.",
        "INVALID_EVENT_CHOICE":"Pilihan event tidak valid.",
    }
    for key,msg in mapping.items():
        if key in s: return msg
    return "Aksi gagal. Coba lagi."

class ActionView(discord.ui.View):
    def __init__(self, character_id):
        super().__init__(timeout=300)
        self.character_id=character_id
        for key,(label,cost) in ACTIONS.items():
            b=discord.ui.Button(label=label,style=discord.ButtonStyle.secondary,row=0 if key in ("eat","drink","rest") else 1)
            b.callback=self._make_callback(key)
            self.add_item(b)
    def _make_callback(self,key):
        async def callback(interaction):
            c=get_character(interaction.user.id,interaction.guild.id)
            if not c or c["id"]!=self.character_id:
                return await interaction.response.send_message("❌ Ini bukan dashboard karaktermu.",ephemeral=True)
            try:
                result=supabase.rpc("game_perform_action",{"p_character_id":self.character_id,"p_action_key":key}).execute().data
                row=result[0] if isinstance(result,list) else result
                msg=f"**{row['action_name']} berhasil.**\n{row['outcome']}\n💵 Tunai: **{money(row['cash'])}**"
                await interaction.response.send_message(msg,ephemeral=True)
                await maybe_create_event(self.character_id,interaction)
            except Exception as exc:
                await interaction.response.send_message("❌ "+_err(exc),ephemeral=True)
        return callback

class EventView(discord.ui.View):
    def __init__(self,event_id,character_id,choices):
        super().__init__(timeout=300)
        self.event_id=event_id
        self.character_id=character_id
        for choice in choices[:5]:
            b=discord.ui.Button(label=choice.get("label","Pilih"),style=discord.ButtonStyle.primary)
            b.callback=self._make_callback(choice["key"])
            self.add_item(b)
    def _make_callback(self,key):
        async def callback(interaction):
            c=get_character(interaction.user.id,interaction.guild.id)
            if not c or c["id"]!=self.character_id:
                return await interaction.response.send_message("❌ Event ini bukan milikmu.",ephemeral=True)
            try:
                result=supabase.rpc("game_resolve_character_event",{"p_event_id":self.event_id,"p_character_id":self.character_id,"p_choice_key":key}).execute().data
                row=result[0] if isinstance(result,list) else result
                for item in self.children: item.disabled=True
                await interaction.response.edit_message(content=f"✅ **Pilihan dicatat.**\n{row['outcome']}\n💵 Tunai: **{money(row['cash'])}**",view=self)
            except Exception as exc:
                await interaction.response.send_message("❌ "+_err(exc),ephemeral=True)
        return callback

async def maybe_create_event(character_id,interaction):
    if random.random()>0.18:
        return
    event=random.choice(EVENTS)
    try:
        event_id=supabase.rpc("game_create_character_event",{
            "p_character_id":character_id,
            "p_event_key":event["key"],
            "p_title":event["title"],
            "p_description":event["description"],
            "p_choices":event["choices"],
        }).execute().data
        if isinstance(event_id,list): event_id=event_id[0]
        await interaction.followup.send(
            embed=discord.Embed(title=event["title"],description=event["description"],color=discord.Color.orange()),
            view=EventView(int(event_id),character_id,event["choices"]),
            ephemeral=True,
        )
    except Exception:
        return

class TravelView(discord.ui.View):
    def __init__(self,character_id):
        super().__init__(timeout=300)
        self.character_id=character_id
        options=[discord.SelectOption(label=x,value=x) for x in CITIES]
        self.select=discord.ui.Select(placeholder="Pilih kota tujuan",options=options)
        self.select.callback=self.travel
        self.add_item(self.select)
    async def travel(self,interaction):
        c=get_character(interaction.user.id,interaction.guild.id)
        if not c or c["id"]!=self.character_id:
            return await interaction.response.send_message("❌ Ini bukan karaktermu.",ephemeral=True)
        dest=self.select.values[0]
        if dest==c["city"]:
            return await interaction.response.send_message("❌ Kamu sudah berada di kota itu.",ephemeral=True)
        try:
            result=supabase.rpc("game_travel",{"p_character_id":self.character_id,"p_destination":dest}).execute().data
            row=result[0] if isinstance(result,list) else result
            await interaction.response.edit_message(content=f"🚆 Kamu sekarang berada di **{dest}**.\n💸 Biaya perjalanan: Rp75.000\n💵 Tunai: **{money(row['cash'])}**",view=None)
        except Exception as exc:
            await interaction.response.send_message("❌ "+_err(exc),ephemeral=True)

class ShopView(discord.ui.View):
    def __init__(self,character_id):
        super().__init__(timeout=300); self.character_id=character_id
        items=supabase.table("game_market").select("item_key,item_name,price,stock").order("item_name").limit(25).execute().data or []
        for item in items:
            label=str(item["item_name"])[:55]+" — "+money(item["price"])
            b=discord.ui.Button(label=label,style=discord.ButtonStyle.success)
            b.callback=self._make_callback(item["item_key"],item["item_name"])
            self.add_item(b)
        back=discord.ui.Button(label="Refresh Toko",emoji="🔄",style=discord.ButtonStyle.secondary)
        back.callback=self._refresh
        self.add_item(back)

    async def _refresh(self,interaction):
        c=get_character(interaction.user.id,interaction.guild.id)
        if not c or c["id"]!=self.character_id:
            return await interaction.response.send_message("❌ Ini bukan karaktermu.",ephemeral=True)
        await interaction.response.edit_message(embed=action_embed(c),view=ShopView(self.character_id))

    def _make_callback(self,key,name):
        async def callback(interaction):
            c=get_character(interaction.user.id,interaction.guild.id)
            if not c or c["id"]!=self.character_id:
                return await interaction.response.send_message("❌ Ini bukan karaktermu.",ephemeral=True)
            try:
                result=supabase.rpc("game_buy_market_item",{"p_character_id":self.character_id,"p_item_key":key,"p_quantity":1}).execute().data
                row=result[0] if isinstance(result,list) else result
                await interaction.response.send_message("🛍️ **"+str(name)+"** berhasil dibeli.\n💵 Tunai: **"+money(row["cash_after"])+"**",ephemeral=True)
            except Exception as exc:
                await interaction.response.send_message("❌ "+_err(exc),ephemeral=True)
        return callback

def action_embed(character):
    e=discord.Embed(title="🎮 Kehidupan",description="Pilih aktivitas. Semua perubahan kebutuhan dan uang diproses oleh engine database.",color=discord.Color.dark_red())
    e.add_field(name="Aktivitas",value="🍚 Makan • 💧 Minum • 😴 Istirahat\n📚 Belajar • 🚶 Jalan-jalan • 🗣️ Bersosialisasi",inline=False)
    e.add_field(name="🚆 Perjalanan",value="Pindah kota dengan biaya Rp75.000 dan memakai energi.",inline=False)
    e.add_field(name="🛍️ Toko",value="Beli kebutuhan sederhana dari inventaris.",inline=False)
    e.set_footer(text="Event kehidupan dapat muncul setelah aktivitas.")
    return e
