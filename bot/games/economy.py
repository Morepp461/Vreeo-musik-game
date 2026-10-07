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
            ai=supabase.rpc("game_ai_life_tick",{"p_tick_key":key+"-ai"}).execute().data
            r=supabase.rpc("game_run_economy_tick",{"p_tick_key":key}).execute().data
            log.info("WNI world tick: %s | AI life: %s | economy: %s",world,ai,r)
        except Exception:
            log.exception("WNI economy tick gagal")
    @tick.before_loop
    async def before_tick(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Economy(bot))
