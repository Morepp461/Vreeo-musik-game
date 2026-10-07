import logging
from datetime import datetime, timezone
from discord.ext import commands, tasks
from ..database import supabase
from .world import reconcile_companies

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
            city_government=supabase.rpc("game_run_city_government_tick",{"p_tick_key":key+"-citygov"}).execute().data
            city=supabase.rpc("game_run_city_simulation",{"p_tick_key":key+"-city"}).execute().data
            health=supabase.rpc("game_run_health_tick",{"p_tick_key":key+"-health"}).execute().data
            quests=supabase.rpc("game_run_job_quest_tick",{"p_tick_key":key+"-career"}).execute().data
            relationships=supabase.rpc("game_update_player_relationship_distance").execute().data
            social=supabase.rpc("game_run_social_control_tick",{"p_tick_key":key+"-social"}).execute().data
            world_state=supabase.table("game_world_state").select("world_time").eq("id",1).limit(1).execute().data
            game_time=(world_state[0]["world_time"] if world_state else datetime.now(timezone.utc).isoformat())
            period_key=str(game_time)[:7]
            city_economy=supabase.rpc("game_run_city_economy_tick",{"p_period_key":period_key}).execute().data
            personal_finance=supabase.rpc("game_snapshot_personal_finance",{"p_period_key":period_key}).execute().data
            payroll=supabase.rpc("game_payroll_period",{"p_period_key":period_key}).execute().data
            business_payroll=supabase.rpc("game_close_business_finance",{"p_period_key":period_key}).execute().data
            for guild in self.bot.guilds:
                try: await reconcile_companies(guild)
                except Exception: log.exception("WNI company reconciliation gagal untuk guild %s",guild.id)
            r=supabase.rpc("game_run_economy_tick",{"p_tick_key":key}).execute().data
            log.info("WNI world tick: %s | autonomous AI: %s | law: %s | government: %s | city government: %s | city: %s | health: %s | career quests: %s | relationships: %s | social control: %s | payroll: %s | business finance: %s | economy: %s",world,ai,law,government,city_government,city,health,quests,relationships,social,payroll,business_payroll,r)
        except Exception:
            log.exception("WNI economy tick gagal")
    @tick.before_loop
    async def before_tick(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Economy(bot))
