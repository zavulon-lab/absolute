from disnake.ext import commands, tasks
from datetime import datetime
import random

from .config import *
from .database import save_giveaway_data, load_all_active_giveaways
from .embeds import (
    create_giveaway_embed,
    create_admin_panel_embed,
    create_winner_dm_embed,
    create_log_embed
)
from .views import GiveawayAdminPanel, GiveawayJoinView


class GiveawayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        # Регистрируем View для всех активных розыгрышей
        for gw in load_all_active_giveaways():
            self.bot.add_view(GiveawayJoinView(gw["id"]))
            print(f"[GIVEAWAY] Восстановлен View: {gw['id']}")

        try:
            channel = self.bot.get_channel(GIVEAWAY_ADMIN_CHANNEL_ID)
            if channel:
                try:
                    await channel.purge(limit=10)
                except Exception:
                    pass
                embed = create_admin_panel_embed(self.bot.user)
                await channel.send(embed=embed, view=GiveawayAdminPanel())
                print("[GIVEAWAY] Админ-панель обновлена.")
        except Exception as e:
            print(f"[GIVEAWAY] Ошибка панели: {e}")

    @tasks.loop(minutes=1)
    async def check_giveaways(self):
        for data in load_all_active_giveaways():
            try:
                end_dt = datetime.strptime(data["end_time"], "%Y-%m-%d %H:%M")
                if datetime.now() >= end_dt:
                    guild = self.bot.get_guild(data["guild_id"])
                    if guild:
                        await self.finish_giveaway(data, guild)
            except Exception as e:
                print(f"[GIVEAWAY] Timer error ({data.get('id')}): {e}")

    async def finish_giveaway(self, data: dict, guild):
        participants = data.get("participants", [])
        count = data.get("winner_count", 1)
        preselected = data.get("preselected_winners", [])

        winners = list(dict.fromkeys(preselected))
        needed = count - len(winners)
        if needed > 0:
            pool = [p for p in participants if p not in winners]
            winners.extend(random.sample(pool, min(needed, len(pool))))

        data["status"] = "finished"
        data["winners"] = winners
        data["participants"] = []
        data["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_giveaway_data(data)

        try:
            chan = guild.get_channel(GIVEAWAY_USER_CHANNEL_ID)
            if chan and data.get("fixed_message_id"):
                try:
                    msg = await chan.fetch_message(data["fixed_message_id"])
                    embed = create_giveaway_embed(data, self.bot.user)
                    embed.title = "РОЗЫГРЫШ ЗАВЕРШЁН"
                    embed.color = AUX_COLOR
                    w_list = (
                        ", ".join([f"<@{uid}>" for uid in winners])
                        if winners else "Нет победителей"
                    )
                    embed.add_field(
                        name=f"{EMOJI_LAUREL} Победители",
                        value=w_list,
                        inline=False
                    )
                    await msg.edit(embed=embed, view=None)
                except Exception:
                    print(f"[GIVEAWAY] Сообщение розыгрыша {data['id']} удалено, пропускаем edit.")

                for uid in winners:
                    try:
                        member = guild.get_member(uid)
                        if member:
                            await member.send(embed=create_winner_dm_embed(
                                data["prize"], data["sponsor"], self.bot.user
                            ))
                    except Exception:
                        pass
        except Exception as e:
            print(f"[GIVEAWAY] Ошибка завершения ({data.get('id')}): {e}")

        log_chan = guild.get_channel(GIVEAWAY_LOG_CHANNEL_ID)
        if log_chan:
            await log_chan.send(embed=create_log_embed(
                "Итоги розыгрыша", data["prize"], winners
            ))


def setup(bot):
    bot.add_cog(GiveawayCog(bot))
