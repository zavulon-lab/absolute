import disnake
from disnake.ext import commands
from disnake import Embed, TextInputStyle, Interaction, ButtonStyle
from disnake.ui import View, button, Button
from datetime import datetime
from constants import *

class VerificationRequestModal(disnake.ui.Modal):
    def __init__(self):
        components = [
            disnake.ui.TextInput(
                label="Причина запроса",
                custom_id="reason",
                style=TextInputStyle.paragraph,
                required=True,
                placeholder="Опишите, почему вы хотите получить верификацию...",
            )
        ]
        super().__init__(title="Запрос верификации", components=components, timeout=300)

    async def callback(self, interaction: disnake.ModalInteraction):
        try:
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message("❌ Ошибка: сервер не найден!", ephemeral=True)
                return

            admin_channel = guild.get_channel(VERIFICATION_ADMIN_CHANNEL_ID)
            if not admin_channel:
                await interaction.response.send_message("❌ Админский канал не найден!", ephemeral=True)
                return

            reason = interaction.text_values["reason"]

            embed = Embed(
                title="🔔 Новый запрос на верификацию",
                description=(
                    f"**Пользователь:** {interaction.user.mention}\n"
                    f"**ID:** `{interaction.user.id}`\n"
                    f"**Дата регистрации:** {interaction.user.created_at.strftime('%d.%m.%Y')}\n\n"
                    f"**Причина запроса:**\n{reason}"
                ),
                color=0x3A3B3C,
                timestamp=datetime.now(),
            )
            embed.set_footer(text=f"Запрос от {interaction.user.display_name}")
            embed.set_thumbnail(url=interaction.user.display_avatar.url)

            await admin_channel.send(embed=embed, view=VerificationAdminButtons(interaction.user))

            confirm_embed = Embed(
                title="✅ Запрос отправлен!",
                description="Ваш запрос на верификацию передан администрации. Ожидайте решения.",
                color=0x3BA55D,
                timestamp=datetime.now(),
            )
            await interaction.response.send_message(embed=confirm_embed, ephemeral=True)

        except Exception as e:
            print(f"Ошибка в VerificationRequestModal: {e}")
            error_embed = Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при отправке запроса. Попробуйте снова.",
                color=0xFF0000,
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class VerificationAdminButtons(View):
    def __init__(self, user):
        super().__init__(timeout=None)
        self.user = user

    @button(label="✅ Одобрить", style=ButtonStyle.success, custom_id="accept_verification_button")
    async def accept_verification_button(self, button: Button, interaction: Interaction):
        if not interaction.user.guild_permissions.administrator and not any(
            role.id == ALLOWED_ROLE_ID for role in interaction.user.roles
        ):
            await interaction.response.send_message("❌ У вас нет прав!", ephemeral=True)
            return

        try:
            notification_channel = interaction.guild.get_channel(VERIFICATION_NOTIFICATION_CHANNEL_ID)
            voice_channel = interaction.guild.get_channel(VOICE_CHANNEL_ID)

            if not notification_channel or not voice_channel:
                await interaction.response.send_message("❌ Канал уведомлений или голосовой канал не найден!", ephemeral=True)
                return

            embed = Embed(
                title="✅ Верификация одобрена",
                description=(
                    f"Поздравляем, {self.user.mention}! Ваша верификация была одобрена.\n\n"
                    f"Теперь вы можете присоединиться к голосовому каналу: {voice_channel.mention}"
                ),
                color=0x3BA55D,
                timestamp=datetime.now(),
            )
            embed.set_footer(text=f"Одобрено {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
            embed.set_thumbnail(url=self.user.display_avatar.url)

            await notification_channel.send(content=self.user.mention, embed=embed)
            await interaction.response.send_message(f"✅ Верификация {self.user.mention} одобрена!", ephemeral=True)

            self.children[0].disabled = True
            self.children[1].disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            print(f"Ошибка при одобрении верификации: {e}")
            await interaction.response.send_message("❌ Произошла ошибка.", ephemeral=True)

    @button(label="❌ Отклонить", style=ButtonStyle.danger, custom_id="reject_verification_button")
    async def reject_verification_button(self, button: Button, interaction: Interaction):
        if not interaction.user.guild_permissions.administrator and not any(
            role.id == ALLOWED_ROLE_ID for role in interaction.user.roles
        ):
            await interaction.response.send_message("❌ У вас нет прав!", ephemeral=True)
            return

        try:
            notification_channel = interaction.guild.get_channel(VERIFICATION_NOTIFICATION_CHANNEL_ID)

            if not notification_channel:
                await interaction.response.send_message("❌ Канал уведомлений не найден!", ephemeral=True)
                return

            embed = Embed(
                title="❌ Верификация отклонена",
                description=f"{self.user.mention}, к сожалению, ваша верификация была отклонена.\nОбратитесь к администрации для уточнения причин.",
                color=0xFF0000,
                timestamp=datetime.now(),
            )
            embed.set_footer(text=f"Отклонено {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
            embed.set_thumbnail(url=self.user.display_avatar.url)

            await notification_channel.send(embed=embed)
            await interaction.response.send_message(f"❌ Верификация {self.user.mention} отклонена!", ephemeral=True)

            self.children[0].disabled = True
            self.children[1].disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            print(f"Ошибка при отклонении верификации: {e}")
            await interaction.response.send_message("❌ Произошла ошибка.", ephemeral=True)

class VerificationRequestButtons(View):
    def __init__(self):
        super().__init__(timeout=None)

    @button(label="📄 Отправить запрос", style=ButtonStyle.primary, custom_id="verification_request_button")
    async def verification_request_button(self, button: Button, interaction: Interaction):
        await interaction.response.send_modal(VerificationRequestModal())

class VerificationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Настройка канала верификации при запуске"""
        try:
            verification_channel = self.bot.get_channel(VERIFICATION_REQUEST_CHANNEL_ID)
            if verification_channel:
                await verification_channel.purge(limit=10)
                embed = Embed(
                    title="✅ Верификация",
                    description="Отправьте запрос на верификацию, нажав кнопку ниже.",
                    color=0x3A3B3C,
                )
                await verification_channel.send(embed=embed)
                await verification_channel.send(view=VerificationRequestButtons())
                print("✅ [Verification] Канал верификации настроен")
        except Exception as e:
            print(f"❌ [Verification] Ошибка при настройке: {e}")

def setup(bot):
    bot.add_cog(VerificationCog(bot))
