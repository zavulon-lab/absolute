import disnake
from disnake.ext import commands
from disnake import Embed, Interaction, ButtonStyle
from disnake.ui import View, Button, button
import sys
import os

# Импорт констант
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from constants import PERSONAL_CHANNEL_REQUEST_ID
except ImportError:
    PERSONAL_CHANNEL_REQUEST_ID = 0

# Импорт ваших вьюшек
from .vacation import VacationActionsView
from .portfolio import PortfolioView
from .verification import VerificationView

# --- ВАЖНО: Импорт логики откатов из соседнего кога ---
# Убедитесь, что путь правильный (cogs.management.cog)
try:
    from cogs.management import RollbackGuideView
except ImportError:
    print("⚠️ [Personal] Не удалось импортировать RollbackGuideView. Кнопка откатов не будет работать.")
    class RollbackGuideView(View): pass 


class MainMenuButtons(View):
    def __init__(self):
        super().__init__(timeout=None)

    @button(label="Отпуск", style=ButtonStyle.secondary, emoji="<:freeicontravel9494750:1473389342092165211>", custom_id="btn_main_vacation")
    async def vacation_btn(self, button: Button, interaction: Interaction):
        embed = Embed(
            title="<:freeicontravel9494750:1473389342092165211> Подать заявку на отпуск",
            description=(
                "Устали от игры или есть другие причины взять паузу? Просто заполните анкету.\n\n"
                "• При отправке формы для отпуска с вас будут сняты все роли и выдана роль инактив\n"
                "• Когда будете готовы вернуться, нажмите кнопку \"Вернуться из отпуска\"."
            ),
            color=disnake.Color.from_rgb(54, 57, 63)
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1462165491278938204/1473389690903330996/free-icon-travel-2832064.png?ex=69960894&is=6994b714&hm=d3904fe4aeae2451b9a724e70e91b4e397b3e7b0e09659d93e92f6d019d7b3ea&")
        
        # Добавляем футер
        embed.set_footer(text="Absolute Famq", icon_url=interaction.client.user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed, view=VacationActionsView(), ephemeral=True)


    @button(label="Создать портфель", style=ButtonStyle.gray, emoji="<:freeiconbriefcase3158116:1473390673054011529>", custom_id="btn_main_tier")
    async def tier_btn(self, button: Button, interaction: Interaction):
        embed = Embed(
            title="<:freeiconbriefcase3158116:1473390673054011529> Создание портфеля",
            description=(
                "• В приватном канале люди с опытом отслеживают вашу активность и прогресс.\n"
                "• Видеоматериалы желательно заливать на [YouTube](https://youtube.com), [Rutube](https://rutube.ru)\n"
                "• Профиль можно создавать только один раз, после создания профиля откаты и скрины отправляйте в свой личный профиль"
            ),  
            color=disnake.Color.from_rgb(54, 57, 63) 
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1462165491278938204/1473390908429963334/free-icon-documents-1548205.png?ex=699609b6&is=6994b836&hm=71ed9aef4240a96d060d89400117674b5fbce66a6737bf9cfd7bcf75e8c6c6e9&") 
        
        # Добавляем футер
        embed.set_footer(text="Absolute Famq", icon_url=interaction.client.user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed, view=PortfolioView(), ephemeral=True)


    @button(label="Верификация", style=ButtonStyle.gray, emoji="<:freeiconproofing10988140:1473391799321104485>", custom_id="btn_main_verif")
    async def verif_btn(self, button: Button, interaction: Interaction):
        embed = Embed(
            title="<:freeiconproofing10988140:1473391799321104485> Проверка на ПО",
            description=(
                "Для доступа к закрытым мероприятиям (капт, mcl) необходимо пройти полную проверку.\n\n"
                " **Этапы проверки:**\n"
                "> **Запрос:** Нажмите «Подать запрос» в меню ниже и укажите причину.\n"
                "> **Рассмотрение:** Модераторы проверят вашу заявку.\n"
                "> **Проверка:** Вас вызовут в голосовой канал для проверки на стороннее ПО (читы, макросы).\n\n"
                "• *Любая попытка скрыть софт, отказ от проверки или выход из игры во время вызова приведет к бану и ЧС семьи.*"
            ),
            color=disnake.Color.from_rgb(54, 57, 63)
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1462165491278938204/1473392052283637933/free-icon-checking-3712161.png?ex=69960ac7&is=6994b947&hm=6e371a0f967b11f702cc2187ef1dc744afc639bcc88559a40fafc85a9a23afdd&")
            
        embed.set_footer(text="Absolute Famq", icon_url=interaction.client.user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed, view=VerificationView(), ephemeral=True)


    # --- КНОПКА ОТКАТОВ (С ГАЙДОМ) ---
    @button(label="Оформить откат", style=ButtonStyle.gray, emoji="<:freeiconvideoplayer1376287:1473393337460457585>", custom_id="btn_main_rollback")
    async def rollback_btn(self, button: Button, interaction: Interaction):
        embed = Embed(
            title="<:freeiconvideoplayer1376287:1473393337460457585> Как оформить откат",
            description=(
                "**Инструкция:**\n"
                "> 1. Залейте видео на хостинг.\n"
                "> 2. Скопируйте ссылку.\n"
                "> 3. Подготовьте таймкоды (если нужно).\n\n"
                "**Выберите тип мероприятия в меню ниже:**"
            ),
            color=disnake.Color.from_rgb(54, 57, 63)
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1462165491278938204/1473393444591374510/free-icon-video-editing-1424733.png?ex=69960c13&is=6994ba93&hm=ada95bd44f2c339dcd3a5f560175a6aa03d275bf787a34ccd816830d8f5434e9&")
        
        embed.set_footer(text="Absolute Famq", icon_url=interaction.client.user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed, view=RollbackGuideView(), ephemeral=True)



class PersonalCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            channel = self.bot.get_channel(PERSONAL_CHANNEL_REQUEST_ID)
            if channel:
                self.bot.add_view(MainMenuButtons())
                
                await channel.purge(limit=10)
                
                embed = Embed(
                    title="Взаимодействие с функционалом бота",
                    description=(
                        "> **Отпуск** — Взять долгосрочный отпуск, отдых от игры\n"
                        "> **Тир** — Создание портфеля, получить Tier роль\n"
                        "> **Верификация** — Пройти проверку для доступа к каптам\n"
                        "> **Откат** — Загрузить запись с мероприятия"
                    ),
                    color=disnake.Color.from_rgb(54, 57, 63)
                )

                # Установка маленькой иконки справа (thumbnail)
                embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1462165491278938204/1473388872598552707/free-icon-boss-265674.png?ex=699607d1&is=6994b651&hm=5eb2c25aa5b83690f4fcc008069d110e06d9557772a8e25756ba77fe603b383a&") 

                # Футер с названием семьи и аватаркой бота
                embed.set_footer(text="Absolute Famq", icon_url=self.bot.user.display_avatar.url)

                
                await channel.send(embed=embed, view=MainMenuButtons())
                print("[Personal] Главное меню обновлено")
        except Exception as e:
            print(f"[Personal] Ошибка: {e}")



def setup(bot):
    bot.add_cog(PersonalCog(bot))
