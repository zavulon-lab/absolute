import sys
import os
import disnake

# Добавляем путь для импорта из корня
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Импорт констант из корневого constants.py
try:
    from constants import (
        GIVEAWAY_USER_CHANNEL_ID,
        GIVEAWAY_ADMIN_CHANNEL_ID,
        GIVEAWAY_LOG_CHANNEL_ID,
        MAX_WINNERS
    )
except ImportError:
    GIVEAWAY_USER_CHANNEL_ID = 0
    GIVEAWAY_ADMIN_CHANNEL_ID = 0
    GIVEAWAY_LOG_CHANNEL_ID = 0
    MAX_WINNERS = 10

# Цвета
AUX_COLOR = disnake.Color.from_rgb(54, 57, 63)

# ===== ЭМОДЗИ =====
# Основные
EMOJI_RAFFLE = "<:freeiconraffle5736412:1473435748207169627>"
EMOJI_GIFT = "<:freeicongift6280355:1473434679808884939>"
EMOJI_SPONSOR = "<:freeiconsponsor1478946:1473435087336112199>"
EMOJI_CROWN = "<:freeiconcrown1404959:1473435086010450041>"
EMOJI_PEOPLE = "<:freeiconpeopletogether4596136:1473433825680953442>"
EMOJI_TIME = "<:freeicontime2071878:1473435086568615966>"
EMOJI_DOCS = "<:freeicondocuments1548205:1473390852234543246>"
EMOJI_LAUREL = "<:freeiconcrown1404959:1473435086010450041>"

# Кнопки админки
EMOJI_PLUS = "<:freeiconplus1828819:1473433100737319114>"
EMOJI_DICE = "<:freeicondice2102161:1473432878841856021>"
EMOJI_MAN = "<:freeiconman7238426:1473433824091443353>"
EMOJI_REFRESH = "<:freeiconrefreshdata12388402:1473401657063899289>"

# Статус
EMOJI_TICK = "<:tick:1473380953245221016>"
EMOJI_CROSS = "<:cross:1473380950770716836>"

# Картинки
THUMBNAIL_URL = "https://media.discordapp.net/attachments/1336423985794682974/1336423986381754409/6FDCFF59-EFBB-4D26-9E57-50B0F3D61B50.jpg"
ADMIN_PANEL_THUMBNAIL = "https://cdn.discordapp.com/attachments/1462165491278938204/1473432485147840563/free-icon-supermarket-gift-372666.png"

FOOTER_TEXT = "Absolute famq"