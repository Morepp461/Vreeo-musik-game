import discord
from ..database import supabase

def news_embed():
    rows=supabase.table("game_news").select("title,body,category,published_at").order("published_at",desc=True).limit(8).execute().data or []
    e=discord.Embed(title="📰 Berita Indonesia",description="Peristiwa dunia simulasi terbaru.",color=discord.Color.dark_red())
    if not rows:e.description="Belum ada berita baru."
    for n in rows:
        loc=""
        e.add_field(name=f"{n['title']} — {n['category'].upper()}{loc}",value=n["body"][:900],inline=False)
    return e

class WorldView(discord.ui.View):
    def __init__(self,character_id):
        super().__init__(timeout=300);self.character_id=character_id
    @discord.ui.button(label="Berita",emoji="📰",style=discord.ButtonStyle.primary)
    async def news(self,i,b):
        await i.response.edit_message(embed=news_embed(),view=self)
    @discord.ui.button(label="Hubungan AI",emoji="❤️",style=discord.ButtonStyle.danger)
    async def relations(self,i,b):
        rows=supabase.table("game_relationships").select("character_a,character_b,relation_type,affinity").order("updated_at",desc=True).limit(8).execute().data or []
        e=discord.Embed(title="❤️ Hubungan Dunia",description="Jaringan sosial AI yang berkembang secara dinamis.",color=discord.Color.magenta())
        if not rows:e.description="Belum ada hubungan yang terbentuk."
        for r in rows:
            a=supabase.table("game_ai_characters").select("name").eq("id",r["character_a"]).limit(1).execute().data
            b2=supabase.table("game_ai_characters").select("name").eq("id",r["character_b"]).limit(1).execute().data
            an=a[0]["name"] if a else "Unknown";bn=b2[0]["name"] if b2 else "Unknown"
            e.add_field(name=f"{an} ↔ {bn}",value=f"{r['relation_type']} • affinity {r['affinity']}",inline=False)
        await i.response.edit_message(embed=e,view=self)
    @discord.ui.button(label="Aktivitas AI", emoji="🤖", style=discord.ButtonStyle.secondary, row=1)
    async def ai_activity(self,i,b):
        rows=supabase.table("game_ai_life_events").select("event_type,description,city,occurred_at,character_id").order("occurred_at",desc=True).limit(8).execute().data or []
        e=discord.Embed(title="🤖 Kehidupan AI",description="Aktivitas terbaru masyarakat AI.",color=discord.Color.blurple())
        if not rows:
            e.description="Belum ada aktivitas AI."
        for r in rows:
            a=supabase.table("game_ai_characters").select("name").eq("id",r["character_id"]).limit(1).execute().data
            name=a[0]["name"] if a else "Unknown"
            e.add_field(name=f"{name} • {r['event_type']}",value=f"{r['description']}\n📍 {r.get('city') or 'Tidak diketahui'}",inline=False)
        await i.response.edit_message(embed=e,view=self)

    @discord.ui.button(label="Kembali",emoji="↩️",style=discord.ButtonStyle.secondary,row=1)
    async def back(self,i,b):
        from .player import get_character,profile_embed
        from .commands import PlayerView
        c=get_character(i.user.id,i.guild.id)
        if not c or c["id"]!=self.character_id:return await i.response.send_message("❌ Ini bukan dashboard karaktermu.",ephemeral=True)
        await i.response.edit_message(embed=profile_embed(c),view=PlayerView(c))
