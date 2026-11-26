# -*- coding: utf-8 -*-
"""渠道连接器层。

硬性隐私约束（本平台的底线）：连接器只对「用户在订阅清单里手动勾选的会话」
拉取消息；未勾选的会话绝不请求、绝不落库。发现（discover）只返回会话元数据
（名字/标识），供用户挑选，不抓取任何消息内容。

凭据仅保存在本机 SQLite（settings 表），接口永不回传原文，只回传掩码。
"""
import json

import db

from connectors import email_imap, feishu

# kind: imap / openapi / local
CATALOG = {
    "email": {
        "name": "邮箱", "kind": "imap", "ready": True,
        "desc": "标准 IMAP 协议直连你的邮箱（QQ邮箱/Gmail/Outlook 等），"
                "凭据只存本机。需在邮箱服务商开启 IMAP 并使用授权码。",
        "fields": [
            {"key": "host", "label": "IMAP 服务器", "placeholder": "imap.qq.com",
             "presets": [("QQ邮箱", "imap.qq.com"), ("163邮箱", "imap.163.com"),
                         ("Gmail", "imap.gmail.com"), ("Outlook", "outlook.office365.com"),
                         ("126邮箱", "imap.126.com")]},
            {"key": "port", "label": "端口", "placeholder": "993", "type": "number"},
            {"key": "username", "label": "邮箱账号", "placeholder": "you@example.com",
             "type": "email"},
            {"key": "password", "label": "密码/授权码", "type": "password",
             "hint": "QQ/163 等需使用「授权码」而非登录密码"},
        ],
        "module": email_imap,
    },
    "feishu": {
        "name": "飞书", "kind": "openapi", "ready": True,
        "desc": "官方 OpenAPI 接入：在飞书开放平台创建「自建应用」，开启机器人能力，"
                "把应用拉进你要监听的群。凭据只存本机。",
        "fields": [
            {"key": "app_id", "label": "App ID", "placeholder": "cli_xxxxxxxx"},
            {"key": "app_secret", "label": "App Secret", "type": "password"},
        ],
        "module": feishu,
    },
    "wechat": {
        "name": "微信", "kind": "local", "ready": False,
        "desc": "规划中：本地只读方案——只读本机微信数据库、由你亲自提供密钥材料，"
                "平台不碰微信密码、不注入不 Hook（个人微信无官方 API，"
                "输密码给平台 = 封号与盗号风险，坚决不做）。",
        "fields": [],
        "module": None,
    },
    "qq": {
        "name": "QQ", "kind": "local", "ready": False,
        "desc": "暂缓：无官方个人 API，安全接入路线不成熟，仅保留接口位。",
        "fields": [], "module": None,
    },
    "dingtalk": {
        "name": "钉钉", "kind": "openapi", "ready": False,
        "desc": "暂缓：钉钉开放平台接口位已预留，待接入。",
        "fields": [], "module": None,
    },
}

CRED_PREFIX = "cred:"


def get_module(key):
    return CATALOG.get(key, {}).get("module")


def credentials(key):
    raw = db.get_setting(CRED_PREFIX + key, "")
    return json.loads(raw) if raw else {}


def save_credentials(key, fields):
    """合并保存凭据；空密码字段不覆盖已有值。"""
    creds = credentials(key)
    for f in CATALOG[key]["fields"]:
        v = str(fields.get(f["key"]) or "").strip()
        if v:
            creds[f["key"]] = v
    db.set_setting(CRED_PREFIX + key, json.dumps(creds, ensure_ascii=False))
    return creds


def is_configured(key):
    creds = credentials(key)
    return all(creds.get(f["key"]) for f in CATALOG[key]["fields"])


def masked_credentials(key):
    """掩码视图：密码类字段只显示是否已设置，其余字段截断显示。"""
    creds = credentials(key)
    out = {}
    for f in CATALOG[key]["fields"]:
        v = creds.get(f["key"], "")
        if f.get("type") == "password":
            out[f["key"]] = "已设置" if v else ""
        else:
            out[f["key"]] = (v[:3] + "…" + v[-4:]) if len(v) > 12 else v
    return out


def test(key):
    mod = get_module(key)
    if mod is None:
        return {"ok": False, "error": "该渠道暂未开放接入"}
    if not is_configured(key):
        return {"ok": False, "error": "凭据不完整"}
    try:
        return mod.test(credentials(key))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"连接失败：{e}"}


def discover(key):
    """列出会话元数据（仅名称/标识，不取消息）。"""
    mod = get_module(key)
    if mod is None:
        return {"ok": False, "error": "该渠道暂未开放接入"}
    if not is_configured(key):
        return {"ok": False, "error": "请先保存凭据"}
    try:
        convs = mod.discover(credentials(key))
        return {"ok": True, "conversations": convs}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"发现会话失败：{e}"}


def sync(key):
    """只拉取该渠道下已订阅（active=1）的会话消息，走统一入站管道。"""
    mod = get_module(key)
    if mod is None:
        return {"ok": False, "error": "该渠道暂未开放接入"}
    if not is_configured(key):
        return {"ok": False, "error": "请先保存凭据"}
    subs = db.q("SELECT * FROM subscriptions WHERE channel_key=? AND active=1 "
                "ORDER BY added_at DESC", (key,))
    if not subs:
        return {"ok": False, "error": "还没有订阅任何会话——请先勾选要监听的群/文件夹"}
    fetched, new_msgs = 0, 0
    errors = []
    import ingest as _ingest  # 延迟导入避免环
    for s in subs:
        try:
            msgs = mod.fetch_conversation(credentials(key), s["conv_key"],
                                          s["conv_title"])
            fetched += len(msgs)
            for m in msgs:
                r = _ingest.ingest(key, s["conv_key"], s["conv_title"],
                                   m["sender"], m["ts"], m["text"], m["dedup"])
                if r:
                    new_msgs += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"{s['conv_title']}: {e}")
    return {"ok": not errors, "fetched": fetched, "new": new_msgs,
            "subscriptions": len(subs), "errors": errors[:5]}
