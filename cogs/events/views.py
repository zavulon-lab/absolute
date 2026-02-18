import disnake
from disnake.ui import View, Button, Select
from disnake import Interaction, ButtonStyle, Embed
import asyncio
import time

from .config import *
from .database import (
    get_event_by_id, get_current_event, get_participants_struct,
    save_event, close_all_active_events, get_global_whitelist,
    clear_global_whitelist
)
from .utils import push_to_reserve_if_full, extract_ids
from .embeds import generate_admin_embeds
from .logging import log_admin_action, log_user_action, log_event_history
from .modals import SmartManageModal, EditEventModal, EventCreateModal

# --- ОБНОВЛЕНИЕ ВСЕХ VIEW ---

async def update_all_views(bot, data=None):
    """Обновляет сообщения админки и публичного канала"""
    embeds = generate_admin_embeds(data, bot=bot)
    
    # Админ-канал
    admin_chan = bot.get_channel(EVENTS_ADMIN_CHANNEL_ID)
    if admin_chan:
        target_msg = None
        try:
            async for msg in admin_chan.history(limit=10):
                if msg.author == bot.user and msg.components:
                    try:
                        if msg.components[0].children and msg.components[0].children[0].custom_id == "start_reg_btn":
                            target_msg = msg
                            break
                    except (IndexError, AttributeError): 
                        pass
        except Exception:
            pass
        
        if target_msg:
            try:
                await target_msg.edit(embeds=embeds, view=MainAdminView())
            except Exception:
                pass
        else:
            try:
                await admin_chan.send(embeds=embeds, view=MainAdminView())
            except Exception:
                pass

    # Публичный канал
    if data and data.get("message_id"):
        try:
            chan = bot.get_channel(data["channel_id"])
            if chan:
                msg = await chan.fetch_message(data["message_id"])
                await msg.edit(embeds=embeds, view=EventUserView(data["id"]))
        except Exception:
            pass

# --- VIEW КЛАССЫ ---

class OtherOptionsView(View):
    def __init__(self, event_id):
        super().__init__(timeout=None)
        self.event_id = event_id
        
        options = [
            disnake.SelectOption(label="White List", description="Управление списком приоритета", emoji=EMOJI_STAR, value="whitelist"),
            disnake.SelectOption(label="WL → Основа", description="Массовый перенос всех из WL в основу", emoji=EMOJI_INBOX, value="wl_mass_add"),
            disnake.SelectOption(label="Внести в резерв", description="Ручной ввод ID участников", emoji=EMOJI_PLUS_CIRCLE, value="add_reserve"),
            disnake.SelectOption(label="Редактировать Embed", description="Изменить название, время, описание, картинку", emoji=EMOJI_SETTINGS, value="edit"),
            disnake.SelectOption(label="Пауза", description="Остановить регистрацию (временно)", emoji=EMOJI_PAUSE, value="pause"),
            disnake.SelectOption(label="Старт", description="Возобновить регистрацию", emoji=EMOJI_RESUME, value="resume"),
            disnake.SelectOption(label="Кик", description="Удалить участника по номеру", emoji=EMOJI_DOOR, value="kick"),
            disnake.SelectOption(label="Запрос откатов", description="Пингануть участников для отправки отката", emoji=EMOJI_CAMERA, value="vods"),
        ]
        self.add_item(Select(placeholder="Меню управления", options=options, custom_id="other_select"))

    @disnake.ui.button(label="Закрыть", style=ButtonStyle.secondary, emoji=EMOJI_CROSS, row=1)
    async def close_menu(self, button, interaction):
        await interaction.message.delete()

    async def interaction_check(self, interaction: Interaction):
        if interaction.data.get("component_type") == 2: 
            return True 
        
        val = interaction.data['values'][0]
        data = get_event_by_id(self.event_id)
        if not data: 
            return await interaction.response.send_message("Ивент не найден.", ephemeral=True)
        
        # === WHITE LIST ===
        if val == "whitelist":
            embed = Embed(title="<:freeiconinvitation7515655:1473373288724959285> White List Управление", color=AUX_COLOR)
            wl = get_global_whitelist()
            desc_list = " ".join([f"<@{uid}>" for uid in wl]) if wl else "*Пусто*"
            embed.description = f"**Текущий список:**\n{desc_list}\n\n*White List — участники с приоритетом попадают в основу вне очереди.*"
            
            view = View()
            
            btn_add = Button(label="Добавить ID", style=ButtonStyle.success, emoji=EMOJI_PLUS_BTN)
            btn_add.callback = lambda i: i.response.send_modal(SmartManageModal("whitelist_add", self.event_id, interaction.message))
            
            btn_rem = Button(label="Удалить ID", style=ButtonStyle.danger, emoji=EMOJI_MINUS_BTN)
            btn_rem.callback = lambda i: i.response.send_modal(SmartManageModal("whitelist_remove", self.event_id, interaction.message))
            
            btn_show = Button(label="Показать WL", style=ButtonStyle.primary, emoji=EMOJI_EYE)
            async def show_cb(inter):
                wl_current = get_global_whitelist()
                txt = "\n".join([f"<@{uid}>" for uid in wl_current]) if wl_current else "*Пусто*"
                await inter.response.send_message(f"**<:freeiconsermon7515746:1473373077818573012> Global White List:**\n{txt}", ephemeral=True)
            btn_show.callback = show_cb
            
            btn_clear = Button(label="Очистить весь WL", style=ButtonStyle.danger, emoji=EMOJI_BIN)
            async def clear_cb(inter):
                clear_global_whitelist()
                await log_admin_action(inter.bot, "Очистка WL", "Весь список удален", inter.user)
                await inter.response.send_message("Global White List очищен.", ephemeral=True)
            btn_clear.callback = clear_cb
            
            view.add_item(btn_add)
            view.add_item(btn_rem)
            view.add_item(btn_show)
            view.add_item(btn_clear)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        # === WL MASS ADD ===
        elif val == "wl_mass_add":
            embed = Embed(title="<:freeiconswitcharrows9282594:1473359651318792282> Массовое добавление WL", color=AUX_COLOR)
            embed.description = (
                "**White List → Основной список**\n\n"
                "Все участники из Global WL будут автоматически добавлены в основу (если еще не записаны).\n"
                "При переполнении лишние уйдут в резерв."
            )
            
            view = View()
            btn_do = Button(label="Выполнить", style=ButtonStyle.primary, emoji=EMOJI_CHECK)
            
            async def mass_add_cb(inter):
                wl = get_global_whitelist()
                if not wl: 
                    return await inter.response.send_message("WL пуст.", ephemeral=True)
                
                struct = get_participants_struct(data)
                existing_ids = {p["user_id"] for p in struct["main"] + struct["reserve"]}
                added_users = []
                
                for uid in wl:
                    if uid not in existing_ids:
                        added_users.append({"user_id": uid, "join_time": time.time()})
                
                struct["main"] = added_users + struct["main"]
                struct = push_to_reserve_if_full(struct, data["max_slots"])
                
                data["participants"] = struct
                save_event(data)
                await update_all_views(inter.bot, data)
                await log_admin_action(inter.bot, "Массовый WL", f"Добавлено: **{len(added_users)}**", inter.user)
                await inter.response.send_message(f"WL → Основа: **{len(added_users)} чел.**", ephemeral=True)
            
            btn_do.callback = mass_add_cb
            view.add_item(btn_do)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        # === ADD RESERVE ===
        elif val == "add_reserve":
            embed = Embed(title="<:freeiconplus1828819:1473433100737319114> Внести в резервный список", color=AUX_COLOR)
            embed.description = (
                "Укажите ID участников или теги, которых нужно внести в резерв вручную.\n"
                "Пример: `@User 123456789 987654321`"
            )
            view = View()
            btn = Button(label="Внести ID", style=ButtonStyle.success, emoji=EMOJI_PLUS_BTN)
            btn.callback = lambda i: i.response.send_modal(SmartManageModal("manual_reserve_add", self.event_id, interaction.message))
            view.add_item(btn)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        elif val == "edit":
            embed = Embed(
                title="<:fsdf:1473443687013810176> Редактирование", 
                color=AUX_COLOR
            )
            embed.description = (
                "Изменить название, время, примечание, картинку.\n"
                "Откроется форма редактирования."
            )
            
            view = View(timeout=300)
            btn = Button(
                label="Редактировать", 
                style=ButtonStyle.secondary, 
                emoji="<:freeiconedit1040228:1472654696891158549>"
            )
            
            btn.callback = lambda i: asyncio.create_task(i.response.send_modal(EditEventModal(data, interaction.message)))
            
            view.add_item(btn)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        # === PAUSE ===
        elif val == "pause":
            embed = Embed(title="<:freeiconstop394592:1473441364938194976> Пауза", color=AUX_COLOR)
            embed.description = "Регистрация будет приостановлена. Участники не смогут записываться."
            view = View()
            btn = Button(label="Остановить регистрацию", style=ButtonStyle.danger, emoji=EMOJI_PAUSE_BTN)
            async def do_pause(inter):
                data["status"] = "paused"
                save_event(data)
                await update_all_views(inter.bot, data)
                await log_admin_action(inter.bot, "Пауза", "Регистрация остановлена", inter.user)
                await inter.response.send_message("<:freeiconstop394592:1473441364938194976> Регистрация ПРИОСТАНОВЛЕНА.", ephemeral=True)
            btn.callback = do_pause
            view.add_item(btn)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        # === RESUME ===
        elif val == "resume":
            embed = Embed(title="<:freeiconpowerbutton4943421:1473441364170772674> Возобновить", color=AUX_COLOR)
            embed.description = "Регистрация снова станет доступна."
            view = View()
            btn = Button(label="Возобновить регистрацию", style=ButtonStyle.success, emoji=EMOJI_PLAY)
            async def do_resume(inter):
                data["status"] = "active"
                save_event(data)
                await update_all_views(inter.bot, data)
                await log_admin_action(inter.bot, "Возобновление", "Регистрация открыта", inter.user)
                await inter.response.send_message("<:freeiconpowerbutton4943421:1473441364170772674> Регистрация ВОЗОБНОВЛЕНА.", ephemeral=True)
            btn.callback = do_resume
            view.add_item(btn)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        # === KICK ===
        elif val == "kick":
            embed = Embed(title="<:freeicongrimreaper7515728:1473373897855340617> Кик участника", color=AUX_COLOR)
            embed.description = (
                "Укажите номер участника для удаления.\n"
                "**Примеры:**\n"
                "• `5` — удалить 5-го из основы\n"
                "• `р5` или `r5` — удалить 5-го из резерва"
            )
            view = View()
            btn = Button(label="Удалить участника", style=ButtonStyle.danger, emoji=EMOJI_DOOR_BTN)
            btn.callback = lambda i: i.response.send_modal(SmartManageModal("kick_user", self.event_id, interaction.message))
            view.add_item(btn)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        elif val == "vods":
            embed = Embed(title="<:teg:1473384504537383157> Запрос откатов", color=AUX_COLOR)
            embed.description = (
                "Пингует всех участников основы с просьбой отправить откат.\n"
                "Сообщение будет отправлено в канал ивента."
            )
            view = View()
            btn = Button(label="Отправить запрос", style=ButtonStyle.primary, emoji=EMOJI_CAMERA_BTN)
            
            async def do_vods(inter):
                struct = get_participants_struct(data)
                if not struct["main"]:
                    return await inter.response.send_message("В основе никого нет.", ephemeral=True)
                
                pings = " ".join([f"<@{p['user_id']}>" for p in struct["main"]])
                msg_content = f"<:teg:1473384504537383157> **Запрос откатов!**\n\n{pings}\n\n Отправлять откаты сюда: <#{VOD_SUBMIT_CHANNEL_ID}>"
                
                target = inter.guild.get_channel(data["channel_id"])
                await target.send(msg_content)
                await log_admin_action(inter.bot, "Запрос откатов", "Пинг участников для запроса отката", inter.user)
                await inter.response.send_message("Запрос отправлен.", ephemeral=True)
            
            btn.callback = do_vods
            view.add_item(btn)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        await interaction.message.edit(view=OtherOptionsView(self.event_id))
        return False

class EventUserView(View):
    def __init__(self, event_id):
        super().__init__(timeout=None)
        self.event_id = event_id

    @disnake.ui.button(label="Записаться", style=ButtonStyle.success, emoji=EMOJI_JOIN, custom_id="usr_join")
    async def join(self, button, interaction):
        data = get_event_by_id(self.event_id)
        if not data: 
            return await interaction.response.send_message("Ивент не найден.", ephemeral=True)
        if data["status"] == "paused": 
            return await interaction.response.send_message("<:freeiconstop394592:1473441364938194976> Регистрация приостановлена.", ephemeral=True)
        if data["status"] != "active": 
            return await interaction.response.send_message("<:freeicongravestone7515635:1473361769987707013> Регистрация закрыта.", ephemeral=True)
        
        struct = get_participants_struct(data)
        uid = interaction.user.id
        wl = get_global_whitelist()
        
        has_priority = False
        if interaction.guild:
            role = interaction.guild.get_role(EVENTS_PRIORITY_ROLE_ID)
            if role and role in interaction.user.roles:
                has_priority = True
        
        all_users = struct["main"] + struct["reserve"]
        if any(p["user_id"] == uid for p in all_users):
            return await interaction.response.send_message("Вы уже записаны.", ephemeral=True)
        
        user_data = {"user_id": uid, "join_time": int(time.time())}
        msg = ""

        if uid in wl or has_priority:
            struct["main"].insert(0, user_data)
            msg = "Вы записаны в **ОСНОВУ** (Priority/WL)!"
            struct = push_to_reserve_if_full(struct, data["max_slots"])
        else:
            struct["reserve"].append(user_data)
            msg = "Вы добавлены в **РЕЗЕРВ**."
        
        data["participants"] = struct
        save_event(data)
        await update_all_views(interaction.bot, data)
        await log_user_action(interaction.bot, "Вход", f"Статус: {msg}", interaction.user, False)
        await interaction.response.send_message(msg, ephemeral=True)

    @disnake.ui.button(label="Покинуть список", style=ButtonStyle.danger, custom_id="usr_leave")
    async def leave(self, button, interaction):
        await interaction.response.defer(ephemeral=True)
        
        data = get_event_by_id(self.event_id)
        if not data: 
            return await interaction.followup.send("Ивент не найден.", ephemeral=True)
        
        struct = get_participants_struct(data)
        uid = interaction.user.id
        
        all_participants = struct["main"] + struct["reserve"]
        user_data = next((p for p in all_participants if p["user_id"] == uid), None)
        
        if not user_data:
            return await interaction.followup.send("Вас нет в списке участников.", ephemeral=True)
        
        join_timestamp = user_data.get("join_time", 0)
        current_time = int(time.time())
        wait_time = 60
        
        if current_time - join_timestamp < wait_time:
            remaining = wait_time - (current_time - join_timestamp)
            return await interaction.followup.send(
                f"Вы не можете покинуть список так быстро! Подождите еще {remaining} сек.", 
                ephemeral=True
            )

        struct["main"] = [p for p in struct["main"] if p["user_id"] != uid]
        struct["reserve"] = [p for p in struct["reserve"] if p["user_id"] != uid]
        
        if len(struct["main"]) < data["max_slots"] and struct["reserve"]:
            struct["main"].append(struct["reserve"].pop(0))
        
        data["participants"] = struct
        save_event(data)
        
        await update_all_views(interaction.bot, data)
        await log_user_action(interaction.bot, "Выход", "Покинул ивент", interaction.user, True)
        
        await interaction.followup.send("Вы вышли из списка.", ephemeral=True)

class MainAdminView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(label="Начать регистрацию", style=ButtonStyle.secondary, emoji=EMOJI_DICE, row=0, custom_id="start_reg_btn")
    async def start_reg(self, button, interaction):
        await interaction.response.send_modal(EventCreateModal())

    @disnake.ui.button(label="Завершить и очистить", style=ButtonStyle.danger, emoji=EMOJI_TRASH, row=0, custom_id="close_evt_btn")
    async def close_evt(self, button, interaction):
        data = get_current_event()
        if not data: 
            return await interaction.response.send_message("Нет активного мероприятия.", ephemeral=True)
        
        try:
            chan = interaction.guild.get_channel(data["channel_id"])
            msg = await chan.fetch_message(data["message_id"])
            await msg.delete() 
        except: 
            pass
        
        await log_event_history(interaction.bot, data)
        await log_admin_action(interaction.bot, "Ивент завершен", f"Имя: **{data['name']}**", interaction.user)
        
        close_all_active_events()
        await update_all_views(interaction.bot, None)
        await interaction.response.send_message("Ивент завершен и удален.", ephemeral=True)

    @disnake.ui.button(label="Внести в основной список", style=ButtonStyle.secondary, emoji=EMOJI_PLUS, row=1, custom_id="add_main_btn")
    async def add_to_main(self, button, interaction):
        data = get_current_event()
        if not data: 
            return await interaction.response.send_message("Сначала создайте ивент.", ephemeral=True)
        await interaction.response.send_modal(SmartManageModal("reserve_to_main", data["id"]))

    @disnake.ui.button(label="Перевести в резервный список", style=ButtonStyle.secondary, emoji=EMOJI_MINUS, row=1, custom_id="to_res_btn")
    async def move_to_res(self, button, interaction):
        data = get_current_event()
        if not data: 
            return await interaction.response.send_message("Сначала создайте ивент.", ephemeral=True)
        await interaction.response.send_modal(SmartManageModal("main_to_reserve", data["id"]))

    @disnake.ui.button(label="Проверка голосового канала", style=ButtonStyle.secondary, emoji=EMOJI_MIC, row=2, custom_id="chk_voice_btn")
    async def check_voice(self, button, interaction):
        data = get_current_event()
        if not data: 
            return await interaction.response.send_message("Нет активного ивента.", ephemeral=True)
        
        voice = interaction.guild.get_channel(EVENT_VOICE_CHANNEL_ID)
        if not voice: 
            return await interaction.response.send_message(f"Канал {EVENT_VOICE_CHANNEL_ID} не найден.", ephemeral=True)
        
        struct = get_participants_struct(data)
        voice_members = {m.id for m in voice.members}
        
        missing_ids = [p["user_id"] for p in struct["main"] if p["user_id"] not in voice_members]
        
        if missing_ids:
            missing_text = ""
            for uid in missing_ids:
                try:
                    idx = next(i for i, p in enumerate(struct["main"]) if p["user_id"] == uid) + 1
                    missing_text += f"{idx}) <@{uid}>\n"
                except: 
                    pass
            
            if len(missing_text) > 1900:
                missing_text = missing_text[:1900].rstrip(",\n") + "\n..."
            else:
                missing_text = missing_text.rstrip()
            
            await interaction.response.send_message(f"**Отсутствуют в войсе:**\n{missing_text}", ephemeral=True)
        else:
            await interaction.response.send_message("Все участники основы в войсе!", ephemeral=True)

    @disnake.ui.button(label="Тегнуть основной список", style=ButtonStyle.secondary, emoji=EMOJI_CHAT, row=2, custom_id="tag_main_btn")
    async def tag_main(self, button, interaction):
        data = get_current_event()
        if not data: 
            return
        
        struct = get_participants_struct(data)
        if not struct["main"]: 
            return await interaction.response.send_message("Основа пуста.", ephemeral=True)
        
        msg = f"**Внимание, основной состав!** {' '.join([f'<@{p['user_id']}>' for p in struct['main']])}"
        event_channel = interaction.guild.get_channel(data["channel_id"])
        await event_channel.send(msg)
        await log_admin_action(interaction.bot, "Тег участников", "Тег основы в канале", interaction.user)
        await interaction.response.send_message("Тег отправлен.", ephemeral=True)

    @disnake.ui.button(label="Пингануть everyone", style=ButtonStyle.secondary, emoji=EMOJI_MEGAPHONE, row=3, custom_id="ping_ev_btn")
    async def ping_everyone(self, button, interaction):
        data = get_current_event()
        if not data: 
            return
        
        embed = Embed(color=AUX_COLOR)
        channel_mention = f"<#{data['channel_id']}>"
        embed.description = (
            f"Регистрация откраты: {channel_mention}\n"
            f"Время: **{data['event_time']}**"
        )
        
        target = interaction.guild.get_channel(EVENTS_TAG_CHANNEL_ID)
        if not target:
            target = interaction.guild.get_channel(data["channel_id"])
        
        await target.send(content=f"@everyone **{data['name']}**", embed=embed)
        await log_admin_action(interaction.bot, "Пинг @everyone", "Анонс ивента", interaction.user)
        await interaction.response.send_message("Анонс отправлен.", ephemeral=True)

    @disnake.ui.button(label="Меню управления", style=ButtonStyle.primary, emoji=EMOJI_GEAR, row=3, custom_id="other_btn")
    async def other(self, button, interaction):
        data = get_current_event()
        if not data: 
            return await interaction.response.send_message("Нет активного ивента.", ephemeral=True)
        
        embed = Embed(title="<:freeiconinvitation7515655:1473373288724959285> Меню управления", color=AUX_COLOR)
        desc = (
            "**<:ddd:1473378828427460618> White List** — управление WL ID и массовый перенос\n"
            "**<:freeiconplus1828819:1473433100737319114> Внести в резерв** — ручной ввод участников\n"
            "**<:freeicondrawing14958309:1473426934732947560> Редактировать Embed** — изменить название, время, описание, картинку\n"
            "**<:freeiconstop394592:1473441364938194976> Пауза / <:freeiconpowerbutton4943421:1473441364170772674> Старт** — остановить/возобновить регистрацию\n"
            "**<:freeicongrimreaper7515728:1473373897855340617> Кик** — удалить участника\n"
            "**<:teg:1473384504537383157> Запрос откатов** — пинг участников для запроса отката\n"
        )
        embed.description = desc
        await interaction.response.send_message(embed=embed, view=OtherOptionsView(data["id"]), ephemeral=False)
