from disnake import Embed, Color
from datetime import datetime
from .config import LOG_ADMIN_ACTIONS_ID, LOG_USER_ACTIONS_ID, LOG_EVENT_HISTORY_ID
from .database import get_participants_struct

async def send_log(bot, channel_id, title, description, color=0x2B2D31, user=None):
    """Универсальная отправка лога"""
    if not channel_id: 
        return
    channel = bot.get_channel(channel_id)
    if not channel: 
        return
    embed = Embed(title=title, description=description, color=color, timestamp=datetime.now())
    if user:
        embed.set_footer(text=f"Выполнил: {user.display_name}", icon_url=user.display_avatar.url)
    try: 
        await channel.send(embed=embed)
    except: 
        pass

async def log_admin_action(bot, action_name, details, user):
    """Лог действий администратора"""
    await send_log(
        bot, LOG_ADMIN_ACTIONS_ID, 
        f"<:freeiconboss265674:1473388753111220357> Админ-действие: {action_name}", 
        details, 0x363941, user
    )

async def log_user_action(bot, action_name, details, user, is_negative=False):
    """Лог действий пользователя"""
    col = Color.red() if is_negative else Color.green()
    await send_log(
        bot, LOG_USER_ACTIONS_ID, 
        f"<:freeiconpeopletogether4596136:1473433825680953442> Участники: {action_name}", 
        details, col, user
    )

async def log_event_history(bot, event_data):
    """Отправляет финальный отчет о закрытом ивенте"""
    if not LOG_EVENT_HISTORY_ID: 
        return
    channel = bot.get_channel(LOG_EVENT_HISTORY_ID)
    if not channel: 
        return
    
    struct = get_participants_struct(event_data)
    main_txt = "\n".join([f"{i+1}. <@{p['user_id']}>" for i, p in enumerate(struct['main'])]) or "Пусто"
    res_txt = "\n".join([f"{i+1}. <@{p['user_id']}>" for i, p in enumerate(struct['reserve'])]) or "Пусто"
    
    embed = Embed(
        title=f"<:cross:1473380950770716836> Ивент завершен: {event_data['name']}", 
        color=0x2B2D31, 
        timestamp=datetime.now()
    )
    embed.add_field(
        name="Инфо", 
        value=f"Орг: {event_data['organizer']}\nВремя: {event_data['event_time']}", 
        inline=False
    )
    
    if len(main_txt) > 1000: 
        main_txt = main_txt[:950] + "\n..."
    if len(res_txt) > 1000: 
        res_txt = res_txt[:950] + "\n..."
    
    embed.add_field(name=f"Основа ({len(struct['main'])})", value=main_txt, inline=False)
    embed.add_field(name=f"Резерв ({len(struct['reserve'])})", value=res_txt, inline=False)
    
    try: 
        await channel.send(embed=embed)
    except: 
        pass
