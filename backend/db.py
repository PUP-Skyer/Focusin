import os
import sqlite3
import datetime
from contextlib import closing

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("FOCUSIN_DB", os.path.join(BASE, "focusin.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels(
  key TEXT PRIMARY KEY, name TEXT, type TEXT, status TEXT DEFAULT 'on');

CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_key TEXT NOT NULL, conv_key TEXT NOT NULL, conv_title TEXT,
  sender TEXT, ts TEXT, text TEXT,
  grp TEXT DEFAULT '', star INTEGER DEFAULT 0,
  dedup_key TEXT UNIQUE, created_at TEXT);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(channel_key, conv_key);
CREATE INDEX IF NOT EXISTS idx_msg_ts ON messages(ts);

CREATE TABLE IF NOT EXISTS schedule_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, start_at TEXT,
  remind_minutes INTEGER DEFAULT 60, source_msg_id INTEGER,
  status TEXT DEFAULT 'pending',
  dedup_key TEXT UNIQUE, created_at TEXT);

CREATE TABLE IF NOT EXISTS todos(
  id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, source_msg_id INTEGER,
  done INTEGER DEFAULT 0, quadrant TEXT DEFAULT '', created_at TEXT);

CREATE TABLE IF NOT EXISTS approvals(
  id INTEGER PRIMARY KEY AUTOINCREMENT, tool TEXT, args TEXT, risk TEXT,
  status TEXT DEFAULT 'pending', decision TEXT, created_at TEXT, decided_at TEXT);

CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, tool TEXT, args TEXT,
  risk TEXT, approval_id INTEGER, result TEXT);

CREATE TABLE IF NOT EXISTS chat_messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, ts TEXT);

CREATE TABLE IF NOT EXISTS drafts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, created_at TEXT);

CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
"""


def now_iso():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def q(sql, args=()):
    with closing(get_conn()) as c:
        return [dict(r) for r in c.execute(sql, args)]


def ex(sql, args=()):
    with closing(get_conn()) as c:
        c.execute(sql, args)
        c.commit()


def init():
    with closing(get_conn()) as c:
        c.executescript(SCHEMA)
        c.commit()


def reset():
    for suffix in ("", "-wal", "-shm"):
        p = DB_PATH + suffix
        if os.path.exists(p):
            os.remove(p)
    init()


def get_setting(key, default=None):
    rows = q("SELECT value FROM settings WHERE key=?", (key,))
    return rows[0]["value"] if rows else default


def set_setting(key, value):
    ex("INSERT INTO settings(key,value) VALUES(?,?) "
       "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
