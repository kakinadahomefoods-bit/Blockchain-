"""SQLite stores identities and biometric templates OFF blockchain."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from .config import data_dir

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS students (
    id TEXT PRIMARY KEY,
    roll TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    consent_at TEXT NOT NULL,
    enrolled_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS face_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    descriptor BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS class_sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    course TEXT NOT NULL,
    created_at TEXT NOT NULL,
    closed_at TEXT
);
'''

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

@contextmanager
def connect():
    conn = sqlite3.connect(data_dir() / 'attendance.sqlite3', timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def initialize():
    with connect() as db:
        db.executescript(SCHEMA)

def get_students():
    with connect() as db:
        return [dict(r) for r in db.execute("""SELECT s.id, s.roll, s.name, s.consent_at, s.enrolled_at,
             COUNT(t.id) AS templates FROM students s LEFT JOIN face_templates t ON t.student_id=s.id
             GROUP BY s.id ORDER BY s.roll""")]

def get_sessions():
    with connect() as db:
        return [dict(r) for r in db.execute('SELECT * FROM class_sessions ORDER BY created_at DESC, rowid DESC')]
