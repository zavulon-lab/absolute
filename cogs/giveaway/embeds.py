from disnake import Embed
from datetime import datetime
from .config import *

def create_giveaway_embed(data: dict, bot_user):
    """Генерация красивого эмбеда в стиле Calogero Famq"""
    
    is_finished = data.get("status") == "finished"
    
    embed = Embed(
        title=f"{EMOJI_RAFFLE} РОЗЫГРЫШ",
        color=AUX_COLOR
    )
    
    if data.get("description"):
        embed.description = f"{data['description']}\n"
    
    # Приз
    embed.add_field(
        name=f"{EMOJI_GIFT} Приз", 
        value=f"```fix\n{data['prize']}\n```", 
        inline=False
    )
    
    # Информация
    embed.add_field(
        name=f"{EMOJI_SPONSOR} Спонсор", 
        value=f"> **{data['sponsor']}**", 
        inline=True
    )
    embed.add_field(
        name=f"{EMOJI_LAUREL} Победителей", 
        value=f"> **{data['winner_count']}**", 
        inline=True
    )
    
    participants_count = len(data.get("participants", []))
    embed.add_field(
        name=f"{EMOJI_PEOPLE} Участников", 
        value=f"> **{participants_count}**", 
        inline=True
    )

    # Таймер (только если активен)
    if not is_finished:
        try:
            dt = datetime.strptime(data["end_time"], "%Y-%m-%d %H:%M")
            ts = int(dt.timestamp())
            time_str = f"<t:{ts}:R> (<t:{ts}:f>)"
        except:
            time_str = data["end_time"]
        
        embed.add_field(name="Итоги", value=time_str, inline=False)

    # Картинка
    if data.get("thumbnail_url"):
        embed.set_thumbnail(url=data["thumbnail_url"])
    
    # Футер
    icon_url = bot_user.display_avatar.url if bot_user else None
    embed.set_footer(text=FOOTER_TEXT, icon_url=icon_url)
    
    return embed

def create_admin_panel_embed(bot_user):
    """Embed для админ-панели"""
    embed = Embed(
        title=f"{EMOJI_GIFT} Управление розыгрышами",
        description=(
            "**Панель администратора**\n"
            "Здесь вы можете запускать новые ивенты, выбирать победителей и просматривать список участников.\n"
        ),
        color=AUX_COLOR
    )
    embed.set_thumbnail(url=THUMBNAIL_URL)
    embed.set_footer(text=FOOTER_TEXT, icon_url=bot_user.display_avatar.url)
    return embed

def create_participants_list_embed(participants: list, page: int, per_page: int, title: str = "Список участников"):
    """Embed для списка участников с пагинацией"""
    start = page * per_page
    end = start + per_page
    chunk = participants[start:end]
    
    description = ""
    for i, uid in enumerate(chunk, start=start + 1):
        description += f"**{i}.** <@{uid}> (`{uid}`)\n"
        
    if not description:
        description = "Список пуст."

    embed = Embed(title=title, description=description, color=AUX_COLOR)
    return embed

def create_winner_dm_embed(prize: str, sponsor: str, bot_user):
    """Embed для ЛС победителю"""
    embed = Embed(
        title="Поздравляем с победой!", 
        description=f"Вы выиграли в розыгрыше: **{prize}**\nСвяжитесь со спонсором {sponsor} для получения приза.",
        color=disnake.Color.from_rgb(54, 57, 63),
        timestamp=datetime.now()
    )
    embed.set_footer(text=FOOTER_TEXT, icon_url=bot_user.display_avatar.url if bot_user else None)
    return embed

def create_log_embed(title: str, prize: str, winners: list):
    """Embed для логов"""
    from disnake import Color
    embed = Embed(title=title, color=Color.green(), timestamp=datetime.now())
    embed.add_field(name="Приз", value=prize)
    embed.add_field(name="Победители", value=", ".join([str(u) for u in winners]))
    embed.set_footer(text=FOOTER_TEXT)
    return embed
