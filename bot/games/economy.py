import logging
from datetime import datetime, timezone
from discord.ext import commands, tasks
from ..database import supabase

log=logging.getLogger(__name__)

class Economy(commands.Cog):
    def __init__(self,bot):
        self.bot=bot
        self.tick.start()
    def cog_unload(self):
        self.tick.cancel()
    @tasks.loop(hours=1)
    async def tick(self):
        key=datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
        try:
            world=supabase.rpc("game_world_tick",{"p_tick_key":key}).execute().data
            ai=supabase.rpc("game_ai_autonomous_tick",{"p_tick_key":key+"-ai","p_limit":25}).execute().data
            law=supabase.rpc("game_run_law_tick",{"p_tick_key":key+"-law"}).execute().data
            government=supabase.rpc("game_run_government_tick",{"p_tick_key":key+"-government"}).execute().data
            city=supabase.rpc("game_run_city_simulation",{"p_tick_key":key+"-city"}).execute().data
            world_state=supabase.table("game_world_state").select("world_time").eq("id",1).limit(1).execute().data
            game_time=(world_state[0]["world_time"] if world_state else datetime.now(timezone.utc).isoformat())
            period_key=str(game_time)[:7]
            payroll=supabase.rpc("game_payroll_period",{"p_period_key":period_key}).execute().data
            business_payroll=supabase.rpc("game_close_business_finance",{"p_period_key":period_key}).execute().data
            r=supabase.rpc("game_run_economy_tick",{"p_tick_key":key}).execute().data
            log.info("WNI world tick: %s | autonomous AI: %s | law: %s | government: %s | city: %s | payroll: %s | business finance: %s | economy: %s",world,ai,law,government,city,payroll,business_payroll,r)
        except Exception:
            log.exception("WNI economy tick gagal")
    @tick.before_loop
    async def before_tick(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Economy(bot))
