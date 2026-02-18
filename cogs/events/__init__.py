from disnake.ext import commands

from .database import init_events_db, get_current_event
from .embeds import generate_admin_embeds
from .views import MainAdminView, EventUserView
from .config import EVENTS_ADMIN_CHANNEL_ID

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        init_events_db()

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.wait_until_ready()
        try:
            self.bot.add_view(MainAdminView())
            current = get_current_event()
            if current:
                self.bot.add_view(EventUserView(current["id"]))
            
            chan = self.bot.get_channel(EVENTS_ADMIN_CHANNEL_ID)
            if chan:
                panel_msg = None
                async for msg in chan.history(limit=10):
                    if msg.author == self.bot.user and msg.components:
                         try:
                             if msg.components[0].children[0].custom_id == "start_reg_btn":
                                 panel_msg = msg
                                 break
                         except: 
                             pass
                
                embeds = generate_admin_embeds(current, bot=self.bot)
                if panel_msg:
                    await panel_msg.edit(embeds=embeds, view=MainAdminView())
                else:
                    await chan.send(embeds=embeds, view=MainAdminView())
        except Exception as e:
            print(f"[EVENTS] Error: {e}")

    @commands.command(name="event")
    @commands.has_permissions(administrator=True)
    async def event_panel(self, ctx):
        await ctx.message.delete()
        await ctx.send(embeds=generate_admin_embeds(None, bot=self.bot), view=MainAdminView())

def setup(bot):
    bot.add_cog(EventsCog(bot))
