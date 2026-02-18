import disnake
from disnake.ext import commands
from disnake import Embed, Interaction, ButtonStyle, TextInputStyle, Color
from disnake.ui import View, TextInput, Button, Modal, button
from datetime import datetime
import sqlite3
import re
import os

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from constants import (
    ACADEMY_REQUEST_CHANNEL_ID, MAIN_ADMIN_CHANNEL_ID, TIER_ADMIN_CHANNEL_ID,
    MAIN_NOTIFY_CHANNEL_ID, TIER_NOTIFY_CHANNEL_ID,
    ACADEMY_ROLE_ID, MAIN_ROLE_ID, TIER_1_ROLE_ID, TIER_2_ROLE_ID,
    SUPPORT_ROLE_ID, TIER_CHECK_ROLE_ID, RECRUITER_ROLE_ID
)

FAM_COLOR = Color.from_rgb(54, 57, 63)

# ─── База данных ───────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "promotion_data.db")


def _init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS active_applications (
                user_id INTEGER PRIMARY KEY,
                app_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')


def _save_application(user_id: int, app_type: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO active_applications (user_id, app_type) VALUES (?, ?)",
            (user_id, app_type)
        )


def _get_application(user_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT user_id, app_type FROM active_applications WHERE user_id = ?",
            (user_id,)
        ).fetchone()
    return {"user_id": row[0], "app_type": row[1]} if row else None


def _delete_application(user_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM active_applications WHERE user_id = ?", (user_id,)
        )


_init_db()

# ─── Базовый миксин ────────────────────────────────────────────────────────────

class _BaseDecisionView(View):
    def __init__(self):
        super().__init__(timeout=None)

    def _get_user_id_from_message(self, message: disnake.Message):
        try:
            for field in message.embeds[0].fields:
                if field.name == "Участник":
                    match = re.search(r"`(\d+)`", field.value)
                    if match:
                        return int(match.group(1))
        except Exception:
            pass
        return None

    async def _resolve(self, interaction: Interaction):
        user_id = self._get_user_id_from_message(interaction.message)
        if not user_id:
            await interaction.response.send_message("Не удалось определить пользователя.", ephemeral=True)
            return None, None
        app = _get_application(user_id)
        app_type = app["app_type"] if app else "main"
        return user_id, app_type

    async def _send_result_log(self, interaction: Interaction, member, title, result_type, app_type):
        channel_id = MAIN_NOTIFY_CHANNEL_ID if app_type == "main" else TIER_NOTIFY_CHANNEL_ID
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            return

        embed = Embed(
            title=f"{'<:tick:1473380953245221016>' if result_type == 'success' else '<:cross:1473380950770716836>'} Результат повышения",
            description=f"Администрация рассмотрела вашу заявку на **{title}**.",
            color=0x3BA55D if result_type == "success" else 0xFF0000,
            timestamp=datetime.now()
        )
        embed.add_field(name="Участник",      value=member.mention,          inline=True)
        embed.add_field(name="Статус",        value="Одобрено" if result_type == "success" else "Отклонено", inline=True)
        embed.add_field(name="Администратор", value=interaction.user.mention, inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(content=member.mention, embed=embed)

    async def _finalize(self, user_id: int):
        _delete_application(user_id)
        for child in self.children:
            child.disabled = True


# ─── View для заявки на Main ───────────────────────────────────────────────────

class MainDecisionView(_BaseDecisionView):
    def __init__(self):
        super().__init__()

    @button(label="Одобрить Absolute", style=ButtonStyle.success,
            emoji="<:tick:1473380953245221016>", custom_id="main_accept")
    async def accept_main(self, btn: Button, interaction: Interaction):
        user_id, app_type = await self._resolve(interaction)
        if not user_id:
            return
        member = interaction.guild.get_member(user_id)
        if not member:
            return
        await interaction.response.defer()
        academy_role = interaction.guild.get_role(ACADEMY_ROLE_ID)
        main_role    = interaction.guild.get_role(MAIN_ROLE_ID)
        if academy_role and academy_role in member.roles:
            await member.remove_roles(academy_role)
        if main_role:
            await member.add_roles(main_role)
        await self._send_result_log(interaction, member, "Absolute", "success", app_type)
        await self._finalize(user_id)
        await interaction.edit_original_response(view=self)

    @button(label="Отклонить", style=ButtonStyle.danger,
            emoji="<:cross:1473380950770716836>", custom_id="main_reject")
    async def reject(self, btn: Button, interaction: Interaction):
        user_id, app_type = await self._resolve(interaction)
        if not user_id:
            return
        member = interaction.guild.get_member(user_id)
        if member:
            await self._send_result_log(interaction, member, "Квалификацию", "reject", app_type)
        await self._finalize(user_id)
        await interaction.response.edit_message(view=self)


# ─── View для заявки на Tier ───────────────────────────────────────────────────

class TierDecisionView(_BaseDecisionView):
    def __init__(self):
        super().__init__()

    @button(label="Выдать Tier 1", style=ButtonStyle.primary,
            emoji="<:freeiconanimal15636581:1473395822484787354>", custom_id="tier_accept_t1")
    async def accept_t1(self, btn: Button, interaction: Interaction):
        user_id, app_type = await self._resolve(interaction)
        if not user_id:
            return
        member = interaction.guild.get_member(user_id)
        if not member:
            return
        await interaction.response.defer()
        await member.add_roles(interaction.guild.get_role(TIER_1_ROLE_ID))
        await self._send_result_log(interaction, member, "Tier I", "success", app_type)
        await self._finalize(user_id)
        await interaction.edit_original_response(view=self)

    @button(label="Выдать Tier 2", style=ButtonStyle.primary,
            emoji="<:freeiconcrow3599008:1473396674511638610>", custom_id="tier_accept_t2")
    async def accept_t2(self, btn: Button, interaction: Interaction):
        user_id, app_type = await self._resolve(interaction)
        if not user_id:
            return
        member = interaction.guild.get_member(user_id)
        if not member:
            return
        await interaction.response.defer()
        await member.add_roles(interaction.guild.get_role(TIER_2_ROLE_ID))
        await self._send_result_log(interaction, member, "Tier II", "success", app_type)
        await self._finalize(user_id)
        await interaction.edit_original_response(view=self)

    @button(label="Отклонить", style=ButtonStyle.danger,
            emoji="<:cross:1473380950770716836>", custom_id="tier_reject")
    async def reject(self, btn: Button, interaction: Interaction):
        user_id, app_type = await self._resolve(interaction)
        if not user_id:
            return
        member = interaction.guild.get_member(user_id)
        if member:
            await self._send_result_log(interaction, member, "Квалификацию", "reject", app_type)
        await self._finalize(user_id)
        await interaction.response.edit_message(view=self)


# ─── Модальные окна ────────────────────────────────────────────────────────────

class MainAppModal(Modal):
    def __init__(self):
        components = [
            TextInput(label="Ваш ник и статик", custom_id="nick",
                      placeholder="Например: Shadow | 285906", required=True),
            TextInput(label="Ваш стаж в игре", custom_id="experience",
                      placeholder="Например: 2 года", required=True),
            TextInput(label="Почему вы достойны Absolute?", custom_id="reason",
                      style=TextInputStyle.paragraph,
                      placeholder="Расскажите о своих достижениях...", required=True),
            TextInput(label="Доказательства", custom_id="proofs",
                      style=TextInputStyle.paragraph,
                      placeholder="Ссылки на отчёты/видео", required=True),
        ]
        super().__init__(title="Анкета на Absolute", components=components)

    async def callback(self, interaction: disnake.ModalInteraction):
        channel = interaction.guild.get_channel(MAIN_ADMIN_CHANNEL_ID)

        embed = Embed(title="Новая заявка: MAIN", color=FAM_COLOR, timestamp=datetime.now())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Участник",       value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        embed.add_field(name="Ник и статик",   value=f"```\n{interaction.text_values['nick']}\n```",          inline=False)
        embed.add_field(name="Стаж",           value=f"```\n{interaction.text_values['experience']}\n```",    inline=True)
        embed.add_field(name="Почему достоин", value=f"```\n{interaction.text_values['reason']}\n```",        inline=False)
        embed.add_field(name="Доказательства", value=f"```\n{interaction.text_values['proofs']}\n```",        inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        await channel.send(content=f"<@&{RECRUITER_ROLE_ID}>", embed=embed, view=MainDecisionView())
        _save_application(interaction.user.id, "main")
        await interaction.response.send_message(
            "Ваша анкета была успешно передана руководству!", ephemeral=True
        )


class TierAppModal(Modal):
    def __init__(self):
        components = [
            TextInput(label="Ваш ник и статик", custom_id="nick",
                      placeholder="Например: Shadow | 285906", required=True),
            TextInput(label="Какой Tier хотите получить?", custom_id="tier_level",
                      placeholder="Tier 1 или Tier 2", required=True),
            TextInput(label="Обоснование", custom_id="reason",
                      style=TextInputStyle.paragraph,
                      placeholder="Почему вы заслуживаете этот Tier?", required=True),
            TextInput(label="Доказательства", custom_id="proofs",
                      style=TextInputStyle.paragraph,
                      placeholder="Ссылки на отчёты/видео", required=True),
        ]
        super().__init__(title="Анкета на Tier", components=components)

    async def callback(self, interaction: disnake.ModalInteraction):
        channel = interaction.guild.get_channel(TIER_ADMIN_CHANNEL_ID)

        embed = Embed(title="Новая заявка: TIER", color=FAM_COLOR, timestamp=datetime.now())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Участник",       value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        embed.add_field(name="Ник и статик",   value=f"```\n{interaction.text_values['nick']}\n```",          inline=False)
        embed.add_field(name="Желаемый Tier",  value=f"```\n{interaction.text_values['tier_level']}\n```",    inline=True)
        embed.add_field(name="Обоснование",    value=f"```\n{interaction.text_values['reason']}\n```",        inline=False)
        embed.add_field(name="Доказательства", value=f"```\n{interaction.text_values['proofs']}\n```",        inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        await channel.send(content=f"<@&{TIER_CHECK_ROLE_ID}>", embed=embed, view=TierDecisionView())
        _save_application(interaction.user.id, "tier")
        await interaction.response.send_message(
            "Ваша анкета была успешно передана руководству!", ephemeral=True
        )


# ─── Главное меню ──────────────────────────────────────────────────────────────

class MainMenuView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @button(label="Подать на Main", style=ButtonStyle.success,
            emoji="<:freeiconcrow2185402:1473395821226754283>", custom_id="btn_main_app")
    async def apply_main(self, b, i):
        await i.response.send_modal(MainAppModal())

    @button(label="Подать на Tier", style=ButtonStyle.primary,
        emoji="<:freeiconanimal15636581:1473395822484787354>", custom_id="btn_tier_app")
    async def apply_tier(self, b, i: disnake.Interaction):
        if not any(role.id == MAIN_ROLE_ID for role in i.user.roles):
            await i.response.send_message(
                embed=Embed(
                    description="<:cross:1473380950770716836> Для подачи заявки на Tier необходима роль **Absolute**.",
                    color=0xFF0000
                ),
                ephemeral=True
            )
            return
        await i.response.send_modal(TierAppModal())



# ─── Ког ───────────────────────────────────────────────────────────────────────

class ApplicationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(MainDecisionView())
        self.bot.add_view(TierDecisionView())
        self.bot.add_view(MainMenuView())
        print("[PROMOTION] Views восстановлены.")

        channel = self.bot.get_channel(ACADEMY_REQUEST_CHANNEL_ID)
        if not channel:
            return

        embed = Embed(title="Повышение", color=FAM_COLOR)
        embed.description = (
            "Приветствуем в системе повышения\n\n"
            "<:freeiconcrow2185402:1473395821226754283> **Повышение до Absolute**\n"
            "Для повышения c young до absolute оставьте заявку\n\n"
            "<:freeiconanimal15636581:1473395822484787354> **Повышение Tier**\n"
            "Для получения tier оставьте заявку"
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1462165491278938204/1473396730803392713/free-icon-crow-3599008.png?ex=69960f23&is=6994bda3&hm=849d7df0a86831c679e5e2a43bcbe3d4fae1228c028ebad48c6eb610ba6db1fb&")
        embed.set_footer(text="Заявки рассматриваются руководством в течение 24 часов.")

        last_msg = None
        async for msg in channel.history(limit=5):
            if msg.author == self.bot.user and msg.embeds and msg.embeds[0].title == "Повышение":
                last_msg = msg
                break

        if last_msg:
            await last_msg.edit(embed=embed, view=MainMenuView())
        else:
            await channel.purge(limit=2)
            await channel.send(embed=embed, view=MainMenuView())


def setup(bot):
    bot.add_cog(ApplicationCog(bot))
