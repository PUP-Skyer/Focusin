# -*- coding: utf-8 -*-
"""聚光 FocusIn · 本地服务进程（FastAPI）。

启动：python -m uvicorn app:app --host 127.0.0.1 --port 8765
"""
import datetime
import json
import secrets
import time
import urllib.parse
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
import pydantic

import agent
import connectors
import db
import dataset
import feishu_oauth
import ingest
import llm
import triage
import uploads
import workspace
from connectors.email_imap import ATTACHMENT_DIR

app = FastAPI(title="聚光 FocusIn")
app.add_middleware(CORSMiddleware,
                    allow_origins=["http://127.0.0.1:5180", "http://localhost:5180"],
                    allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"ok": True, "service": "focusin"}


GROUP_LABEL = triage.GROUPS
_OAUTH_STATES = {}
_FEISHU_REDIRECT_URI = "http://127.0.0.1:8765/api/connectors/feishu/oauth/callback"


def _local_web_origin(value):
    parsed = urllib.parse.urlparse(value or "")
    if parsed.scheme not in ("http", "https") or parsed.hostname not in (
            "localhost", "127.0.0.1", "::1"):
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


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
        "SELECT channel_key, account_key, conv_key, conv_title, COUNT(*) n, MAX(ts) last_ts, "
        "SUM(CASE WHEN grp != 'chatter' THEN 1 ELSE 0 END) important "
        "FROM messages GROUP BY channel_key, account_key, conv_key, conv_title "
        "ORDER BY last_ts DESC")
    accounts = {a["account_key"]: a for a in connectors.email_accounts()}
    for row in rows:
        account = accounts.get(row.get("account_key"))
        if account:
            row["provider_key"] = account["provider_key"]
            row["provider"] = account["provider"]
            row["account_label"] = account["username"]
    return rows


@app.get("/api/messages")
def messages(channel: str = "", conv: str = "", account: str = ""):
    where, args = [], []
    if channel:
        where.append("channel_key=?"), args.append(channel)
    if account:
        where.append("account_key=?"), args.append(account)
    if conv:
        where.append("conv_key=?"), args.append(conv)
    sql = "SELECT * FROM messages"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ts ASC"
    rows = db.q(sql, args)
    attachments = {}
    if rows:
        ids = [r["id"] for r in rows]
        marks = ",".join("?" for _ in ids)
        for a in db.q(f"SELECT id, message_id, filename, mime, size FROM attachments "
                      f"WHERE message_id IN ({marks}) ORDER BY id", ids):
            attachments.setdefault(a["message_id"], []).append({
                "id": a["id"], "filename": a["filename"], "mime": a["mime"], "size": a["size"]
            })
    for r in rows:
        try:
            r["links"] = json.loads(r.get("links") or "[]")
        except (TypeError, ValueError):
            r["links"] = []
        r["attachments"] = attachments.get(r["id"], [])
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


class SenderAliasBody(pydantic.BaseModel):
    channel_key: str = "feishu"
    sender_id: str
    name: str


@app.post("/api/senders/alias")
def save_sender_alias(body: SenderAliasBody):
    name = " ".join(body.name.split())
    sender_id = body.sender_id.strip()
    if body.channel_key != "feishu":
        return {"ok": False, "error": "当前仅支持补充飞书用户昵称"}
    if not sender_id or len(sender_id) > 128 or not all(
            c.isalnum() or c in "_-:" for c in sender_id):
        return {"ok": False, "error": "发送人标识无效"}
    if not name or len(name) > 50:
        return {"ok": False, "error": "昵称长度需为 1–50 个字符"}
    if name in {"member", "昵称未同步", "未知发送人"} or name.startswith(("ou_", "on_", "cli_")):
        return {"ok": False, "error": "请填写真实昵称，不要填写系统占位文字或 ID"}
    exists = db.q("SELECT 1 FROM messages WHERE channel_key=? AND sender_id=? LIMIT 1",
                  (body.channel_key, sender_id))
    if not exists:
        return {"ok": False, "error": "未找到该发送人的历史消息"}
    updated = db.set_sender_alias(body.channel_key, sender_id, name)
    return {"ok": True, "name": name, "updated": updated}


@app.get("/api/attachments/{aid}")
def download_attachment(aid: int):
    row = db.q("SELECT * FROM attachments WHERE id=?", (aid,))
    if not row:
        raise HTTPException(status_code=404, detail="附件不存在")
    attachment = row[0]
    path = Path(ATTACHMENT_DIR) / attachment["storage_key"]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="附件文件不存在")
    return FileResponse(path, media_type=attachment["mime"] or "application/octet-stream",
                        filename=attachment["filename"] or "附件",
                        headers={"X-Content-Type-Options": "nosniff",
                                 "Cache-Control": "private, max-age=3600"})


# ---------------- 日程 ----------------

@app.get("/api/schedule")
def schedule():
    rows = db.q(
        "SELECT e.*, m.text AS src, m.conv_title AS src_conv, m.ts AS src_ts, "
        "m.sender AS src_sender, m.channel_key AS src_channel, "
        "m.conv_key AS src_conv_key, m.account_key AS src_account, "
        "m.dedup_key AS src_dedup "
        "FROM schedule_events e LEFT JOIN messages m ON m.id = e.source_msg_id "
        "WHERE e.status != 'dismissed' ORDER BY e.start_at ASC")
    for r in rows:
        r["title"] = triage.event_title(r["title"], limit=80)
        r["source"] = None
        if r["src"]:
            r["source"] = {"id": r["source_msg_id"], "text": r["src"], "conv": r["src_conv"],
                            "ts": r["src_ts"], "sender": r["src_sender"],
                            "channel_key": r["src_channel"], "conv_key": r["src_conv_key"],
                            "account_key": r["src_account"], "dedup_key": r["src_dedup"]}
    return rows


@app.post("/api/schedule/{sid}/confirm")
def confirm(sid: int):
    db.ex("UPDATE schedule_events SET status='confirmed' WHERE id=?", (sid,))
    return {"ok": True}


@app.post("/api/schedule/{sid}/dismiss")
def dismiss(sid: int):
    db.ex("UPDATE schedule_events SET status='dismissed' WHERE id=?", (sid,))
    return {"ok": True}


# ---------------- 对话与会话 ----------------

@app.get("/api/chat/sessions")
def chat_sessions():
    return db.list_chat_sessions()


@app.post("/api/chat/sessions")
async def create_chat_session(req: Request):
    body = await req.json()
    title = str(body.get("title") or "新对话").strip()[:32] or "新对话"
    return db.create_chat_session(title)


@app.get("/api/chat/sessions/{session_id}/messages")
def session_messages(session_id: str):
    return db.chat_messages(session_id)


@app.get("/api/chat/history")
def chat_history(session_id: str = "legacy"):
    return db.chat_messages(session_id, 60)


@app.get("/api/models")
def model_catalog():
    return {"models": llm.list_models(), "default": db.get_setting("llm_model", "")}


class WorkspaceBody(pydantic.BaseModel):
    path: str
    access: str = "read"
    confirm: bool = False


class WorkspaceAccessBody(pydantic.BaseModel):
    access: str
    confirm: bool = False


class WorkspaceChooseBody(pydantic.BaseModel):
    confirm: bool = False


class UploadDeleteBody(pydantic.BaseModel):
    ids: list[int] = []
    session_id: str = "legacy"


@app.get("/api/workspaces")
def list_workspaces():
    return workspace.list_workspaces()


@app.post("/api/workspaces/choose")
def choose_workspace(body: WorkspaceChooseBody):
    if not body.confirm:
        raise HTTPException(status_code=400, detail="选择目录需要明确确认")
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="当前运行环境不支持目录选择，请手动填写路径") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(parent=root, title="选择聚光本地工作目录", mustexist=True)
    finally:
        root.destroy()
    return {"path": selected}


@app.post("/api/workspaces")
def add_workspace(body: WorkspaceBody):
    if body.access not in ("read", "write"):
        raise HTTPException(status_code=400, detail="无效的访问权限")
    if body.access == "write" and not body.confirm:
        raise HTTPException(status_code=400, detail="编辑权限需要明确确认")
    try:
        return workspace.grant_workspace(body.path, body.access)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/workspaces/{workspace_id}/access")
def update_workspace_access(workspace_id: int, body: WorkspaceAccessBody):
    if body.access not in ("read", "write"):
        raise HTTPException(status_code=400, detail="无效的访问权限")
    if body.access == "write" and not body.confirm:
        raise HTTPException(status_code=400, detail="编辑权限需要明确确认")
    row = workspace.set_access(workspace_id, body.access)
    if not row:
        raise HTTPException(status_code=404, detail="工作区不存在")
    return row


@app.post("/api/workspaces/{workspace_id}/delete")
def delete_workspace(workspace_id: int):
    workspace.remove_workspace(workspace_id)
    return {"ok": True}


@app.post("/api/chat/uploads")
async def upload_chat_files(session_id: str = Form(...), files: list[UploadFile] = File(...)):
    try:
        return uploads.save_uploads(session_id, [(file.filename, file.file) for file in files])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat/uploads/delete")
def delete_chat_uploads(body: UploadDeleteBody):
    return {"ok": True, "deleted": uploads.delete_attachments(body.ids, body.session_id)}


@app.post("/api/chat")
async def chat(req: Request):
    body = await req.json()
    user_text = (body.get("message") or "").strip()
    session_id = str(body.get("session_id") or "legacy").strip()[:64] or "legacy"
    if not user_text and not body.get("attachment_ids"):
        return {"error": "empty message"}
    user_text = user_text or "请查看我上传的附件。"
    model = str(body.get("model") or "").strip()[:120]
    reasoning_effort = str(body.get("reasoning_effort") or "").strip()
    if reasoning_effort not in ("", "low", "medium", "high"):
        reasoning_effort = ""
    attachment_ids = [int(value) for value in body.get("attachment_ids") or []
                      if str(value).isdigit()][:200]
    db.touch_chat_session(session_id, user_text)

    def gen():
        options = {"model": model, "reasoning_effort": reasoning_effort,
                   "attachment_ids": attachment_ids}
        for ev in agent.flow(user_text, session_id, options):
            yield json.dumps(ev, ensure_ascii=False) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


# ---------------- 自动化工作流 ----------------

WORKFLOWS = {
    "daily_brief": {
        "title": "今日重点简报",
        "desc": "汇总今日重点消息、待办与日程，先看最需要处理的事。",
        "tag": "只读",
    },
    "important_digest": {
        "title": "重要消息摘要",
        "desc": "从近期重要消息中提炼带出处的关注点。",
        "tag": "只读",
    },
    "schedule_check": {
        "title": "日程体检",
        "desc": "检查待确认日程和最近安排，避免遗漏。",
        "tag": "只读",
    },
}


def _message_brief(m):
    return {"id": m["id"], "title": m["conv_title"], "channel": m["channel_key"],
            "sender": m["sender"], "ts": m["ts"], "text": m["text"],
            "group": m["grp"], "conv_key": m["conv_key"],
            "account_key": m["account_key"], "dedup_key": m["dedup_key"]}


@app.get("/api/workflows")
def workflow_catalog():
    return [{"id": key, **value} for key, value in WORKFLOWS.items()]


class WorkflowRun(pydantic.BaseModel):
    session_id: str = ""


@app.post("/api/workflows/{workflow_id}/execute")
def execute_workflow(workflow_id: str, run: WorkflowRun):
    if workflow_id not in WORKFLOWS:
        raise HTTPException(status_code=404, detail="unknown workflow")
    now = datetime.datetime.now()
    steps = []
    data = {}
    if workflow_id in ("daily_brief", "important_digest"):
        since = _today() if workflow_id == "daily_brief" else (
            now - datetime.timedelta(days=7)).strftime("%Y-%m-%d %H:%M")
        steps.append({"name": "筛选重点消息", "status": "done",
                      "detail": f"读取 {since} 之后的已订阅消息"})
        messages = db.q("SELECT * FROM messages WHERE ts >= ? AND grp IN "
                        "('important','notice','todo','schedule') "
                        "ORDER BY ts DESC LIMIT 12", (since,))
        data["messages"] = [_message_brief(m) for m in messages]
    if workflow_id in ("daily_brief", "schedule_check"):
        steps.append({"name": "检查日程", "status": "done", "detail": "排除已忽略项"})
        data["schedule"] = db.q("SELECT * FROM schedule_events WHERE status != 'dismissed' "
                                "ORDER BY start_at ASC LIMIT 8")
        for event in data["schedule"]:
            event["title"] = triage.event_title(event["title"], limit=80)
    if workflow_id == "daily_brief":
        steps.append({"name": "汇总待办", "status": "done", "detail": "仅统计未完成事项"})
        data["todos"] = db.q("SELECT * FROM todos WHERE done=0 ORDER BY id DESC LIMIT 8")
        pending = sum(1 for s in data["schedule"] if s["status"] == "pending")
        summary = (f"今天有 {len(data['messages'])} 条重点消息、"
                   f"{len(data['todos'])} 个待办，{pending} 个日程待确认。")
    elif workflow_id == "important_digest":
        summary = f"近期找到 {len(data['messages'])} 条重点消息，已按时间整理。"
    else:
        pending = sum(1 for s in data["schedule"] if s["status"] == "pending")
        summary = f"接下来有 {len(data['schedule'])} 个日程，{pending} 个仍待确认。"
    steps.append({"name": "生成可执行摘要", "status": "done", "detail": "保留原文出处"})
    run_id = secrets.token_hex(8)
    result = {"id": run_id, "workflow_id": workflow_id,
              "title": WORKFLOWS[workflow_id]["title"], "status": "completed",
              "steps": steps, "summary": summary, "data": data}
    session_id = run.session_id.strip()[:64]
    db.ex("INSERT INTO workflow_runs(id,session_id,workflow_id,status,result,created_at) "
          "VALUES(?,?,?,?,?,?)", (run_id, session_id, workflow_id, "completed",
                                  json.dumps(result, ensure_ascii=False), db.now_iso()))
    if session_id:
        db.ex("INSERT INTO chat_messages(role,content,ts,session_id) VALUES(?,?,?,?)",
              ("assistant", summary, db.now_iso(), session_id))
        db.touch_chat_session(session_id)
    return result


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
    r = ingest.ingest(msg.channel, msg.conv, title, msg.sender, now, msg.text, dedup)
    if not r:
        return {"ok": False, "reason": "重复消息已去重"}
    m, grp, event = r
    return {"ok": True, "message": m, "grp": grp, "event": event,
            "grp_label": GROUP_LABEL.get(grp, grp)}


# ---------------- 渠道接入（真实连接器）----------------

@app.get("/api/connectors")
def connector_catalog():
    out = []
    for key, c in connectors.CATALOG.items():
        n_subs = db.q("SELECT COUNT(*) n FROM subscriptions WHERE channel_key=? "
                      "AND active=1", (key,))[0]["n"]
        accounts = connectors.email_accounts() if key == "email" else []
        out.append({"key": key, "name": c["name"], "kind": c["kind"],
                    "ready": c["ready"], "desc": c["desc"], "fields": c["fields"],
                    "configured": bool(accounts) if key == "email" else connectors.is_configured(key),
                    "masked": accounts[0]["masked"] if accounts else connectors.masked_credentials(key),
                    "subscriptions": n_subs, "accounts": accounts})
    return out


class AccountBody(pydantic.BaseModel):
    account_id: str = ""


class CredentialBody(AccountBody):
    fields: dict = {}


@app.post("/api/connectors/{key}/credentials")
def save_credentials(key: str, body: CredentialBody):
    if key not in connectors.CATALOG or not connectors.CATALOG[key]["ready"]:
        return {"ok": False, "error": "该渠道暂未开放接入"}
    try:
        _, account_id = connectors.save_credentials(key, body.fields, body.account_id or None)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    result = connectors.test(key, account_id)
    account = next((a for a in connectors.email_accounts()
                    if a["account_key"] == account_id), None)
    return {**result, "account_id": account_id, "account": account,
            "masked": connectors.masked_credentials(key, account_id)}


@app.post("/api/connectors/{key}/test")
def test_connector(key: str, body: AccountBody = AccountBody()):
    return connectors.test(key, body.account_id or None)


@app.post("/api/connectors/{key}/discover")
def discover_conversations(key: str, body: AccountBody = AccountBody()):
    return connectors.discover(key, body.account_id or None)


class SubBody(pydantic.BaseModel):
    conv_key: str
    conv_title: str = ""
    on: bool = True
    account_key: str = ""


@app.post("/api/connectors/{key}/subscribe")
def subscribe(key: str, body: SubBody):
    """订阅/退订唯一入口：只有 active=1 的会话会被同步，未勾选的绝不拉取。"""
    if key not in connectors.CATALOG:
        return {"ok": False}
    account_key = body.account_key if key == "email" else ""
    if body.on:
        db.ex("INSERT INTO subscriptions(channel_key, account_key, conv_key, "
              "conv_title, active, added_at) VALUES(?,?,?,?,1,?) "
              "ON CONFLICT(channel_key, account_key, conv_key) DO UPDATE SET "
              "active=1, conv_title=excluded.conv_title",
              (key, account_key, body.conv_key, body.conv_title, db.now_iso()))
    else:
        db.ex("UPDATE subscriptions SET active=0 WHERE channel_key=? AND account_key=? "
              "AND conv_key=?", (key, account_key, body.conv_key))
    n = db.q("SELECT COUNT(*) n FROM subscriptions WHERE channel_key=? AND active=1",
             (key,))[0]["n"]
    return {"ok": True, "active": body.on, "subscriptions": n}


class KeywordBody(pydantic.BaseModel):
    conv_key: str
    keywords: list[str] = []


@app.post("/api/connectors/{key}/subscriptions/keywords")
def update_subscription_keywords(key: str, body: KeywordBody):
    """只更新已订阅会话的关键词，不创建订阅、不扩大监听范围。"""
    if key != "feishu":
        return {"ok": False, "error": "自定义同步关键词当前仅支持飞书群聊"}
    if any(len(keyword.strip()) > 50 for keyword in body.keywords):
        return {"ok": False, "error": "单个关键词不能超过 50 个字符"}
    if len(body.keywords) > 20:
        return {"ok": False, "error": "每个群聊最多设置 20 个关键词"}
    keywords = connectors.normalize_keywords(body.keywords)
    existing = db.q("SELECT id FROM subscriptions WHERE channel_key=? AND account_key='' "
                    "AND conv_key=? AND active=1", (key, body.conv_key))
    if not existing:
        return {"ok": False, "error": "请先订阅该群聊，再设置关键词"}
    db.ex("UPDATE subscriptions SET keywords=? WHERE id=?",
          (json.dumps(keywords, ensure_ascii=False), existing[0]["id"]))
    return {"ok": True, "keywords": keywords}


@app.get("/api/subscriptions")
def subscriptions():
    rows = db.q("SELECT * FROM subscriptions ORDER BY active DESC, added_at DESC")
    for row in rows:
        row["keywords"] = connectors.normalize_keywords(row.get("keywords"))
    return rows


@app.get("/api/email-accounts")
def email_accounts():
    return connectors.email_accounts()


@app.post("/api/connectors/{key}/sync")
def sync_connector(key: str, body: AccountBody = AccountBody()):
    return connectors.sync(key, body.account_id or None)


class FeishuOAuthStartBody(pydantic.BaseModel):
    web_origin: str = ""


@app.get("/api/connectors/feishu/oauth/status")
def feishu_oauth_status():
    creds = connectors.credentials("feishu")
    if not creds:
        return {"authorized": False, "configured": False, "user": None}
    return {"configured": True, **feishu_oauth.status(creds)}


@app.post("/api/connectors/feishu/oauth/start")
def feishu_oauth_start(body: FeishuOAuthStartBody):
    creds = connectors.credentials("feishu")
    if not creds.get("app_id") or not creds.get("app_secret"):
        return {"ok": False, "error": "请先保存飞书 App ID 和 App Secret"}
    web_origin = _local_web_origin(body.web_origin)
    if not web_origin:
        return {"ok": False, "error": "无法识别本地页面地址"}
    state = secrets.token_urlsafe(32)
    _OAUTH_STATES[state] = {
        "created": time.time(), "web_origin": web_origin,
        "redirect_uri": _FEISHU_REDIRECT_URI,
    }
    now = time.time()
    for key in list(_OAUTH_STATES):
        if now - _OAUTH_STATES[key]["created"] > 600:
            _OAUTH_STATES.pop(key, None)
    return {
        "ok": True,
        "authorize_url": feishu_oauth.build_authorize_url(
            creds["app_id"], _FEISHU_REDIRECT_URI, state),
        "redirect_uri": _FEISHU_REDIRECT_URI,
    }


@app.get("/api/connectors/feishu/oauth/callback")
def feishu_oauth_callback(code: str = "", state: str = "", error: str = ""):
    saved = _OAUTH_STATES.pop(state, None)
    if not saved or time.time() - saved["created"] > 600:
        return RedirectResponse(
            "http://localhost:5180/?tab=connectors&feishu=oauth_failed&reason=state",
            status_code=302,
        )
    web_origin = saved["web_origin"]

    def redirect(result, reason=""):
        query = {"tab": "connectors", "feishu": result}
        if reason:
            query["reason"] = reason
        return RedirectResponse(f"{web_origin}/?{urllib.parse.urlencode(query)}", status_code=302)

    if error:
        return redirect("denied", error)
    if not code:
        return redirect("oauth_failed", "missing_code")
    creds = connectors.credentials("feishu")
    try:
        feishu_oauth.authorize(creds, code, saved["redirect_uri"])
    except RuntimeError as exc:
        return redirect("oauth_failed", str(exc)[:160])
    return redirect("connected")


@app.post("/api/connectors/feishu/oauth/logout")
def feishu_oauth_logout():
    feishu_oauth.clear()
    return {"ok": True}


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
