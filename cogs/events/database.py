import sqlite3
import json
from .config import DB_PATH

def init_events_db():
    """Инициализация базы данных ивентов"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            name TEXT,
            organizer TEXT,
            event_time TEXT,
            description TEXT,
            image_url TEXT,
            max_slots INTEGER,
            status TEXT,
            message_id INTEGER,
            admin_message_id INTEGER,
            channel_id INTEGER,
            participants TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS global_whitelist (user_id INTEGER PRIMARY KEY)''')
    conn.commit()
    conn.close()

def get_global_whitelist():
    """Получить список WL"""
    init_events_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM global_whitelist")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def add_to_global_whitelist(user_ids):
    """Добавить пользователей в WL"""
    init_events_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for uid in user_ids:
        try: 
            cursor.execute("INSERT OR IGNORE INTO global_whitelist (user_id) VALUES (?)", (uid,))
        except: 
            pass
    conn.commit()
    conn.close()

def remove_from_global_whitelist(user_ids):
    """Удалить из WL"""
    init_events_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for uid in user_ids:
        cursor.execute("DELETE FROM global_whitelist WHERE user_id = ?", (uid,))
    conn.commit()
    conn.close()

def clear_global_whitelist():
    """Очистить весь WL"""
    init_events_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM global_whitelist")
    conn.commit()
    conn.close()

def get_current_event():
    """Получить текущий активный ивент"""
    init_events_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM events WHERE status IN ("active", "draft", "paused") ORDER BY created_at DESC LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_event_by_id(event_id):
    """Получить ивент по ID"""
    init_events_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def save_event(data):
    """Сохранить ивент"""
    init_events_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    parts_data = data.get("participants", {"main": [], "reserve": []})
    parts_json = json.dumps(parts_data) if not isinstance(parts_data, str) else parts_data
    cursor.execute('''
        INSERT OR REPLACE INTO events 
        (id, name, organizer, event_time, description, image_url, max_slots, status, message_id, admin_message_id, channel_id, participants)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data["id"], data["name"], data["organizer"], data["event_time"], 
        data["description"], data.get("image_url"), data["max_slots"], 
        data["status"], data.get("message_id"), data.get("admin_message_id"), 
        data.get("channel_id"), parts_json
    ))
    conn.commit()
    conn.close()

def close_all_active_events():
    """Закрыть все активные ивенты"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE events SET status = "closed" WHERE status IN ("active", "draft", "paused")')
    conn.commit()
    conn.close()

def get_participants_struct(data):
    """Получить структуру участников из данных ивента"""
    val = data.get("participants")
    default = {"main": [], "reserve": []}
    if not val: 
        return default
    parsed = val
    if isinstance(val, str):
        try: 
            parsed = json.loads(val)
        except: 
            return default
    if isinstance(parsed, list): 
        return {"main": [], "reserve": parsed}
    return parsed
