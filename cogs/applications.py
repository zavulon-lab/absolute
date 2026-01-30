import disnake
from disnake.ext import commands
from disnake import Embed, TextInputStyle, CategoryChannel, Interaction, ButtonStyle, SelectOption
from disnake.ui import View, button, Button, Modal, TextInput, StringSelect
from datetime import datetime
from constants import *
from database import add_created_channel, save_application_form, get_application_form

# ==================== ФУНКЦИЯ МИГРАЦИИ ====================

def migrate_old_form_data(form_config: list) -> list:
    """Добавляет поле 'type' к старым записям без него"""
    migrated = []
    for field in form_config:
        if "type" not in field:
            if "options" in field and len(field.get("options", [])) > 0:
                field["type"] = "select_menu"
            else:
                field["type"] = "text_input"
                if "options" not in field:
                    field["options"] = []
        migrated.append(field)
    return migrated

# ==================== ЕДИНОЕ МОДАЛЬНОЕ ОКНО ДЛЯ ФОРМЫ ====================

class CompleteApplicationModal(Modal):
    """Модальное окно со ВСЕМИ полями формы (максимум 5)"""
    def __init__(self, bot, form_config: list):
        self.bot = bot
        self.form_config = form_config
        
        components = []
        
        # Берём первые 5 полей (ограничение Discord)
        for field in form_config[:5]:
            style_map = {
                "short": TextInputStyle.short,
                "paragraph": TextInputStyle.paragraph
            }
            
            # Для селект-меню показываем варианты в placeholder
            if field.get("type") == "select_menu":
                options_text = " / ".join([opt["label"] for opt in field.get("options", [])[:5]])
                placeholder_text = f"Варианты: {options_text}"
                input_style = TextInputStyle.short
            else:
                placeholder_text = field.get("placeholder", "")
                input_style = style_map.get(field.get("style", "short"), TextInputStyle.short)
            
            text_input = TextInput(
                label=field["label"],
                custom_id=field["custom_id"],
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

            # Собираем данные из формы
            form_data = {}
            for field in self.form_config[:5]:
                form_data[field["custom_id"]] = interaction.text_values.get(field["custom_id"], "Не указано")

            # Создаём название канала
            first_value = list(form_data.values())[0] if form_data else "заявка"
            channel_name = f"заявка-{first_value.lower().replace(' ', '-')[:20]}"
            
            new_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                reason="Создание канала заявки"
            )

            # Настройка прав доступа
            role = guild.get_role(ROLE_ID)
            if role:
                await new_channel.set_permissions(guild.default_role, view_channel=False)
                await new_channel.set_permissions(role, view_channel=True)
                await new_channel.set_permissions(interaction.user, view_channel=True)

            # Формируем эмбед заявки
            description_parts = [
                f"**Кандидат:** {interaction.user.mention}",
                f"**ID:** `{interaction.user.id}`",
                ""
            ]
            
            for field in self.form_config[:5]:
                field_label = field["label"]
                field_value = form_data.get(field["custom_id"], "Не указано")
                description_parts.append(f"**{field_label}:** {field_value}")
            
            if role:
                description_parts.append(f"\n{role.mention}, пожалуйста, рассмотрите заявку.")

            embed = Embed(
                title="📋 Новая заявка на вступление",
                description="\n".join(description_parts),
                color=0x3A3B3C,
                timestamp=datetime.now(),
            )
            embed.set_footer(text=f"Заявка от {interaction.user.display_name}")
            embed.set_thumbnail(url=interaction.user.display_avatar.url)

            await new_channel.send(embed=embed)

            # Сохраняем в БД
            add_created_channel(new_channel.id, interaction.user.id, channel_name)
            self.bot.created_channels_cache[new_channel.id] = {
                "channel": new_channel,
                "creator": interaction.user
            }

            # Подтверждение пользователю
            confirm_embed = Embed(
                title="✅ Заявка успешно отправлена!",
                description=(
                    f"Ваша заявка создана в канале {new_channel.mention}.\n"
                    f"Администрация рассмотрит её в ближайшее время."
                ),
                color=0x3BA55D,
                timestamp=datetime.now(),
            )
            
            await interaction.response.send_message(embed=confirm_embed, ephemeral=True)

        except Exception as e:
            print(f"Ошибка в CompleteApplicationModal: {e}")
            import traceback
            traceback.print_exc()
            
            error_embed = Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при отправке заявки. Попробуйте снова.",
                color=0xFF0000,
            )
            
            try:
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
            except:
                await interaction.followup.send(embed=error_embed, ephemeral=True)

# ==================== КНОПКА ПОДАЧИ ЗАЯВКИ ====================

class ApplicationChannelButtons(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @button(label="📝 Подать заявку", style=ButtonStyle.primary, custom_id="submit_application_btn")
    async def submit_application_button(self, button: Button, interaction: Interaction):
        form_config = get_application_form()
        form_config = migrate_old_form_data(form_config)
        
        if not form_config:
            await interaction.response.send_message("❌ Форма не настроена!", ephemeral=True)
            return
        
        if len(form_config) > 5:
            # Предупреждение если полей больше 5
            warning_embed = Embed(
                title="⚠️ Внимание",
                description=f"В форме {len(form_config)} полей, но Discord позволяет показать только 5 за раз.\n\nБудут показаны первые 5 полей.",
                color=0xFFAA00
            )
            await interaction.response.send_message(embed=warning_embed, ephemeral=True)
            await interaction.followup.send_modal(CompleteApplicationModal(self.bot, form_config))
        else:
            await interaction.response.send_modal(CompleteApplicationModal(self.bot, form_config))

# ==================== АДМИН-ПАНЕЛЬ ====================

class FieldTypeSelectView(View):
    """View с селектом для выбора типа поля"""
    def __init__(self, field_index: int = None):
        super().__init__(timeout=300)
        self.field_index = field_index
        
        select = StringSelect(
            placeholder="Выберите тип поля...",
            options=[
                SelectOption(label="📝 Текстовое поле (короткое)", value="text_short", description="Однострочное текстовое поле", emoji="📝"),
                SelectOption(label="📄 Текстовое поле (длинное)", value="text_long", description="Многострочное текстовое поле", emoji="📄"),
            ],
            custom_id="field_type_select"
        )
        
        async def select_callback(interaction: Interaction):
            field_type = interaction.data["values"][0]
            
            if field_type == "text_short":
                await interaction.response.send_modal(TextFieldEditorModal(self.field_index, style="short"))
            elif field_type == "text_long":
                await interaction.response.send_modal(TextFieldEditorModal(self.field_index, style="paragraph"))
        
        select.callback = select_callback
        self.add_item(select)

class TextFieldEditorModal(Modal):
    """Редактор текстового поля"""
    def __init__(self, field_index: int = None, existing_field: dict = None, style: str = "short"):
        self.field_index = field_index
        self.is_new = field_index is None
        self.existing_field = existing_field
        self.style = style
        
        default_label = existing_field.get("label", "") if existing_field else ""
        default_custom_id = existing_field.get("custom_id", "") if existing_field else ""
        default_placeholder = existing_field.get("placeholder", "") if existing_field else ""
        default_emoji = existing_field.get("emoji", "📝") if existing_field else "📝"  # ← НОВОЕ
        
        components = [
            TextInput(
                label="Название поля",
                custom_id="field_label",
                style=TextInputStyle.short,
                required=True,
                max_length=45,
                value=default_label,
                placeholder="Например: Имя и фамилия"
            ),
            TextInput(
                label="ID поля (англ. буквы и _)",
                custom_id="field_custom_id",
                style=TextInputStyle.short,
                required=True,
                max_length=100,
                value=default_custom_id,
                placeholder="Например: full_name"
            ),
            TextInput(
                label="Эмодзи для поля",  # ← НОВОЕ ПОЛЕ
                custom_id="field_emoji",
                style=TextInputStyle.short,
                required=False,
                max_length=10,
                value=default_emoji,
                placeholder="Например: 💎 или 🏛️"
            ),
            TextInput(
                label="Подсказка (placeholder)",
                custom_id="field_placeholder",
                style=TextInputStyle.short,
                required=False,
                max_length=100,
                value=default_placeholder
            )
        ]
        
        title = f"➕ Добавить {'короткое' if style == 'short' else 'длинное'} поле" if self.is_new else f"✏️ Редактировать поле #{field_index + 1}"
        super().__init__(title=title, components=components, timeout=300)

    async def callback(self, interaction: disnake.ModalInteraction):
        try:
            # Показываем селект для обязательности
            required_view = View(timeout=60)
            required_select = StringSelect(
                placeholder="Выберите обязательность...",
                options=[
                    SelectOption(label="✅ Обязательное", value="yes", emoji="✅"),
                    SelectOption(label="❌ Необязательное", value="no", emoji="❌")
                ],
                custom_id="required_select"
            )
            
            async def required_callback(inter: Interaction):
                required_value = inter.data["values"][0]
                
                new_field = {
                    "type": "text_input",
                    "label": interaction.text_values["field_label"],
                    "custom_id": interaction.text_values["field_custom_id"],
                    "style": self.style,
                    "required": required_value == "yes",
                    "placeholder": interaction.text_values["field_placeholder"],
                    "emoji": interaction.text_values.get("field_emoji", "📝") or "📝",  # ← НОВОЕ
                    "min_length": None,
                    "max_length": None,
                    "options": []
                }
                
                current_form = get_application_form()
                current_form = migrate_old_form_data(current_form)
                
                if self.is_new:
                    current_form.append(new_field)
                else:
                    if self.field_index < len(current_form):
                        current_form[self.field_index] = new_field
                
                save_application_form(current_form)
                
                embed = Embed(
                    title="✅ Текстовое поле сохранено",
                    description=f"**Label:** {new_field['label']}\n**ID:** `{new_field['custom_id']}`\n**Эмодзи:** {new_field['emoji']}\n**Тип:** {new_field['style']}\n**Обязательное:** {'Да' if new_field['required'] else 'Нет'}",
                    color=0x3BA55D
                )
                await inter.response.send_message(embed=embed, ephemeral=True)
            
            required_select.callback = required_callback
            required_view.add_item(required_select)
            
            req_embed = Embed(
                title="Настройка обязательности",
                description="Выберите, обязательно ли это поле для заполнения:",
                color=0x5865F2
            )
            await interaction.response.send_message(embed=req_embed, view=required_view, ephemeral=True)
            
        except Exception as e:
            print(f"Ошибка в TextFieldEditorModal: {e}")
            import traceback
            traceback.print_exc()
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)


class FieldDeleteSelectView(View):
    """View с селектом для удаления поля"""
    def __init__(self):
        super().__init__(timeout=300)
        current_form = get_application_form()
        current_form = migrate_old_form_data(current_form)
        
        options = []
        for i, field in enumerate(current_form):
            emoji = "📝" if field.get("style") == "short" else "📄"
            options.append(
                SelectOption(
                    label=f"{i+1}. {field['label'][:40]}",
                    value=str(i),
                    description=f"ID: {field['custom_id']}",
                    emoji=emoji
                )
            )
        
        select = StringSelect(
            placeholder="Выберите поле для удаления...",
            options=options,
            custom_id="delete_field_select"
        )
        
        async def select_callback(interaction: Interaction):
            field_index = int(interaction.data["values"][0])
            
            current = get_application_form()
            current = migrate_old_form_data(current)
            
            if field_index < len(current):
                deleted_field = current.pop(field_index)
                save_application_form(current)
                
                embed = Embed(
                    title="✅ Поле удалено",
                    description=f"Удалено поле: **{deleted_field['label']}**",
                    color=0x3BA55D
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("❌ Поле не найдено!", ephemeral=True)
        
        select.callback = select_callback
        self.add_item(select)

class ApplicationAdminSelect(StringSelect):
    """Селект-меню админ-панели"""
    def __init__(self):
        options = [
            SelectOption(label="⚙️ Настроить форму", value="configure_form", description="Добавить/изменить/удалить поля"),
            SelectOption(label="📋 Посмотреть текущую форму", value="view_form", description="Показать все поля"),
            SelectOption(label="🗑️ Удалить конкретное поле", value="delete_field", description="Выбрать поле для удаления"),
            SelectOption(label="🔄 Сбросить до стандартной", value="reset_form", description="Вернуть дефолт"),
        ]
        
        super().__init__(
            placeholder="Выберите действие...",
            options=options,
            custom_id="application_admin_select"
        )

    async def callback(self, interaction: Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Только администраторы!", ephemeral=True)
            return
        
        choice = self.values[0]
        
        # Сбрасываем селект
        reset_view = ApplicationAdminView()
        try:
            await interaction.message.edit(view=reset_view)
        except:
            pass
        
        if choice == "configure_form":
            await self.show_form_configuration(interaction)
        elif choice == "view_form":
            await self.view_current_form(interaction)
        elif choice == "delete_field":
            await self.delete_specific_field(interaction)
        elif choice == "reset_form":
            await self.reset_to_default(interaction)

    async def show_form_configuration(self, interaction: Interaction):
        current_form = get_application_form()
        current_form = migrate_old_form_data(current_form)
        save_application_form(current_form)
        
        if len(current_form) == 0:
            view = View(timeout=300)
            add_button = Button(label="➕ Добавить первое поле", style=ButtonStyle.success, custom_id="add_field")
            
            async def add_callback(inter: Interaction):
                type_select_view = FieldTypeSelectView()
                type_embed = Embed(
                    title="Выберите тип поля",
                    description="Выберите тип текстового поля:",
                    color=0x5865F2
                )
                await inter.response.send_message(embed=type_embed, view=type_select_view, ephemeral=True)
            
            add_button.callback = add_callback
            view.add_item(add_button)
            
            embed = Embed(
                title="⚙️ Настройка формы заявки",
                description="**Форма пуста.** Нажмите кнопку ниже, чтобы добавить первое поле.",
                color=0x5865F2
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return
        
        view = View(timeout=300)
        
        # Селект для редактирования
        edit_options = []
        for i, field in enumerate(current_form):
            emoji = "📝" if field.get("style") == "short" else "📄"
            edit_options.append(
                SelectOption(
                    label=f"{i+1}. {field['label'][:40]}",
                    value=str(i),
                    description=f"ID: {field['custom_id']}",
                    emoji=emoji
                )
            )
        
        edit_select = StringSelect(
            placeholder="Выберите поле для редактирования...",
            options=edit_options,
            custom_id="edit_field_select"
        )
        
        async def edit_select_callback(inter: Interaction):
            field_index = int(inter.data["values"][0])
            field = current_form[field_index]
            await inter.response.send_modal(TextFieldEditorModal(field_index=field_index, existing_field=field))
        
        edit_select.callback = edit_select_callback
        view.add_item(edit_select)
        
        # Кнопка добавления
        add_button = Button(label="➕ Добавить поле", style=ButtonStyle.success, custom_id="add_field")
        
        async def add_callback(inter: Interaction):
            type_select_view = FieldTypeSelectView()
            type_embed = Embed(
                title="Выберите тип поля",
                description="Выберите тип текстового поля:",
                color=0x5865F2
            )
            await inter.response.send_message(embed=type_embed, view=type_select_view, ephemeral=True)
        
        add_button.callback = add_callback
        view.add_item(add_button)
        
        # Список полей
        fields_list = []
        for i, field in enumerate(current_form, 1):
            emoji = "📝" if field.get("style") == "short" else "📄"
            field_type_name = "Короткое" if field.get("style") == "short" else "Длинное"
            required_mark = "✅" if field["required"] else "⭕"
            
            fields_list.append(f"{emoji} **{i}. {field['label']}** ({field_type_name}) {required_mark}")
        
        warning = ""
        if len(current_form) > 5:
            warning = f"\n\n⚠️ **Внимание:** В форме {len(current_form)} полей, но Discord показывает только первые 5!"
        
        embed = Embed(
            title="⚙️ Настройка формы заявки",
            description=f"**Всего полей:** {len(current_form)}\n\n" + "\n".join(fields_list) + f"\n\n**Легенда:**\n📝 = Короткое поле\n📄 = Длинное поле\n✅ = Обязательное\n⭕ = Необязательное{warning}",
            color=0x5865F2
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def view_current_form(self, interaction: Interaction):
        current_form = get_application_form()
        current_form = migrate_old_form_data(current_form)
        
        if len(current_form) == 0:
            embed = Embed(
                title="📋 Текущая конфигурация формы",
                description="**Форма пуста.** Добавьте поля через меню настройки.",
                color=0x5865F2
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = Embed(
            title="📋 Текущая конфигурация формы",
            description=f"**Всего полей:** {len(current_form)}\n",
            color=0x5865F2
        )
        
        for i, field in enumerate(current_form, 1):
            emoji = "📝" if field.get("style") == "short" else "📄"
            field_info = (
                f"**Тип:** {'Короткое' if field.get('style') == 'short' else 'Длинное'} текстовое поле\n"
                f"**ID:** `{field['custom_id']}`\n"
                f"**Обязательное:** {'Да' if field['required'] else 'Нет'}\n"
                f"**Подсказка:** {field.get('placeholder', 'Нет')}"
            )
            
            embed.add_field(
                name=f"{emoji} {i}. {field['label']}",
                value=field_info,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def delete_specific_field(self, interaction: Interaction):
        current_form = get_application_form()
        current_form = migrate_old_form_data(current_form)
        
        if len(current_form) == 0:
            await interaction.response.send_message("❌ Нет полей для удаления!", ephemeral=True)
            return
        
        delete_view = FieldDeleteSelectView()
        delete_embed = Embed(
            title="🗑️ Удаление поля",
            description="Выберите поле, которое хотите удалить:",
            color=0xFF5555
        )
        await interaction.response.send_message(embed=delete_embed, view=delete_view, ephemeral=True)

    async def reset_to_default(self, interaction: Interaction):
        from database import get_default_application_form
        
        default_form = get_default_application_form()
        save_application_form(default_form)
        
        embed = Embed(
            title="🔄 Форма сброшена",
            description="Форма возвращена к дефолтной конфигурации.",
            color=0x3BA55D
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ApplicationAdminView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ApplicationAdminSelect())

# ==================== КОГ ====================

class ApplicationsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            application_channel = self.bot.get_channel(APPLICATION_CHANNEL_ID)
            if application_channel:
                await application_channel.purge(limit=10)
                embed = Embed(
                    title="📝 Подача заявки",
                    description="Нажмите кнопку ниже, чтобы подать заявку на вступление в семью.",
                    color=0x3A3B3C,
                )
                await application_channel.send(embed=embed)
                await application_channel.send(view=ApplicationChannelButtons(self.bot))
                print("✅ [Applications] Канал заявок настроен")
            
            admin_panel_channel = self.bot.get_channel(APPLICATION_ADMIN_PANEL_ID)
            if admin_panel_channel:
                await admin_panel_channel.purge(limit=10)
                
                admin_embed = Embed(
                    title="🛠️ Админ-панель настройки заявок",
                    description=(
                        "**Простой конструктор формы заявки:**\n\n"
                        "📝 **Короткие поля** - однострочный ввод\n"
                        "📄 **Длинные поля** - многострочный ввод\n\n"
                        "**Особенности:**\n"
                        "• Одно модальное окно для всей формы\n"
                        "• Максимум 5 полей (ограничение Discord)\n"
                        "• Простое и быстрое заполнение\n"
                        "• Все поля настраиваемые\n\n"
                        "🔄 Селект-меню сбрасывается автоматически."
                    ),
                    color=0x5865F2
                )
                admin_embed.set_footer(text="Только для администраторов")
                
                await admin_panel_channel.send(embed=admin_embed)
                await admin_panel_channel.send(view=ApplicationAdminView())
                print("✅ [Applications] Админ-панель настроена")
                
        except Exception as e:
            print(f"❌ [Applications] Ошибка: {e}")
            import traceback
            traceback.print_exc()

def setup(bot):
    bot.add_cog(ApplicationsCog(bot))
