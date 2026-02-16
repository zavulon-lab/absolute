import disnake
from disnake import Embed, Interaction, ButtonStyle, TextInputStyle
from disnake.ui import View, button, Button, Modal, TextInput
from disnake.errors import Forbidden
from datetime import datetime

from constants import (
    APPLICATION_RESULTS_CHANNEL_ID,
    ACCEPT_ROLE_ID,
    ACADEMY_CHANNEL_ID,
    VOICE_CHANNEL_ID,
    APPLICATIONS_CATEGORY_ID,
    # CURATOR_ROLE_ID,  # Больше не используется для выбора
)
from .utils import extract_user_id_from_embed, create_personal_file

# ===== ИМПОРТ ЛОГИРОВАНИЯ =====
from database import log_staff_action


# ===== МОДАЛЬНОЕ ОКНО ДЛЯ ПРИЧИНЫ ОТКАЗА =====
class DenyReasonModal(Modal):
    def __init__(self, review_view, member, original_interaction):
        self.review_view = review_view
        self.member = member
        self.original_interaction = original_interaction

        components = [
            TextInput(
                label="Причина отказа",
                custom_id="deny_reason",
                style=TextInputStyle.paragraph,
                placeholder="Стрельба, мувмент...",
                required=True,
                max_length=200,
            )
        ]
        super().__init__(title="Отклонение заявки", components=components)

    async def callback(self, interaction: Interaction):
        reason = interaction.text_values["deny_reason"]
        await self.review_view.process_denial(interaction, self.member, reason)


# ===== ОСНОВНОЙ КЛАСС УПРАВЛЕНИЯ ЗАЯВКАМИ =====
class ApplicationReviewView(View):
    """Кнопки управления заявкой для администраторов + логирование активности"""

    def __init__(self):
        super().__init__(timeout=None)

    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========
    async def get_candidate(self, interaction: Interaction) -> disnake.Member | None:
        if not interaction.message.embeds:
            return None

        user_id = extract_user_id_from_embed(interaction.message.embeds[0])
        if not user_id:
            return None

        member = interaction.guild.get_member(user_id)
        if member:
            return member

        try:
            return await interaction.guild.fetch_member(user_id)
        except:
            return None

    async def send_dm_embed(self, member: disnake.Member, embed: Embed, content: str = None) -> bool:
        try:
            await member.send(content=content, embed=embed)
            return True
        except Forbidden:
            return False

    async def find_and_delete_clarification_channel(self, guild, member_id: int):
        try:
            for channel in guild.text_channels:
                is_topic_match = channel.topic and str(member_id) in channel.topic
                if is_topic_match:
                    try:
                        await channel.delete(reason="Заявка закрыта")
                    except Exception:
                        pass
        except Exception:
            pass

    async def send_result_log(self, guild, content: str, embed: Embed):
        try:
            channel = guild.get_channel(APPLICATION_RESULTS_CHANNEL_ID)
            if channel:
                await channel.send(content=content, embed=embed)
            else:
                print(f"[Warning] Канал итогов {APPLICATION_RESULTS_CHANNEL_ID} не найден.")
        except Exception as e:
            print(f"[Error] Не удалось отправить итог заявки: {e}")

    # ===== ЛОГИРОВАНИЕ (ИСПРАВЛЕННОЕ) =====
    def _log_action(self, interaction: Interaction, action_type: str, target_id: int | None = None, details: str | None = None):
        try:
            log_staff_action(
                guild_id=interaction.guild.id,
                staff_id=interaction.user.id,
                action_type=action_type,
                target_user_id=target_id,
                extra=details
            )
        except Exception as e:
            print(f"[ActivityLog] Ошибка логирования: {e}")

    # ========== БИЗНЕС-ЛОГИКА ==========
    async def process_denial(self, interaction: Interaction, member: disnake.Member, reason: str):
        await interaction.response.defer(ephemeral=True)
        recruiter = interaction.user

        # 🔥 ЛОГИРУЕМ ОТКАЗ
        self._log_action(interaction, "deny", member.id, details=reason[:400])

        await self.find_and_delete_clarification_channel(interaction.guild, member.id)

        original_embed = interaction.message.embeds[0]
        if original_embed:
            original_embed.color = 0xED4245
            original_embed.set_footer(text=f"Отклонил: {recruiter.display_name} • Причина: {reason}")
            await interaction.message.edit(embed=original_embed, view=None)

        result_embed = Embed(
            description=(
                f"Заявка от пользователя {member.mention}\n\n"
                f"На Вступление в семью была отклонена. <:cross:1472654174788255996>\n\n"
                f"Причина: {reason}\n"
                f"Рассматривал заявку: {recruiter.mention}"
            ),
            color=0xED4245,
        )
        result_embed.set_thumbnail(url=member.display_avatar.url)
        result_embed.set_footer(text="Calogero Famq", icon_url=interaction.client.user.display_avatar.url)

        await self.send_result_log(interaction.guild, content=member.mention, embed=result_embed)
        await self.send_dm_embed(member, result_embed, content=member.mention)

        await interaction.followup.send(f"<:cross:1472654174788255996> Заявка {member.mention} отклонена.", ephemeral=True)

    async def process_acceptance_final(self, interaction: Interaction, member: disnake.Member):
        """ФИНАЛЬНОЕ ПРИНЯТИЕ (АВТО-КУРАТОР)"""
        # Тот, кто нажал кнопку (Рекрутер), становится куратором
        recruiter = interaction.user
        curator = recruiter 

        # 🔥 ЛОГИРУЕМ ПРИНЯТИЕ
        self._log_action(interaction, "accept_final", member.id, details=f"auto_curator={curator.id}")

        # 1. Роль
        role = interaction.guild.get_role(ACCEPT_ROLE_ID)
        if role:
            try:
                await member.add_roles(role, reason=f"Принят: {recruiter}")
            except:
                pass

        # 2. Удаляем чат уточнений
        await self.find_and_delete_clarification_channel(interaction.guild, member.id)

        # 3. Личное дело
        personal_channel = await create_personal_file(interaction.guild, member, curator)
        
        # Обновляем оригинальное сообщение
        message = interaction.message
        original_embed = message.embeds[0]
        if original_embed:
            original_embed.color = 0x3BA55D
            original_embed.add_field(name="▬▬▬▬▬▬▬▬▬▬", value="**<:tik:1472654073814581268> ПРИНЯТ**", inline=False)
            original_embed.add_field(
                name="<:freeiconcurator5301960:1472946853694668933> Куратор", value=curator.mention, inline=True
            )
            original_embed.add_field(
                name="<:freeiconrecruiter2724952:1472947030937571358> Рекрутер", value=recruiter.mention, inline=True
            )
            await message.edit(embed=original_embed, view=None)

        # Отправляем лог в академию
        try:
            academy_channel = interaction.guild.get_channel(ACADEMY_CHANNEL_ID)
            if academy_channel:
                academy_embed = Embed(
                    title="Новый участник принят",
                    description=(
                        f"{member.mention} — {recruiter.mention} принял(а)\n"
                        f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                        f"Личное дело: {personal_channel.mention if personal_channel else 'Не создано'}\n"
                        f"Куратор — {curator.mention}"
                    ),
                    color=0x2B2D31,
                )
                academy_embed.set_thumbnail(
                    url="https://media.discordapp.net/attachments/1336423985794682974/1336423986381754409/6FDCFF59-EFBB-4D26-9E57-50B0F3D61B50.jpg"
                )
                academy_embed.set_footer(text=f"{datetime.now().strftime('%d.%m.%Y %H:%M')}")
                await academy_channel.send(embed=academy_embed)
        except Exception as e:
            print(f"[Error] Лог академии: {e}")

        # Пишем в ЛС новичку
        await self.send_dm_embed(
            member,
            Embed(
                title="🎉 Добро пожаловать!",
                description=f"Вы официально приняты в семью!\nВаш куратор: {curator.mention}",
                color=0x3BA55D,
            ),
        )

        await interaction.followup.send(
            f"<:tik:1472654073814581268> {member.mention} принят. Вы назначены куратором.", ephemeral=True
        )

    # ========== КНОПКИ ==========
    @button(label=" Принять (После обзвона)", style=ButtonStyle.success, custom_id="app_accept", emoji="<:tik:1472654073814581268>")
    async def accept_button(self, button: Button, interaction: Interaction):
        """Сразу принимаем, без выбора куратора"""
        await interaction.response.defer(ephemeral=True)
        member = await self.get_candidate(interaction)
        
        if not member:
            await interaction.followup.send("Кандидат не найден.", ephemeral=True)
            return

        # Сразу вызываем метод принятия
        await self.process_acceptance_final(interaction, member)

    @button(label="👀 Взять на рассмотрение", style=ButtonStyle.secondary, custom_id="app_review")
    async def review_button(self, button: Button, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        member = await self.get_candidate(interaction)
        if not member:
            return

        self._log_action(interaction, "review", member.id)

        original_embed = interaction.message.embeds[0]
        original_embed.color = 0xF59E0B
        original_embed.title = "👀 Заявка на рассмотрении"
        original_embed.set_footer(text=f"Рассматривает: {interaction.user.display_name}")
        await interaction.message.edit(embed=original_embed)
        await interaction.followup.send("👀 Статус обновлен.", ephemeral=True)

    @button(label=" Вызвать на обзвон", style=ButtonStyle.primary, custom_id="app_call", emoji="<:freeiconcall3870799:1472668017170186331>")
    async def call_button(self, button: Button, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        member = await self.get_candidate(interaction)
        recruiter = interaction.user
        if not member:
            return

        self._log_action(interaction, "call", member.id)

        voice_channel = interaction.guild.get_channel(VOICE_CHANNEL_ID)
        voice_mention = voice_channel.mention if voice_channel else "#не-настроен"

        result_embed = Embed(
            description=(
                f"Заявка от пользователя {member.mention}\n\n"
                f"На Вступление в семью была рассмотрена! <:tik:1472654073814581268>\n\n"
                f"Для прохода обзвона ожидаем вас в канале :\n"
                f"{voice_mention}\n\n"
                f"Рассматривал заявку: {recruiter.mention}"
            ),
            color=0x3BA55D,
        )
        result_embed.set_thumbnail(url=member.display_avatar.url)
        result_embed.set_footer(text="Calogero Famq", icon_url=interaction.client.user.display_avatar.url)

        await self.send_result_log(interaction.guild, content=member.mention, embed=result_embed)
        await self.send_dm_embed(member, result_embed, content=member.mention)

        original_embed = interaction.message.embeds[0]
        original_embed.color = 0x5865F2
        original_embed.title = "<:freeiconcall3870799:1472668017170186331> Вызван на обзвон"
        original_embed.set_footer(text=f"Вызвал: {recruiter.display_name}")
        await interaction.message.edit(embed=original_embed)

        await interaction.followup.send(f"{member.mention} вызван на обзвон.", ephemeral=True)

    @button(label="Отклонить", style=ButtonStyle.danger, custom_id="app_deny", emoji="<:cross:1472654174788255996>")
    async def deny_button(self, button: Button, interaction: Interaction):
        member = await self.get_candidate(interaction)
        if not member:
            await interaction.response.send_message("Кандидат не найден.", ephemeral=True)
            return
        await interaction.response.send_modal(DenyReasonModal(self, member, interaction))

    @button(label="💬 Создать чат", style=ButtonStyle.secondary, custom_id="app_create_chat")
    async def create_chat_button(self, button: Button, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        member = await self.get_candidate(interaction)

        if not member:
            await interaction.followup.send("Кандидат не найден.", ephemeral=True, delete_after=20)
            return

        try:
            guild = interaction.guild
            cat = guild.get_channel(APPLICATIONS_CATEGORY_ID)

            if not cat:
                await interaction.followup.send("Категория заявок не найдена.", ephemeral=True)
                return

            chan = await guild.create_text_channel(
                name=f"заявка-{member.display_name}", category=cat, topic=f"ID: {member.id} | Обсуждение заявки"
            )

            await chan.set_permissions(guild.default_role, view_channel=False)
            await chan.set_permissions(member, view_channel=True, send_messages=True)
            await chan.set_permissions(interaction.user, view_channel=True, send_messages=True)

            self._log_action(interaction, "chat_created", member.id, details=f"channel_id={chan.id}")

            original_embed = interaction.message.embeds[0]
            app_url = f"https://discord.com/channels/{guild.id}/{interaction.channel.id}/{interaction.message.id}"

            chat_embed = Embed(
                title="<:freeiconrules5692161:1472654721117589606> Обсуждение заявки",
                description=f"Администратор {interaction.user.mention} создал этот чат для уточнения деталей.\n\n**[Перейти к сообщению с заявкой]({app_url})**",
                color=0x2B2D31,
            )

            if original_embed and original_embed.fields:
                for f in original_embed.fields:
                    chat_embed.add_field(name=f.name, value=f.value, inline=f.inline)

            chat_embed.set_thumbnail(url=member.display_avatar.url)
            chat_embed.set_footer(text=f"ID: {member.id}")

            await chan.send(
                content=f"{member.mention}, администратор {interaction.user.mention} хочет уточнить детали вашей заявки.",
                embed=chat_embed,
            )

            dm_embed = Embed(
                title="💬 Уточнение по заявке",
                description=f"Пожалуйста, перейдите в созданный канал: {chan.mention}",
                color=disnake.Color.from_rgb(54, 57, 63),
            )
            try:
                await member.send(embed=dm_embed)
            except:
                pass

            await interaction.followup.send(f"✅ Чат создан: {chan.mention}", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"Ошибка при создании чата: {e}", ephemeral=True, delete_after=20)
