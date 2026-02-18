import disnake
from disnake.ext import commands
from disnake import Embed, Interaction, ButtonStyle, TextInputStyle, PermissionOverwrite
from disnake.ui import View, TextInput, Button, button, Modal
from datetime import datetime
from constants import *
from database import log_staff_action
import asyncio
import re


# ─── Хелпер: достать user_id из эмбеда ───────────────────────────────────────


def _extract_user_id(message: disnake.Message) -> int | None:
    try:
        for embed in message.embeds:
            for field in embed.fields:
                match = re.search(r"`(\d+)`", field.value or "")
                if match:
                    return int(match.group(1))
            if embed.description:
                match = re.search(r"\*\*ID:\*\*\s*`(\d+)`", embed.description)
                if match:
                    return int(match.group(1))
    except Exception:
        pass
    return None


def _log(interaction: Interaction, action_type: str, target_user_id: int | None = None, extra: str | None = None):
    """Универсальный хелпер логирования для чит-хантеров."""
    try:
        log_staff_action(
            guild_id=interaction.guild.id,
            staff_id=interaction.user.id,
            action_type=action_type,
            target_user_id=target_user_id,
            extra=extra,
            role_type="cheathunter",
        )
    except Exception as e:
        print(f"[VerifLog] Ошибка логирования {action_type}: {e}")


# ─── View финального решения (внутри канала проверки) ─────────────────────────


class VerificationFinalDecisionView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _close_channel(self, interaction: Interaction):
        await interaction.channel.send("**Канал будет удален через 5 секунд...**")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except (disnake.NotFound, Exception):
            pass

    async def _delete_notification(self, interaction: Interaction, user_id: int):
        notification_channel = interaction.guild.get_channel(VERIFICATION_NOTIFICATION_CHANNEL_ID)
        if not notification_channel:
            return
        try:
            async for msg in notification_channel.history(limit=50):
                if str(user_id) in msg.content:
                    await msg.delete()
                    break
        except (disnake.NotFound, disnake.Forbidden):
            pass

    @button(label="Подтвердить (Выдать роль)", style=ButtonStyle.success,
            custom_id="final_accept", emoji="<:tick:1473380953245221016>")
    async def final_accept(self, btn: Button, interaction: Interaction):
        await interaction.response.defer()
        try:
            user_id = _extract_user_id(interaction.message)
            if not user_id:
                await interaction.followup.send("Не удалось определить пользователя.", ephemeral=True)
                return

            role   = interaction.guild.get_role(VERIFIED_ROLE_ID)
            member = interaction.guild.get_member(user_id)

            if not member:
                await interaction.followup.send("Пользователь вышел с сервера.", ephemeral=True)
                return
            if not role:
                await interaction.followup.send("Роль VERIFIED_ROLE_ID не найдена.", ephemeral=True)
                return

            await member.add_roles(role, reason="Верификация пройдена")

            # ── 🔥 ЛОГ: выдал роль после проверки ────────────────────────────
            _log(interaction, "verify_accept", user_id,
                 extra=f"role_id={VERIFIED_ROLE_ID}")

            await interaction.followup.send(
                embed=Embed(
                    description=f"Роль {role.mention} выдана пользователю {member.mention}!",
                    color=disnake.Color.from_rgb(54, 57, 63)
                )
            )
            await self._delete_notification(interaction, user_id)

            log_channel = interaction.guild.get_channel(LOG_VERIF)
            if log_channel:
                embed_log = Embed(
                    title="<:tick:1473380953245221016> Верификация: ОДОБРЕНО",
                    color=0x3BA55D,
                    timestamp=datetime.now()
                )
                embed_log.add_field(name="Пользователь", value=f"{member.mention}\n`{user_id}`", inline=True)
                embed_log.add_field(name="Администратор", value=interaction.user.mention, inline=True)
                embed_log.set_thumbnail(url=member.display_avatar.url)
                await log_channel.send(embed=embed_log)

            for child in self.children:
                child.disabled = True
            await interaction.edit_original_response(view=self)
            await self._close_channel(interaction)

        except Exception as e:
            await interaction.followup.send(
                embed=Embed(description=f"Ошибка: {e}", color=0xFF0000)
            )

    @button(label="Отказать", style=ButtonStyle.danger,
            custom_id="final_reject", emoji="<:cross:1473380950770716836>")
    async def final_reject(self, btn: Button, interaction: Interaction):
        await interaction.response.defer()

        user_id = _extract_user_id(interaction.message)
        member  = interaction.guild.get_member(user_id) if user_id else None

        # ── 🔥 ЛОГ: отказал после проверки ───────────────────────────────────
        _log(interaction, "verify_reject_final", user_id,
             extra="rejected_after_check")

        await self._delete_notification(interaction, user_id)

        log_channel = interaction.guild.get_channel(LOG_VERIF)
        if log_channel:
            embed_log = Embed(
                title="<:cross:1473380950770716836> Верификация: ОТКАЗАНО (После проверки)",
                color=0xFF0000,
                timestamp=datetime.now()
            )
            val = f"{member.mention}\n`{user_id}`" if member else f"`{user_id}`"
            embed_log.add_field(name="Пользователь", value=val, inline=True)
            embed_log.add_field(name="Администратор", value=interaction.user.mention, inline=True)
            if member:
                embed_log.set_thumbnail(url=member.display_avatar.url)
            await log_channel.send(embed=embed_log)

        mention = member.mention if member else f"`{user_id}`"
        await interaction.followup.send(
            embed=Embed(
                description=f"<:cross:1473380950770716836> Верификация {mention} отклонена.",
                color=0xFF0000
            )
        )

        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(view=self)
        await self._close_channel(interaction)


# ─── View кнопок администратора (в канале заявок) ─────────────────────────────


class VerificationAdminButtons(View):
    def __init__(self):
        super().__init__(timeout=None)

    @button(label="На проверку (Создать канал)", style=ButtonStyle.success,
            custom_id="accept_verif", emoji="<:tick:1473380953245221016>")
    async def accept(self, btn: Button, interaction: Interaction):
        is_allowed = (
            interaction.user.guild_permissions.administrator or
            any(role.id == CHEAT_HUNTER_ROLE_ID for role in interaction.user.roles)
        )
        if not is_allowed:
            await interaction.response.send_message(
                embed=Embed(description="У вас нет прав!", color=0xFF0000), ephemeral=True
            )
            return

        user_id = _extract_user_id(interaction.message)
        if not user_id:
            await interaction.response.send_message("Не удалось определить пользователя.", ephemeral=True)
            return

        category      = interaction.guild.get_channel(VERIFICATION_CATEGORY_ID)
        target_member = interaction.guild.get_member(user_id)

        if not category:
            await interaction.response.send_message(
                f"Категория (ID: {VERIFICATION_CATEGORY_ID}) не найдена!", ephemeral=True
            )
            return
        if not target_member:
            await interaction.response.send_message("Пользователь покинул сервер.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            overwrites = {
                interaction.guild.default_role: PermissionOverwrite(read_messages=False),
                interaction.guild.me:           PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
                interaction.user:               PermissionOverwrite(read_messages=True, send_messages=True),
                target_member:                  PermissionOverwrite(read_messages=True, send_messages=True),
            }

            new_channel = await interaction.guild.create_text_channel(
                name=f"verify-{target_member.display_name[:80]}",
                category=category,
                overwrites=overwrites,
                reason=f"Проверка {target_member.name} от {interaction.user.name}"
            )

            # ── 🔥 ЛОГ: создал канал проверки ────────────────────────────────
            _log(interaction, "verify_check", user_id,
                 extra=f"channel_id={new_channel.id}")

            voice_channel = interaction.guild.get_channel(VOICE_CHANNEL_ID)
            voice_text    = voice_channel.mention if voice_channel else "голосовой канал"

            embed_verify = Embed(
                title="<:freeiconproofing10988140:1473391799321104485> Проверка на ПО",
                description=(
                    f"{target_member.mention}, вас вызвал на проверку администратор {interaction.user.mention}.\n\n"
                    f"**Инструкция:**\n"
                    f"1. Зайдите в {voice_text}.\n"
                    f"2. Включите демонстрацию экрана.\n"
                    f"3. Следуйте указаниям администратора.\n\n"
                    "<:freeiconwarning3756712:1473429407980064788> **Попытка выхода с сервера, игнорирование или отказ от проверки приведет к блокировке.**\n\n"
                    f"**ID:** `{user_id}`"
                ),
                color=disnake.Color.from_rgb(54, 57, 63)
            )

            notification_channel = interaction.guild.get_channel(VERIFICATION_NOTIFICATION_CHANNEL_ID)
            if notification_channel:
                try:
                    notify_embed = Embed(
                        title="<:freeiconwarning3756712:1473429407980064788> Вызов на проверку",
                        description=f"Вас вызвали на проверку. Перейдите в канал: {new_channel.mention}",
                        color=disnake.Color.from_rgb(54, 57, 63)
                    )
                    await notification_channel.send(content=target_member.mention, embed=notify_embed)
                except Exception:
                    pass

            await new_channel.send(
                content=f"{target_member.mention} {interaction.user.mention}",
                embed=embed_verify,
                view=VerificationFinalDecisionView()
            )

            await interaction.followup.send(f"Канал проверки создан: {new_channel.mention}", ephemeral=True)

            for child in self.children:
                child.disabled = True
                if child.custom_id == "accept_verif":
                    child.label = "На проверке"
                    child.style = ButtonStyle.secondary

            embed = interaction.message.embeds[0]
            embed.add_field(name="Статус", value=f"В процессе (Канал: {new_channel.mention})", inline=False)
            await interaction.message.edit(embed=embed, view=self)

        except disnake.Forbidden:
            await interaction.followup.send("У бота нет прав создавать каналы.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Ошибка: {e}", ephemeral=True)

    @button(label="Отказать (Сразу)", style=ButtonStyle.danger,
            custom_id="reject_verif", emoji="<:cross:1473380950770716836>")
    async def reject(self, btn: Button, interaction: Interaction):
        is_allowed = (
            interaction.user.guild_permissions.administrator or
            any(role.id == CHEAT_HUNTER_ROLE_ID for role in interaction.user.roles)
        )
        if not is_allowed:
            await interaction.response.send_message(
                embed=Embed(description="У вас нет прав!", color=0xFF0000), ephemeral=True
            )
            return

        user_id = _extract_user_id(interaction.message)
        member  = interaction.guild.get_member(user_id) if user_id else None

        # ── 🔥 ЛОГ: отказал сразу по заявке ──────────────────────────────────
        _log(interaction, "verify_reject", user_id,
             extra="rejected_by_request")

        log_channel = interaction.guild.get_channel(LOG_VERIF)
        if log_channel:
            embed_log = Embed(
                title="<:cross:1473380950770716836> Верификация: ОТКАЗАНО (По заявке)",
                color=0xFF0000,
                timestamp=datetime.now()
            )
            val = f"{member.mention}\n`{user_id}`" if member else f"`{user_id}`"
            embed_log.add_field(name="Пользователь", value=val, inline=True)
            embed_log.add_field(name="Администратор", value=interaction.user.mention, inline=True)
            if member:
                embed_log.set_thumbnail(url=member.display_avatar.url)
            await log_channel.send(embed=embed_log)

        await interaction.response.send_message(
            embed=Embed(description="<:cross:1473380950770716836> Заявка отклонена.", color=0xFF0000),
            ephemeral=True
        )

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)


# ─── Модальное окно запроса ───────────────────────────────────────────────────


class VerificationRequestModal(Modal):
    def __init__(self):
        components = [
            TextInput(
                label="Причина запроса",
                custom_id="reason",
                style=TextInputStyle.paragraph,
                required=True,
                placeholder="Опишите, почему вы хотите получить верификацию...",
                max_length=500
            )
        ]
        super().__init__(title="Запрос верификации", components=components, timeout=300)

    async def callback(self, interaction: disnake.ModalInteraction):
        await interaction.response.defer(ephemeral=True)

        admin_channel = interaction.guild.get_channel(VERIFICATION_ADMIN_CHANNEL_ID)
        if not admin_channel:
            await interaction.followup.send(
                embed=Embed(description="Админский канал не найден!", color=0xFF0000), ephemeral=True
            )
            return

        embed = Embed(
            title="<:freeiconproofing10988140:1473391799321104485> Новый запрос на верификацию",
            description=(
                f"**Пользователь:** {interaction.user.mention}\n"
                f"**ID:** `{interaction.user.id}`\n"
                f"**Дата регистрации:** {interaction.user.created_at.strftime('%d.%m.%Y')}\n\n"
                f"**Причина запроса:**\n{interaction.text_values['reason']}"
            ),
            color=0x3A3B3C,
            timestamp=datetime.now(),
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        await admin_channel.send(embed=embed, view=VerificationAdminButtons())
        await interaction.followup.send(
            embed=Embed(
                title="Запрос отправлен!",
                description="Ваш запрос передан администрации. Ожидайте уведомления.",
                color=disnake.Color.from_rgb(54, 57, 63)
            ),
            ephemeral=True
        )


# ─── Кнопка запроса верификации ──────────────────────────────────────────────


class VerificationView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @button(label="Подать запрос на верификацию", style=ButtonStyle.success,
            emoji="<:freeiconproofing10988140:1473391799321104485>", custom_id="btn_request_verify")
    async def request_verify_btn(self, btn: Button, interaction: Interaction):
        await interaction.response.send_modal(VerificationRequestModal())


# ─── Ког ─────────────────────────────────────────────────────────────────────


class VerificationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(VerificationView())
        self.bot.add_view(VerificationAdminButtons())
        self.bot.add_view(VerificationFinalDecisionView())
        print("[VERIFICATION] Views восстановлены.")

        channel = self.bot.get_channel(VERIFICATION_REQUEST_CHANNEL_ID)
        if not channel:
            return

        embed = Embed(
            title="Верификация",
            description="Для получения доступа к каналам сервера необходимо пройти верификацию.",
            color=0x2B2D31
        )

        last_msg = None
        async for msg in channel.history(limit=10):
            if msg.author == self.bot.user:
                last_msg = msg
                break

        if last_msg:
            await last_msg.edit(embed=embed, view=VerificationView())
            print("[VERIFICATION] Меню ОБНОВЛЕНО.")
        else:
            await channel.purge(limit=10)
            await channel.send(embed=embed, view=VerificationView())
            print("[VERIFICATION] Меню СОЗДАНО.")


def setup(bot):
    bot.add_cog(VerificationCog(bot))
