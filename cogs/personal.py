import disnake
from disnake.ext import commands
from disnake import Embed, TextInputStyle, Interaction, ButtonStyle, CategoryChannel
from disnake.ui import View, button, Button
from disnake.errors import HTTPException
from datetime import datetime
from constants import *
from database import get_private_channel, set_private_channel

class PersonalChannelModal(disnake.ui.Modal):
    def __init__(self):
        components = [
            disnake.ui.TextInput(
                label="Ссылка на материал (YouTube/Imgur)",
                custom_id="media_link",
                style=TextInputStyle.short,
                required=True,
                placeholder="https://www.youtube.com/... или https://imgur.com/...",
            )
        ]
        super().__init__(title="Запрос личного канала", components=components, timeout=300)

    async def callback(self, interaction: disnake.ModalInteraction):
        try:
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message("❌ Ошибка: сервер не найден!", ephemeral=True)
                return

            category = guild.get_channel(CATEGORY_ID)
            if not category or not isinstance(category, CategoryChannel):
                await interaction.response.send_message("❌ Категория не найдена!", ephemeral=True)
                return

            media_link = interaction.text_values["media_link"]

            # Логика с лимитом 50 каналов
            if len(category.channels) >= 50:
                category_name_base = category.name if category else "Личные каналы"
                new_category = None
                category_index = 1

                for cat in guild.categories:
                    if cat.name.startswith(category_name_base) and len(cat.channels) < 50:
                        new_category = cat
                        break

                if not new_category:
                    while True:
                        new_category_name = f"{category_name_base} {category_index}" if category_index > 1 else category_name_base
                        try:
                            new_category = await guild.create_category(
                                name=new_category_name, reason="Достигнут лимит каналов в категории (50)"
                            )
                            if category:
                                for target, permission_overwrite in category.overwrites.items():
                                    await new_category.set_permissions(target, overwrite=permission_overwrite)
                            break
                        except HTTPException as http_err:
                            if http_err.code == 50035 and "Maximum number" in str(http_err):
                                category_index += 1
                                continue
                            elif http_err.code == 50035 and "Guild has reached" in str(http_err):
                                await interaction.response.send_message(
                                    "❌ Сервер достиг максимального количества каналов!", ephemeral=True
                                )
                                return
                            raise

                category = new_category

            user_id = str(interaction.user.id)
            personal_channel = None

            channel_id = get_private_channel(user_id)
            if channel_id:
                personal_channel = guild.get_channel(channel_id)

            if not personal_channel:
                personal_channel = await guild.create_text_channel(
                    name=f"{interaction.user.display_name}",
                    category=category,
                    reason="Создание личного канала",
                )
                await personal_channel.set_permissions(guild.default_role, view_channel=False)
                await personal_channel.set_permissions(interaction.user, view_channel=True)

                role = guild.get_role(PRIVATE_THREAD_ROLE_ID)
                if role:
                    await personal_channel.set_permissions(role, view_channel=True)

                set_private_channel(user_id, personal_channel.id)

            # Эмбед с материалом
            embed = Embed(
                title="🔹 Новый материал",
                description=(
                    f"**Автор:** {interaction.user.mention}\n"
                    f"**Ссылка:** {media_link}\n"
                ),
                color=0x3A3B3C,
                timestamp=datetime.now(),
            )
            embed.set_footer(text=f"Размещено {interaction.user.display_name}")
            embed.set_thumbnail(url=interaction.user.display_avatar.url)

            await personal_channel.send(embed=embed)

            # Подтверждение
            confirm_embed = Embed(
                title="✅ Материал размещён!",
                description=f"Ваш материал опубликован в канале {personal_channel.mention}.",
                color=0x3BA55D,
                timestamp=datetime.now(),
            )
            await interaction.response.send_message(embed=confirm_embed, ephemeral=True)

        except Exception as e:
            print(f"Ошибка в PersonalChannelModal: {e}")
            error_embed = Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при создании канала или размещении материала.",
                color=0xFF0000,
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class PersonalChannelButtons(View):
    def __init__(self):
        super().__init__(timeout=None)

    @button(label="💬 Запросить канал", style=ButtonStyle.primary, custom_id="personal_channel_button")
    async def personal_channel_button(self, button: Button, interaction: Interaction):
        await interaction.response.send_modal(PersonalChannelModal())

class PersonalCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Настройка канала личных каналов при запуске"""
        try:
            personal_channel = self.bot.get_channel(PERSONAL_CHANNEL_REQUEST_ID)
            if personal_channel:
                await personal_channel.purge(limit=10)
                embed = Embed(
                    title="💬 Личные каналы",
                    description="Запросите создание личного канала для размещения ваших материалов.",
                    color=0x3A3B3C,
                )
                await personal_channel.send(embed=embed)
                await personal_channel.send(view=PersonalChannelButtons())
                print("✅ [Personal] Канал личных каналов настроен")
        except Exception as e:
            print(f"❌ [Personal] Ошибка при настройке: {e}")

def setup(bot):
    bot.add_cog(PersonalCog(bot))
