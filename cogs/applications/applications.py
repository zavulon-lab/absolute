import disnake
from disnake.ext import commands
from disnake import Embed

from .review_view import ApplicationReviewView
from .admin_panel import ApplicationAdminView
from .submit_button import ApplicationChannelView

try:
    from constants import APPLICATION_CHANNEL_ID, APPLICATION_ADMIN_PANEL_ID
except ImportError:
    print("Constants file not found!")
    APPLICATION_CHANNEL_ID = 0
    APPLICATION_ADMIN_PANEL_ID = 0

class ApplicationsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Ждем готовности бота, чтобы кэш каналов прогрузился
        await self.bot.wait_until_ready()
        
        print("="*30)
        print("[Applications] Запуск восстановления View...")

        # 1. Регистрируем View для кнопок (Persistent Views)
        try:
            self.bot.add_view(ApplicationReviewView())
            self.bot.add_view(ApplicationChannelView(self.bot))
            self.bot.add_view(ApplicationAdminView())
            print("[Applications] Кнопки успешно зарегистрированы!")
        except Exception as e:
            print(f"[Applications] Ошибка регистрации кнопок: {e}")

        # 2. Обновляем каналы (Заявки и Админка)
        await self.setup_channels()

    async def setup_channels(self):
        # --- КАНАЛ ПОДАЧИ ЗАЯВОК ---
        if APPLICATION_CHANNEL_ID:
            # Используем fetch_channel для надежности
            try:
                app_channel = await self.bot.fetch_channel(APPLICATION_CHANNEL_ID)
                await self.setup_application_channel(app_channel)
            except Exception as e:
                print(f"[Applications] ⚠️ Канал заявок {APPLICATION_CHANNEL_ID} не найден или недоступен: {e}")

        # --- АДМИН ПАНЕЛЬ ---
        if APPLICATION_ADMIN_PANEL_ID:
            try:
                admin_channel = await self.bot.fetch_channel(APPLICATION_ADMIN_PANEL_ID)
                await self.setup_admin_channel(admin_channel)
            except Exception as e:
                print(f"[Applications] ⚠️ Админ-канал {APPLICATION_ADMIN_PANEL_ID} не найден или недоступен: {e}")

    async def setup_application_channel(self, channel):
        # Проверяем последние сообщения
        last_msg = None
        async for msg in channel.history(limit=5):
            if msg.author == self.bot.user:
                last_msg = msg
                break
        
        embed = Embed(
            title="<:freeiconhand2866069:1473359285294596186> Оформление заявки в семью.",
            description=(
                "Уведомление о приглашении на обзвон отправляется в личные сообщения.\n\n"
                "> В среднем заявки обрабатываются в течение 1–2 дней — всё зависит от загруженности.\n\n"
                "Следите за статусом набора. **Если возможности заполнить заявку нет – набор закрыт. Каждое открытие набора сопровождается тегами в этом канале.**\n\n"
                "> В случае отказа можете подать заявку повторно через 7 дней\n\n"
                "Подавай заявку! Мы ждем именно **тебя**."
            ),
            color=disnake.Color.from_rgb(54, 57, 63)
        )
        embed.set_image(url= "https://cdn.discordapp.com/attachments/1462165491278938204/1473370136760029381/C2631068-A343-4D38-8D63-9BAA2DC0CE29.png?ex=6995f65e&is=6994a4de&hm=2856ce0f47daf9e26ab1f2cbd5e4fbca6c9738215ba76f5a59c2db3df8834b27&")
        embed.set_footer(text="Absolute Famq", icon_url=self.bot.user.display_avatar.url)
        
        view = ApplicationChannelView(self.bot)

        if last_msg:
            try:
                await last_msg.edit(embed=embed, view=view)
                print(f"[Applications] Сообщение в '{channel.name}' обновлено.")
            except:
                await channel.send(embed=embed, view=view)
        else:
            await channel.send(embed=embed, view=view)
            print(f"[Applications] Сообщение в '{channel.name}' создано.")

    async def setup_admin_channel(self, channel):
        last_msg = None
        async for msg in channel.history(limit=5):
            if msg.author == self.bot.user:
                last_msg = msg
                break

        embed = Embed(
            title="<:freeiconsermon7515746:1473373077818573012> Управление заявками",
            description=(
                "Добро пожаловать в панель управления набором!\n"
                "Здесь вы можете настроить статус приема заявок, изменить вопросы анкеты и управлять процессом рекрутинга.\n\n"
                " **Доступные действия:**\n"
                "<:freeiconrocket6699887:1473360986265227325> **Открыть набор** — Разрешить подачу заявок.\n"
                "<:freeiconmeteorite6699854:1473360985216782509> **Закрыть набор** — Временно приостановить прием.\n"
                "<:freeiconquestion5326501:1473361636046934198> **Редактировать вопросы** — Изменить анкету для кандидатов.\n"
                "<:freeicongravestone7515635:1473361769987707013> **Сброс** — Вернуть настройки по умолчанию."
            ),
            color=disnake.Color.from_rgb(54, 57, 63)
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1462165491278938204/1473373387928899584/free-icon-invitation-7515655.png?ex=6995f965&is=6994a7e5&hm=56a53a3c6c3f79af10ff230b87fbb0aa418ea715843bcfa7e72088def98cf93c&")
        embed.set_footer(text="Absolute famq", icon_url=self.bot.user.display_avatar.url)

        view = ApplicationAdminView()

        if last_msg:
            try:
                await last_msg.edit(embed=embed, view=view)
                print(f"[Applications] Админ-панель обновлена.")
            except:
                await channel.send(embed=embed, view=view)
        else:
            await channel.send(embed=embed, view=view)
            print(f"[Applications] Админ-панель создана.")

def setup(bot):
    bot.add_cog(ApplicationsCog(bot))
