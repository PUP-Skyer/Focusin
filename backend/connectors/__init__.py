# -*- coding: utf-8 -*-
"""渠道连接器层。

硬性隐私约束（本平台的底线）：连接器只对「用户在订阅清单里手动勾选的会话」
拉取消息；未勾选的会话绝不请求、绝不落库。发现（discover）只返回会话元数据
（名字/标识），供用户挑选，不抓取任何消息内容。

凭据仅保存在本机 SQLite（settings 表），接口永不回传原文，只回传掩码。
"""
import hashlib
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
             "presets": [("QQ邮箱 / Foxmail", "imap.qq.com"), ("163邮箱", "imap.163.com"),
                         ("126邮箱", "imap.126.com"), ("Yeah.net", "imap.yeah.net"),
                         ("139邮箱", "imap.139.com"), ("189邮箱", "imap.189.cn"),
                         ("10086邮箱", "imap.wo.cn"), ("阿里邮箱", "imap.aliyun.com"),
                         ("新浪邮箱", "imap.sina.com"), ("TOM邮箱", "imap.tom.com"),
                         ("263邮箱", "imap.263.net"), ("Outlook", "outlook.office365.com"),
                         ("iCloud", "imap.mail.me.com"), ("Gmail", "imap.gmail.com"),
                         ("Zoho Mail", "imap.zoho.com")]},
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
        "desc": "官方 OpenAPI 接入：创建自建应用并开启机器人能力，申请群信息、"
                "读取消息和群组所有消息权限，发布后把机器人拉进要监听的群。凭据只存本机。",
        "fields": [
            {"key": "app_id", "label": "App ID", "placeholder": "cli_xxxxxxxx",
             "hint": "在飞书开放平台创建自建应用，并开启机器人能力"},
            {"key": "app_secret", "label": "App Secret", "type": "password",
             "hint": "需要 im:chat:readonly、im:message:readonly、im:message.group_msg；真实头像另需 contact:contact.base:readonly"},
        ],
        "module": feishu,
    },
    "wechat": {
        "name": "微信", "kind": "local", "ready": False,
        "desc": "规划中：本地只读方案——只读本机微信数据库、由你亲自提供密钥材料，"
                "平台不碰微信密码、不注入不 Hook（个人微信无官方 API，"
                "输密码给平台 = 封号与盗号风险，坚决不做）。",
        "fields": [], "module": None,
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


def _setting_key(key, account_id=None):
    if key == "email" and account_id:
        return f"{CRED_PREFIX}email:{account_id}"
    return CRED_PREFIX + key


def email_account_id(creds):
    host = str(creds.get("host") or "").strip().lower()
    username = str(creds.get("username") or "").strip().lower()
    if not host or not username:
        return ""
    return hashlib.sha256(f"{host}\n{username}".encode("utf-8")).hexdigest()[:12]


EMAIL_PROVIDERS = [
    ("qq", "QQ邮箱", ("qq.com", "foxmail.com")),
    ("163", "163邮箱", ("163.com",)),
    ("126", "126邮箱", ("126.com",)),
    ("yeah", "Yeah.net", ("yeah.net",)),
    ("139", "139邮箱", ("139.com",)),
    ("189", "189邮箱", ("189.cn",)),
    ("wo", "10086邮箱", ("wo.cn",)),
    ("aliyun", "阿里邮箱", ("aliyun.com",)),
    ("sina", "新浪邮箱", ("sina.com", "sina.cn")),
    ("tom", "TOM邮箱", ("tom.com",)),
    ("263", "263邮箱", ("263.net", "263.com")),
    ("outlook", "Outlook", ("outlook.", "office365", "hotmail.")),
    ("icloud", "iCloud邮箱", ("icloud.com", "me.com", "mac.com")),
    ("gmail", "Gmail", ("gmail.com",)),
    ("proton", "ProtonMail", ("protonmail.com", "proton.me")),
    ("zoho", "Zoho Mail", ("zoho.com",)),
]


def email_provider_info(host):
    host = (host or "").lower()
    for key, label, domains in EMAIL_PROVIDERS:
        if any(domain in host for domain in domains):
            return key, label
    return "other", "其他邮箱"


def email_provider(host):
    return email_provider_info(host)[1]


def _migrate_legacy_email():
    raw = db.get_setting(CRED_PREFIX + "email", "")
    if not raw:
        return
    try:
        creds = json.loads(raw)
        aid = email_account_id(creds)
        if not aid or db.get_setting(_setting_key("email", aid)):
            return
        db.set_setting(_setting_key("email", aid), json.dumps(creds, ensure_ascii=False))
        db.ex("UPDATE subscriptions SET account_key=? WHERE channel_key='email' "
              "AND account_key=''", (aid,))
        db.ex("UPDATE messages SET account_key=? WHERE channel_key='email' "
              "AND account_key='' AND dedup_key LIKE 'imap:%'", (aid,))
    except (ValueError, TypeError):
        return


def email_accounts():
    _migrate_legacy_email()
    rows = db.q("SELECT key, value FROM settings WHERE key LIKE ? ORDER BY key",
                (f"{CRED_PREFIX}email:%",))
    out = []
    for row in rows:
        aid = row["key"].split(":", 2)[-1]
        try:
            creds = json.loads(row["value"])
        except (ValueError, TypeError):
            continue
        username = str(creds.get("username") or "")
        host = str(creds.get("host") or "")
        provider_key, provider = email_provider_info(host)
        local = username.split("@", 1)[0]
        out.append({
            "account_key": aid, "username": username, "host": host,
            "port": creds.get("port") or 993, "provider": provider,
            "provider_key": provider_key, "label": f"{provider} · {username}" if username else provider,
            "short_label": f"{provider} · {local}" if local else provider,
            "configured": all(creds.get(f["key"]) for f in CATALOG["email"]["fields"]),
            "masked": masked_credentials("email", aid),
        })
    return out


def get_module(key):
    return CATALOG.get(key, {}).get("module")


def credentials(key, account_id=None):
    if key == "email" and not account_id:
        raw = db.get_setting(CRED_PREFIX + key, "")
        if raw:
            return json.loads(raw)
        accounts = email_accounts()
        if len(accounts) == 1:
            return credentials(key, accounts[0]["account_key"])
        return {}
    raw = db.get_setting(_setting_key(key, account_id), "")
    return json.loads(raw) if raw else {}


def save_credentials(key, fields, account_id=None):
    """合并保存凭据；空密码字段不覆盖已有值。"""
    if key == "email":
        account_id = account_id or email_account_id(fields)
        if not account_id:
            raise ValueError("邮箱账号和 IMAP 服务器不能为空")
    creds = credentials(key, account_id)
    for f in CATALOG[key]["fields"]:
        v = str(fields.get(f["key"]) or "").strip()
        if v:
            creds[f["key"]] = v
    db.set_setting(_setting_key(key, account_id), json.dumps(creds, ensure_ascii=False))
    return creds, account_id


def is_configured(key, account_id=None):
    creds = credentials(key, account_id)
    return all(creds.get(f["key"]) for f in CATALOG[key]["fields"])


def _connector_credentials(key, account_id=None):
    creds = credentials(key, account_id)
    if key == "feishu":
        import feishu_oauth
        token = feishu_oauth.get_access_token(creds)
        if token:
            creds["user_access_token"] = token
    return creds


def masked_credentials(key, account_id=None):
    """掩码视图：密码类字段只显示是否已设置，其余字段截断显示。"""
    creds = credentials(key, account_id)
    out = {}
    for f in CATALOG[key]["fields"]:
        v = creds.get(f["key"], "")
        if f.get("type") == "password":
            out[f["key"]] = "已设置" if v else ""
        elif f.get("type") == "checkbox":
            out[f["key"]] = "已确认" if v else ""
        else:
            out[f["key"]] = (v[:3] + "…" + v[-4:]) if len(v) > 12 else v
    return out


def test(key, account_id=None):
    mod = get_module(key)
    if mod is None:
        return {"ok": False, "error": "该渠道暂未开放接入"}
    if not is_configured(key, account_id):
        return {"ok": False, "error": "凭据不完整"}
    try:
        return mod.test(_connector_credentials(key, account_id))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"连接失败：{e}"}


def discover(key, account_id=None):
    """列出会话元数据（仅名称/标识，不取消息）。"""
    mod = get_module(key)
    if mod is None:
        return {"ok": False, "error": "该渠道暂未开放接入"}
    if not is_configured(key, account_id):
        return {"ok": False, "error": "请先保存凭据"}
    try:
        convs = mod.discover(_connector_credentials(key, account_id))
        return {"ok": True, "conversations": convs}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"发现会话失败：{e}"}


def normalize_keywords(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return []
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        keyword = str(item).strip()
        if keyword and keyword not in out:
            out.append(keyword)
    return out[:20]


def _refresh_feishu_names(names):
    rows = db.q("SELECT DISTINCT sender_id FROM messages WHERE channel_key='feishu'")
    aliased = {r["sender_id"] for r in db.q("SELECT sender_id FROM sender_aliases WHERE channel_key='feishu'")}
    for row in rows:
        if row["sender_id"] in aliased:
            continue
        name = names.get(row["sender_id"], "")
        if name and name != "member" and not name.startswith(("ou_", "on_", "cli_")):
            db.ex("UPDATE messages SET sender=? WHERE channel_key='feishu' AND sender_id=?",
                  (name, row["sender_id"]))


def sync(key, account_id=None):
    """只拉取该渠道下已订阅（active=1）的会话消息，走统一入站管道。"""
    mod = get_module(key)
    if mod is None:
        return {"ok": False, "error": "该渠道暂未开放接入"}
    if not is_configured(key, account_id):
        return {"ok": False, "error": "请先保存凭据"}
    sql = "SELECT * FROM subscriptions WHERE channel_key=? AND active=1"
    args = [key]
    if account_id:
        sql += " AND account_key=?"
        args.append(account_id)
    sql += " ORDER BY added_at DESC"
    subs = db.q(sql, tuple(args))
    if not subs:
        return {"ok": False, "error": "还没有订阅任何会话——请先勾选要监听的群/文件夹"}
    fetched, new_msgs = 0, 0
    errors, warnings = [], []
    import ingest as _ingest  # 延迟导入避免环
    for s in subs:
        sub_account = s.get("account_key") or ""
        try:
            known_names = {}
            member_stats = {}
            if key == "feishu":
                msgs = mod.fetch_conversation(_connector_credentials(key, sub_account), s["conv_key"],
                                              s["conv_title"], warnings=warnings,
                                              keywords=normalize_keywords(s.get("keywords")),
                                              known_names=known_names,
                                              member_stats=member_stats)
            else:
                msgs = mod.fetch_conversation(_connector_credentials(key, sub_account), s["conv_key"],
                                              s["conv_title"])
            fetched += len(msgs)
            for m in msgs:
                r = _ingest.ingest(key, s["conv_key"], s["conv_title"],
                                   m["sender"], m["ts"], m["text"], m["dedup"],
                                   account_key=sub_account, links=m.get("links"),
                                   attachments=m.get("attachments"),
                                   sender_id=m.get("sender_id", ""),
                                   sender_avatar=m.get("sender_avatar", ""),
                                   grp_hint=m.get("grp"))
                if r:
                    new_msgs += 1
            if key == "feishu":
                _refresh_feishu_names(known_names)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{s['conv_title']}: {e}")
    result = {"ok": not errors, "fetched": fetched, "new": new_msgs,
              "subscriptions": len(subs), "errors": errors[:5],
              "warnings": list(dict.fromkeys(warnings))[:5]}
    if key == "feishu":
        import feishu_oauth
        session = feishu_oauth.load()
        result["identity"] = "user" if session and feishu_oauth.get_access_token(
            credentials(key)) else "bot"
        result["unresolved_senders"] = db.q(
            "SELECT COUNT(DISTINCT sender_id) n FROM messages WHERE channel_key='feishu' "
            "AND sender_id != '' AND (sender IS NULL OR sender='' OR sender='member' "
            "OR sender GLOB 'ou_*' OR sender GLOB 'on_*' OR sender GLOB 'cli_*')")[0]["n"]
    return result
