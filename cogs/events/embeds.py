from disnake import Embed
from .database import get_participants_struct

def generate_admin_embeds(data=None, bot=None):
    """Возвращает СПИСОК с одним эмбедом, содержащим и основу, и резерв"""
    
    embed = Embed(color=0x2B2D31)
    
    # Пытаемся получить иконку бота, если передан bot
    icon_url = None
    if bot:
        icon_url = bot.user.display_avatar.url
    
    if not data:
        embed.description = "**Регистрация:** не активна"
        if icon_url: 
            embed.set_footer(text="Absolute Famq", icon_url=icon_url)
        else: 
            embed.set_footer(text="Absolute Famq")
        return [embed]

    struct = get_participants_struct(data)
    main_list = struct["main"]
    reserve_list = struct["reserve"]
    max_slots = data["max_slots"]
    
    if data["status"] == "paused": 
        status_text = "ПАУЗА <:freeiconstop394592:1473441364938194976>"
    elif data["status"] == "draft": 
        status_text = "приостановлена"
    else: 
        status_text = "доступна <:tick:1473380953245221016> "
    
    desc_text = (
        f"**Мероприятие:** {data['name']}\n"
        f"**Регистрация:** {status_text}\n\n"
        f"> **Время:** {data['event_time']}\n"
        f"> **Примечание:** {data['description']}\n"
    )
    embed.description = desc_text
    
    embed.add_field(
        name=f"**Зарегистрированные участники: {len(main_list) + len(reserve_list)}**",
        value=f"**Основной состав ({len(main_list)}/{max_slots}):**",
        inline=False
    )
    
    # Генерация колонок ОСНОВЫ
    USERS_PER_COLUMN = 20
    all_lines = [f"{i+1}) <@{p['user_id']}>" for i, p in enumerate(main_list)]
    chunks = [all_lines[i:i + USERS_PER_COLUMN] for i in range(0, len(all_lines), USERS_PER_COLUMN)]
    
    if not chunks:
        embed.add_field(name="⠀", value="*Список пуст*", inline=False)
    else:
        for i, chunk in enumerate(chunks):
            if i >= 6:
                embed.add_field(name="...", value=f"... еще {len(main_list) - (i*USERS_PER_COLUMN)} ...", inline=False)
                break
            embed.add_field(name="⠀", value="\n".join(chunk), inline=True)

    # ЗАГОЛОВОК РЕЗЕРВА
    embed.add_field(
        name="⠀",
        value=f"**Резервный список ({len(reserve_list)}):**",
        inline=False
    )
    
    # Генерация колонок РЕЗЕРВА
    if reserve_list:
        res_lines = [f"{i+1}) <@{p['user_id']}>" for i, p in enumerate(reserve_list)]
        res_chunks = [res_lines[i:i + USERS_PER_COLUMN] for i in range(0, len(res_lines), USERS_PER_COLUMN)]
        
        for i, chunk in enumerate(res_chunks):
            if i >= 6:
                embed.add_field(name="...", value="... (список слишком велик) ...", inline=False)
                break
            embed.add_field(name="⠀", value="\n".join(chunk), inline=True)
    else:
        embed.add_field(name="⠀", value="*Резерв пуст*", inline=False)

    if data.get("image_url"):
        embed.set_image(url=data["image_url"])
    
    # Установка футера
    if icon_url:
        embed.set_footer(text="Absolute Famq", icon_url=icon_url)
    else:
        embed.set_footer(text="Absolute Famq")

    return [embed]
