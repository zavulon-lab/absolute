from disnake.ui import Modal, TextInput
from disnake import Interaction, TextInputStyle
import uuid
import time
import re

from .config import EVENTS_CHANNEL_ID
from .database import (
    close_all_active_events, save_event, get_event_by_id, 
    get_participants_struct, get_global_whitelist,
    add_to_global_whitelist, remove_from_global_whitelist
)
from .utils import extract_ids, push_to_reserve_if_full
from .embeds import generate_admin_embeds
from .logging import log_admin_action

# Import для update_all_views будет через circular import, используем прямой вызов
async def _update_all_views(bot, data):
    """Локальная версия update_all_views"""
    from .views import update_all_views
    await update_all_views(bot, data)

class EventCreateModal(Modal):
    def __init__(self):
        components = [
            TextInput(label="Название мероприятия", custom_id="name", placeholder="Капт", required=True),
            TextInput(label="Организатор", custom_id="organizer", placeholder="Alexis", required=True),
            TextInput(label="Время", custom_id="time", placeholder="19:00", required=True),
            TextInput(label="Слоты (число)", custom_id="slots", placeholder="35", required=True),
            TextInput(label="Ссылка на скриншот (необяз.)", custom_id="image", required=False),
        ]
        super().__init__(title="Настройка мероприятия", components=components)

    async def callback(self, interaction: Interaction):
        try: 
            slots = int(interaction.text_values["slots"])
        except: 
            return await interaction.response.send_message("Слоты должны быть числом.", ephemeral=True)
        
        close_all_active_events()
        event_id = str(uuid.uuid4())[:8]
        struct = {"main": [], "reserve": []}
        
        new_event = {
            "id": event_id,
            "name": interaction.text_values["name"],
            "organizer": interaction.text_values["organizer"],
            "event_time": interaction.text_values["time"],
            "description": interaction.text_values["name"], 
            "image_url": interaction.text_values["image"],
            "max_slots": slots,
            "status": "active",
            "participants": struct,
            "channel_id": EVENTS_CHANNEL_ID
        }
        
        pub_chan = interaction.guild.get_channel(EVENTS_CHANNEL_ID)
        if not pub_chan: 
            return await interaction.response.send_message("Нет публичного канала.", ephemeral=True)
        
        # Импортируем EventUserView здесь, чтобы избежать circular import
        from .views import EventUserView
        
        embeds = generate_admin_embeds(new_event)
        pub_msg = await pub_chan.send(embeds=embeds, view=EventUserView(event_id))
        new_event["message_id"] = pub_msg.id
        
        save_event(new_event)
        await _update_all_views(interaction.bot, new_event)
        await log_admin_action(interaction.bot, "Старт регистрации", f"Ивент: **{new_event['name']}**", interaction.user)
        await interaction.response.send_message("Регистрация запущена!", ephemeral=True)

class SmartManageModal(Modal):
    def __init__(self, mode, event_id, menu_msg=None):
        self.mode = mode
        self.event_id = event_id
        self.menu_msg = menu_msg 
        
        ph, title, label = "", "Управление", "Данные"
        
        if mode == "reserve_to_main":
            title, label, ph = "Из Резерва → В Основу", "Номера из РЕЗЕРВА", "1 2 5"
        elif mode == "main_to_reserve":
            title, label, ph = "Из Основы → В Резерв", "Номера из ОСНОВЫ", "1 5"
        elif mode == "whitelist_add":
            title, label, ph = "Добавить в White List", "ID (через пробел)", "123456789 987654321"
        elif mode == "whitelist_remove":
            title, label, ph = "Удалить из White List", "ID (через пробел)", "123456789"
        elif mode == "manual_reserve_add":
            title, label, ph = "Внести в РЕЗЕРВ (ID)", "ID или теги", "123456789"
        elif mode == "kick_user":
            title, label, ph = "Удаление участника", "Номер (1) или (р1)", "5"
            
        components = [TextInput(label=label, custom_id="input", placeholder=ph)]
        super().__init__(title=title, components=components)

    async def callback(self, interaction: Interaction):
        if self.menu_msg:
            try: 
                from .views import OtherOptionsView
                await self.menu_msg.edit(view=OtherOptionsView(self.event_id))
            except: 
                pass
        
        data = get_event_by_id(self.event_id)
        if not data: 
            return
        struct = get_participants_struct(data)
        inp = interaction.text_values["input"]

        # === WL ADD ===
        if self.mode == "whitelist_add":
            ids = extract_ids(inp)
            add_to_global_whitelist(ids)
            await log_admin_action(interaction.bot, "Добавлено в WL", f"ID: {ids}", interaction.user)
            await interaction.response.send_message(f"Добавлено в Global WL: **{len(ids)} чел.**", ephemeral=True)
            return

        # === WL REMOVE ===
        if self.mode == "whitelist_remove":
            ids = extract_ids(inp)
            remove_from_global_whitelist(ids)
            await log_admin_action(interaction.bot, "Удалено из WL", f"ID: {ids}", interaction.user)
            await interaction.response.send_message(f"Удалено из Global WL: **{len(ids)} чел.**", ephemeral=True)
            return

        # === MANUAL RESERVE ===
        if self.mode == "manual_reserve_add":
            ids = extract_ids(inp)
            added = 0
            for uid in ids:
                if not any(p["user_id"] == uid for p in struct["main"] + struct["reserve"]):
                    struct["reserve"].append({"user_id": uid, "join_time": time.time()})
                    added += 1
            data["participants"] = struct
            save_event(data)
            await _update_all_views(interaction.bot, data)
            await log_admin_action(interaction.bot, "Ручной ввод (Резерв)", f"Добавлено: **{added}**", interaction.user)
            await interaction.response.send_message(f"Добавлено в резерв: **{added} чел.**", ephemeral=True)
            return

        # === KICK ===
        if self.mode == "kick_user":
            txt = inp.strip().lower()
            is_res = True if (txt.startswith('r') or txt.startswith('р')) else False
            try: 
                idx = int(re.sub(r"\D", "", txt)) - 1
            except: 
                return await interaction.response.send_message("Некорректный номер.", ephemeral=True)
            
            lst = struct["reserve"] if is_res else struct["main"]
            if 0 <= idx < len(lst):
                removed = lst.pop(idx)
                data["participants"] = struct
                save_event(data)
                await _update_all_views(interaction.bot, data)
                await log_admin_action(interaction.bot, "Кик участника", f"User: <@{removed['user_id']}>", interaction.user)
                await interaction.response.send_message(f"Кикнут <@{removed['user_id']}>.", ephemeral=True)
            else:
                await interaction.response.send_message("Номер вне диапазона.", ephemeral=True)
            return

        # === МАССОВЫЕ ПЕРЕНОСЫ ===
        try: 
            indices = sorted(list(set([int(x) for x in inp.replace(",", " ").split() if x.isdigit()])))
        except: 
            return await interaction.response.send_message("Ошибка ввода чисел.", ephemeral=True)
        if not indices: 
            return await interaction.response.send_message("Пустой ввод.", ephemeral=True)

        if self.mode == "reserve_to_main":
            moved = []
            valid = [i-1 for i in indices if 0 < i <= len(struct["reserve"])]
            for i in sorted(valid, reverse=True): 
                moved.append(struct["reserve"].pop(i))
            moved.reverse()
            struct["main"].extend(moved)
            struct = push_to_reserve_if_full(struct, data["max_slots"])
            data["participants"] = struct
            save_event(data)
            await _update_all_views(interaction.bot, data)
            await log_admin_action(interaction.bot, "Перенос Резерв→Основа", f"Кол-во: **{len(moved)}**", interaction.user)
            await interaction.response.send_message(f"Перемещено: **{len(moved)} чел.**", ephemeral=True)

        elif self.mode == "main_to_reserve":
            moved = []
            valid = [i-1 for i in indices if 0 < i <= len(struct["main"])]
            for i in sorted(valid, reverse=True): 
                moved.append(struct["main"].pop(i))
            moved.reverse()
            for u in reversed(moved): 
                struct["reserve"].insert(0, u)
            data["participants"] = struct
            save_event(data)
            await _update_all_views(interaction.bot, data)
            await log_admin_action(interaction.bot, "Перенос Основа→Резерв", f"Кол-во: **{len(moved)}**", interaction.user)
            await interaction.response.send_message(f"Перемещено: **{len(moved)} чел.**", ephemeral=True)

class EditEventModal(Modal):
    def __init__(self, data, menu_msg=None):
        self.event_id = data["id"]
        self.menu_msg = menu_msg
        components = [
            TextInput(label="Название", custom_id="name", value=data["name"], required=True),
            TextInput(label="Время", custom_id="time", value=data["event_time"], required=True),
            TextInput(label="Примечание (Орг)", custom_id="desc", value=data["description"], required=True),
            TextInput(label="URL Картинки", custom_id="image", value=data.get("image_url", ""), required=False),
        ]
        super().__init__(title="Редактировать ивент", components=components)

    async def callback(self, interaction: Interaction):
        if self.menu_msg:
            try: 
                from .views import OtherOptionsView
                await self.menu_msg.edit(view=OtherOptionsView(self.event_id))
            except: 
                pass
        data = get_event_by_id(self.event_id)
        if not data: 
            return
        data["name"] = interaction.text_values["name"]
        data["event_time"] = interaction.text_values["time"]
        data["description"] = interaction.text_values["desc"]
        data["image_url"] = interaction.text_values["image"]
        save_event(data)
        await _update_all_views(interaction.bot, data)
        await log_admin_action(interaction.bot, "Редактирование", "Параметры ивента обновлены", interaction.user)
        await interaction.response.send_message("Ивент обновлен.", ephemeral=True)
