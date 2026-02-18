import disnake
from disnake.ui import Modal, TextInput
from disnake import TextInputStyle, Embed, Interaction
from datetime import datetime
from constants import APPLICATIONS_REVIEW_CHANNEL_ID, RECRUITER_ROLE_ID
from disnake.errors import Forbidden

# Пытаемся импортировать View для админов
try:
    from .review_view import ApplicationReviewView 
except ImportError:
    class ApplicationReviewView(disnake.ui.View): pass

class CompleteApplicationModal(Modal):
    """Модальное окно со ВСЕМИ полями формы (максимум 5)"""
    def __init__(self, bot, form_config: list, message_to_reset: disnake.Message = None):
        self.bot = bot
        self.message_to_reset = message_to_reset
        
        # 1. Создаем защищенную копию конфига для этого запуска
        self.safe_config = []
        used_ids = set()
        
        components = []
        
        # Берем только первые 5 полей (лимит Discord)
        for index, original_field in enumerate(form_config[:5]):
            # Делаем копию поля, чтобы не менять глобальные настройки
            field = original_field.copy()
            
            # --- ЛОГИКА УСТРАНЕНИЯ ДУБЛИКАТОВ ID ---
            cid = field["custom_id"]
            if cid in used_ids:
                # Если такой ID уже был, добавляем уникальный суффикс
                cid = f"{cid}_{index}"
            used_ids.add(cid)
            
            # Записываем уникальный ID в наше поле
            field["custom_id"] = cid
            self.safe_config.append(field)
            
            # Настройка стиля
            style_map = {
                "short": TextInputStyle.short,
                "paragraph": TextInputStyle.paragraph
            }
            
            if field.get("type") == "select_menu":
                options_text = " / ".join([opt["label"] for opt in field.get("options", [])[:5]])
                placeholder_text = f"Варианты: {options_text}"
                input_style = TextInputStyle.short
            else:
                placeholder_text = field.get("placeholder", "")
                input_style = style_map.get(field.get("style", "short"), TextInputStyle.short)
            
            text_input = TextInput(
                label=field["label"][:45],
                custom_id=cid, # Используем проверенный уникальный ID
                style=input_style,
                required=field["required"],
                placeholder=placeholder_text[:100],
                min_length=field.get("min_length"),
                max_length=field.get("max_length") if field.get("type") == "text_input" else 200
            )
            components.append(text_input)
        
        super().__init__(
            title="Форма заявки",
            components=components,
            timeout=600
        )
    
    async def callback(self, interaction: Interaction):
        # 1. Откладываем ответ
        await interaction.response.defer(ephemeral=True)

        # 2. Сброс меню выбора (если нужно)
        if self.message_to_reset:
            try:
                from .submit_button import ApplicationChannelView
                await self.message_to_reset.edit(view=ApplicationChannelView(self.bot))
            except Exception as e:
                print(f"[Warning] Не удалось сбросить меню: {e}")

        try:
            guild = interaction.guild
            if not guild:
                await interaction.followup.send(embed=Embed(title="Ошибка", description="Сервер не найден!", color=0xED4245), ephemeral=True)
                return

            review_channel = guild.get_channel(APPLICATIONS_REVIEW_CHANNEL_ID)
            if not review_channel:
                await interaction.followup.send(embed=Embed(title="Ошибка конфигурации", description="Канал для заявок не найден.", color=0xED4245), ephemeral=True)
                return

            # Собираем ответы, используя self.safe_config (там правильные ID)
            form_data = {}
            for field in self.safe_config:
                # Получаем значение по уникальному ID
                val = interaction.text_values.get(field["custom_id"], "Не указано")
                form_data[field["custom_id"]] = val

            # --- ЭМБЕД ЗАЯВКИ ---
            embed = Embed(
                title="Новая заявка на вступление",
                color=disnake.Color.from_rgb(54, 57, 63),
                timestamp=datetime.now(),
            )
            
            for field in self.safe_config:
                embed.add_field(
                    name=field['label'],
                    value=f"```{form_data.get(field['custom_id'], 'Не указано')}```",
                    inline=False
                )

            # Информация о пользователе
            created_at = interaction.user.created_at.replace(tzinfo=None)
            now = datetime.now()
            delta = now - created_at
            years = delta.days // 365
            days = delta.days % 365
            account_age_str = f"{years} лет" if years > 0 else f"{days} дней"

            user_info = (
                f"**Пользователь:** {interaction.user.mention}\n"
                f"**ID:** `{interaction.user.id}`\n"
                f"**Возраст аккаунта:** {account_age_str}"
            )
            embed.add_field(name="<:freeiconsermon7515746:1473373077818573012> Информация об аккаунте", value=user_info, inline=False)

            embed.set_footer(text="Absolute Famq • Заявка", icon_url=self.bot.user.display_avatar.url)
            embed.set_thumbnail(url=interaction.user.display_avatar.url)

            staff_role = guild.get_role(RECRUITER_ROLE_ID)
            mention = staff_role.mention if staff_role else ""

            await review_channel.send(content=mention, embed=embed, view=ApplicationReviewView())

            # --- ОТВЕТ ПОЛЬЗОВАТЕЛЮ ---
            confirm_embed = Embed(
                title="Заявка успешно отправлена!",
                description=(
                    "Ваша заявка отправлена.\n"
                    "Ожидайте дальнейших действий, уведомления приходят в личные сообщения."
                ),
                color=disnake.Color.from_rgb(54, 57, 63)
            )
            await interaction.followup.send(embed=confirm_embed, ephemeral=True)

            try:
                dm_embed = Embed(
                    title="Ваша заявка отправлена!",
                    description=(
                        "Ожидайте дальнейших действий от администрации.\n"
                        "Мы свяжемся с вами в ближайшее время."
                    ),
                    color=disnake.Color.from_rgb(54, 57, 63)
                )
                dm_embed.set_footer(text="Absolute Famq", icon_url=self.bot.user.display_avatar.url)
                await interaction.user.send(embed=dm_embed)
            except Forbidden:
                pass

        except Exception as e:
            print(f"[ERROR] Ошибка в CompleteApplicationModal: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(embed=Embed(title="Ошибка", description="Произошла ошибка при отправке заявки.", color=0xFF0000), ephemeral=True)
