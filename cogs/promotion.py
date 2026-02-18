import disnake
from disnake.ext import commands
from disnake import Embed, Interaction, ButtonStyle, TextInputStyle, Color
from disnake.ui import View, TextInput, Button, Modal, button
from datetime import datetime

# Импортируем константы
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from constants import (
    ACADEMY_REQUEST_CHANNEL_ID, MAIN_ADMIN_CHANNEL_ID, TIER_ADMIN_CHANNEL_ID,
    MAIN_NOTIFY_CHANNEL_ID, TIER_NOTIFY_CHANNEL_ID,
    ACADEMY_ROLE_ID, MAIN_ROLE_ID, TIER_1_ROLE_ID, TIER_2_ROLE_ID, SUPPORT_ROLE_ID
)

# Твой основной цвет
FAM_COLOR = Color.from_rgb(54, 57, 63)

class ApplicationDecisionView(View):
    def __init__(self, user_id: int, app_type: str):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.app_type = app_type
        self.accept_main.custom_id = f"accept_main:{user_id}"
        self.accept_t1.custom_id = f"accept_t1:{user_id}"
        self.accept_t2.custom_id = f"accept_t2:{user_id}"
        self.reject.custom_id = f"reject_app:{user_id}"

    async def _check_admin(self, interaction: Interaction):
        if not any(role.id == SUPPORT_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("У вас нет прав для управления квалификацией.", ephemeral=True)
            return False
        return True

    async def _send_result_log(self, interaction: Interaction, member, title, result_type):
        """Отправка красивого лога в канал результатов"""
        channel_id = MAIN_NOTIFY_CHANNEL_ID if self.app_type == "main" else TIER_NOTIFY_CHANNEL_ID
        channel = interaction.guild.get_channel(channel_id)
        if not channel: return

        embed = Embed(
            title=f"{'<:tick:1473380953245221016>' if result_type == 'success' else '<:cross:1473380950770716836>'} Результат повышения",
            description=f"Администрация рассмотрела вашу заявку на **{title}**.",
            color=0x3BA55D if result_type == "success" else 0xFF0000,
            timestamp=datetime.now()
        )
        embed.add_field(name="Участник", value=f"{member.mention}", inline=True)
        embed.add_field(name="Статус", value="Одобрено" if result_type == "success" else "Отклонено", inline=True)
        embed.add_field(name="Администратор", value=f"{interaction.user.mention}", inline=False)
        # Thumbnail аватара пользователя в логе результата
        embed.set_thumbnail(url=member.display_avatar.url)
        
        await channel.send(content=member.mention, embed=embed)

    @button(label="Одобрить Absolute", style=ButtonStyle.success, emoji="<:tick:1473380953245221016>")
    async def accept_main(self, button: Button, interaction: Interaction):
        if not await self._check_admin(interaction): return
        member = interaction.guild.get_member(self.user_id)
        if not member: return
        
        await interaction.response.defer()
        academy_role = interaction.guild.get_role(ACADEMY_ROLE_ID)
        main_role = interaction.guild.get_role(MAIN_ROLE_ID)
        
        if academy_role and academy_role in member.roles: await member.remove_roles(academy_role)
        if main_role: await member.add_roles(main_role)

        await self._send_result_log(interaction, member, "Absolute", "success")
        for child in self.children: child.disabled = True
        await interaction.edit_original_response(view=self)

    @button(label="Выдать Tier 1", style=ButtonStyle.primary, emoji="<:freeiconanimal15636581:1473395822484787354>")
    async def accept_t1(self, button: Button, interaction: Interaction):
        if not await self._check_admin(interaction): return
        member = interaction.guild.get_member(self.user_id)
        if not member: return
        await interaction.response.defer()
        await member.add_roles(interaction.guild.get_role(TIER_1_ROLE_ID))
        await self._send_result_log(interaction, member, "Tier I", "success")
        for child in self.children: child.disabled = True
        await interaction.edit_original_response(view=self)

    @button(label="Выдать Tier 2", style=ButtonStyle.primary, emoji="<:freeiconcrow3599008:1473396674511638610>")
    async def accept_t2(self, button: Button, interaction: Interaction):
        if not await self._check_admin(interaction): return
        member = interaction.guild.get_member(self.user_id)
        if not member: return
        await interaction.response.defer()
        await member.add_roles(interaction.guild.get_role(TIER_2_ROLE_ID))
        await self._send_result_log(interaction, member, "Tier II", "success")
        for child in self.children: child.disabled = True
        await interaction.edit_original_response(view=self)

    @button(label="Отклонить", style=ButtonStyle.danger, emoji="<:cross:1473380950770716836>")
    async def reject(self, button: Button, interaction: Interaction):
        if not await self._check_admin(interaction): return
        member = interaction.guild.get_member(self.user_id)
        if member: await self._send_result_log(interaction, member, "Квалификацию", "reject")
        for child in self.children: child.disabled = True
        await interaction.response.edit_message(view=self)

class AppModal(Modal):
    def __init__(self, app_type: str):
        self.app_type = app_type
        title = "Анкета на Absolute" if app_type == "main" else "Анкета на Tier"
        components = [
            TextInput(label="Ваша информация", custom_id="info", style=TextInputStyle.paragraph, placeholder="Ник, стаж, почему вы достойны...", required=True),
            TextInput(label="Доказательства", custom_id="proofs", placeholder="Ссылки на отчеты/видео", required=True)
        ]
        super().__init__(title=title, components=components)

    async def callback(self, interaction: disnake.ModalInteraction):
        admin_channel_id = MAIN_ADMIN_CHANNEL_ID if self.app_type == "main" else TIER_ADMIN_CHANNEL_ID
        channel = interaction.guild.get_channel(admin_channel_id)
        
        embed = Embed(title=f"Новая заявка: {self.app_type.upper()}", color=FAM_COLOR, timestamp=datetime.now())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Участник", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        embed.add_field(name="Информация", value=f"```\n{interaction.text_values['info']}\n```", inline=False)
        embed.add_field(name="Доказательства", value=f"```\n{interaction.text_values['proofs']}\n```", inline=False)
        
        # Thumbnail аватара пользователя для формы админа
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        view = ApplicationDecisionView(interaction.user.id, self.app_type)
        if self.app_type == "main":
            view.remove_item(view.accept_t1); view.remove_item(view.accept_t2)
        else:
            view.remove_item(view.accept_main)

        await channel.send(embed=embed, view=view)
        await interaction.response.send_message("Ваша анкета была успешно передана руководству!", ephemeral=True)

class MainMenuView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @button(label="Подать на Main", style=ButtonStyle.success, emoji="<:freeiconcrow2185402:1473395821226754283>", custom_id="btn_main_app")
    async def apply_main(self, b, i): await i.response.send_modal(AppModal("main"))

    @button(label="Подать на Tier", style=ButtonStyle.primary, emoji="<:freeiconanimal15636581:1473395822484787354>", custom_id="btn_tier_app")
    async def apply_tier(self, b, i): await i.response.send_modal(AppModal("tier"))

class ApplicationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(MainMenuView())
        channel = self.bot.get_channel(ACADEMY_REQUEST_CHANNEL_ID)
        if channel:
            embed = Embed(title="Повышение", color=FAM_COLOR)
            embed.description = (
                "Приветствуем в системе повышения\n\n"
                "<:freeiconcrow2185402:1473395821226754283> **Повышение до Absolute**\n"
                "Для повышения c young до absolute оставьте заявку\n\n"
                "<:freeiconanimal15636581:1473395822484787354> **Повышение Tier**\n"
                "Для получения tier оставьте заявку"
            )
            
            if channel.guild.icon:
                embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1462165491278938204/1473396730803392713/free-icon-crow-3599008.png?ex=69960f23&is=6994bda3&hm=849d7df0a86831c679e5e2a43bcbe3d4fae1228c028ebad48c6eb610ba6db1fb&")
            
            embed.set_footer(text="Заявки рассматриваются руководством в течение 24 часов.")

            last_msg = None
            async for msg in channel.history(limit=5):
                if msg.author == self.bot.user and msg.embeds and msg.embeds[0].title == "Повышение":
                    last_msg = msg; break
            if last_msg: await last_msg.edit(embed=embed, view=MainMenuView())
            else: await channel.purge(limit=2); await channel.send(embed=embed, view=MainMenuView())

def setup(bot):
    bot.add_cog(ApplicationCog(bot))
