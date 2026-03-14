"""
Постоянная память бота — хранит:
- загруженные справки по каналам
- историю диалогов (по user_id)
- загруженные рекламные данные (CSV/Excel)
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "bot_memory.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Справочная база знаний по рекламным каналам
    cur.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source TEXT NOT NULL,          -- название/url источника
            content TEXT NOT NULL,          -- текст справки
            channel TEXT,                   -- Яндекс.Директ / Google Ads / VK и т.д.
            created_at TEXT NOT NULL
        )
    """)

    # История диалогов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,             -- 'user' или 'assistant'
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Загруженные рекламные данные
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ad_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            channel TEXT,
            data_json TEXT NOT NULL,        -- JSON-представление таблицы
            summary TEXT,                   -- краткое описание данных
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# Знания (справки по каналам)
# ──────────────────────────────────────────────

def save_knowledge(user_id: int, source: str, content: str, channel: str = None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO knowledge_base (user_id, source, content, channel, created_at) VALUES (?,?,?,?,?)",
        (user_id, source, content, channel, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_knowledge(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT source, content, channel, created_at FROM knowledge_base WHERE user_id=? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_knowledge(user_id: int, source: str):
    conn = get_conn()
    conn.execute("DELETE FROM knowledge_base WHERE user_id=? AND source=?", (user_id, source))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# История диалогов
# ──────────────────────────────────────────────

def add_message(user_id: int, role: str, content: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO chat_history (user_id, role, content, created_at) VALUES (?,?,?,?)",
        (user_id, role, content, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_history(user_id: int, limit: int = 20) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT role, content FROM chat_history WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return list(reversed([dict(r) for r in rows]))


def clear_history(user_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM chat_history WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# Рекламные данные (CSV / Excel)
# ──────────────────────────────────────────────

def save_ad_data(user_id: int, filename: str, data: list[dict], channel: str = None, summary: str = None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO ad_data (user_id, filename, channel, data_json, summary, created_at) VALUES (?,?,?,?,?,?)",
        (user_id, filename, channel, json.dumps(data, ensure_ascii=False), summary, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_ad_data(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, filename, channel, data_json, summary, created_at FROM ad_data WHERE user_id=? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["data"] = json.loads(d.pop("data_json"))
        result.append(d)
    return result


def delete_ad_data(user_id: int, data_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM ad_data WHERE user_id=? AND id=?", (user_id, data_id))
    conn.commit()
    conn.close()


def get_ad_data_summary(user_id: int) -> str:
    """Краткая сводка всех загруженных данных для передачи в промпт."""
    items = get_ad_data(user_id)
    if not items:
        return "Рекламные данные не загружены."
    parts = []
    for item in items:
        ch = item.get("channel") or "неизвестный канал"
        summary = item.get("summary") or ""
        rows_count = len(item.get("data", []))
        # Передаём первые 50 строк в контекст
        preview = item["data"][:50]
        parts.append(
            f"📊 Файл: {item['filename']} | Канал: {ch} | Строк: {rows_count}\n"
            f"Описание: {summary}\n"
            f"Данные (первые {len(preview)} строк):\n{json.dumps(preview, ensure_ascii=False, indent=2)}"
        )
    return "\n\n---\n\n".join(parts)
