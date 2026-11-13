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
CREATE TABLE IF NOT EXISTS student_accounts (
 student_id TEXT PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
 password_salt TEXT NOT NULL, password_hash TEXT NOT NULL,
 password_rounds INTEGER NOT NULL, created_at TEXT NOT NULL
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
             COUNT(t.id) AS templates, EXISTS(SELECT 1 FROM student_accounts a WHERE a.student_id=s.id) AS login_enabled FROM students s LEFT JOIN face_templates t ON t.student_id=s.id
             GROUP BY s.id ORDER BY s.roll""")]

def get_sessions():
    with connect() as db:
        return [dict(r) for r in db.execute('SELECT * FROM class_sessions ORDER BY created_at DESC, rowid DESC')]

def put_student_login(student_id, salt, hashed, rounds):
    with connect() as conn:
        if not conn.execute('SELECT id FROM students WHERE id=?', (student_id,)).fetchone():
            return False
        conn.execute("""INSERT INTO student_accounts(student_id,password_salt,password_hash,password_rounds,created_at)
                        VALUES(?,?,?,?,?) ON CONFLICT(student_id) DO UPDATE SET
                        password_salt=excluded.password_salt,password_hash=excluded.password_hash,
                        password_rounds=excluded.password_rounds,created_at=excluded.created_at""",
                     (student_id,salt,hashed,rounds,now()))
        return True


def student_login_record(roll):
    with connect() as conn:
        row=conn.execute("""SELECT s.id,s.name,s.roll,a.password_salt,a.password_hash,a.password_rounds,
                            EXISTS(SELECT 1 FROM face_templates t WHERE t.student_id=s.id) AS biometric_enrolled
                            FROM students s JOIN student_accounts a ON s.id=a.student_id
                            WHERE s.roll=? COLLATE NOCASE""",(roll.strip().upper(),)).fetchone()
        return dict(row) if row else None


def get_student_login_by_id(student_id):
    with connect() as conn:
        row=conn.execute("""SELECT s.id,s.name,s.roll,
                            EXISTS(SELECT 1 FROM face_templates t WHERE t.student_id=s.id) AS biometric_enrolled
                            FROM students s JOIN student_accounts a ON s.id=a.student_id WHERE s.id=?""",
                         (student_id,)).fetchone()
        return dict(row) if row else None
