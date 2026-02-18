from disnake.ui import Modal, TextInput
from disnake import Interaction, TextInputStyle, Embed
from datetime import datetime, timezone
import uuid

from .config import *
from .database import save_giveaway_data, load_giveaway_by_id
from .embeds import create_giveaway_embed


class GiveawayEditModal(Modal):
    def __init__(self):
        components = [
            TextInput(
                label="Описание",
                custom_id="desc",
                style=TextInputStyle.paragraph,
                placeholder="Условия...",
                required=True
            ),
            TextInput(
                label="Приз",
                custom_id="prize",
                placeholder="Например: 500 рублей",
                required=True
            ),
            TextInput(
                label="Спонсор",
                custom_id="sponsor",
                placeholder="Ник спонсора",
                required=True
            ),
            TextInput(
                label="Количество победителей",
                custom_id="winners",
                value="1",
                required=True
            ),
            TextInput(
                label="Время окончания (YYYY-MM-DD HH:MM)",
                custom_id="end_time",
                placeholder="2026-02-15 18:00",
                required=True
            ),
        ]
        super().__init__(title="Создать розыгрыш", components=components)

    async def callback(self, interaction: Interaction):
        try:
            w_count = int(interaction.text_values["winners"])
            if w_count < 1 or w_count > MAX_WINNERS:
                raise ValueError
            end_dt = datetime.strptime(interaction.text_values["end_time"], "%Y-%m-%d %H:%M")
        except ValueError:
            await interaction.response.send_message(
                "Ошибка данных! Проверьте число победителей и формат даты.",
                ephemeral=True
            )
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
            "thumbnail_url": THUMBNAIL_URL,
        }

        from .views import GiveawayPreviewView

        preview_embed = create_giveaway_embed(temp_data, interaction.bot.user)
        preview_embed.title = f"{EMOJI_DOCS} Предпросмотр"

        await interaction.response.send_message(
            embed=preview_embed,
            view=GiveawayPreviewView(temp_data),
            ephemeral=True
        )


class WinnerSelectModal(Modal):
    """Ручной выбор победителей для конкретного розыгрыша."""

    def __init__(self, giveaway_id: str):
        self.giveaway_id = giveaway_id
        components = [
            TextInput(
                label="ID победителей (через пробел)",
                custom_id="winners",
                style=TextInputStyle.paragraph,
                placeholder="123456789 987654321",
                required=True
            )
        ]
        super().__init__(title="Ручной выбор победителей", components=components)

    async def callback(self, interaction: Interaction):
        data = load_giveaway_by_id(self.giveaway_id)
        if not data or data.get("status") != "active":
            await interaction.response.send_message("Розыгрыш не найден или завершён.", ephemeral=True)
            return

        try:
            input_text = interaction.text_values["winners"].replace(",", " ").split()
            winner_ids = [int(x) for x in input_text]
        except ValueError:
            await interaction.response.send_message("Ошибка: введите только цифры ID.", ephemeral=True)
            return

        guild = interaction.guild
        mentions = [
            guild.get_member(uid).mention if guild.get_member(uid) else f"ID {uid}"
            for uid in winner_ids
        ]

        log_chan = guild.get_channel(GIVEAWAY_LOG_CHANNEL_ID)
        if log_chan:
            emb = Embed(
                title=f"{EMOJI_CROWN} Ручной выбор победителей",
                description=(
                    f"Администратор {interaction.user.mention} зафиксировал "
                    f"для розыгрыша `{self.giveaway_id}`:\n" + ", ".join(mentions)
                ),
                color=AUX_COLOR,
                timestamp=datetime.now()
            )
            await log_chan.send(embed=emb)

        data["preselected_winners"] = winner_ids
        data["preselected_by"] = interaction.user.id
        data["preselected_at"] = datetime.now(timezone.utc).isoformat()
        save_giveaway_data(data)

        await interaction.response.send_message(
            f"Зафиксировано {len(winner_ids)} победителей для розыгрыша `{self.giveaway_id}`.",
            ephemeral=True
        )
