import sqlite3
import datetime
from contextlib import contextmanager

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

        # Migration for older databases that lack content_hash
        cols = [r[1] for r in conn.execute("PRAGMA table_info(files)").fetchall()]
        if "content_hash" not in cols:
            conn.execute("ALTER TABLE files ADD COLUMN content_hash TEXT")


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
