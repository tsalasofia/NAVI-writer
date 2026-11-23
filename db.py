import sqlite3
import datetime
from contextlib import contextmanager
import hashlib, hmac, os

DB_FILE = "history.db"


@contextmanager
def get_conn():
    """One place to open connections. Foreign keys are a PER-CONNECTION
    setting in SQLite, so they must be enabled every time."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("PRAGMA journal_mode = WAL;")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id)
                    REFERENCES chat_sessions (id)
                    ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT UNIQUE NOT NULL,
                chunk_count INTEGER NOT NULL,
                content_hash TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                template_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("""CREATE TABLE IF NOT EXISTS diary_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL,
        content TEXT NOT NULL, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        # Migration for older databases that lack content_hash
        cols = [r[1] for r in conn.execute("PRAGMA table_info(files)").fetchall()]
        if "content_hash" not in cols:
            conn.execute("ALTER TABLE files ADD COLUMN content_hash TEXT")

        # Diary chats: each diary entry belongs to a diary session
        conn.execute(
            "CREATE TABLE IF NOT EXISTS diary_sessions ("
            "id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        dcols = [r[1] for r in conn.execute("PRAGMA table_info(diary_entries)").fetchall()]
        if "session_id" not in dcols:
            conn.execute("ALTER TABLE diary_entries ADD COLUMN session_id TEXT")
        if conn.execute("SELECT COUNT(*) FROM diary_entries WHERE session_id IS NULL").fetchone()[0]:
            legacy = "legacy_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            conn.execute("INSERT INTO diary_sessions (id, title) VALUES (?, ?)", (legacy, "Earlier entries"))
            conn.execute("UPDATE diary_entries SET session_id = ? WHERE session_id IS NULL", (legacy,))


# ---------- sessions ----------

def create_new_session(title=None):
    session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    if not title:
        title = f"Chat {datetime.datetime.now().strftime('%d/%m %H:%M')}"
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_sessions (id, title) VALUES (?, ?)",
            (session_id, title),
        )
    return session_id


def get_all_sessions():
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, title FROM chat_sessions ORDER BY created_at DESC, id DESC"
        ).fetchall()


def clear_session_db(session_id):
    # ON DELETE CASCADE removes the messages too
    with get_conn() as conn:
        conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))


# ---------- messages ----------

def save_message(session_id, role, content):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )


def load_chat_history(session_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM chat_history "
            "WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    return [{"role": r[0], "content": r[1]} for r in rows]


# ---------- files ----------

def save_file_record(file_name, chunk_count, content_hash=None):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO files (file_name, chunk_count, content_hash)
            VALUES (?, ?, ?)
            ON CONFLICT(file_name) DO UPDATE SET
                chunk_count = excluded.chunk_count,
                content_hash = excluded.content_hash,
                uploaded_at = CURRENT_TIMESTAMP
            """,
            (file_name, chunk_count, content_hash),
        )


def get_stored_files():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT file_name FROM files ORDER BY uploaded_at DESC, id DESC"
        ).fetchall()
    return [r[0] for r in rows]


def get_file_hash(file_name):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT content_hash FROM files WHERE file_name = ?", (file_name,)
        ).fetchone()
    return row[0] if row else None


def delete_file_from_db(file_name):
    with get_conn() as conn:
        conn.execute("DELETE FROM files WHERE file_name = ?", (file_name,))


# ---------- generated reports ----------

def save_report_record(title, template_name, file_path):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reports (title, template_name, file_path) VALUES (?, ?, ?)",
            (title, template_name, file_path),
        )


def get_reports():
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, title, template_name, file_path, created_at "
            "FROM reports ORDER BY id DESC"
        ).fetchall()


def delete_report_record(report_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))



def rename_session(session_id, title):
    with get_conn() as conn:
        conn.execute("UPDATE chat_sessions SET title = ? WHERE id = ?", (title, session_id))

def _hash_pin(pin, salt):
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 200_000).hex()

def has_pin():
    with get_conn() as conn:
        return conn.execute("SELECT 1 FROM settings WHERE key='diary_pin'").fetchone() is not None

def set_pin(pin):
    salt = os.urandom(16)
    value = salt.hex() + "$" + _hash_pin(pin, salt)
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('diary_pin', ?)", (value,))

def verify_pin(pin):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='diary_pin'").fetchone()
    if not row or not pin:
        return False
    salt_hex, digest = row[0].split("$")
    return hmac.compare_digest(_hash_pin(pin, bytes.fromhex(salt_hex)), digest)

