# database.py

import os
import json
import sqlite3
import logging
from typing import Optional, Dict, List
from contextlib import contextmanager
from datetime import datetime, timedelta
import time # Добавили time для работы с timestamp

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = "bot_data.db"

@contextmanager
def get_db_connection():
    """Контекстный менеджер для работы с БД"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Ошибка при работе с БД: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_db():
    """Инициализация базы данных"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Таблицы (твои старые)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS private_channels (
                user_id TEXT PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS created_channels (
                channel_id INTEGER PRIMARY KEY,
                creator_id INTEGER NOT NULL,
                channel_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS application_form_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_data TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vacations (
                user_id TEXT PRIMARY KEY,
                roles_data TEXT,
                start_date TEXT,
                end_date TEXT,
                reason TEXT
            )
        ''')
        
        # --- ТАБЛИЦА ДЛЯ ОБЩИХ НАСТРОЕК (включая ID объявления) ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # --- ТАБЛИЦА ДЛЯ РОЗЫГРЫШЕЙ ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS giveaways (
                id TEXT PRIMARY KEY,
                description TEXT,
                prize TEXT,
                sponsor TEXT,
                winner_count INTEGER,
                end_time TEXT,
                status TEXT,
                fixed_message_id INTEGER,
                participants TEXT,
                winners TEXT,
                preselected_winners TEXT,
                preselected_by INTEGER,
                preselected_at TEXT,
                finished_at TEXT,
                guild_id INTEGER,
                thumbnail_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # --- 🔥 ТАБЛИЦА ДЛЯ МОНИТОРИНГА АКТИВНОСТИ СОТРУДНИКОВ ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                staff_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                target_user_id INTEGER,
                extra TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_staff_activity_lookup
            ON staff_activity (guild_id, staff_id, created_at DESC)
        """)
        
        # --- 🧊 ТАБЛИЦА ДЛЯ КУЛДАУНОВ ЗАЯВОК (НОВОЕ) ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS application_cooldowns (
                user_id INTEGER PRIMARY KEY,
                unban_timestamp REAL
            )
        ''')

        # Миграция колонок (если старая база)
        cursor.execute("PRAGMA table_info(giveaways)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if "thumbnail_url" not in existing_cols:
            cursor.execute("ALTER TABLE giveaways ADD COLUMN thumbnail_url TEXT")
        
        logger.info("База данных инициализирована")

# ========== ЛИЧНЫЕ КАНАЛЫ ==========
def get_private_channel(user_id: str) -> Optional[int]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT channel_id FROM private_channels WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result['channel_id'] if result else None

def set_private_channel(user_id: str, channel_id: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO private_channels (user_id, channel_id) VALUES (?, ?)",
            (user_id, channel_id)
        )

# ========== СОЗДАННЫЕ КАНАЛЫ (ОТКАТЫ) ==========
def add_created_channel(channel_id: int, creator_id: int, channel_name: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO created_channels (channel_id, creator_id, channel_name) VALUES (?, ?, ?)",
            (channel_id, creator_id, channel_name)
        )

def delete_created_channel(channel_id: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM created_channels WHERE channel_id = ?", (channel_id,))

def channel_exists(channel_id: int) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM created_channels WHERE channel_id = ?", (channel_id,))
        return cursor.fetchone() is not None

# ========== ФОРМА ЗАЯВОК ==========
def save_application_form(form_fields: List[Dict]):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        form_json = json.dumps(form_fields, ensure_ascii=False)
        cursor.execute("DELETE FROM application_form_config")
        cursor.execute(
            "INSERT INTO application_form_config (form_data, updated_at) VALUES (?, CURRENT_TIMESTAMP)",
            (form_json,)
        )

def get_application_form() -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT form_data FROM application_form_config ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        if result:
            return json.loads(result['form_data'])
        else:
            return get_default_application_form()

def get_default_application_form() -> List[Dict]:
    return [
        {
            "type": "text_input",
            "label": "Ваше имя, ник в игре и статик на 17 сервере",
            "custom_id": "nick_static",
            "style": "short",
            "required": True,
            "placeholder": "Виталий, Alexis, 344",
            "min_length": None, "max_length": None, "options": []
        },
        {
            "type": "text_input",
            "label": "Ваш средний онлайн + часовой пояс",
            "custom_id": "online_tz",
            "style": "short",
            "required": True,
            "placeholder": "5ч | +2 от мск",
            "min_length": None, "max_length": None, "options": []
        },
        {
            "type": "text_input",
            "label": "Откаты МП и ГГ сайга/спеш 5+ минут ",
            "custom_id": "chars_screen",
            "style": "paragraph",
            "required": True,
            "placeholder": "link",
            "min_length": None, "max_length": None, "options": []
        },
        {
            "type": "text_input",
            "label": "Ваша история семей",
            "custom_id": "Fam_id",
            "style": "paragraph",
            "required": True,
            "placeholder": "Ag, Blade, Cartel",
            "min_length": None, "max_length": None, "options": []
        }, 
    ]

# ========== УПРАВЛЕНИЕ ID ОБЪЯВЛЕНИЯ (НОВОЕ) ==========
def save_announcement_message_id(msg_id: int):
    """Сохраняет ID объявления об открытии набора"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', ('announcement_msg_id', str(msg_id)))

def get_announcement_message_id() -> Optional[int]:
    """Возвращает ID объявления (или None)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM config WHERE key = ?', ('announcement_msg_id',))
        row = cursor.fetchone()
        return int(row['value']) if row else None

def clear_announcement_message_id():
    """Удаляет сохранённый ID объявления"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM config WHERE key = ?', ('announcement_msg_id',))

# ========== ОТПУСКА ==========
def save_vacation_data(user_id, roles_list, start_date, end_date, reason):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        roles_json = json.dumps(roles_list)
        cursor.execute('''
            INSERT OR REPLACE INTO vacations (user_id, roles_data, start_date, end_date, reason)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, roles_json, start_date, end_date, reason))

def get_vacation_data(user_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT roles_data FROM vacations WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
    if result:
        return json.loads(result['roles_data'])
    return None

def delete_vacation_data(user_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM vacations WHERE user_id = ?', (user_id,))

# ========== РОЗЫГРЫШИ (ОБНОВЛЕНО) ==========
def load_giveaway_data() -> Optional[Dict]:
    """Получить последний активный розыгрыш"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM giveaways
            ORDER BY created_at DESC
            LIMIT 1
        ''')
        row = cursor.fetchone()

    if not row:
        return None

    # Функция для безопасной загрузки JSON
    def safe_load_list(val):
        if not val:
            return []
        try:
            return json.loads(val)
        except:
            return []

    return {
        "id": row['id'],
        "description": row['description'],
        "prize": row['prize'],
        "sponsor": row['sponsor'],
        "winner_count": row['winner_count'],
        "end_time": row['end_time'],
        "status": row['status'],
        "fixed_message_id": row['fixed_message_id'],
        "participants": safe_load_list(row['participants']),
        "winners": safe_load_list(row['winners']),
        "preselected_winners": safe_load_list(row['preselected_winners']),
        "preselected_by": row['preselected_by'],
        "preselected_at": row['preselected_at'],
        "finished_at": row['finished_at'],
        "guild_id": row['guild_id'],
        "thumbnail_url": row['thumbnail_url']
    }

def save_giveaway_data(data: Dict):
    """Сохранить или обновить данные розыгрыша"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Используем JSON вместо str() для надежности
        participants_json = json.dumps(data.get("participants", []))
        winners_json = json.dumps(data.get("winners", []))
        preselected_json = json.dumps(data.get("preselected_winners", []))

        cursor.execute('''
            INSERT OR REPLACE INTO giveaways
            (id, description, prize, sponsor, winner_count, end_time, status,
             fixed_message_id, participants, winners, preselected_winners,
             preselected_by, preselected_at, finished_at, guild_id, thumbnail_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(data.get("id", "")),
            str(data.get("description", "")),
            str(data.get("prize", "")),
            str(data.get("sponsor", "")),
            int(data.get("winner_count", 1)),
            str(data.get("end_time", "")),
            str(data.get("status", "active")),
            int(data.get("fixed_message_id")) if data.get("fixed_message_id") else None,
            participants_json,
            winners_json,
            preselected_json,
            int(data.get("preselected_by")) if data.get("preselected_by") else None,
            str(data.get("preselected_at", "")) if data.get("preselected_at") else None,
            str(data.get("finished_at", "")) if data.get("finished_at") else None,
            int(data.get("guild_id")) if data.get("guild_id") else None,
            str(data.get("thumbnail_url", "")) if data.get("thumbnail_url") else None
        ))
        logger.info(f"Розыгрыш {data.get('id')} сохранён")

# ========== СТАТУС ЗАЯВОК ==========
STATUS_FILE = "applications_status.json"

def get_applications_status():
    if not os.path.exists(STATUS_FILE):
        set_applications_status(True)
        return True
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("enabled", True)
    except:
        return True

def set_applications_status(enabled: bool):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump({"enabled": enabled}, f, ensure_ascii=False, indent=4)
    except:
        pass

# ========== 🔥 МОНИТОРИНГ АКТИВНОСТИ СОТРУДНИКОВ ==========

def log_staff_action(
    guild_id: int,
    staff_id: int,
    action_type: str,
    target_user_id: Optional[int] = None,
    extra: Optional[str] = None
):
    """
    Логирует действие сотрудника
    action_type: 'accept', 'accept_final', 'deny', 'call', 'chat_created', 'review'
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO staff_activity (guild_id, staff_id, action_type, target_user_id, extra)
            VALUES (?, ?, ?, ?, ?)
        """, (int(guild_id), int(staff_id), str(action_type), int(target_user_id) if target_user_id else None, extra))

def get_staff_stats(guild_id: int, staff_id: int, days: int = 7) -> Dict:
    """Получить статистику сотрудника за последние N дней"""
    since = (datetime.now() - timedelta(days=days)).isoformat(sep=" ")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Подсчёт по типам действий
        cursor.execute("""
            SELECT action_type, COUNT(*) as count
            FROM staff_activity
            WHERE guild_id = ? AND staff_id = ? AND created_at >= ?
            GROUP BY action_type
        """, (int(guild_id), int(staff_id), since))
        
        stats = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Общее количество действий
        cursor.execute("""
            SELECT COUNT(*) FROM staff_activity
            WHERE guild_id = ? AND staff_id = ? AND created_at >= ?
        """, (int(guild_id), int(staff_id), since))
        total = cursor.fetchone()[0]
        
        # Последнее действие
        cursor.execute("""
            SELECT action_type, created_at FROM staff_activity
            WHERE guild_id = ? AND staff_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (int(guild_id), int(staff_id)))
        last_action = cursor.fetchone()
        
        return {
            "total": total,
            "accepts": stats.get("accept", 0) + stats.get("accept_final", 0),  # Объединяем все принятия
            "denies": stats.get("deny", 0),
            "calls": stats.get("call", 0),
            "chats": stats.get("chat_created", 0),
            "reviews": stats.get("review", 0),
            "last_action": last_action[0] if last_action else None,
            "last_action_time": last_action[1] if last_action else None
        }

def get_all_staff_stats(guild_id: int, staff_members: List, days: int = 7) -> List[Dict]:
    """Получить статистику всех сотрудников"""
    stats_list = []
    
    for member in staff_members:
        if member.bot:
            continue
        
        stats = get_staff_stats(guild_id, member.id, days)
        if stats["total"] > 0:  # Показываем только активных
            stats_list.append({
                "member": member,
                "stats": stats
            })
    
    # Сортируем по активности
    stats_list.sort(key=lambda x: x["stats"]["total"], reverse=True)
    return stats_list


def set_application_cooldown(user_id: int, days: int = 7):
    """Устанавливает дату, до которой пользователю нельзя подавать заявку"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Вычисляем время разбана (текущее время + N дней в секундах)
        unban_time = time.time() + (days * 24 * 60 * 60)
        
        cursor.execute('''
            INSERT OR REPLACE INTO application_cooldowns (user_id, unban_timestamp)
            VALUES (?, ?)
        ''', (user_id, unban_time))

def check_application_cooldown(user_id: int) -> tuple[bool, Optional[float]]:
    """
    Проверяет, есть ли у пользователя кулдаун.
    Возвращает (True, timestamp_разбана), если заблокирован.
    Возвращает (False, None), если можно подавать.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT unban_timestamp FROM application_cooldowns WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    
    if row:
        unban_time = row['unban_timestamp']
        if time.time() < unban_time:
            return True, unban_time # Все еще в бане
        else:
            # Срок вышел, можно удалить запись (опционально, но полезно для очистки)
            # Но в данном случае оставим, просто вернем False
            return False, None
            
    return False, None

# Инициализация при старте
init_db()
