import disnake
from disnake.ext import commands, tasks
from disnake.ui import Modal, TextInput, View, Button
from disnake import Interaction, ButtonStyle, Color, Embed
from datetime import datetime, timezone
import random
import uuid
import asyncio

# Импорт конфига и базы данных
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import (
    GIVEAWAY_USER_CHANNEL_ID,
    GIVEAWAY_ADMIN_CHANNEL_ID,
    GIVEAWAY_LOG_CHANNEL_ID,
    MAX_WINNERS
)

from database import load_giveaway_data, save_giveaway_data


# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ EMBED ---
def create_giveaway_embed(data: dict, bot_user: disnake.User):
    
    # Если розыгрыш активен — призыв к действию, если завершен — просто описание
    is_finished = data.get("status") == "finished"
    
    embed = Embed(
        title="<:freeiconraffle5736412:1473435748207169627> РОЗЫГРЫШ",
        color=disnake.Color.from_rgb(54, 57, 63)
    )
    
    # 1. Приз
    embed.add_field(
        name="<:freeicongift6280355:1473434679808884939> Приз", 
        value=f"```fix\n{data['prize']}\n```", 
        inline=False
    )
    
    # 2. Инфо
    embed.add_field(name="<:freeiconsponsor1478946:1473435087336112199> Спонсор", value=f"> **{data['sponsor']}**", inline=True)
    embed.add_field(name="<:freeiconcrown1404959:1473435086010450041> Победителей", value=f"> **{data['winner_count']}**", inline=True)
    
    participants_count = len(data.get("participants", []))
    embed.add_field(name="<:freeiconpeopletogether4596136:1473433825680953442> Участников", value=f"> **{participants_count}**", inline=True)

    # 3. Таймер (Только если активен)
    if not is_finished:
        try:
            dt = datetime.strptime(data["end_time"], "%Y-%m-%d %H:%M")
            ts = int(dt.timestamp())
            time_str = f"<t:{ts}:R> (<t:{ts}:f>)"
        except:
            time_str = data["end_time"]
        
        embed.add_field(name="Итоги", value=time_str, inline=False)

    # 4. Картинка
    if data.get("thumbnail_url"):
        embed.set_thumbnail(url=data["thumbnail_url"])
    
    # 5. Футер
    icon_url = bot_user.display_avatar.url if bot_user else None
    embed.set_footer(text=f"Absolute Famq", icon_url=icon_url)
    
    return embed


# --- VIEW: СПИСОК УЧАСТНИКОВ (ПАГИНАЦИЯ) ---
class ParticipantsPaginationView(View):
    def __init__(self, participants: list, title: str = "Список участников"):
        super().__init__(timeout=120)
        self.participants = participants
        self.title = title
        self.page = 0
        self.per_page = 20
        self.total_pages = max(1, (len(participants) + self.per_page - 1) // self.per_page)
        self.update_buttons()

    def update_buttons(self):
        self.prev_page.disabled = (self.page == 0)
        self.next_page.disabled = (self.page == self.total_pages - 1)
        self.counter.label = f"Стр. {self.page + 1}/{self.total_pages} ({len(self.participants)} чел.)"

    def create_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        chunk = self.participants[start:end]
        
        description = ""
        for i, uid in enumerate(chunk, start=start + 1):
            description += f"**{i}.** <@{uid}> (`{uid}`)\n"
            
        if not description: description = "Список пуст."

        embed = Embed(title=self.title, description=description, color=0x2B2D31)
        return embed

    @disnake.ui.button(label="◀️", style=ButtonStyle.secondary, custom_id="prev")
    async def prev_page(self, button: Button, interaction: Interaction):
        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @disnake.ui.button(label="Стр. 1/1", style=ButtonStyle.gray, custom_id="counter", disabled=True)
    async def counter(self, button: Button, interaction: Interaction): pass

    @disnake.ui.button(label="▶️", style=ButtonStyle.secondary, custom_id="next")
    async def next_page(self, button: Button, interaction: Interaction):
        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)


# --- MODALS & VIEWS (ОСНОВНОЙ ФУНКЦИОНАЛ) ---

class GiveawayPreviewView(View):
    def __init__(self, data: dict):
        super().__init__(timeout=600)
        self.data = data

    @disnake.ui.button(label="Опубликовать", style=ButtonStyle.success, emoji="<:tick:1473380953245221016>")
    async def confirm(self, button: Button, interaction: Interaction):
        if not self.data.get("id"):
            self.data["id"] = str(uuid.uuid4())[:8]

        save_giveaway_data(self.data)
        
        channel = interaction.guild.get_channel(GIVEAWAY_USER_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Ошибка: Канал розыгрышей не найден в конфиге.", ephemeral=True)
            return

        # === ОЧИСТКА КАНАЛА ПЕРЕД ПУБЛИКАЦИЕЙ ===
        try:
            await channel.purge(limit=50) # Удаляем последние 50 сообщений
        except Exception as e:
            print(f"[GIVEAWAY] Ошибка очистки канала: {e}")

        # Отправка нового
        embed = create_giveaway_embed(self.data, interaction.bot.user)
        try:
            msg = await channel.send(embed=embed, view=GiveawayJoinView(self.data["id"]))
            
            self.data["fixed_message_id"] = msg.id
            save_giveaway_data(self.data)
            
            await interaction.response.edit_message(content=f"Розыгрыш опубликован! [Перейти]({msg.jump_url})", view=None, embed=None)
        except Exception as e:
            print(f"[GIVEAWAY] Ошибка отправки розыгрыша: {e}")
            await interaction.response.edit_message(content="Ошибка при публикации розыгрыша.", view=None, embed=None)

    @disnake.ui.button(label="Отмена", style=ButtonStyle.danger, emoji="<:cross:1473380950770716836>")
    async def cancel(self, button: Button, interaction: Interaction):
        await interaction.response.edit_message(content="Создание отменено.", view=None, embed=None)


class GiveawayEditModal(Modal):
    def __init__(self):
        components = [
            TextInput(label="Описание", custom_id="desc", style=disnake.TextInputStyle.paragraph, placeholder="Условия...", required=True),
            TextInput(label="Приз", custom_id="prize", placeholder="Например: 500 рублей", required=True),
            TextInput(label="Спонсор", custom_id="sponsor", placeholder="Ник спонсора", required=True),
            TextInput(label="Количество победителей", custom_id="winners", value="1", required=True),
            TextInput(label="Время окончания (YYYY-MM-DD HH:MM)", custom_id="end_time", placeholder="2026-02-15 18:00", required=True)
        ]
        super().__init__(title="Создать розыгрыш", components=components)

    async def callback(self, interaction: Interaction):
        try:
            w_count = int(interaction.text_values["winners"])
            if w_count < 1 or w_count > MAX_WINNERS: raise ValueError
            end_dt = datetime.strptime(interaction.text_values["end_time"], "%Y-%m-%d %H:%M")
        except ValueError:
            await interaction.response.send_message(f"Ошибка данных! Проверьте число победителей и формат даты.", ephemeral=True)
            return

        temp_data = {
            "id": str(uuid.uuid4())[:8],
            "description": interaction.text_values["desc"],
            "prize": interaction.text_values["prize"],
            "sponsor": interaction.text_values["sponsor"],
            "winner_count": w_count,
            "end_time": end_dt.strftime("%Y-%m-%d %H:%M"),
            "participants": [],
            "status": "active",
            "guild_id": interaction.guild.id,
            "thumbnail_url": "https://media.discordapp.net/attachments/1336423985794682974/1336423986381754409/6FDCFF59-EFBB-4D26-9E57-50B0F3D61B50.jpg"
        }

        preview_embed = create_giveaway_embed(temp_data, interaction.bot.user)
        preview_embed.title = "<:freeicondocuments1548205:1473390852234543246> Предпросмотр"
        
        await interaction.response.send_message(embed=preview_embed, view=GiveawayPreviewView(temp_data), ephemeral=True)


class WinnerSelectModal(Modal):
    def __init__(self):
        components = [
            TextInput(
                label="ID победителей (через пробел)",
                custom_id="winners",
                style=disnake.TextInputStyle.paragraph,
                required=True
            )
        ]
        super().__init__(title="Ручной выбор победителей", components=components)

    async def callback(self, interaction: Interaction):
        data = load_giveaway_data()
        if not data or data.get("status") != "active":
            await interaction.response.send_message("Нет активного розыгрыша.", ephemeral=True)
            return

        try:
            input_text = interaction.text_values["winners"].replace(",", " ").split()
            winner_ids = [int(x) for x in input_text]
        except ValueError:
            await interaction.response.send_message("Ошибка: Введите только цифры ID.", ephemeral=True)
            return

        guild = interaction.guild
        mentions = []
        for uid in winner_ids:
            u = guild.get_member(uid)
            mentions.append(u.mention if u else f"ID {uid}")

        log_chan = guild.get_channel(GIVEAWAY_LOG_CHANNEL_ID)
        if log_chan:
            emb = Embed(
                title="<:fsdf:1473443687013810176> Ручной выбор победителей",
                description=f"Администратор {interaction.user.mention} зафиксировал:\n" + ", ".join(mentions),
                color=disnake.Color.from_rgb(54, 57, 63)
            )
            await log_chan.send(embed=emb)

        data["preselected_winners"] = winner_ids
        data["preselected_by"] = interaction.user.id
        data["preselected_at"] = datetime.now(timezone.utc).isoformat()
        save_giveaway_data(data)
        
        await interaction.response.send_message(f"Зафиксировано {len(winner_ids)} победителей.", ephemeral=True)


class GiveawayJoinView(View):
    def __init__(self, giveaway_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @disnake.ui.button(label="Участвовать", style=ButtonStyle.success, emoji="<:freeiconraffle5736412:1473435748207169627>", custom_id="btn_join_giveaway")
    async def join(self, button: Button, interaction: Interaction):
        data = load_giveaway_data()
        
        if not data or str(data.get("id")) != str(self.giveaway_id) or data.get("status") != "active":
            await interaction.response.send_message("Этот розыгрыш уже завершен.", ephemeral=True)
            return

        uid = interaction.user.id
        participants = data.get("participants", [])
        
        if uid in participants:
            participants.remove(uid)
            msg = "Вы больше не участвуете."
        else:
            participants.append(uid)
            msg = "Вы успешно участвуете!"
        
        data["participants"] = participants
        save_giveaway_data(data)

        # Обновляем счетчик
        try:
            embed = create_giveaway_embed(data, interaction.bot.user)
            await interaction.message.edit(embed=embed)
        except:
            pass
            
        await interaction.response.send_message(msg, ephemeral=True)


class GiveawayAdminPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(label="Создать", style=ButtonStyle.primary, emoji="<:freeiconplus1828819:1473433100737319114>", custom_id="adm_gw_create", row=0)
    async def create(self, button: Button, interaction: Interaction):
        await interaction.response.send_modal(GiveawayEditModal())

    @disnake.ui.button(label="Тест Рандома", style=ButtonStyle.secondary, emoji="<:freeicondice2102161:1473432878841856021>", custom_id="adm_gw_reroll", row=0)
    async def reroll(self, button: Button, interaction: Interaction):
        data = load_giveaway_data()
        if not data or data["status"] != "active":
            await interaction.response.send_message("Нет активных розыгрышей.", ephemeral=True)
            return
        
        participants = data.get("participants", [])
        if not participants:
            await interaction.response.send_message("Нет участников.", ephemeral=True)
            return
        
        random_winner = random.choice(participants)
        await interaction.response.send_message(f"<:freeicondice2102161:1473432878841856021> Тестовый победитель: <@{random_winner}>", ephemeral=True)

    @disnake.ui.button(label="Выбрать", style=ButtonStyle.success, emoji="<:freeiconman7238426:1473433824091443353>", custom_id="adm_gw_pick", row=0)
    async def pick(self, button: Button, interaction: Interaction):
        await interaction.response.send_modal(WinnerSelectModal())

    @disnake.ui.button(label="Участники", style=ButtonStyle.gray, emoji="<:freeiconpeopletogether4596136:1473433825680953442>", custom_id="adm_gw_list", row=0)
    async def list_participants(self, button: Button, interaction: Interaction):
        data = load_giveaway_data()
        if not data:
            await interaction.response.send_message("Нет данных.", ephemeral=True)
            return

        participants = data.get("participants", [])
        if not participants:
            await interaction.response.send_message("Список пуст.", ephemeral=True)
            return

        view = ParticipantsPaginationView(participants)
        await interaction.response.send_message(embed=view.create_embed(), view=view, ephemeral=True)



# --- MAIN COG ---

class GiveawayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            channel = self.bot.get_channel(GIVEAWAY_ADMIN_CHANNEL_ID)
            if channel:
                try: await channel.purge(limit=10)
                except: pass

                embed = Embed(
                    title="<:freeiconrefreshdata12388402:1473401657063899289> Управление розыгрышами",
                    description=(
                        "\n"
                        "Здесь вы можете запускать новые ивенты, выбирать победителей и просматривать список участников.\n"
                    ),
                    color=disnake.Color.from_rgb(54, 57, 63)
                )
                embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1462165491278938204/1473432485147840563/free-icon-supermarket-gift-372666.png?ex=6996306f&is=6994deef&hm=47078757bcba58904198fef68565880d646fe254a7e5aa7f93fbae61294fe6e9&")
                embed.set_footer(text="Absolute Famq", icon_url=self.bot.user.display_avatar.url)
                
                await channel.send(embed=embed, view=GiveawayAdminPanel())
                print(f"[GIVEAWAY] Админ-панель обновлена.")
        except Exception as e:
            print(f"[GIVEAWAY] Ошибка панели: {e}")

    @tasks.loop(minutes=1)
    async def check_giveaways(self):
        data = load_giveaway_data()
        if not data or data["status"] != "active": return
        
        try:
            end_dt = datetime.strptime(data["end_time"], "%Y-%m-%d %H:%M")
            if datetime.now() >= end_dt:
                guild = self.bot.get_guild(data["guild_id"])
                if guild:
                    await self.finish_giveaway(data, guild)
        except Exception as e:
            print(f"[GIVEAWAY] Timer error: {e}")

    async def finish_giveaway(self, data, guild):
        participants = data.get("participants", [])
        count = data.get("winner_count", 1)
        preselected = data.get("preselected_winners", [])
        
        winners = []
        # 1. Приоритет: Ручные победители
        for uid in preselected:
            if uid not in winners: winners.append(uid)
        
        # 2. Добивка рандомом
        needed = count - len(winners)
        if needed > 0:
            pool = [p for p in participants if p not in winners]
            if len(pool) >= needed:
                winners.extend(random.sample(pool, needed))
            else:
                winners.extend(pool)

        # Сохраняем статус и ОЧИЩАЕМ участников
        data["status"] = "finished"
        data["winners"] = winners
        data["participants"] = [] # <--- ОЧИСТКА СПИСКА УЧАСТНИКОВ
        data["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_giveaway_data(data)

        # 3. Редактируем сообщение (Эмбед)
        try:
            chan = guild.get_channel(GIVEAWAY_USER_CHANNEL_ID)
            if chan and data.get("fixed_message_id"):
                msg = await chan.fetch_message(data["fixed_message_id"])
                
                embed = create_giveaway_embed(data, self.bot.user)
                
                embed.title = "РОЗЫГРЫШ ЗАВЕРШЕН"
                embed.color = disnake.Color.from_rgb(54, 57, 63) 
                
                # Формируем список победителей с тегами
                w_list = ", ".join([f"<@{uid}>" for uid in winners]) if winners else "Нет победителей"
                
                # Добавляем поле с тегами
                embed.add_field(name="<:freeiconlaurel5021780:1472654712758341793> Победители", value=w_list, inline=False)

                # Удаляем кнопки (view=None)
                await msg.edit(embed=embed, view=None)
                
                if winners:
                    for uid in winners:
                        try:
                            member = guild.get_member(uid)
                            if member:
                                await member.send(embed=Embed(
                                    title="Поздравляем с победой!", 
                                    description=f"Вы выиграли в розыгрыше: **{data['prize']}**\nСвяжитесь со спонсором {data['sponsor']} для получения приза.",
                                    color=0xF1C40F,
                                    timestamp=datetime.now()
                                ).set_footer(text="Absolute Famq", icon_url=self.bot.user.display_avatar.url))
                        except: pass
        except Exception as e:
            print(f"[GIVEAWAY] Ошибка завершения: {e}")

        log_chan = guild.get_channel(GIVEAWAY_LOG_CHANNEL_ID)
        if log_chan:
            emb = Embed(title="Итоги розыгрыша", color=Color.green(), timestamp=datetime.now())
            emb.add_field(name="Приз", value=data["prize"])
            emb.add_field(name="Победители", value=", ".join([str(u) for u in winners]))
            emb.set_footer(text="Absolute Famq", icon_url=self.bot.user.display_avatar.url)
            await log_chan.send(embed=emb)

def setup(bot):
    bot.add_cog(GiveawayCog(bot))
