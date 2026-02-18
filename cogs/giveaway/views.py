import disnake
from disnake.ui import View, Button
from disnake import Interaction, ButtonStyle, Embed
import random
import uuid

from .config import *
from .database import save_giveaway_data, load_giveaway_by_id, load_all_active_giveaways
from .embeds import create_giveaway_embed, create_participants_list_embed
from .modals import GiveawayEditModal, WinnerSelectModal


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

    @disnake.ui.button(label="◀️", style=ButtonStyle.secondary, custom_id="prev")
    async def prev_page(self, button: Button, interaction: Interaction):
        self.page -= 1
        self.update_buttons()
        embed = create_participants_list_embed(self.participants, self.page, self.per_page, self.title)
        await interaction.response.edit_message(embed=embed, view=self)

    @disnake.ui.button(label="Стр. 1/1", style=ButtonStyle.gray, custom_id="counter", disabled=True)
    async def counter(self, button: Button, interaction: Interaction):
        pass

    @disnake.ui.button(label="▶️", style=ButtonStyle.secondary, custom_id="next")
    async def next_page(self, button: Button, interaction: Interaction):
        self.page += 1
        self.update_buttons()
        embed = create_participants_list_embed(self.participants, self.page, self.per_page, self.title)
        await interaction.response.edit_message(embed=embed, view=self)


class GiveawayPreviewView(View):
    def __init__(self, data: dict):
        super().__init__(timeout=600)
        self.data = data

    @disnake.ui.button(label="Опубликовать", style=ButtonStyle.success, emoji=EMOJI_TICK)
    async def confirm(self, button: Button, interaction: Interaction):
        if not self.data.get("id"):
            self.data["id"] = str(uuid.uuid4())[:8]

        save_giveaway_data(self.data)

        channel = interaction.guild.get_channel(GIVEAWAY_USER_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message(
                "Ошибка: канал розыгрышей не найден.", ephemeral=True
            )
            return

        embed = create_giveaway_embed(self.data, interaction.bot.user)
        try:
            msg = await channel.send(embed=embed, view=GiveawayJoinView(self.data["id"]))
            self.data["fixed_message_id"] = msg.id
            save_giveaway_data(self.data)
            await interaction.response.edit_message(
                content=f"Розыгрыш опубликован! [Перейти]({msg.jump_url})",
                view=None, embed=None
            )
        except Exception as e:
            print(f"[GIVEAWAY] Ошибка отправки: {e}")
            await interaction.response.edit_message(
                content="Ошибка при публикации розыгрыша.",
                view=None, embed=None
            )

    @disnake.ui.button(label="Отмена", style=ButtonStyle.danger, emoji=EMOJI_CROSS)
    async def cancel(self, button: Button, interaction: Interaction):
        await interaction.response.edit_message(content="Создание отменено.", view=None, embed=None)


class GiveawayJoinView(View):
    def __init__(self, giveaway_id: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @disnake.ui.button(
        label="Участвовать",
        style=ButtonStyle.success,
        emoji=EMOJI_RAFFLE,
        custom_id="btn_join_giveaway"
    )
    async def join(self, button: Button, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        data = load_giveaway_by_id(self.giveaway_id)
        if not data or data.get("status") != "active":
            return await interaction.followup.send("Этот розыгрыш уже завершён.", ephemeral=True)

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

        try:
            embed = create_giveaway_embed(data, interaction.bot.user)
            await interaction.message.edit(embed=embed)
        except Exception:
            pass

        await interaction.followup.send(msg, ephemeral=True)


# ---------------------------------------------------------------------------
# Управление конкретным розыгрышем
# ---------------------------------------------------------------------------

class GiveawayControlView(View):
    def __init__(self, giveaway_id: str):
        super().__init__(timeout=300)
        self.giveaway_id = giveaway_id

    @disnake.ui.button(label="Участники", style=ButtonStyle.gray, emoji="👥", row=0)
    async def list_participants(self, button: Button, interaction: Interaction):
        data = load_giveaway_by_id(self.giveaway_id)
        if not data:
            return await interaction.response.send_message("Розыгрыш не найден.", ephemeral=True)

        participants = data.get("participants", [])
        if not participants:
            return await interaction.response.send_message("Список пуст.", ephemeral=True)

        view = ParticipantsPaginationView(participants, title=f"Участники | {data['prize']}")
        embed = create_participants_list_embed(participants, 0, 20, title=f"Участники | {data['prize']}")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @disnake.ui.button(label="Тест рандома", style=ButtonStyle.secondary, emoji="🎲", row=0)
    async def reroll(self, button: Button, interaction: Interaction):
        data = load_giveaway_by_id(self.giveaway_id)
        if not data or data["status"] != "active":
            return await interaction.response.send_message("Розыгрыш не активен.", ephemeral=True)

        participants = data.get("participants", [])
        if not participants:
            return await interaction.response.send_message("Нет участников.", ephemeral=True)

        winner = random.choice(participants)
        await interaction.response.send_message(
            f"🎲 Тестовый победитель: <@{winner}>", ephemeral=True
        )

    @disnake.ui.button(label="Сбросить выбор", style=ButtonStyle.danger, emoji="✖️", row=1)
    async def reset_winners(self, button: Button, interaction: Interaction):
        data = load_giveaway_by_id(self.giveaway_id)
        if not data:
            return await interaction.response.send_message("Розыгрыш не найден.", ephemeral=True)

        data["preselected_winners"] = []
        data.pop("preselected_by", None)
        data.pop("preselected_at", None)
        save_giveaway_data(data)
        await interaction.response.send_message("Предварительные победители сброшены.", ephemeral=True)

    @disnake.ui.button(label="Обновить Embed", style=ButtonStyle.secondary, emoji="🔄", row=1)
    async def refresh_embed(self, button: Button, interaction: Interaction):
        data = load_giveaway_by_id(self.giveaway_id)
        if not data:
            return await interaction.response.send_message("Розыгрыш не найден.", ephemeral=True)

        try:
            chan = interaction.guild.get_channel(GIVEAWAY_USER_CHANNEL_ID)
            if not chan or not data.get("fixed_message_id"):
                return await interaction.response.send_message("Сообщение не найдено.", ephemeral=True)

            msg = await chan.fetch_message(data["fixed_message_id"])
            embed = create_giveaway_embed(data, interaction.bot.user)
            await msg.edit(embed=embed, view=GiveawayJoinView(data["id"]))
            await interaction.response.send_message("Embed обновлён!", ephemeral=True)

        except disnake.NotFound:
            await interaction.response.send_message("Сообщение было удалено.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Ошибка: {e}", ephemeral=True)

    @disnake.ui.button(label="Завершить", style=ButtonStyle.danger, emoji="🛑", row=1)
    async def force_finish(self, button: Button, interaction: Interaction):
        data = load_giveaway_by_id(self.giveaway_id)
        if not data or data.get("status") != "active":
            return await interaction.response.send_message("Розыгрыш не активен.", ephemeral=True)

        await interaction.response.send_message(
            f"Завершаю розыгрыш `{self.giveaway_id}`...", ephemeral=True
        )
        from .__init__ import GiveawayCog
        cog: GiveawayCog = interaction.bot.get_cog("GiveawayCog")
        if cog:
            await cog.finish_giveaway(data, interaction.guild)


# ---------------------------------------------------------------------------
# Список активных розыгрышей
# ---------------------------------------------------------------------------

class ActiveGiveawaysView(View):
    def __init__(self, giveaways: list):
        super().__init__(timeout=120)
        self.giveaways = giveaways
        self._build_buttons()

    def _build_buttons(self):
        for gw in self.giveaways[:25]:
            btn = Button(
                label=f"🎁 {gw['prize'][:40]} [{gw['id']}]",
                style=ButtonStyle.primary,
                custom_id=f"select_gw_{gw['id']}"
            )
            btn.callback = self._make_callback(gw["id"])
            self.add_item(btn)

    def _make_callback(self, giveaway_id: str):
        async def callback(interaction: Interaction):
            data = load_giveaway_by_id(giveaway_id)
            if not data:
                return await interaction.response.send_message("Розыгрыш не найден.", ephemeral=True)
            embed = create_giveaway_embed(data, interaction.bot.user)
            embed.title = f"⚙️ Управление | {data['prize']}"
            await interaction.response.send_message(
                embed=embed,
                view=GiveawayControlView(giveaway_id),
                ephemeral=True
            )
        return callback

    def create_embed(self) -> Embed:
        embed = Embed(title="🎉 Активные розыгрыши", color=AUX_COLOR)
        for gw in self.giveaways:
            count = len(gw.get("participants", []))
            embed.add_field(
                name=f"🎁 {gw['prize']} | ID: `{gw['id']}`",
                value=(
                    f"Спонсор: **{gw['sponsor']}** · "
                    f"Участников: **{count}** · "
                    f"Завершится: **{gw['end_time']}**"
                ),
                inline=False
            )
        return embed


# ---------------------------------------------------------------------------
# Админ-панель
# ---------------------------------------------------------------------------

class GiveawayAdminPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(
        label="Создать",
        style=ButtonStyle.primary,
        emoji=EMOJI_PLUS,
        custom_id="adm_gw_create",
        row=0
    )
    async def create(self, button: Button, interaction: Interaction):
        await interaction.response.send_modal(GiveawayEditModal())

    @disnake.ui.button(
        label="Управление",
        style=ButtonStyle.secondary,
        emoji="⚙️",
        custom_id="adm_gw_manage",
        row=0
    )
    async def manage(self, button: Button, interaction: Interaction):
        giveaways = load_all_active_giveaways()
        if not giveaways:
            return await interaction.response.send_message("Нет активных розыгрышей.", ephemeral=True)
        view = ActiveGiveawaysView(giveaways)
        await interaction.response.send_message(
            embed=view.create_embed(), view=view, ephemeral=True
        )

