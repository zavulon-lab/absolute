import disnake
from disnake.ext import commands
from disnake import Embed, TextInputStyle, Interaction, ButtonStyle, CategoryChannel, TextChannel, SelectOption
from disnake.ui import View, button, Button, Select
from disnake.errors import NotFound
from datetime import datetime
from constants import *
from database import add_created_channel, get_private_channel, set_private_channel, channel_exists, delete_created_channel

class RollbackForm(disnake.ui.Modal):
    def __init__(self, channel: TextChannel):
        self.channel = channel

        components = [
            disnake.ui.TextInput(
                label="Детали отката",
                custom_id="rollback_details",
                style=TextInputStyle.paragraph,
                required=True,
                placeholder="Опишите детали отката...",
            )
        ]
        super().__init__(title="Форма отката", components=components, timeout=300)

    async def callback(self, interaction: disnake.ModalInteraction):
        await interaction.response.defer(ephemeral=True)

        try:
            guild = interaction.guild
            if not guild:
                await interaction.followup.send("❌ Ошибка: сервер не найден!", ephemeral=True)
                return

            rollback_details = interaction.text_values["rollback_details"]

            # Эмбед для публичного канала
            public_embed = Embed(
                title="🔄 Откат отправлен",
                description=(
                    f"**Детали:**\n{rollback_details}\n\n"
                    f"**Отправитель:** {interaction.user.mention}"
                ),
                color=0x3A3B3C,
                timestamp=datetime.now(),
            )
            public_embed.set_footer(text=f"Откат от {interaction.user.display_name}")
            await self.channel.send(embed=public_embed)

            private_channel = guild.get_channel(PRIVATE_CHANNEL_ID)
            if not private_channel:
                await interaction.followup.send("❌ Приватный канал не найден!", ephemeral=True)
                return

            user_id = str(interaction.user.id)
            channel_id = get_private_channel(user_id)

            if channel_id:
                private_channel_instance = guild.get_channel(channel_id)
            else:
                private_channel_instance = None

            if not private_channel_instance:
                private_channel_instance = await guild.create_text_channel(
                    name=f"{interaction.user.name}",
                    category=guild.get_channel(CATEGORY_ID),
                    reason="Создание приватного канала",
                )
                await private_channel_instance.set_permissions(guild.default_role, view_channel=False)
                await private_channel_instance.set_permissions(interaction.user, view_channel=True)

                role = guild.get_role(PRIVATE_THREAD_ROLE_ID)
                if role:
                    await private_channel_instance.set_permissions(role, view_channel=True)

                set_private_channel(user_id, private_channel_instance.id)

            # Эмбед для приватного канала
            private_embed = Embed(
                title="🔄 Копия отката",
                description=(
                    f"**Канал:** {self.channel.mention}\n"
                    f"**Детали:**\n{rollback_details}"
                ),
                color=0x3A3B3C,
                timestamp=datetime.now(),
            )
            private_embed.set_footer(text=f"Откат от {interaction.user.display_name}")
            await private_channel_instance.send(embed=private_embed)

            # Подтверждение
            confirm_embed = Embed(
                title="✅ Откат отправлен!",
                description=f"Откат опубликован в {self.channel.mention} и продублирован в ваш личный канал {private_channel_instance.mention}.",
                color=0x3BA55D,
                timestamp=datetime.now(),
            )
            await interaction.followup.send(embed=confirm_embed, ephemeral=True)

        except NotFound:
            await interaction.followup.send("❌ Канал не найден. Возможно, он был удалён.", ephemeral=True)
        except Exception as e:
            print(f"Ошибка в RollbackForm: {e}")
            error_embed = Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при отправке отката.",
                color=0xFF0000,
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class CreateChannelModal(disnake.ui.Modal):
    def __init__(self, category: CategoryChannel, bot):
        self.category = category
        self.bot = bot

        components = [
            disnake.ui.TextInput(
                label="Название канала",
                custom_id="nickname",
                style=TextInputStyle.short,
                required=True,
                max_length=50,
                placeholder="например: my-channel",
            )
        ]

        super().__init__(
            title="Создание канала",
            components=components,
            timeout=300,
        )

    async def callback(self, interaction: disnake.ModalInteraction):
        try:
            if len(self.category.channels) >= 50:
                await interaction.response.send_message("❌ В этой категории уже 50 каналов!", ephemeral=True)
                return

            nickname = interaction.text_values["nickname"]
            channel_name = nickname.lower().replace(" ", "-")

            channel = await interaction.guild.create_text_channel(
                name=channel_name,
                category=self.category,
                reason="Создание канала администратором",
            )

            add_created_channel(channel.id, interaction.user.id, channel.name)
            self.bot.created_channels_cache[channel.id] = {"channel": channel, "creator": interaction.user}

            # Подтверждение с эмбедом
            embed = Embed(
                title="✅ Канал создан",
                description=(
                    f"**Название:** `{nickname}`\n"
                    f"**Категория:** {self.category.name}\n"
                    f"**Создатель:** {interaction.user.mention}\n"
                    f"**Канал:** {channel.mention}"
                ),
                color=0x3BA55D,
                timestamp=datetime.now(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            print(f"Ошибка в CreateChannelModal: {e}")
            error_embed = Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при создании канала.",
                color=0xFF0000,
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class ChannelSelect(Select):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(
            placeholder="Выберите категорию...",
            options=[
                SelectOption(label="Категория 1", value=str(CATEGORY_1_ID)),
                SelectOption(label="Категория 2", value=str(CATEGORY_2_ID)),
            ],
        )

    async def callback(self, interaction: Interaction):
        selected_category_id = int(self.values[0])
        selected_category = interaction.guild.get_channel(selected_category_id)

        if not selected_category or not isinstance(selected_category, CategoryChannel):
            await interaction.response.send_message("❌ Категория не найдена!", ephemeral=True)
            return

        if len(selected_category.channels) >= 50:
            await interaction.response.send_message("❌ В этой категории уже 50 каналов!", ephemeral=True)
            return

        await interaction.response.send_modal(CreateChannelModal(selected_category, self.bot))

class ChannelSelectView(View):
    def __init__(self, channels_category1=None, channels_category2=None):
        super().__init__()

        if channels_category1 is None:
            channels_category1 = []
        if channels_category2 is None:
            channels_category2 = []

        if channels_category1:
            for i in range(0, len(channels_category1), 25):
                group = channels_category1[i : i + 25]
                options_category1 = [SelectOption(label=channel.name, value=str(channel.id)) for channel in group]
                select_category1 = Select(
                    custom_id=f"category1_select_{i}", placeholder=f"Категория 1 (каналы {i + 1}+)", options=options_category1
                )
                select_category1.callback = self.on_select_category1
                self.add_item(select_category1)

        if channels_category2:
            for i in range(0, len(channels_category2), 25):
                group = channels_category2[i : i + 25]
                options_category2 = [SelectOption(label=channel.name, value=str(channel.id)) for channel in group]
                select_category2 = Select(
                    custom_id=f"category2_select_{i}", placeholder=f"Категория 2 (каналы {i + 1}+)", options=options_category2
                )
                select_category2.callback = self.on_select_category2
                self.add_item(select_category2)

    async def on_select_category1(self, interaction: Interaction):
        selected_channel_id = int(interaction.data["values"][0])
        selected_channel = interaction.guild.get_channel(selected_channel_id)

        if selected_channel:
            await interaction.response.send_modal(RollbackForm(selected_channel))
        else:
            await interaction.response.send_message("❌ Канал не найден.", ephemeral=True)

    async def on_select_category2(self, interaction: Interaction):
        selected_channel_id = int(interaction.data["values"][0])
        selected_channel = interaction.guild.get_channel(selected_channel_id)

        if selected_channel:
            await interaction.response.send_modal(RollbackForm(selected_channel))
        else:
            await interaction.response.send_message("❌ Канал не найден.", ephemeral=True)

class MainChannelButtons(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @button(label="🔄 Откат", style=ButtonStyle.success, custom_id="send_rollback_button")
    async def send_rollback_button(self, button: Button, interaction: Interaction):
        try:
            await interaction.response.defer(ephemeral=True)

            category1 = interaction.guild.get_channel(CATEGORY_1_ID)
            category2 = interaction.guild.get_channel(CATEGORY_2_ID)

            if not category1 or not category2:
                await interaction.followup.send("❌ Категории не найдены!", ephemeral=True)
                return

            channels_category1 = sorted(
                [channel for channel in category1.channels if isinstance(channel, TextChannel)],
                key=lambda x: x.created_at,
                reverse=True,
            )
            channels_category2 = sorted(
                [channel for channel in category2.channels if isinstance(channel, TextChannel)],
                key=lambda x: x.created_at,
                reverse=True,
            )

            if not channels_category1 and not channels_category2:
                await interaction.followup.send("❌ Нет каналов для отката!", ephemeral=True)
                return

            view = ChannelSelectView(channels_category1, channels_category2)
            await interaction.followup.send("Выберите канал для отката:", view=view, ephemeral=True)

        except Exception as e:
            print(f"Ошибка в send_rollback_button: {e}")
            await interaction.followup.send("❌ Произошла ошибка.", ephemeral=True)

    @button(label="➕ Создать канал", style=ButtonStyle.primary, custom_id="create_channel_button")
    async def create_channel_button(self, button: Button, interaction: Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ У вас нет прав!", ephemeral=True)
            return

        view = View()
        view.add_item(ChannelSelect(self.bot))
        await interaction.response.send_message("Выберите категорию:", view=view, ephemeral=True)

class ManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Настройка главного канала при запуске"""
        try:
            main_channel = self.bot.get_channel(MAIN_CHANNEL_ID)
            if main_channel:
                await main_channel.purge(limit=10)
                embed = Embed(
                    title="🎮 Главная панель",
                    description="Выберите действие из списка ниже:",
                    color=0x3A3B3C,
                )
                await main_channel.send(embed=embed)
                await main_channel.send(view=MainChannelButtons(self.bot))
                print("✅ [Management] Главный канал настроен")
        except Exception as e:
            print(f"❌ [Management] Ошибка при настройке: {e}")

    @commands.Cog.listener()
    async def on_channel_delete(self, channel):
        """Удаление канала из кэша и БД при удалении"""
        if channel.id in self.bot.created_channels_cache:
            del self.bot.created_channels_cache[channel.id]
        
        if channel_exists(channel.id):
            delete_created_channel(channel.id)

def setup(bot):
    bot.add_cog(ManagementCog(bot))
