# -*- coding: utf-8 -*-
"""消息入站统一管道：去重落库 → 分诊 → 日程/待办提取。
所有渠道（演示注入、IMAP 邮件、飞书 API、未来的本地只读微信）共用此管道，
保证分诊与防幻觉日程提取的行为完全一致。"""
import json

import db
import triage


def ingest(channel_key, conv_key, conv_title, sender, ts, text, dedup_key, account_key="",
           links=None, attachments=None, sender_id="", sender_avatar="", grp_hint=None):
    """入站一条消息。返回 (message, grp, event) 或 None（重复）。"""
    now = db.now_iso()
    sender = db.sender_alias(channel_key, sender_id) or sender
    links_json = json.dumps(links or [], ensure_ascii=False)
    db.ex("INSERT OR IGNORE INTO messages(channel_key, account_key, conv_key, conv_title, "
          "sender, sender_id, sender_avatar, ts, text, grp, links, dedup_key, created_at) "
          "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
          (channel_key, account_key, conv_key, conv_title, sender, sender_id, sender_avatar,
           ts, text, "", links_json, dedup_key, now))
    row = db.q("SELECT * FROM messages WHERE dedup_key=?", (dedup_key,))
    if not row:
        return None
    m = row[0]
    grp = grp_hint or triage.classify(m["text"], m["sender"])
    db.ex("UPDATE messages SET sender=?, sender_id=?, sender_avatar=?, text=?, grp=?, links=? WHERE id=?",
          (sender, sender_id, sender_avatar, text, grp, links_json, m["id"]))
    if channel_key == "feishu" and sender_id and sender and not sender.startswith(("ou_", "on_", "cli_")):
        db.ex("UPDATE messages SET sender=? WHERE channel_key='feishu' AND sender_id=?",
              (sender, sender_id))
        if sender_avatar:
            db.ex("UPDATE messages SET sender_avatar=? WHERE channel_key='feishu' AND sender_id=?",
                  (sender_avatar, sender_id))
    if attachments is not None:
        db.ex("DELETE FROM attachments WHERE message_id=?", (m["id"],))
        for attachment in attachments:
            db.ex("INSERT INTO attachments(message_id, filename, mime, size, storage_key, created_at) "
                  "VALUES(?,?,?,?,?,?)",
                  (m["id"], attachment["filename"], attachment["mime"], attachment["size"],
                   attachment["storage_key"], now))
    m = db.q("SELECT * FROM messages WHERE id=?", (m["id"],))[0]

    event = None
    if grp == "schedule":
        dt = triage.parse_time(m["text"])
        if dt:
            db.ex("INSERT OR IGNORE INTO schedule_events(title, start_at, "
                  "source_msg_id, status, dedup_key, created_at) VALUES(?,?,?,?,?,?)",
                  (triage.event_title(m["text"]), dt.strftime("%Y-%m-%d %H:%M"),
                   m["id"], "pending", f"msg:{m['id']}", now))
            rows = db.q("SELECT * FROM schedule_events WHERE source_msg_id=?", (m["id"],))
            event = rows[0] if rows else None
    elif grp == "todo":
        db.ex("INSERT OR IGNORE INTO todos(text, source_msg_id, created_at) "
              "VALUES(?,?,?)", (triage.event_title(m["text"]), m["id"], now))
    return m, grp, event
