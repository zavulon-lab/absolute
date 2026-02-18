import json
import sqlite3
import logging
from typing import Optional, Dict, List
from contextlib import contextmanager

logger = logging.getLogger(__name__)

GIVEAWAY_DB_PATH = "giveaway_data.db"


@contextmanager
def get_db():
    conn = None
    try:
        conn = sqlite3.connect(GIVEAWAY_DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"[GIVEAWAY DB] Ошибка: {e}")
        raise
    finally:
        if conn:
            conn.close()


def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS giveaways (
                id TEXT PRIMARY KEY,
                description TEXT,
                prize TEXT,
                sponsor TEXT,
                winner_count INTEGER,
                end_time TEXT,
                status TEXT DEFAULT 'active',
                fixed_message_id INTEGER,
                participants TEXT DEFAULT '[]',
                winners TEXT DEFAULT '[]',
                preselected_winners TEXT DEFAULT '[]',
                preselected_by INTEGER,
                preselected_at TEXT,
                finished_at TEXT,
                guild_id INTEGER,
                thumbnail_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_status
            ON giveaways (status, created_at)
        ''')
    logger.info("[GIVEAWAY DB] Инициализирована.")


def _to_dict(row) -> Dict:
    def safe(val):
        if not val:
            return []
        try:
            return json.loads(val)
        except Exception:
            return []

    return {
        "id":                  row["id"],
        "description":         row["description"],
        "prize":               row["prize"],
        "sponsor":             row["sponsor"],
        "winner_count":        row["winner_count"],
        "end_time":            row["end_time"],
        "status":              row["status"],
        "fixed_message_id":    row["fixed_message_id"],
        "participants":        safe(row["participants"]),
        "winners":             safe(row["winners"]),
        "preselected_winners": safe(row["preselected_winners"]),
        "preselected_by":      row["preselected_by"],
        "preselected_at":      row["preselected_at"],
        "finished_at":         row["finished_at"],
        "guild_id":            row["guild_id"],
        "thumbnail_url":       row["thumbnail_url"],
    }


def load_giveaway_by_id(giveaway_id: str) -> Optional[Dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM giveaways WHERE id = ?", (giveaway_id,)
        ).fetchone()
    return _to_dict(row) if row else None


def load_all_active_giveaways() -> List[Dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM giveaways WHERE status = 'active' ORDER BY created_at ASC"
        ).fetchall()
    return [_to_dict(r) for r in rows]


def load_giveaway_data() -> Optional[Dict]:
    """Обратная совместимость."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM giveaways WHERE status = 'active' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return _to_dict(row) if row else None


def save_giveaway_data(data: Dict):
    with get_db() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO giveaways
            (id, description, prize, sponsor, winner_count, end_time, status,
             fixed_message_id, participants, winners, preselected_winners,
             preselected_by, preselected_at, finished_at, guild_id, thumbnail_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(data["id"]),
            str(data.get("description", "")),
            str(data.get("prize", "")),
            str(data.get("sponsor", "")),
            int(data.get("winner_count", 1)),
            str(data.get("end_time", "")),
            str(data.get("status", "active")),
            int(data["fixed_message_id"]) if data.get("fixed_message_id") else None,
            json.dumps(data.get("participants", [])),
            json.dumps(data.get("winners", [])),
            json.dumps(data.get("preselected_winners", [])),
            int(data["preselected_by"]) if data.get("preselected_by") else None,
            str(data["preselected_at"]) if data.get("preselected_at") else None,
            str(data["finished_at"]) if data.get("finished_at") else None,
            int(data["guild_id"]) if data.get("guild_id") else None,
            str(data["thumbnail_url"]) if data.get("thumbnail_url") else None,
        ))
    logger.info(f"[GIVEAWAY DB] Розыгрыш {data['id']} сохранён.")


init_db()
