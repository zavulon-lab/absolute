import os
import json
import sqlite3
import logging
from typing import Optional, Dict, List
from contextlib import contextmanager
from datetime import datetime, timedelta
import time

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
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # ── 1. Создание таблиц ────────────────────────────────────────────────

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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                staff_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                target_user_id INTEGER,
                extra TEXT,
                role_type TEXT NOT NULL DEFAULT 'recruiter',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS application_cooldowns (
                user_id INTEGER PRIMARY KEY,
                unban_timestamp REAL
            )
        ''')

        # ── 2. Миграции (ALTER TABLE) — ОБЯЗАТЕЛЬНО ДО создания индексов ─────

        # giveaways: thumbnail_url
        cursor.execute("PRAGMA table_info(giveaways)")
        giveaway_cols = {row[1] for row in cursor.fetchall()}
        if "thumbnail_url" not in giveaway_cols:
            cursor.execute("ALTER TABLE giveaways ADD COLUMN thumbnail_url TEXT")
            logger.info("Миграция: добавлена колонка thumbnail_url в giveaways")

        # staff_activity: role_type — главная причина ошибки
        cursor.execute("PRAGMA table_info(staff_activity)")
        activity_cols = {row[1] for row in cursor.fetchall()}
        if "role_type" not in activity_cols:
            cursor.execute(
                "ALTER TABLE staff_activity ADD COLUMN role_type TEXT NOT NULL DEFAULT 'recruiter'"
            )
            logger.info("Миграция: добавлена колонка role_type в staff_activity")

        # ── 3. Индексы — ТОЛЬКО ПОСЛЕ миграций ───────────────────────────────
        # Теперь role_type гарантированно существует в таблице

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_staff_activity_lookup
            ON staff_activity (guild_id, staff_id, role_type, created_at DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_staff_activity_role
            ON staff_activity (guild_id, role_type, created_at DESC)
        """)

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


# ========== СОЗДАННЫЕ КАНАЛЫ ==========

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
            "label": "Откаты МП и ГГ сайга/спеш 5+ минут",
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


# ========== ОБЪЯВЛЕНИЯ ==========

def save_announcement_message_id(msg_id: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)',
            ('announcement_msg_id', str(msg_id))
        )


def get_announcement_message_id() -> Optional[int]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM config WHERE key = ?', ('announcement_msg_id',))
        row = cursor.fetchone()
        return int(row['value']) if row else None


def clear_announcement_message_id():
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


# ========== РОЗЫГРЫШИ ==========

def load_giveaway_data() -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM giveaways ORDER BY created_at DESC LIMIT 1')
        row = cursor.fetchone()

    if not row:
        return None

    def safe_list(val):
        if not val:
            return []
        try:
            return json.loads(val)
        except Exception:
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
        "participants": safe_list(row['participants']),
        "winners": safe_list(row['winners']),
        "preselected_winners": safe_list(row['preselected_winners']),
        "preselected_by": row['preselected_by'],
        "preselected_at": row['preselected_at'],
        "finished_at": row['finished_at'],
        "guild_id": row['guild_id'],
        "thumbnail_url": row['thumbnail_url'],
    }


def save_giveaway_data(data: Dict):
    with get_db_connection() as conn:
        cursor = conn.cursor()
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
            json.dumps(data.get("participants", [])),
            json.dumps(data.get("winners", [])),
            json.dumps(data.get("preselected_winners", [])),
            int(data.get("preselected_by")) if data.get("preselected_by") else None,
            str(data.get("preselected_at")) if data.get("preselected_at") else None,
            str(data.get("finished_at")) if data.get("finished_at") else None,
            int(data.get("guild_id")) if data.get("guild_id") else None,
            str(data.get("thumbnail_url")) if data.get("thumbnail_url") else None,
        ))
        logger.info(f"Розыгрыш {data.get('id')} сохранён")


# ========== СТАТУС ЗАЯВОК ==========

STATUS_FILE = "applications_status.json"


def get_applications_status() -> bool:
    if not os.path.exists(STATUS_FILE):
        set_applications_status(True)
        return True
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("enabled", True)
    except Exception:
        return True


def set_applications_status(enabled: bool):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump({"enabled": enabled}, f, ensure_ascii=False, indent=4)
    except Exception:
        pass


# ========== МОНИТОРИНГ АКТИВНОСТИ СОТРУДНИКОВ ==========
#
#  role_type = 'recruiter'   → действия в заявках (review_view.py)
#              'cheathunter' → действия верификации на ПО (verification.py)
#
#  Таблица action_type по ролям:
#   recruiter:   accept_final, deny, call, chat_created, review
#   cheathunter: verify_check (создал канал проверки),
#                verify_accept (выдал роль),
#                verify_reject (отказал сразу),
#                verify_reject_final (отказал после проверки)


def log_staff_action(
    guild_id: int,
    staff_id: int,
    action_type: str,
    target_user_id: Optional[int] = None,
    extra: Optional[str] = None,
    role_type: str = "recruiter",   # 'recruiter' или 'cheathunter'
):
    """
    Логирует действие сотрудника.

    Вызов для рекрутёра (review_view.py):
        log_staff_action(..., role_type="recruiter")

    Вызов для чит-хантера (verification.py):
        log_staff_action(..., role_type="cheathunter")
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO staff_activity
                (guild_id, staff_id, action_type, target_user_id, extra, role_type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            int(guild_id),
            int(staff_id),
            str(action_type),
            int(target_user_id) if target_user_id else None,
            extra,
            role_type,
        ))


def get_staff_stats(
    guild_id: int,
    staff_id: int,
    days: int = 7,
    role_type: Optional[str] = None,   # None = все действия сотрудника
) -> Dict:
    """
    Возвращает статистику сотрудника за последние N дней.
    Если role_type указан — фильтрует только по этому типу роли.
    """
    since = (datetime.now() - timedelta(days=days)).isoformat(sep=" ")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        if role_type:
            where = "guild_id = ? AND staff_id = ? AND created_at >= ? AND role_type = ?"
            params = (int(guild_id), int(staff_id), since, role_type)
        else:
            where = "guild_id = ? AND staff_id = ? AND created_at >= ?"
            params = (int(guild_id), int(staff_id), since)

        cursor.execute(f"""
            SELECT action_type, COUNT(*) as cnt
            FROM staff_activity
            WHERE {where}
            GROUP BY action_type
        """, params)
        counts = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute(f"SELECT COUNT(*) FROM staff_activity WHERE {where}", params)
        total = cursor.fetchone()[0]

        # Последнее действие — без фильтра по role_type, чтобы всегда было актуально
        cursor.execute("""
            SELECT action_type, created_at FROM staff_activity
            WHERE guild_id = ? AND staff_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (int(guild_id), int(staff_id)))
        last = cursor.fetchone()

    # ── Рекрутёрские метрики ──────────────────────────────────────────────────
    recruiter_stats = {
        "accepts":  counts.get("accept", 0) + counts.get("accept_final", 0),
        "denies":   counts.get("deny", 0),
        "calls":    counts.get("call", 0),
        "chats":    counts.get("chat_created", 0),
        "reviews":  counts.get("review", 0),
    }

    # ── Чит-хантерские метрики ────────────────────────────────────────────────
    hunter_stats = {
        "verify_checks":        counts.get("verify_check", 0),         # создал канал проверки
        "verify_accepts":       counts.get("verify_accept", 0),        # выдал роль
        "verify_rejects":       counts.get("verify_reject", 0),        # отказал сразу
        "verify_rejects_final": counts.get("verify_reject_final", 0),  # отказал после проверки
    }

    return {
        "total": total,
        # рекрутёр
        **recruiter_stats,
        # чит-хантер
        **hunter_stats,
        "last_action":      last[0] if last else None,
        "last_action_time": last[1] if last else None,
    }


def get_all_staff_stats(
    guild_id: int,
    staff_members: List,
    days: int = 7,
    role_type: Optional[str] = None,   # передай 'recruiter' или 'cheathunter'
) -> List[Dict]:
    """
    Возвращает список сотрудников с их статистикой.
    role_type позволяет показывать только нужные действия для каждого отдела.
    """
    result = []
    for member in staff_members:
        if member.bot:
            continue
        stats = get_staff_stats(guild_id, member.id, days, role_type=role_type)
        if stats["total"] > 0:
            result.append({"member": member, "stats": stats})

    result.sort(key=lambda x: x["stats"]["total"], reverse=True)
    return result


# ========== КУЛДАУНЫ ЗАЯВОК ==========

def set_application_cooldown(user_id: int, days: int = 7):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        unban_time = time.time() + (days * 24 * 60 * 60)
        cursor.execute(
            'INSERT OR REPLACE INTO application_cooldowns (user_id, unban_timestamp) VALUES (?, ?)',
            (user_id, unban_time)
        )


def check_application_cooldown(user_id: int) -> tuple[bool, Optional[float]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT unban_timestamp FROM application_cooldowns WHERE user_id = ?", (user_id,)
        )
        row = cursor.fetchone()

    if row:
        unban_time = row['unban_timestamp']
        if time.time() < unban_time:
            return True, unban_time
    return False, None


# Инициализация при старте
init_db()
