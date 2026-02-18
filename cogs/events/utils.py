import re

def extract_ids(text):
    """Извлекает ID пользователей из текста"""
    ids = re.findall(r'<@!?(\d+)>|(\d{17,20})', text)
    result = []
    for match in ids:
        uid = match[0] if match[0] else match[1]
        if uid: 
            result.append(int(uid))
    return list(set(result))

def push_to_reserve_if_full(struct, max_slots):
    """Переносит лишних из основы в резерв"""
    if len(struct["main"]) <= max_slots:
        return struct
    while len(struct["main"]) > max_slots:
        overflow_user = struct["main"].pop(-1)
        struct["reserve"].insert(0, overflow_user)
    return struct
