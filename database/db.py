import sqlite3
import json
import logging
from datetime import datetime
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Инициализация всех таблиц базы данных."""
    conn = get_connection()
    c = conn.cursor()

    # История диалогов
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Загруженные документы и справки
    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            content_preview TEXT,
            chroma_ids TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Рекламные данные (распарсенные из CSV/Excel)
    c.execute("""
        CREATE TABLE IF NOT EXISTS ad_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source_file TEXT,
            channel TEXT,
            data_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Профиль пользователя (предпочтения, контекст)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            context TEXT DEFAULT '{}',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    logger.info("БД инициализирована")


# ─── История диалогов ────────────────────────────────────────────────────────

def add_message(user_id: int, role: str, content: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)",
        (user_id, role, content)
    )
    conn.commit()
    conn.close()


def get_history(user_id: int, limit: int = 20) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT role, content FROM chat_history
           WHERE user_id = ?
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def clear_history(user_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ─── Документы ───────────────────────────────────────────────────────────────

def save_document(user_id: int, filename: str, doc_type: str,
                  content_preview: str, chroma_ids: list[str]):
    conn = get_connection()
    conn.execute(
        """INSERT INTO documents (user_id, filename, doc_type, content_preview, chroma_ids)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, filename, doc_type, content_preview, json.dumps(chroma_ids))
    )
    conn.commit()
    conn.close()


def get_user_documents(user_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM documents WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Рекламные данные ─────────────────────────────────────────────────────────

def save_ad_data(user_id: int, source_file: str, channel: str, data: dict):
    conn = get_connection()
    conn.execute(
        """INSERT INTO ad_data (user_id, source_file, channel, data_json)
           VALUES (?, ?, ?, ?)""",
        (user_id, source_file, channel, json.dumps(data, ensure_ascii=False))
    )
    conn.commit()
    conn.close()


def get_user_ad_data(user_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM ad_data WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["data_json"] = json.loads(d["data_json"])
        result.append(d)
    return result


# ─── Профиль пользователя ─────────────────────────────────────────────────────

def upsert_user_profile(user_id: int, username: str):
    conn = get_connection()
    conn.execute(
        """INSERT INTO user_profiles (user_id, username, updated_at)
           VALUES (?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, updated_at=CURRENT_TIMESTAMP""",
        (user_id, username)
    )
    conn.commit()
    conn.close()


def get_user_stats(user_id: int) -> dict:
    conn = get_connection()
    msg_count = conn.execute(
        "SELECT COUNT(*) as c FROM chat_history WHERE user_id = ?", (user_id,)
    ).fetchone()["c"]
    doc_count = conn.execute(
        "SELECT COUNT(*) as c FROM documents WHERE user_id = ?", (user_id,)
    ).fetchone()["c"]
    data_count = conn.execute(
        "SELECT COUNT(*) as c FROM ad_data WHERE user_id = ?", (user_id,)
    ).fetchone()["c"]
    conn.close()
    return {"messages": msg_count, "documents": doc_count, "ad_datasets": data_count}
