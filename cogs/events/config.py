import sys
import os
from pathlib import Path
import disnake

# Добавляем путь для импорта из корня
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Импорт констант из корневого constants.py
try:
    from constants import (
        EVENTS_CHANNEL_ID, EVENTS_ADMIN_CHANNEL_ID,
        LOG_ADMIN_ACTIONS_ID, LOG_EVENT_HISTORY_ID, LOG_USER_ACTIONS_ID
    )
    try: 
        from constants import EVENT_VOICE_CHANNEL_ID 
    except: 
        EVENT_VOICE_CHANNEL_ID = 1469489179766292755
    try: 
        from constants import EVENTS_TAG_CHANNEL_ID 
    except: 
        EVENTS_TAG_CHANNEL_ID = 1469491042679128164
    try: 
        from constants import EVENTS_PRIORITY_ROLE_ID
    except: 
        EVENTS_PRIORITY_ROLE_ID = 123456789012345678
    try:
        from constants import VOD_SUBMIT_CHANNEL_ID
    except:
        VOD_SUBMIT_CHANNEL_ID = 1472985007403307191
except ImportError:
    EVENTS_CHANNEL_ID = 0
    EVENTS_ADMIN_CHANNEL_ID = 0
    LOG_ADMIN_ACTIONS_ID = 0
    LOG_EVENT_HISTORY_ID = 0
    LOG_USER_ACTIONS_ID = 0
    EVENT_VOICE_CHANNEL_ID = 1469489179766292755
    EVENTS_TAG_CHANNEL_ID = 1469491042679128164
    EVENTS_PRIORITY_ROLE_ID = 123456789012345678
    VOD_SUBMIT_CHANNEL_ID = 1472985007403307191

# Путь к базе данных
DB_PATH = Path("events.db")

# Цвета
AUX_COLOR = disnake.Color.from_rgb(54, 57, 63)

# ===== КАСТОМНЫЕ ЭМОДЗИ =====
# Админ-панель (MainAdminView)
EMOJI_DICE = "<:freeiconrocket6699887:1473360986265227325>"
EMOJI_TRASH = "<:freeiconmeteorite6699854:1473360985216782509>"
EMOJI_PLUS = "<:freeiconplus1828819:1473433100737319114>"
EMOJI_MINUS = "<:freeiconminus10263924:1473440518536171746>"
EMOJI_MIC = "🎙️"
EMOJI_CHAT = "<:__:1473379222432256083>"
EMOJI_MEGAPHONE = "<:freeiconmegaphone716224:1473440844806619136>"
EMOJI_GEAR = "<:freeicondocuments1548205:1473390852234543246>"

# Публичная панель (EventUserView)
EMOJI_JOIN = "<:freeiconplus1828819:1473433100737319114>"
EMOJI_LEAVE = "<:freeiconminus10263924:1473440518536171746>"

# Меню управления (OtherOptionsView) - Select Options
EMOJI_STAR = "<:ddd:1473378828427460618>"
EMOJI_INBOX = "<:add:1473387233372541102>"
EMOJI_PLUS_CIRCLE = "<:freeiconplus1828819:1473433100737319114>"
EMOJI_SETTINGS = "<:freeicondrawing14958309:1473426934732947560>"
EMOJI_PAUSE = "<:freeiconstop394592:1473441364938194976>"
EMOJI_RESUME = "<:freeiconpowerbutton4943421:1473441364170772674>"
EMOJI_DOOR = "<:freeicongrimreaper7515728:1473373897855340617>"
EMOJI_CAMERA = "<:teg:1473384504537383157>"

# Меню управления - кнопки внутри
EMOJI_PLUS_BTN = "<:freeiconplus1828819:1472681225935392858>"
EMOJI_MINUS_BTN = "<:freeiconminus10263924:1473440518536171746>"
EMOJI_EYE = "<:freeiconrecruiter7250697:1473386162566598756>"
EMOJI_BIN = "<:freeicontrash10654603:1473426946552496211>"
EMOJI_CHECK = "<:freeiconswitcharrows9282594:1473359651318792282>"
EMOJI_PENCIL = "<:freeicondrawing14958309:1473426934732947560>"
EMOJI_PLAY = "<:freeiconpowerbutton4943421:1473441364170772674>"
EMOJI_PAUSE_BTN = "<:freeiconstop394592:1473441364938194976>"
EMOJI_DOOR_BTN = "<:freeicongrimreaper7515728:1473373897855340617>"
EMOJI_CAMERA_BTN = "<:teg:1473384504537383157>"

# Закрыть меню
EMOJI_CROSS = "<:cross:1473380950770716836>"
