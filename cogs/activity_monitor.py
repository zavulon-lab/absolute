# cogs/activity_monitor.py

import disnake
from disnake import Embed, ButtonStyle, SelectOption
from disnake.ui import View, Button, Select
from disnake.ext import commands
from datetime import datetime

# Импортируем константы
try:
    from constants import (
        ACTIVITY_MONITOR_CHANNEL_ID, 
        CHEAT_HUNTER_ROLE_ID,
        RECRUITER_ROLE_ID 
    )
except ImportError:
    # Заглушки, если файл constants.py не найден или неполный
    ACTIVITY_MONITOR_CHANNEL_ID = 0
    CHEAT_HUNTER_ROLE_ID = 0
    RECRUITER_ROLE_ID = 0

from database import get_all_staff_stats, get_staff_stats

# ========== ГЛАВНОЕ МЕНЮ (VIEW) ==========
class MainMonitorView(View):
    def __init__(self):
        super().__init__(timeout=None) # Персистентное меню

    @disnake.ui.button(label="Рекрутеры", style=ButtonStyle.primary, custom_id="monitor_recruiters", emoji="<:freeiconrecruiter7250697:1473386162566598756>")
    async def recruiters_btn(self, button: Button, interaction: disnake.Interaction):
        if not interaction.guild:
            return
        await show_department_stats(interaction, interaction.guild, "recruiters")

    @disnake.ui.button(label="Чит-хантеры", style=ButtonStyle.danger, custom_id="monitor_hunters", emoji="<:freeiconman901851:1473401185611288658>")
    async def hunters_btn(self, button: Button, interaction: disnake.Interaction):
        if not interaction.guild:
            return
        await show_department_stats(interaction, interaction.guild, "hunters")

    @disnake.ui.button(label="Обновить", style=ButtonStyle.secondary, custom_id="monitor_refresh", emoji="<:freeiconrefreshdata12388402:1473401657063899289>")
    async def refresh_btn(self, button: Button, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True)
        if interaction.message:
            embed = await generate_main_embed(interaction.guild)
            await interaction.message.edit(embed=embed, view=self)
            await interaction.followup.send("Данные обновлены.", ephemeral=True)


# ========== МЕНЮ ОТДЕЛА (VIEW) ==========
class DepartmentView(View):
    def __init__(self, guild, staff_list, dept_type, pages, current_page=0):
        super().__init__(timeout=180)
        self.guild = guild
        self.staff_list = staff_list 
        self.dept_type = dept_type
        self.pages = pages
        self.current_page = current_page
        
        self.update_components()

    def update_components(self):
        self.clear_items()
        
        # 1. Навигация
        btn_prev = Button(label="◀", style=ButtonStyle.secondary, custom_id="prev", disabled=(self.current_page == 0))
        btn_prev.callback = self.prev_callback
        self.add_item(btn_prev)

        btn_ind = Button(label=f"{self.current_page + 1}/{len(self.pages)}", style=ButtonStyle.secondary, disabled=True)
        self.add_item(btn_ind)

        btn_next = Button(label="▶", style=ButtonStyle.secondary, custom_id="next", disabled=(self.current_page >= len(self.pages) - 1))
        btn_next.callback = self.next_callback
        self.add_item(btn_next)

        # 2. Выбор сотрудника (Топ-25 для селекта)
        options = []
        for data in self.staff_list[:25]:
            member = data['member']
            stats = data['stats']
            options.append(SelectOption(
                label=member.display_name[:25],
                value=str(member.id),
                description=f"Всего: {stats['total']} |  {stats['accepts']}",
                emoji="<:freeiconboss265674:1473388753111220357>"
            ))
        
        if not options:
            options.append(SelectOption(label="Нет сотрудников", value="none"))

        select = Select(placeholder=" Подробная статистика...", options=options, custom_id="staff_select", row=1)
        select.callback = self.select_callback
        self.add_item(select)

        # 3. Кнопка "Домой"
        btn_back = Button(label=" В главное меню", emoji="<:freeicontinyhouse4661011:1473402148703440956>", style=ButtonStyle.success, row=2)
        btn_back.callback = self.home_callback
        self.add_item(btn_back)

    async def prev_callback(self, interaction: disnake.Interaction):
        self.current_page -= 1
        self.update_components()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    async def next_callback(self, interaction: disnake.Interaction):
        self.current_page += 1
        self.update_components()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    async def home_callback(self, interaction: disnake.Interaction):
        embed = await generate_main_embed(self.guild)
        view = MainMonitorView()
        await interaction.response.edit_message(embed=embed, view=view)

    async def select_callback(self, interaction: disnake.Interaction):
        val = interaction.data['values'][0]
        if val == "none":
            await interaction.response.send_message("Пусто...", ephemeral=True)
            return

        staff_id = int(val)
        member = self.guild.get_member(staff_id)
        
        if not member:
            await interaction.response.send_message("Сотрудник не найден (возможно вышел).", ephemeral=True)
            return
            
        # Личный эмбед
        stats = get_staff_stats(self.guild.id, staff_id, 30)
        
        embed = Embed(
            title=f"<:freeiconboss265674:1473388753111220357> Досье: {member.display_name}",
            description="Подробная статистика за **30 дней**",
            color=0x2B2D31
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        info = (
            f"**Всего действий:** `{stats['total']}`\n"
            f"────────────────\n"
            f"<:tick:1473380953245221016> Принято: **{stats['accepts']}**\n"
            f"<:cross:1473380950770716836> Отклонено: **{stats['denies']}**\n"
            f"<:call:1473378348863586304> Обзвонов: **{stats['calls']}**\n"
            f"<:__:1473379222432256083> Чатов создано: **{stats['chats']}**\n"
            f"<:ddd:1473378828427460618> Рассмотрений: **{stats['reviews']}**\n"
            f"────────────────\n"
            f"<:freeiconfasttime4285622:1473402456309498039> Последняя активность:\n{stats['last_action_time'] or 'Нет данных'}"
        )
        
        embed.add_field(name="Сводка активности", value=info)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ========== ЛОГИКА ГЕНЕРАЦИИ ==========

async def get_dept_data(guild, role_id):
    """Безопасное получение данных отдела по Role ID"""
    role = guild.get_role(role_id)
    if not role: 
        return [], 0
        
    # Фильтруем участников именно по этой роли
    members = [m for m in role.members if not m.bot]
    if not members:
        return [], 0
        
    stats_list = get_all_staff_stats(guild.id, members, 7)
    total_actions = sum(s['stats']['total'] for s in stats_list)
    return stats_list, total_actions

async def generate_main_embed(guild):
    """Генерирует главный экран (Сводка)"""
    # Получаем данные раздельно
    rec_stats, rec_total = await get_dept_data(guild, RECRUITER_ROLE_ID)
    hunt_stats, hunt_total = await get_dept_data(guild, CHEAT_HUNTER_ROLE_ID)
    
    embed = Embed(
        title="<:freeiconinferentialstatistics248:1473400670101962913> Центр Мониторинга Персонала",
        description="Сводная статистика активности за **7 дней**.\nВыберите отдел для просмотра деталей.",
        color=disnake.Color.from_rgb(54, 57, 63),
        timestamp=datetime.now()
    )
    
    # Блок Рекрутеров
    top_rec = rec_stats[0]['member'].display_name if rec_stats else "—"
    embed.add_field(
        name=f"<:freeiconrecruiter7250697:1473386162566598756> Рекрутеры",
        value=f"> Сотрудников: `{len(rec_stats)}`\n> Действий: `{rec_total}`\n> <:freeiconwheat12027423:1473405222683545641> Топ: **{top_rec}**",
        inline=True
    )
    
    # Блок Чит-хантеров
    top_hunt = hunt_stats[0]['member'].display_name if hunt_stats else "—"
    embed.add_field(
        name=f"<:freeiconman901851:1473401185611288658> Чит-хантеры",
        value=f"> Сотрудников: `{len(hunt_stats)}`\n> Действий: `{hunt_total}`\n> <:freeiconwheat12027423:1473405222683545641> Топ: **{top_hunt}**",
        inline=True
    )
    
    if guild.icon:
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1462165491278938204/1473404890976878806/free-icon-monitoring-6186365.png")
    embed.set_footer(text="Absolute Famq")
    
    return embed

async def show_department_stats(interaction, guild, dept_type):
    """Показывает статистику конкретного отдела"""
    
    # Определяем, какую роль сканировать
    if dept_type == "recruiters":
        role_id = RECRUITER_ROLE_ID
        title = "<:freeiconproofing10988140:1473391799321104485> Отдел Рекрутинга"
        color = disnake.Color.from_rgb(54, 57, 63)
    else:
        role_id = CHEAT_HUNTER_ROLE_ID
        title = "<:freeiconman901851:1473401185611288658> Отдел Чит-хантеров"
        color = disnake.Color.from_rgb(54, 57, 63)
    
    stats_list, _ = await get_dept_data(guild, role_id)
    
    if not stats_list:
        await interaction.response.send_message(
            "В этом отделе пока нет данных или активных сотрудников.", 
            ephemeral=True
        )
        return

    await interaction.response.defer()
    
    # Пагинация
    pages = []
    items_per_page = 5
    
    for i in range(0, len(stats_list), items_per_page):
        chunk = stats_list[i:i + items_per_page]
        
        embed = Embed(
            title=title, 
            description=f"Активность за **7 дней**", 
            color=color
        )
        embed.set_footer(text=f"Страница {(i // items_per_page) + 1} из {(len(stats_list) - 1) // items_per_page + 1} • Absolute Famq")
        
        for idx, data in enumerate(chunk, start=i+1):
            m = data['member']
            s = data['stats']
            
            medal = "<:freeicon1stprize11166526:1473405841444179968>" if idx == 1 else "<:freeicon2ndplace11166528:1473405840219177204>" if idx == 2 else "<:freeicon3rdplace11166530:1473405838625472656>" if idx == 3 else f"`{idx}.`"
            
            val = (
                f"Всего: **{s['total']}** "
                f"(<:tick:1473380953245221016>{s['accepts']} <:cross:1473380950770716836>{s['denies']} <:call:1473378348863586304>{s['calls']})\n"
                f"<:freeiconfasttime4285622:1473402456309498039> {s['last_action_time'] or '—'}"
            )
            embed.add_field(name=f"{medal} {m.display_name}", value=val, inline=False)
        
        pages.append(embed)
        
    view = DepartmentView(guild, stats_list, dept_type, pages)
    await interaction.edit_original_response(embed=pages[0], view=view)


# ========== COG ==========
class ActivityMonitorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Автоматическое обновление панели при запуске"""
        self.bot.add_view(MainMonitorView())
        
        if not ACTIVITY_MONITOR_CHANNEL_ID:
            return

        channel = self.bot.get_channel(ACTIVITY_MONITOR_CHANNEL_ID)
        if not channel: return

        # Ищем существующее сообщение бота
        found = False
        async for msg in channel.history(limit=5):
            if msg.author == self.bot.user:
                try:
                    embed = await generate_main_embed(channel.guild)
                    await msg.edit(embed=embed, view=MainMonitorView())
                    found = True
                    print("[ActivityMonitor] Панель обновлена.")
                    break
                except Exception as e:
                    print(f"[Error] Не удалось обновить панель: {e}")
        
        if not found:
            await channel.purge(limit=5)
            embed = await generate_main_embed(channel.guild)
            await channel.send(embed=embed, view=MainMonitorView())
            print("[ActivityMonitor] Панель создана.")

def setup(bot):
    bot.add_cog(ActivityMonitorCog(bot))
