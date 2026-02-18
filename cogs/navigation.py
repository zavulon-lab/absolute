# cogs/navigation.py

import disnake
from disnake import Embed
from disnake.ext import commands
from datetime import datetime

try:
    from constants import (
        NAVIGATION_ADMIN_ID,
        NAVIGATION_USER_ID,
        APPLICATION_ADMIN_PANEL_ID,
        GIVEAWAY_ADMIN_CHANNEL_ID,
        ADMIN_MANAGEMENT_CHANNEL_ID,
        ACTIVITY_MONITOR_CHANNEL_ID,
        PROTECTION_ADMIN_CHANNEL_ID,
        EVENTS_ADMIN_CHANNEL_ID,
        NEWS,
        EVENTS_CHANNEL_ID,
        GIVEAWAY_USER_CHANNEL_ID,
        RAZBOR,
        PERSONAL_CHANNEL_REQUEST_ID,
        ACADEMY_REQUEST_CHANNEL_ID,
        VERIFICATION_NOTIFICATION_CHANNEL_ID,
    )
except ImportError as e:
    print(f"[NAVIGATION] Ошибка импорта констант: {e}")


# ========== ЭМБЕД АДМИНСКОЙ НАВИГАЦИИ ==========

def build_admin_nav_embed(guild: disnake.Guild) -> Embed:
    def ch(channel_id: int) -> str:
        c = guild.get_channel(channel_id)
        return c.mention if c else f"`#{channel_id}`"

    embed = Embed(
        title="<:freeiconobjective6020418:1473756846568243264> Панель Администратора",
        description="Быстрый доступ ко всем административным разделам сервера.",
        color=disnake.Color.from_rgb(54, 57, 63),
        timestamp=datetime.now(),
    )

    embed.add_field(
        name="<:freeiconinferentialstatistics248:1473400670101962913> Заявки",
        value=f"> {ch(APPLICATION_ADMIN_PANEL_ID)}\n> Управление формой заявок, приём и отклонение.",
        inline=False,
    )
    embed.add_field(
        name="<:freeiconproofing10988140:1473391799321104485> Мониторинг сотрудников",
        value=f"> {ch(ACTIVITY_MONITOR_CHANNEL_ID)}\n> Активность рекрутёров и чит-хантеров.",
        inline=False,
    )
    embed.add_field(
        name="<:freeiconserver12869272:1473431594021949633> Активная защита",
        value=f"> {ch(PROTECTION_ADMIN_CHANNEL_ID)}\n> Настройка системы защиты сервера.",
        inline=False,
    )
    embed.add_field(
        name="<:freeicondice2102161:1473432878841856021> Розыгрыши",
        value=f"> {ch(GIVEAWAY_ADMIN_CHANNEL_ID)}\n> Создание и управление розыгрышами.",
        inline=False,
    )
    embed.add_field(
        name="<:freeicondocuments1548205:1473390852234543246> Ветки МП",
        value=f"> {ch(ADMIN_MANAGEMENT_CHANNEL_ID)}\n> Создание веток личных переписок.",
        inline=False,
    )
    embed.add_field(
        name="<:freeiconinvitation7515655:1473373288724959285> Мероприятия",
        value=f"> {ch(EVENTS_ADMIN_CHANNEL_ID)}\n> Создание плюсов и управление ивентами.",
        inline=False,
    )

    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)

    embed.set_footer(text="Absolute Famq")
    return embed


# ========== ЭМБЕД ПОЛЬЗОВАТЕЛЬСКОЙ НАВИГАЦИИ ==========

def build_user_nav_embed(guild: disnake.Guild) -> Embed:
    def ch(channel_id: int) -> str:
        c = guild.get_channel(channel_id)
        return c.mention if c else f"`#{channel_id}`"

    embed = Embed(
        title="<:freeiconobjective6020418:1473756846568243264> Навигация по серверу",
        description="Все важные разделы сервера в одном месте.",
        color=disnake.Color.from_rgb(54, 57, 63),
        timestamp=datetime.now(),
    )

    embed.add_field(
        name="📰 Новости",
        value=f"> {ch(NEWS)}\n> Последние новости и объявления сервера.",
        inline=False,
    )
    embed.add_field(
        name="<:freeiconinvitation7515655:1473373288724959285> Мероприятия",
        value=f"> {ch(EVENTS_CHANNEL_ID)}\n> Участвуй в ивентах — отмечайся плюсом.",
        inline=False,
    )
    embed.add_field(
        name="<:freeicondice2102161:1473432878841856021> Розыгрыши",
        value=f"> {ch(GIVEAWAY_USER_CHANNEL_ID)}\n> Участвуй в розыгрышах и выигрывай призы.",
        inline=False,
    )
    embed.add_field(
        name="<:freeiconwarning3756712:1473429407980064788> Разбор ошибок МП",
        value=f"> {ch(RAZBOR)}\n> Разбор ситуаций и ошибок в личных переписках.",
        inline=False,
    )
    embed.add_field(
        name="<:freeicondocuments1548205:1473390852234543246> Функционал бота",
        value=f"> {ch(PERSONAL_CHANNEL_REQUEST_ID)}\n> Взаимодействие с возможностями бота.",
        inline=False,
    )
    embed.add_field(
        name="<:freeiconsermon7515746:1473373077818573012> Повышение",
        value=f"> {ch(ACADEMY_REQUEST_CHANNEL_ID)}\n> Подай запрос на повышение между рангами.",
        inline=False,
    )
    embed.add_field(
        name="<:freeiconwarning3756712:1473429407980064788> Вызов на проверку",
        value=f"> {ch(VERIFICATION_NOTIFICATION_CHANNEL_ID)}\n> Уведомления о вызове на проверку ПО.",
        inline=False,
    )

    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)

    embed.set_footer(text="Absolute Famq")
    return embed


# ========== COG ==========

class NavigationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        await self._update_or_create(
            channel_id=NAVIGATION_ADMIN_ID,
            build_fn=build_admin_nav_embed,
            label="ADMIN",
        )
        await self._update_or_create(
            channel_id=NAVIGATION_USER_ID,
            build_fn=build_user_nav_embed,
            label="USER",
        )

    async def _update_or_create(self, channel_id: int, build_fn, label: str):
        channel = self.bot.get_channel(channel_id)
        if not channel:
            print(f"[NAVIGATION] {label}: канал {channel_id} не найден.")
            return

        embed = build_fn(channel.guild)

        async for msg in channel.history(limit=10):
            if msg.author == self.bot.user:
                try:
                    await msg.edit(embed=embed)
                    print(f"[NAVIGATION] {label}: навигация обновлена.")
                except Exception as e:
                    print(f"[NAVIGATION] {label}: ошибка обновления — {e}")
                return

        try:
            await channel.purge(limit=10)
            await channel.send(embed=embed)
            print(f"[NAVIGATION] {label}: навигация создана.")
        except Exception as e:
            print(f"[NAVIGATION] {label}: ошибка создания — {e}")

    @commands.command(name="nav_update")
    @commands.has_permissions(administrator=True)
    async def nav_update(self, ctx):
        """Принудительно обновляет оба канала навигации."""
        await self._update_or_create(NAVIGATION_ADMIN_ID, build_admin_nav_embed, "ADMIN")
        await self._update_or_create(NAVIGATION_USER_ID,  build_user_nav_embed,  "USER")
        await ctx.message.delete()
        await ctx.send(" Навигация обновлена.", delete_after=5)


def setup(bot):
    bot.add_cog(NavigationCog(bot))
