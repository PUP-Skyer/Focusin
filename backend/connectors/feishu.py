# -*- coding: utf-8 -*-
"""飞书连接器：官方 OpenAPI（自建应用 + 机器人）。
- 凭据：App ID / App Secret → tenant_access_token
- 发现：机器人所在群列表（元数据）
- 拉取：仅订阅群的消息，只读
需要应用开通 im:message 读取权限（读取用户所在群/机器人所在群消息）。"""
import datetime
import json
import time
import urllib.request

BASE = "https://open.feishu.cn/open-apis"


def _post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _get(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _token(creds):
    data = _post(f"{BASE}/auth/v3/tenant_access_token/internal", {
        "app_id": creds["app_id"], "app_secret": creds["app_secret"]})
    tok = data.get("tenant_access_token")
    if not tok:
        raise RuntimeError(f"获取 tenant_access_token 失败：{data.get('msg', data)}")
    return tok


def test(creds):
    _token(creds)
    return {"ok": True, "note": "飞书应用凭据有效"}


def discover(creds):
    """机器人所在的群（元数据）。没把机器人拉进群就看不到群。"""
    token = _token(creds)
    chats, page = [], None
    while True:
        url = (f"{BASE}/im/v1/chats?page_size=100"
               + (f"&page_token={page}" if page else ""))
        data = _get(url, token)
        for it in data.get("data", {}).get("items", []) or []:
            chats.append({"conv_key": it["chat_id"],
                          "conv_title": it.get("name") or "未命名群"})
        if not data.get("data", {}).get("has_more"):
            break
        page = data["data"].get("page_token")
    return chats


def _text_of(content_json, msg_type):
    """从消息 content JSON 里提取纯文本。"""
    try:
        c = json.loads(content_json or "{}")
    except json.JSONDecodeError:
        return ""
    if msg_type == "text":
        return c.get("text", "")
    if msg_type == "post":
        out = []
        for lang in (c.get("content") or {}).values():
            for para in lang or []:
                for piece in para or []:
                    if isinstance(piece, dict) and piece.get("text"):
                        out.append(piece["text"])
        return " ".join(out)
    if msg_type == "interactive":  # 卡片消息：提取 markdown 里的文字
        return str(c)[:200]
    return ""


def fetch_conversation(creds, conv_key, conv_title):
    """拉取单个已订阅群的最近消息（最多 50 条，只读）。"""
    token = _token(creds)
    url = (f"{BASE}/im/v1/messages?container_id_type=chat&container_id={conv_key}"
           "&page_size=50&sort_type=ByCreateTimeDesc")
    data = _get(url, token)
    out = []
    for it in (data.get("data", {}).get("items", []) or [])[:50]:
        body = it.get("body") or {}
        text = _text_of(body.get("content"), body.get("msg_type"))
        if not text:
            continue
        ts_ms = int(it.get("create_time") or time.time() * 1000)
        ts = datetime.datetime.fromtimestamp(ts_ms / 1000).strftime(
            "%Y-%m-%d %H:%M")
        out.append({"sender": (it.get("sender") or {}).get("sender_type", "member"),
                    "ts": ts, "text": text.strip()[:1500],
                    "dedup": f"feishu:{it.get('message_id', '')}"})
    out.reverse()  # 时间正序入库
    return out
