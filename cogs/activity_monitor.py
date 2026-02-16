# cogs/activity_monitor.py

import disnake
from disnake import Embed, ButtonStyle, SelectOption
from disnake.ui import View, Button, Select
from disnake.ext import commands
from datetime import datetime

# Импортируем константы (убедитесь, что они есть в constants.py)
from constants import (
    ACTIVITY_MONITOR_CHANNEL_ID, 
    CHEAT_HUNTER_ROLE_ID,
    RECRUITER_ROLE_ID 
)

# ЗАГЛУШКА НА СЛУЧАЙ ЕСЛИ НЕТ КОНСТАНТЫ (удалите, если добавили в constants.py)
try:
    from constants import RECRUITER_ROLE_ID
except ImportError:
    RECRUITER_ROLE_ID = 0  # Замените на реальный ID, если не используете constants.py

from database import get_all_staff_stats, get_staff_stats


# ========== ГЛАВНОЕ МЕНЮ (VIEW) ==========
class MainMonitorView(View):
    def __init__(self):
        super().__init__(timeout=None) # Персистентное меню

    @disnake.ui.button(label="📊 Рекрутеры", style=ButtonStyle.primary, custom_id="monitor_recruiters", emoji="📝")
    async def recruiters_btn(self, button: Button, interaction: disnake.Interaction):
        # Берем guild из interaction, чтобы работало даже после перезапуска бота
        if not interaction.guild:
            return
        await show_department_stats(interaction, interaction.guild, "recruiters")

    @disnake.ui.button(label="🛡️ Чит-хантеры", style=ButtonStyle.danger, custom_id="monitor_hunters", emoji="⚔️")
    async def hunters_btn(self, button: Button, interaction: disnake.Interaction):
        if not interaction.guild:
            return
        await show_department_stats(interaction, interaction.guild, "hunters")

    @disnake.ui.button(label="🔄 Обновить", style=ButtonStyle.secondary, custom_id="monitor_refresh", emoji="🔄")
    async def refresh_btn(self, button: Button, interaction: disnake.Interaction):
        await interaction.response.defer(ephemeral=True) # Скрытый ответ, чтобы не спамить
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
        
        # Сборка интерфейса
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

        # 2. Выбор сотрудника
        options = []
        # Берем срез сотрудников для текущей страницы (или топ-25)
        # Для селекта лучше брать топ-25 из всего списка, чтобы не терялись
        for data in self.staff_list[:25]:
            member = data['member']
            stats = data['stats']
            options.append(SelectOption(
                label=member.display_name[:25],
                value=str(member.id),
                description=f"Всего: {stats['total']} | ✅ {stats['accepts']}",
                emoji="👤"
            ))
        
        if not options:
            options.append(SelectOption(label="Нет сотрудников", value="none"))

        select = Select(placeholder="🔍 Подробная статистика...", options=options, custom_id="staff_select", row=1)
        select.callback = self.select_callback
        self.add_item(select)

        # 3. Кнопка "Домой"
        btn_back = Button(label="🏠 В главное меню", style=ButtonStyle.success, row=2)
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
        # Возвращаем главное меню
        embed = await generate_main_embed(self.guild)
        view = MainMonitorView() # Создаем новое вью главного меню
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
            
        # Генерируем личный эмбед (статистика за 30 дней)
        stats = get_staff_stats(self.guild.id, staff_id, 30)
        
        embed = Embed(
            title=f"👤 Досье: {member.display_name}",
            description="Подробная статистика за **30 дней**",
            color=0x2B2D31
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # Формируем красивый список
        info = (
            f"**Всего действий:** `{stats['total']}`\n"
            f"────────────────\n"
            f"<:tik:1472654073814581268> Принято: **{stats['accepts']}**\n"
            f"<:cross:1472654174788255996> Отклонено: **{stats['denies']}**\n"
            f"📞 Обзвонов: **{stats['calls']}**\n"
            f"💬 Чатов создано: **{stats['chats']}**\n"
            f"👀 Рассмотрений: **{stats['reviews']}**\n"
            f"────────────────\n"
            f"🕒 Последняя активность:\n{stats['last_action_time'] or 'Нет данных'}"
        )
        
        embed.add_field(name="Сводка активности", value=info)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ========== ЛОГИКА ГЕНЕРАЦИИ ==========

async def get_dept_data(guild, role_id):
    """Безопасное получение данных отдела"""
    role = guild.get_role(role_id)
    if not role: 
        return [], 0 # Если роли нет, возвращаем пустоту
        
    members = [m for m in role.members if not m.bot]
    if not members:
        return [], 0
        
    stats_list = get_all_staff_stats(guild.id, members, 7)
    total_actions = sum(s['stats']['total'] for s in stats_list)
    return stats_list, total_actions

async def generate_main_embed(guild):
    """Генерирует главный экран"""
    rec_stats, rec_total = await get_dept_data(guild, RECRUITER_ROLE_ID)
    hunt_stats, hunt_total = await get_dept_data(guild, CHEAT_HUNTER_ROLE_ID)
    
    embed = Embed(
        title="<:freeiconstatistics7026486:1472676834167234631> Центр Мониторинга Персонала",
        description="Сводная статистика активности за **7 дней**.\nВыберите отдел для просмотра деталей.",
        color=0x2B2D31,
        timestamp=datetime.now()
    )
    
    # Блок Рекрутеров
    top_rec = rec_stats[0]['member'].display_name if rec_stats else "—"
    embed.add_field(
        name=f"📝 Рекрутеры",
        value=f"> Сотрудников: `{len(rec_stats)}`\n> Действий: `{rec_total}`\n> 🔥 Топ: **{top_rec}**",
        inline=True
    )
    
    # Блок Чит-хантеров
    top_hunt = hunt_stats[0]['member'].display_name if hunt_stats else "—"
    embed.add_field(
        name=f"⚔️ Чит-хантеры",
        value=f"> Сотрудников: `{len(hunt_stats)}`\n> Действий: `{hunt_total}`\n> 🔥 Топ: **{top_hunt}**",
        inline=True
    )
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text="Calogero Famq System")
    
    return embed

async def show_department_stats(interaction, guild, dept_type):
    """Показывает статистику конкретного отдела с пагинацией"""
    
    # Сначала проверим данные, НЕ трогая сообщение
    role_id = RECRUITER_ROLE_ID if dept_type == "recruiters" else CHEAT_HUNTER_ROLE_ID
    
    stats_list, _ = await get_dept_data(guild, role_id)
    
    # 1. ЕСЛИ ПУСТО -> Шлем скрытое сообщение и ВЫХОДИМ
    if not stats_list:
        await interaction.response.send_message(
            "❌ В этом отделе пока нет данных или активных сотрудников.", 
            ephemeral=True
        )
        return

    # 2. ЕСЛИ ДАННЫЕ ЕСТЬ -> Только теперь редактируем сообщение
    await interaction.response.defer() # Говорим дискорду "сейчас обновлю"
    
    title = "<:freeiconstatistics7026486:1472676834167234631> Отдел Рекрутинга" if dept_type == "recruiters" else "🛡️ Отдел Чит-хантеров"
    color = 0x5865F2 if dept_type == "recruiters" else 0xED4245
    
    # Разбиваем на страницы
    pages = []
    items_per_page = 5
    
    for i in range(0, len(stats_list), items_per_page):
        chunk = stats_list[i:i + items_per_page]
        
        embed = Embed(
            title=title, 
            description=f"Активность за **7 дней**", 
            color=color
        )
        embed.set_footer(text=f"Страница {(i // items_per_page) + 1} из {(len(stats_list) - 1) // items_per_page + 1} • Calogero Famq")
        
        for idx, data in enumerate(chunk, start=i+1):
            m = data['member']
            s = data['stats']
            
            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"`{idx}.`"
            
            val = (
                f"Всего: **{s['total']}** "
                f"(✅{s['accepts']} ❌{s['denies']} 📞{s['calls']})\n"
                f"🕒 {s['last_action_time'] or '—'}"
            )
            embed.add_field(name=f"{medal} {m.display_name}", value=val, inline=False)
        
        pages.append(embed)
        
    view = DepartmentView(guild, stats_list, dept_type, pages)
    
    # Обновляем оригинальное сообщение
    await interaction.edit_original_response(embed=pages[0], view=view)



# ========== COG ==========
class ActivityMonitorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Восстанавливаем прослушку кнопок главного меню"""
        self.bot.add_view(MainMonitorView())
        
        channel = self.bot.get_channel(ACTIVITY_MONITOR_CHANNEL_ID)
        if not channel: return

        # Пытаемся найти и обновить существующее сообщение
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
            # Если не нашли - создаем новую
            await channel.purge(limit=5)
            embed = await generate_main_embed(channel.guild)
            await channel.send(embed=embed, view=MainMonitorView())
            print("[ActivityMonitor] Панель создана.")

    @commands.slash_command(name="monitor_update")
    @commands.has_permissions(administrator=True)
    async def manual_update(self, inter):
        """Принудительно пересоздать панель"""
        await inter.response.defer(ephemeral=True)
        channel = self.bot.get_channel(ACTIVITY_MONITOR_CHANNEL_ID)
        
        await channel.purge(limit=10)
        embed = await generate_main_embed(inter.guild)
        await channel.send(embed=embed, view=MainMonitorView())
        
        await inter.followup.send("✅ Мониторинг пересоздан!", ephemeral=True)

def setup(bot):
    bot.add_cog(ActivityMonitorCog(bot))
