# -*- coding: utf-8 -*-
"""聚光 FocusIn · 本地服务进程（FastAPI）。

启动：python -m uvicorn app:app --host 127.0.0.1 --port 8765
"""
import datetime
import json

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import pydantic

import agent
import db
import dataset
import triage

app = FastAPI(title="聚光 FocusIn")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                    allow_methods=["*"], allow_headers=["*"])

GROUP_LABEL = triage.GROUPS


@app.on_event("startup")
def _startup():
    db.init()
    if not db.q("SELECT 1 FROM messages LIMIT 1"):
        dataset.seed()


def _today():
    return datetime.date.today().strftime("%Y-%m-%d")


def _greeting():
    h = datetime.datetime.now().hour
    if h < 6:
        return "夜深了"
    if h < 11:
        return "早上好"
    if h < 14:
        return "中午好"
    if h < 18:
        return "下午好"
    return "晚上好"


# ---------------- 概览 ----------------

@app.get("/api/overview")
def overview():
    today = _today()
    msgs = db.q("SELECT * FROM messages WHERE ts >= ? ORDER BY ts DESC", (today,))
    total_today = len(msgs)
    by_channel = {}
    for m in msgs:
        by_channel.setdefault(m["channel_key"], {"msgs": 0, "todo": 0})
        by_channel[m["channel_key"]]["msgs"] += 1
        if m["grp"] == "todo":
            by_channel[m["channel_key"]]["todo"] += 1
    things = sum(1 for m in msgs if m["grp"] in ("todo", "schedule", "notice", "important"))
    convs_today = len({m["conv_key"] for m in msgs})

    channels = db.q("SELECT * FROM channels ORDER BY key")
    ch_rows = []
    for ch in channels:
        st = by_channel.get(ch["key"], {"msgs": 0, "todo": 0})
        ch_rows.append({"key": ch["key"], "name": ch["name"], "type": ch["type"],
                        "msgs": st["msgs"], "todo": st["todo"]})

    recent = db.q(
        "SELECT * FROM messages WHERE grp IN ('todo','schedule','notice',"
        "'important') AND ts >= date('now','-1 day') ORDER BY ts DESC LIMIT 6")

    todos = db.q("SELECT COUNT(*) n FROM todos WHERE done=0")[0]["n"]
    todos_done = db.q("SELECT COUNT(*) n FROM todos WHERE done=1")[0]["n"]
    pending = db.q("SELECT COUNT(*) n FROM schedule_events WHERE status='pending'")[0]["n"]

    # 一周消息量柱状图（按渠道分色）
    bars = []
    for i in range(6, -1, -1):
        d = (datetime.date.today() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        rows = db.q("SELECT channel_key, COUNT(*) n FROM messages WHERE ts LIKE ? "
                    "GROUP BY channel_key", (d + "%",))
        bars.append({"date": d[5:], "counts": {r["channel_key"]: r["n"] for r in rows}})

    return {"greeting": _greeting(), "channels": ch_rows,
            "hero": {"convs": convs_today, "msgs": total_today, "things": things},
            "recent": recent, "digest": recent[:8],
            "stats": {"todos": todos, "todos_done": todos_done,
                      "todo_total": todos + todos_done, "pending_events": pending,
                      "bars": bars, "groups": GROUP_LABEL}}


# ---------------- 消息流 ----------------

@app.get("/api/conversations")
def conversations():
    rows = db.q(
        "SELECT channel_key, conv_key, conv_title, COUNT(*) n, MAX(ts) last_ts, "
        "SUM(CASE WHEN grp != 'chatter' THEN 1 ELSE 0 END) important "
        "FROM messages GROUP BY channel_key, conv_key, conv_title "
        "ORDER BY last_ts DESC")
    return rows


@app.get("/api/messages")
def messages(channel: str = "", conv: str = ""):
    where, args = [], []
    if channel:
        where.append("channel_key=?"), args.append(channel)
    if conv:
        where.append("conv_key=?"), args.append(conv)
    sql = "SELECT * FROM messages"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ts ASC"
    rows = db.q(sql, args)
    chatter_idx = [i for i, r in enumerate(rows) if r["grp"] == "chatter"]
    return {"messages": rows, "n": len(rows),
            "chatter": chatter_idx}  # 前端折叠闲聊区间


@app.post("/api/messages/{mid}/star")
def star(mid: int):
    row = db.q("SELECT star FROM messages WHERE id=?", (mid,))
    if not row:
        return {"ok": False}
    db.ex("UPDATE messages SET star=1-star WHERE id=?", (mid,))
    return {"ok": True, "star": 1 - row[0]["star"]}


# ---------------- 日程 ----------------

@app.get("/api/schedule")
def schedule():
    rows = db.q(
        "SELECT e.*, m.text AS src, m.conv_title AS src_conv, m.ts AS src_ts, "
        "m.sender AS src_sender, m.channel_key AS src_channel "
        "FROM schedule_events e LEFT JOIN messages m ON m.id = e.source_msg_id "
        "WHERE e.status != 'dismissed' ORDER BY e.start_at ASC")
    for r in rows:
        r["source"] = None
        if r["src"]:
            r["source"] = {"text": r["src"], "conv": r["src_conv"],
                            "ts": r["src_ts"], "sender": r["src_sender"]}
    return rows


@app.post("/api/schedule/{sid}/confirm")
def confirm(sid: int):
    db.ex("UPDATE schedule_events SET status='confirmed' WHERE id=?", (sid,))
    return {"ok": True}


@app.post("/api/schedule/{sid}/dismiss")
def dismiss(sid: int):
    db.ex("UPDATE schedule_events SET status='dismissed' WHERE id=?", (sid,))
    return {"ok": True}


# ---------------- 对话（SSE）----------------

@app.get("/api/chat/history")
def chat_history():
    return db.q("SELECT * FROM chat_messages ORDER BY id DESC LIMIT 60")


@app.post("/api/chat")
async def chat(req: Request):
    body = await req.json()
    user_text = (body.get("message") or "").strip()
    if not user_text:
        return {"error": "empty message"}

    def gen():
        for ev in agent.flow(user_text):
            yield json.dumps(ev, ensure_ascii=False) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


# ---------------- 审批 ----------------

class Decision(pydantic.BaseModel):
    decision: str  # approve | deny


@app.get("/api/approvals/pending")
def pending_approvals():
    return db.q("SELECT * FROM approvals WHERE status='pending' ORDER BY id DESC")


@app.post("/api/approvals/{aid}/decision")
def decide(aid: int, d: Decision):
    db.ex("UPDATE approvals SET status=?, decision=?, decided_at=? WHERE id=?",
          ("resolved", d.decision, db.now_iso(), aid))
    return {"ok": True}


# ---------------- 渠道注入（演示新消息入站管道）----------------

class InjectMsg(pydantic.BaseModel):
    text: str = "刚接到通知：周五下午 3 点客户到访，提前订好会议室，材料记得带上。"
    channel: str = "feishu"
    conv: str = "dept"
    sender: str = "李经理(领导)"


@app.post("/api/demo/inject")
def inject(msg: InjectMsg):
    now = db.now_iso()
    conv = db.q("SELECT DISTINCT conv_title FROM messages WHERE channel_key=? "
                "AND conv_key=?", (msg.channel, msg.conv))
    title = conv[0]["conv_title"] if conv else msg.conv
    dedup = f"inj:{msg.channel}:{msg.conv}:{now}:{msg.text[:12]}"
    db.ex("INSERT OR IGNORE INTO messages(channel_key, conv_key, conv_title, "
          "sender, ts, text, grp, dedup_key, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
          (msg.channel, msg.conv, title, msg.sender, now, msg.text, "", dedup, now))
    row = db.q("SELECT * FROM messages WHERE dedup_key=?", (dedup,))
    if not row:
        return {"ok": False, "reason": "重复消息已去重"}
    m = row[0]
    grp = triage.classify(m["text"], m["sender"])
    db.ex("UPDATE messages SET grp=? WHERE id=?", (grp, m["id"]))
    event = None
    if grp == "schedule":
        dt = triage.parse_time(m["text"])
        if dt:
            db.ex("INSERT OR IGNORE INTO schedule_events(title, start_at, "
                  "source_msg_id, status, dedup_key, created_at) "
                  "VALUES(?,?,?,?,?,?)",
                  (triage.event_title(m["text"]), dt.strftime("%Y-%m-%d %H:%M"),
                   m["id"], "pending", f"msg:{m['id']}", now))
            event = db.q("SELECT * FROM schedule_events WHERE source_msg_id=?",
                         (m["id"],))[0]
    elif grp == "todo":
        db.ex("INSERT OR IGNORE INTO todos(text, source_msg_id, created_at) "
              "VALUES(?,?,?)", (triage.event_title(m["text"]), m["id"], now))
    return {"ok": True, "message": m, "grp": grp, "event": event,
            "grp_label": GROUP_LABEL.get(grp, grp)}


# ---------------- 其他 ----------------

@app.get("/api/audit")
def audit_log():
    return db.q("SELECT * FROM audit_log ORDER BY id DESC LIMIT 50")


@app.get("/api/notifications")
def notifications():
    today = _today()
    soon = db.q("SELECT e.*, m.text src FROM schedule_events e LEFT JOIN messages m "
                "ON m.id = e.source_msg_id WHERE e.status != 'dismissed' "
                "AND e.start_at >= ? AND e.start_at < date(?, '+2 day') "
                "ORDER BY e.start_at", (today, today))
    pending = [r for r in soon if r["status"] == "pending"]
    return {"n": len(pending), "items": soon[:12]}


@app.get("/api/settings")
def get_settings():
    return {"llm_base_url": db.get_setting("llm_base_url", ""),
            "llm_model": db.get_setting("llm_model", ""),
            "has_key": bool(db.get_setting("llm_api_key", ""))}


class SettingsBody(pydantic.BaseModel):
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""


@app.post("/api/settings")
def save_settings(body: SettingsBody):
    if body.llm_base_url is not None and body.llm_base_url != "":
        db.set_setting("llm_base_url", body.llm_base_url)
    if body.llm_model != "":
        db.set_setting("llm_model", body.llm_model)
    if body.llm_api_key != "":
        db.set_setting("llm_api_key", body.llm_api_key)
    return {"ok": True}


@app.post("/api/seed")
def reseed():
    stats = dataset.seed()
    return {"ok": True, "groups": stats}


@app.get("/api/health")
def health():
    return {"ok": True, "name": "聚光 FocusIn", "version": "0.1.0-demo"}
