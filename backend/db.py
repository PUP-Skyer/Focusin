import os
import sqlite3
import datetime
import secrets
from contextlib import closing

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("FOCUSIN_DB", os.path.join(BASE, "focusin.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels(
  key TEXT PRIMARY KEY, name TEXT, type TEXT, status TEXT DEFAULT 'on');

CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_key TEXT NOT NULL, account_key TEXT DEFAULT '', conv_key TEXT NOT NULL, conv_title TEXT,
  sender TEXT, sender_id TEXT DEFAULT '', sender_avatar TEXT DEFAULT '',
  ts TEXT, text TEXT,
  grp TEXT DEFAULT '', star INTEGER DEFAULT 0, links TEXT DEFAULT '[]',
  dedup_key TEXT UNIQUE, created_at TEXT);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(channel_key, conv_key);
CREATE INDEX IF NOT EXISTS idx_msg_ts ON messages(ts);

CREATE TABLE IF NOT EXISTS attachments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id INTEGER NOT NULL,
  filename TEXT, mime TEXT, size INTEGER, storage_key TEXT,
  created_at TEXT);
CREATE INDEX IF NOT EXISTS idx_attachment_message ON attachments(message_id);

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
  id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, ts TEXT,
  session_id TEXT DEFAULT 'legacy');

CREATE TABLE IF NOT EXISTS chat_sessions(
  id TEXT PRIMARY KEY, title TEXT DEFAULT '新对话', created_at TEXT, updated_at TEXT);

CREATE TABLE IF NOT EXISTS workflow_runs(
  id TEXT PRIMARY KEY, session_id TEXT, workflow_id TEXT, status TEXT,
  result TEXT, created_at TEXT);

CREATE TABLE IF NOT EXISTS drafts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, created_at TEXT);

CREATE TABLE IF NOT EXISTS chat_attachments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL, name TEXT, relative_path TEXT,
  mime TEXT, size INTEGER, storage_key TEXT NOT NULL,
  kind TEXT DEFAULT 'file', group_key TEXT DEFAULT '', created_at TEXT);
CREATE INDEX IF NOT EXISTS idx_chat_attachment_session ON chat_attachments(session_id, id);

CREATE TABLE IF NOT EXISTS workspaces(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, path TEXT NOT NULL UNIQUE,
  access TEXT DEFAULT 'read', created_at TEXT, updated_at TEXT);

CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS sender_aliases(
  channel_key TEXT NOT NULL,
  sender_id TEXT NOT NULL,
  name TEXT NOT NULL,
  updated_at TEXT,
  PRIMARY KEY(channel_key, sender_id));

CREATE TABLE IF NOT EXISTS subscriptions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_key TEXT NOT NULL, account_key TEXT DEFAULT '', conv_key TEXT NOT NULL, conv_title TEXT,
  active INTEGER DEFAULT 1, added_at TEXT, keywords TEXT DEFAULT '[]',
  UNIQUE(channel_key, account_key, conv_key));
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
        rowcount = c.execute(sql, args).rowcount
        c.commit()
        return rowcount


def init():
    with closing(get_conn()) as c:
        c.executescript(SCHEMA)
        chat_cols = {r["name"] for r in c.execute("PRAGMA table_info(chat_messages)")}
        if "session_id" not in chat_cols:
            c.execute("ALTER TABLE chat_messages ADD COLUMN session_id TEXT DEFAULT 'legacy'")
        c.execute("CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id, id)")
        legacy_count = c.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id='legacy'").fetchone()[0]
        if legacy_count and not c.execute("SELECT 1 FROM chat_sessions WHERE id='legacy'").fetchone():
            legacy_ts = now_iso()
            c.execute("INSERT INTO chat_sessions(id,title,created_at,updated_at) VALUES(?,?,?,?)",
                      ("legacy", "历史对话", legacy_ts, legacy_ts))
        msg_cols = {r["name"] for r in c.execute("PRAGMA table_info(messages)")}
        if "account_key" not in msg_cols:
            c.execute("ALTER TABLE messages ADD COLUMN account_key TEXT DEFAULT ''")
        if "links" not in msg_cols:
            c.execute("ALTER TABLE messages ADD COLUMN links TEXT DEFAULT '[]'")
        if "sender_id" not in msg_cols:
            c.execute("ALTER TABLE messages ADD COLUMN sender_id TEXT DEFAULT ''")
        if "sender_avatar" not in msg_cols:
            c.execute("ALTER TABLE messages ADD COLUMN sender_avatar TEXT DEFAULT ''")
        sub_cols = {r["name"] for r in c.execute("PRAGMA table_info(subscriptions)")}
        if "account_key" not in sub_cols:
            c.execute("ALTER TABLE subscriptions RENAME TO subscriptions_old")
            c.execute("""CREATE TABLE subscriptions(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              channel_key TEXT NOT NULL, account_key TEXT DEFAULT '',
              conv_key TEXT NOT NULL, conv_title TEXT,
              active INTEGER DEFAULT 1, added_at TEXT, keywords TEXT DEFAULT '[]',
              UNIQUE(channel_key, account_key, conv_key))""")
            c.execute("INSERT INTO subscriptions(id, channel_key, account_key, conv_key, "
                      "conv_title, active, added_at) SELECT id, channel_key, '', conv_key, "
                      "conv_title, active, added_at FROM subscriptions_old")
            c.execute("DROP TABLE subscriptions_old")
        sub_cols = {r["name"] for r in c.execute("PRAGMA table_info(subscriptions)")}
        if "keywords" not in sub_cols:
            c.execute("ALTER TABLE subscriptions ADD COLUMN keywords TEXT DEFAULT '[]'")
        c.execute("CREATE INDEX IF NOT EXISTS idx_msg_account_conv "
                  "ON messages(channel_key, account_key, conv_key)")
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


def sender_alias(channel_key, sender_id):
    rows = q("SELECT name FROM sender_aliases WHERE channel_key=? AND sender_id=?",
             (channel_key, sender_id))
    return rows[0]["name"] if rows else ""


def set_sender_alias(channel_key, sender_id, name):
    ex("INSERT INTO sender_aliases(channel_key,sender_id,name,updated_at) VALUES(?,?,?,?) "
       "ON CONFLICT(channel_key,sender_id) DO UPDATE SET name=excluded.name, updated_at=excluded.updated_at",
       (channel_key, sender_id, name, now_iso()))
    return ex("UPDATE messages SET sender=? WHERE channel_key=? AND sender_id=?",
              (name, channel_key, sender_id))


def set_setting(key, value):
    ex("INSERT INTO settings(key,value) VALUES(?,?) "
       "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def create_chat_session(title="新对话"):
    sid = secrets.token_hex(8)
    ts = now_iso()
    ex("INSERT INTO chat_sessions(id,title,created_at,updated_at) VALUES(?,?,?,?)",
       (sid, title, ts, ts))
    return {"id": sid, "title": title, "created_at": ts, "updated_at": ts}


def list_chat_sessions():
    return q("""SELECT s.*, (
                 SELECT COUNT(*) FROM chat_messages m WHERE m.session_id=s.id
               ) AS message_count
               FROM chat_sessions s ORDER BY s.updated_at DESC LIMIT 40""")


def touch_chat_session(session_id, title=None):
    ts = now_iso()
    if title:
        ex("UPDATE chat_sessions SET updated_at=?, title=CASE "
           "WHEN title='新对话' OR title='' THEN ? ELSE title END WHERE id=?",
           (ts, title[:32], session_id))
    else:
        ex("UPDATE chat_sessions SET updated_at=? WHERE id=?", (ts, session_id))


def chat_messages(session_id, limit=80):
    rows = q("SELECT * FROM chat_messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
             (session_id, limit))
    return list(reversed(rows))
