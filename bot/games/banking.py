import discord
from ..database import supabase
from .player import get_character, money, profile_embed

def bank_embed(character_id):
    a=supabase.table("game_bank_accounts").select("account_number,balance").eq("character_id",character_id).eq("status","active").limit(1).execute().data
    hist=supabase.table("game_credit_history").select("score_delta").eq("character_id",character_id).execute().data or []
    score=max(300,min(850,600+sum(int(x.get("score_delta") or 0) for x in hist)))
    e=discord.Embed(title="🏦 Bank WNI",description="Rekening, transfer, kredit, dan pinjaman.",color=discord.Color.blue())
    e.add_field(name="Rekening",value=("`"+str(a[0]["account_number"])+"`\nSaldo "+money(a[0]["balance"])) if a else "Belum memiliki rekening aktif.",inline=False)
    e.add_field(name="Credit Score",value=str(score),inline=True)
    loans=supabase.table("game_bank_loans").select("id,outstanding_principal,installment").eq("character_id",character_id).eq("status","active").limit(3).execute().data or []
    e.add_field(name="Pinjaman aktif",value="\n".join("#"+str(x["id"])+" • "+money(x["outstanding_principal"])+" • cicilan "+money(x["installment"]) for x in loans) if loans else "Tidak ada.",inline=False)
    return e


def finance_embed(character_id):
    row=supabase.table("game_personal_finance_snapshots").select("*").eq("character_id",character_id).order("created_at",desc=True).limit(1).execute().data
    e=discord.Embed(title="📊 Keuangan Pribadi",description="Aset, liabilitas, pemasukan, pengeluaran, dan net worth.",color=discord.Color.gold())
    if not row:
        e.description="Belum ada snapshot keuangan. Engine akan membuatnya otomatis."
        return e
    x=row[0]
    for key,label in [("income","Pemasukan"),("expenses","Pengeluaran"),("assets","Aset"),("liabilities","Liabilitas"),("net_worth","Net Worth")]:
        e.add_field(name=label,value=money(x.get(key)),inline=True)
    e.set_footer(text="Periode "+str(x.get("period_key","-")))
    return e

class FinanceButton(discord.ui.Button):
    def __init__(self,c): super().__init__(label="Keuangan",emoji="📊",style=discord.ButtonStyle.secondary); self.c=c
    async def callback(self,i):
        c=get_character(i.user.id,i.guild.id)
        if not c or c["id"]!=self.c: return await i.response.send_message("❌ Ini bukan dashboard karaktermu.",ephemeral=True)
        await i.response.edit_message(embed=finance_embed(self.c),view=BankView(self.c))

class BankOpenModal(discord.ui.Modal,title="🏦 Buka Rekening"):
    deposit=discord.ui.TextInput(label="Setoran awal",default="0",max_length=15)
    def __init__(self,c): super().__init__(); self.c=c
    async def on_submit(self,i):
        try:
            r=supabase.rpc("game_open_bank_account",{"p_character_id":self.c,"p_initial_deposit":int(str(self.deposit.value).strip() or "0")}).execute().data
            await i.response.edit_message(embed=bank_embed(self.c),view=BankView(self.c),content="✅ Rekening aktif.")
        except Exception as e: await i.response.send_message("❌ "+str(e)[:180],ephemeral=True)

class BankTransferModal(discord.ui.Modal,title="💸 Transfer Bank"):
    account=discord.ui.TextInput(label="Nomor rekening tujuan",max_length=20)
    amount=discord.ui.TextInput(label="Nominal",max_length=15)
    def __init__(self,c): super().__init__(); self.c=c
    async def on_submit(self,i):
        try:
            t=supabase.table("game_bank_accounts").select("id").eq("account_number",str(self.account.value).strip()).eq("status","active").limit(1).execute().data
            s=supabase.table("game_bank_accounts").select("id").eq("character_id",self.c).eq("status","active").limit(1).execute().data
            if not t or not s: raise ValueError("Rekening tidak ditemukan.")
            r=supabase.rpc("game_bank_transfer",{"p_from":s[0]["id"],"p_to":t[0]["id"],"p_amount":int(str(self.amount.value).strip()),"p_reference":"discord:"+str(i.user.id)}).execute().data
            row=r[0] if isinstance(r,list) else r
            await i.response.edit_message(embed=bank_embed(self.c),view=BankView(self.c),content="✅ Transfer berhasil. Saldo: "+money(row["from_balance"]))
        except Exception as e: await i.response.send_message("❌ "+str(e)[:180],ephemeral=True)

class BankLoanModal(discord.ui.Modal,title="💳 Ajukan Pinjaman"):
    amount=discord.ui.TextInput(label="Jumlah",max_length=15)
    term=discord.ui.TextInput(label="Tenor bulan",default="12",max_length=3)
    def __init__(self,c): super().__init__(); self.c=c
    async def on_submit(self,i):
        try:
            r=supabase.rpc("game_apply_bank_loan",{"p_character_id":self.c,"p_amount":int(str(self.amount.value).strip()),"p_term_months":int(str(self.term.value).strip())}).execute().data
            row=r[0] if isinstance(r,list) else r
            if row.get("status")!="approved": raise ValueError("Pinjaman ditolak. Credit Score: "+str(row.get("credit_score")))
            await i.response.edit_message(embed=bank_embed(self.c),view=BankView(self.c),content="✅ Pinjaman disetujui. Cicilan: "+money(row["installment"])+"/bulan")
        except Exception as e: await i.response.send_message("❌ "+str(e)[:180],ephemeral=True)

class BankRepayModal(discord.ui.Modal,title="💰 Bayar Pinjaman"):
    loan_id=discord.ui.TextInput(label="Loan ID",max_length=20)
    amount=discord.ui.TextInput(label="Nominal",required=False,max_length=15)
    def __init__(self,c): super().__init__(); self.c=c
    async def on_submit(self,i):
        try:
            p={"p_loan_id":int(str(self.loan_id.value).strip())}; v=str(self.amount.value).strip()
            if v: p["p_amount"]=int(v)
            r=supabase.rpc("game_repay_bank_loan",p).execute().data; row=r[0] if isinstance(r,list) else r
            await i.response.edit_message(embed=bank_embed(self.c),view=BankView(self.c),content="✅ Dibayar "+money(row["paid"])+" • Sisa "+money(row["remaining"]))
        except Exception as e: await i.response.send_message("❌ "+str(e)[:180],ephemeral=True)

class BankView(discord.ui.View):
    def __init__(self,c):
        super().__init__(timeout=300); self.c=c
        a=supabase.table("game_bank_accounts").select("id").eq("character_id",c).eq("status","active").limit(1).execute().data
        self.add_item(BankOpenButton(c) if not a else BankTransferButton(c))
        self.add_item(BankLoanButton(c)); self.add_item(BankRepayButton(c)); self.add_item(FinanceButton(c)); self.add_item(BankBackButton(c))

class BankOpenButton(discord.ui.Button):
    def __init__(self,c): super().__init__(label="Buka Rekening",emoji="🏦",style=discord.ButtonStyle.success); self.c=c
    async def callback(self,i): await i.response.send_modal(BankOpenModal(self.c))
class BankTransferButton(discord.ui.Button):
    def __init__(self,c): super().__init__(label="Transfer",emoji="💸",style=discord.ButtonStyle.primary); self.c=c
    async def callback(self,i): await i.response.send_modal(BankTransferModal(self.c))
class BankLoanButton(discord.ui.Button):
    def __init__(self,c): super().__init__(label="Pinjaman",emoji="💳",style=discord.ButtonStyle.primary); self.c=c
    async def callback(self,i): await i.response.send_modal(BankLoanModal(self.c))
class BankRepayButton(discord.ui.Button):
    def __init__(self,c): super().__init__(label="Bayar",emoji="💰",style=discord.ButtonStyle.success); self.c=c
    async def callback(self,i): await i.response.send_modal(BankRepayModal(self.c))
class BankBackButton(discord.ui.Button):
    def __init__(self,c): super().__init__(label="Kembali",emoji="↩️",style=discord.ButtonStyle.secondary); self.c=c
    async def callback(self,i):
        c=get_character(i.user.id,i.guild.id)
        if not c or c["id"]!=self.c: return await i.response.send_message("❌ Ini bukan dashboard karaktermu.",ephemeral=True)
        await i.response.edit_message(embed=profile_embed(c),view=__import__("bot.games.commands",fromlist=["PlayerView"]).PlayerView(c))
