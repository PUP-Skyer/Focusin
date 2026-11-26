# -*- coding: utf-8 -*-
"""Agent 执行层：工具注册表（schema + 风险分级）→ Sentinel 审批门 → 执行 → 流式回流。
无 LLM Key 时由规则兜底路由驱动同样的工具链，Demo 闭环不依赖网络。"""
import json
import re
import time

import db
import llm
import triage

SYSTEM_PROMPT = """你是「聚光 FocusIn」的智能助理小聚，帮助用户打理跨渠道聚合的消息。
规则：
1. 你以平台聚合的消息为工作上下文，回答务必引用出处（渠道·会话 + 时间 + 发送者）。
2. 涉及外发动作（发消息、发邮件）永远只起草，不代发，发送由用户自己完成。
3. 创建/修改/删除日程必须调用日程工具，不允许口头宣布成功；日程时间必须来自消息原文。
4. 语气轻松友好，简洁中文回复。"""

RISK_UPGRADE_KW = ["密码", "支付", "转账", "删除", "注销", "password", "delete"]


# ---------------- 工具实现 ----------------

def _fmt_hit(m):
    return f"[{m['ts']}] {m['conv_title']}｜{m['sender']}：{m['text']}（消息#{m['id']}）"


def t_search_messages(args):
    query = (args.get("query") or "").strip()
    for w in ["什么", "怎么", "帮我", "说了", "说啥", "关于", "到底", "有没有", "？", "?", "了", "的"]:
        query = query.replace(w, "")
    segs = [s for s in re.split(r"[，。,.！!？?\s]+", query) if len(s) >= 2]
    if not segs and query:
        segs = [query]
    # bigram 混合召回：中文长句拆二元词组，任一命中即召回
    bigrams = {query[i:i + 2] for i in range(len(query) - 1)} if len(query) >= 4 else set()
    terms = list(dict.fromkeys(segs + list(bigrams)))
    where = " OR ".join(["text LIKE ?"] * len(terms)) if terms else "1=1"
    params = [f"%{t}%" for t in terms]
    rows = db.q(f"SELECT * FROM messages WHERE ({where}) AND grp != 'chatter' "
                "ORDER BY ts DESC LIMIT 8", params)
    if not rows:
        rows = db.q("SELECT * FROM messages WHERE grp IN ('todo','schedule',"
                    "'important','notice') ORDER BY ts DESC LIMIT 5")
    return "\n".join(_fmt_hit(m) for m in rows) or "（没有找到相关消息）"


def t_list_schedule(args):
    rows = db.q(
        "SELECT e.*, m.text AS src FROM schedule_events e "
        "LEFT JOIN messages m ON m.id = e.source_msg_id "
        "WHERE e.status != 'dismissed' ORDER BY start_at ASC")
    if not rows:
        return "当前没有日程。"
    lines = []
    for r in rows:
        tag = "已确认" if r["status"] == "confirmed" else "待确认"
        src = (r["src"] or "")[:30]
        lines.append(f"{r['start_at']}｜{r['title']}（{tag}）依据：{src}（日程#{r['id']}）")
    return "\n".join(lines)


def t_create_schedule(args):
    title = (args.get("title") or "").strip()
    start_at = (args.get("start_at") or "").strip()
    if not title or not re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", start_at):
        return {"ok": False, "reason": "标题或时间格式不合法（需 YYYY-MM-DD HH:MM）"}
    db.ex("INSERT OR IGNORE INTO schedule_events(title, start_at, status, "
          "dedup_key, created_at, source_msg_id) VALUES(?,?,?,?,?,NULL)",
          (title, start_at, "confirmed", f"agent:{title}:{start_at}", db.now_iso()))
    return {"ok": True, "title": title, "start_at": start_at}


def t_update_schedule(args):
    sid = args.get("id")
    if not sid:
        return {"ok": False, "reason": "缺少日程 id"}
    if args.get("title"):
        db.ex("UPDATE schedule_events SET title=? WHERE id=?", (args["title"], sid))
    if args.get("start_at"):
        db.ex("UPDATE schedule_events SET start_at=? WHERE id=?", (args["start_at"], sid))
    return {"ok": True, "id": sid}


def t_delete_schedule(args):
    sid = args.get("id")
    db.ex("UPDATE schedule_events SET status='dismissed' WHERE id=?", (sid,))
    return {"ok": True, "id": sid}


def t_save_draft(args):
    title = args.get("title") or "未命名草稿"
    content = args.get("content") or ""
    db.ex("INSERT INTO drafts(title, content, created_at) VALUES(?,?,?)",
          (title, content, db.now_iso()))
    return {"ok": True, "note": "草稿已保存（只起草，不代发）", "draft_id": db.q(
        "SELECT MAX(id) id FROM drafts")[0]["id"]}


# ---------------- 工具注册表 ----------------
# name → {desc(中文用途), risk, handler, schema(OpenAI function 参数)}

TOOLS = {
    "search_messages": {
        "desc": "检索平台聚合的历史消息（跨渠道），返回带出处的原文。",
        "risk": "safe", "handler": t_search_messages,
        "schema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "检索关键词"}},
            "required": ["query"]}},
    "list_schedule": {
        "desc": "列出日程清单（含待确认项与其原文依据）。",
        "risk": "safe", "handler": t_list_schedule,
        "schema": {"type": "object", "properties": {}}},
    "create_schedule": {
        "desc": "创建日程事件。时间必须来自消息原文，不许编造。",
        "risk": "moderate", "handler": t_create_schedule,
        "schema": {"type": "object", "properties": {
            "title": {"type": "string"},
            "start_at": {"type": "string", "description": "格式 YYYY-MM-DD HH:MM"}},
            "required": ["title", "start_at"]}},
    "update_schedule": {
        "desc": "修改日程标题或时间。",
        "risk": "sensitive", "handler": t_update_schedule,
        "schema": {"type": "object", "properties": {
            "id": {"type": "integer"}, "title": {"type": "string"},
            "start_at": {"type": "string"}},
            "required": ["id"]}},
    "delete_schedule": {
        "desc": "删除日程（软删除为 dismissed）。",
        "risk": "sensitive", "handler": t_delete_schedule,
        "schema": {"type": "object", "properties": {
            "id": {"type": "integer"}}, "required": ["id"]}},
    "save_draft": {
        "desc": "保存回复/邮件草稿到草稿箱。只起草不代发。",
        "risk": "safe", "handler": t_save_draft,
        "schema": {"type": "object", "properties": {
            "title": {"type": "string"}, "content": {"type": "string"}},
            "required": ["content"]}},
}


def tools_schema():
    return [{"type": "function", "function": {
        "name": n, "description": t["desc"], "parameters": t["schema"]}}
        for n, t in TOOLS.items()]


def audit(tool, args, risk, approval_id, result):
    db.ex("INSERT INTO audit_log(ts, tool, args, risk, approval_id, result) "
          "VALUES(?,?,?,?,?,?)",
          (db.now_iso(), tool, json.dumps(args, ensure_ascii=False), risk,
           approval_id, str(result)[:300]))


def risk_of(name, args):
    risk = TOOLS.get(name, {}).get("risk", "sensitive")
    blob = json.dumps(args, ensure_ascii=False)
    if any(k in blob for k in RISK_UPGRADE_KW):
        return "sensitive"  # 运行时参数动态升级
    return risk


def request_approval(name, args, risk, emit):
    """HITL 审批门：落库 → 通知前端 → 轮询决定（≤120s，超时视为拒绝）。"""
    db.ex("INSERT INTO approvals(tool, args, risk, status, created_at) "
          "VALUES(?,?,?,?,?)", (name, json.dumps(args, ensure_ascii=False),
                                risk, "pending", db.now_iso()))
    aid = db.q("SELECT MAX(id) id FROM approvals")[0]["id"]
    emit({"type": "approval", "id": aid, "tool": name, "risk": risk,
          "args": args})
    deadline = time.time() + 120
    while time.time() < deadline:
        row = db.q("SELECT status, decision FROM approvals WHERE id=?", (aid,))
        if row and row[0]["status"] != "pending":
            decision = row[0]["decision"]
            emit({"type": "approval_resolved", "id": aid, "decision": decision})
            return decision == "approve", aid
        time.sleep(0.5)
    db.ex("UPDATE approvals SET status='timeout', decision='deny', "
          "decided_at=? WHERE id=?", (db.now_iso(), aid))
    emit({"type": "approval_resolved", "id": aid, "decision": "timeout"})
    return False, aid


def execute_tool(name, args, emit):
    """统一执行入口：safe 直跑；moderate/sensitive 过审批门。"""
    if name not in TOOLS:
        result = {"ok": False, "reason": f"未知工具 {name}"}
        audit(name, args, "unknown", None, result)
        return result
    risk = risk_of(name, args)
    emit({"type": "tool_start", "name": name, "args": args, "risk": risk})
    approval_id = None
    if risk != "safe":
        ok, approval_id = request_approval(name, args, risk, emit)
        if not ok:
            result = {"ok": False, "reason": "用户拒绝了该操作（宁拦勿纵）"}
            emit({"type": "tool_end", "name": name, "ok": False,
                  "result": result["reason"]})
            audit(name, args, risk, approval_id, result)
            return result
    try:
        result = TOOLS[name]["handler"](args)
    except Exception as e:  # noqa: BLE001
        result = {"ok": False, "reason": f"工具执行异常: {e}"}
    failed = isinstance(result, dict) and result.get("ok") is False
    emit({"type": "tool_end", "name": name, "ok": not failed,
          "result": result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)})
    audit(name, args, risk, approval_id, result)
    return result


# ---------------- 主流程 ----------------

def flow(user_text):
    """事件生成器：Agent 流程在后台线程执行，事件经队列实时产出（审批等待不阻塞流）。"""
    import queue
    import threading
    q = queue.Queue()

    def run():
        try:
            _flow_sync(user_text, q.put)
        except Exception as e:  # noqa: BLE001
            q.put({"type": "error", "message": str(e)})
        finally:
            q.put(None)

    threading.Thread(target=run, daemon=True).start()
    while True:
        ev = q.get()
        if ev is None:
            break
        yield ev


def _flow_sync(user_text, emit):
    db.ex("INSERT INTO chat_messages(role, content, ts) VALUES(?,?,?)",
          ("user", user_text, db.now_iso()))
    full = []
    try:
        if llm.available():
            _llm_flow(user_text, emit, full)
        else:
            _fallback_flow(user_text, emit, full)
    except Exception as e:  # noqa: BLE001
        emit({"type": "error", "message": str(e)})
        full.append("\n（出错了，但我还在）")
    answer = "".join(full).strip() or "（小聚走神了，再试一次？）"
    db.ex("INSERT INTO chat_messages(role, content, ts) VALUES(?,?,?)",
          ("assistant", answer, db.now_iso()))
    emit({"type": "done", "content": answer})


def _llm_flow(user_text, emit, full):
    emit({"type": "thinking", "text": "正在思考…（LLM）"})
    history = db.q("SELECT role, content FROM chat_messages ORDER BY id DESC LIMIT 24")
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + [
        {"role": r["role"], "content": r["content"]} for r in reversed(history)]

    for _round in range(6):
        text, tool_calls = llm.run(msgs, tools_schema(), on_delta=full.append)
        if not tool_calls:
            emit({"type": "thinking_done"})
            return
        msgs.append({"role": "assistant", "content": text,
                     "tool_calls": [{"id": t["id"], "type": "function",
                                     "function": {"name": t["name"],
                                                  "arguments": t["args"]}}
                                    for t in tool_calls]})
        for tc in tool_calls:
            try:
                args = json.loads(tc["args"] or "{}")
            except json.JSONDecodeError:
                args = {}
            result = execute_tool(tc["name"], args, emit)
            msgs.append({"role": "tool", "tool_call_id": tc["id"],
                         "content": result if isinstance(result, str)
                         else json.dumps(result, ensure_ascii=False)})
        emit({"type": "thinking_done"})


def _fallback_flow(user_text, emit, full):
    """规则兜底路由：同样走工具链与审批门，断网也能演示 P0 闭环。"""
    emit({"type": "thinking", "text": "正在检索消息上下文…（本地规则模式）"})
    t = user_text

    dt = triage.parse_time(t)
    if dt and any(k in t for k in ["提醒", "安排", "记", "定", "加个"]):
        emit({"type": "thinking", "text": "识别到日程，走审批门…"})
        result = execute_tool("create_schedule",
                              {"title": triage.event_title(t),
                               "start_at": dt.strftime("%Y-%m-%d %H:%M")}, emit)
        if isinstance(result, dict) and result.get("ok"):
            full.append(f"好嘞，日程已安排：{result['title']}，{result['start_at']}，"
                        "提醒会在 1 小时前到。来源是你说的话，我没有编造。")
        else:
            full.append("这次没有创建日程（你拒绝了或操作未通过）。")
        emit({"type": "thinking_done"})
        return

    if any(k in t for k in ["日程", "会议", "今天有什么", "接下来", "安排了什么"]):
        emit({"type": "thinking", "text": "查询日程清单…"})
        rows = execute_tool("list_schedule", {}, emit)
        full.append("接下来的日程如下（均带原文依据，可到日历页核对）：\n" + str(rows))
        emit({"type": "thinking_done"})
        return

    if any(k in t for k in ["起草", "回复", "写一条", "草稿"]):
        emit({"type": "thinking", "text": "检索相关上下文以起草…"})
        hits = execute_tool("search_messages", {"query": t}, emit)
        hit_lines = [l for l in str(hits).splitlines() if l.strip()][:3]
        context = "\n".join(hit_lines)
        draft = (f"【草稿】收到，{ '这件事' }我记下了。\n基于上下文：\n{context}\n"
                 "我拟了一条回复（只起草，发送由你自己完成）：\n"
                 "「方案/材料已在推进，今天下班前给到 v2，明早十点前请查收。如有调整随时说。」")
        execute_tool("save_draft", {"title": "回复草稿", "content": draft}, emit)
        full.append(draft)
        emit({"type": "thinking_done"})
        return

    emit({"type": "thinking", "text": "跨渠道检索消息…"})
    hits = execute_tool("search_messages", {"query": t}, emit)
    lines = [l for l in str(hits).splitlines() if l.strip()]
    if lines and "没有找到" not in lines[0]:
        full.append("我在聚合消息里找到了这些（带出处）：\n" + "\n".join(lines[:5]) +
                    "\n以上均来自你已接入渠道的原文，点击消息流页可跳转查看上下文。")
    else:
        full.append("没有直接命中。我可以帮你：查日程（“今天有什么安排”）、检索历史消息"
                    "（“领导上周说了啥”）、起草回复（“帮我起草一条回复”）。"
                    "配置 LLM API Key 后我还能理解更自由的说法。")
    emit({"type": "thinking_done"})
