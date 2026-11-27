# -*- coding: utf-8 -*-
"""飞书连接器：官方 OpenAPI（自建应用 + 机器人）。
- 凭据：App ID / App Secret → tenant_access_token
- 发现：机器人所在群列表（元数据）
- 拉取：仅订阅群的消息，只读
需要应用开通 im:message 读取权限（读取用户所在群/机器人所在群消息）。"""
import datetime
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import triage

BASE = "https://open.feishu.cn/open-apis"
_PROFILE_CACHE = {}


class FeishuPermissionError(RuntimeError):
    pass


class FeishuScopeError(RuntimeError):
    pass


def _checked(data):
    if data.get("code", 0) != 0:
        raise RuntimeError(f"飞书接口错误 {data.get('code')}: {data.get('msg', data)}")
    return data


def _post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return _checked(json.loads(r.read()))


def _get(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return _checked(json.loads(r.read()))
    except urllib.error.HTTPError as exc:
        try:
            error = json.loads(exc.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            error = {}
        if error.get("code"):
            raise RuntimeError(
                f"飞书接口错误 {error['code']}: {error.get('msg') or '请求失败'}") from exc
        raise


def _token(creds):
    user_token = creds.get("user_access_token") or ""
    if user_token:
        return user_token
    data = _post(f"{BASE}/auth/v3/tenant_access_token/internal", {
        "app_id": creds["app_id"], "app_secret": creds["app_secret"]})
    tok = data.get("tenant_access_token")
    if not tok:
        raise RuntimeError(f"获取 tenant_access_token 失败：{data.get('msg', data)}")
    return tok


def test(creds):
    _token(creds)
    note = "飞书用户账号授权有效" if creds.get("user_access_token") else "飞书应用凭据有效"
    return {"ok": True, "note": note}


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


def _collect_text(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(_collect_text(item))
        return out
    if not isinstance(value, dict):
        return []
    out = []
    for key in ("title", "text", "content", "content_v2", "elements", "fields", "value", "name"):
        if key in value:
            out.extend(_collect_text(value[key]))
    if not out:
        skipped = {"style", "url", "image_key", "template", "fallback", "width", "size"}
        for key, item in value.items():
            if key not in skipped:
                out.extend(_collect_text(item))
    return out


def _decode_escapes(value):
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), value)


def _plain_text(value):
    value = html.unescape(_decode_escapes(str(value or "")))
    value = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", "", value)
    value = re.sub(r"(?i)<br\s*/?>", "\n", value)
    value = re.sub(r"(?i)</(?:p|div|li|h[1-6]|tr|blockquote|section|article)\s*>", "\n", value)
    value = re.sub(r"(?s)<[^>]+>", "", value)
    lines = [re.sub(r"[\t \u00a0]+", " ", line).strip() for line in value.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _text_of(content_json, msg_type):
    """从消息 content JSON 里提取纯文本。"""
    try:
        c = json.loads(content_json or "{}")
    except (json.JSONDecodeError, TypeError):
        return ""
    if isinstance(c, str):
        try:
            c = json.loads(c)
        except json.JSONDecodeError:
            return _plain_text(c)
    if msg_type == "text" and isinstance(c, dict):
        return _plain_text(c.get("text", ""))
    if msg_type == "post" and isinstance(c, dict):
        title = str(c.get("title") or "").strip()
        body = c.get("content") or c.get("content_v2") or c
        parts = ([title] if title else []) + _collect_text(body)
        return _plain_text(" ".join(parts))
    return _plain_text(" ".join(_collect_text(c)))


def _display_text(text, mentions):
    display_text = _plain_text(text)
    for mention in mentions:
        key = mention.get("key")
        name = mention.get("name")
        if not key:
            continue
        if name:
            replacement = f"@{name}"
        elif "@_all" in key:
            replacement = "@所有人"
        else:
            replacement = "@用户"
        display_text = display_text.replace(key, replacement)
    display_text = re.sub(r"@_user_\d+", "@用户", display_text)
    display_text = re.sub(r"\bat\s+@_all\b", "@所有人", display_text)
    display_text = display_text.replace("@_all", "@所有人")
    return re.sub(r"@所有人(?:\s*所有人)+", "@所有人", display_text)


def _member_names(token, conv_key, stats=None):
    names, page, seen_pages = {}, None, set()
    while True:
        query = {"page_size": 100}
        if page:
            query["page_token"] = page
        url = f"{BASE}/im/v1/chats/{conv_key}/members?{urllib.parse.urlencode(query)}"
        data = _get(url, token).get("data", {})
        for member in data.get("items", []) or []:
            name = member.get("name")
            if not name:
                continue
            member_id = member.get("member_id") or {}
            if isinstance(member_id, str):
                names[member_id] = name
                continue
            for key in ("open_id", "user_id", "union_id"):
                if member_id.get(key):
                    names[member_id[key]] = name
        if stats is not None:
            stats["member_total"] = data.get("member_total") or 0
            stats["loaded"] = len(names)
            stats["has_more"] = bool(data.get("has_more"))
        next_page = data.get("page_token") or ""
        if not data.get("has_more") or not next_page or next_page in seen_pages:
            break
        seen_pages.add(next_page)
        page = next_page
    return names


def _sender_name(sender, member_names):
    sender_type = sender.get("sender_type") or ""
    sender_id = sender.get("id") or ""
    if sender_type == "user":
        return member_names.get(sender_id) or sender.get("name") or sender_id or "未知发送人"
    if sender_type == "app":
        return sender.get("name") or "机器人"
    if sender_type:
        return sender.get("name") or sender_type
    return "系统消息"


def _user_profile(token, user_id, id_type="open_id"):
    cache_key = (token, user_id, id_type)
    if cache_key in _PROFILE_CACHE:
        return _PROFILE_CACHE[cache_key]
    query = urllib.parse.urlencode({"user_id_type": id_type or "open_id"})
    try:
        user = _get(f"{BASE}/contact/v3/users/{user_id}?{query}", token).get("data", {}).get("user", {})
        avatar = user.get("avatar") or {}
        profile = {
            "name": user.get("name") or user.get("nickname") or "",
            "avatar_url": (user.get("avatar_url") or avatar.get("avatar_72")
                           or avatar.get("avatar_240") or avatar.get("avatar_origin") or ""),
        }
    except Exception as exc:
        message = str(exc)
        if "99991672" in message:
            raise FeishuPermissionError(
                "缺少通讯录权限，无法读取真实姓名和头像；请开通 "
                "contact:user.base:readonly 后重新同步。") from exc
        if "41050" in message:
            raise FeishuScopeError(
                "飞书返回 41050：当前账号的组织架构可见范围不包含该用户；"
                "需由企业管理员调整「安全 → 成员权限 → 组织架构可见范围」。") from exc
        return {"name": "", "avatar_url": ""}
    _PROFILE_CACHE[cache_key] = profile
    return profile


def _bot_profile(token):
    cache_key = (token, "__bot__", "")
    if cache_key in _PROFILE_CACHE:
        return _PROFILE_CACHE[cache_key]
    try:
        bot = _get(f"{BASE}/bot/v3/info", token).get("bot", {})
        profile = {"name": bot.get("app_name") or "机器人",
                   "avatar_url": bot.get("avatar_url") or "",
                   "open_id": bot.get("open_id") or ""}
    except Exception:
        profile = {"name": "机器人", "avatar_url": "", "open_id": ""}
    _PROFILE_CACHE[cache_key] = profile
    return profile


def fetch_conversation(creds, conv_key, conv_title, warnings=None, keywords=None, known_names=None,
                       member_stats=None):
    """拉取最近 500 条中的 @、重要、待办、通知、日程和关键词消息（只读）。"""
    wanted_keywords = tuple(dict.fromkeys(
        str(keyword).strip().casefold() for keyword in (keywords or []) if str(keyword).strip()))
    token = _token(creds)
    items, page = [], None
    while len(items) < 500:
        query = {
            "container_id_type": "chat", "container_id": conv_key,
            "page_size": 50, "sort_type": "ByCreateTimeDesc",
        }
        if page:
            query["page_token"] = page
        data = _get(f"{BASE}/im/v1/messages?{urllib.parse.urlencode(query)}", token).get("data", {})
        items.extend(data.get("items") or [])
        if not data.get("has_more") or len(items) >= 500:
            break
        page = data.get("page_token")
    items = items[:500]
    try:
        member_names = _member_names(token, conv_key, member_stats)
        if member_stats is not None:
            member_stats["identity"] = "user" if creds.get("user_access_token") else "bot"
    except Exception as exc:
        member_names = {}
        if warnings is not None:
            warnings.append(f"{conv_title}：无法读取群成员名单，部分昵称可能无法显示（{exc}）")
    if (warnings is not None and member_stats and member_stats.get("member_total", 0) >
            member_stats.get("loaded", 0) and not member_stats.get("has_more")):
        warnings.append(
            f"{conv_title}：飞书仅返回 {member_stats['loaded']}/{member_stats['member_total']} "
            "个群成员且未提供后续分页，部分昵称无法自动同步")

    mention_names = {}
    prepared = []
    wanted_sender_ids = set()
    for item in items:
        body = item.get("body") or {}
        msg_type = item.get("msg_type") or body.get("msg_type")
        text = _text_of(body.get("content"), msg_type)
        mentions = item.get("mentions") or []
        if not text:
            if not mentions:
                continue
            text = " ".join(f"@{m.get('name')}" if m.get("name") else "@用户"
                            for m in mentions)
        for mention in mentions:
            mention_id = mention.get("id")
            mention_name = mention.get("name")
            if mention_id and mention_name:
                mention_names[mention_id] = mention_name
        sender_data = item.get("sender") or {}
        is_user = sender_data.get("sender_type") == "user"
        sender_id = (sender_data.get("id") or "") if is_user else ""
        sender_guess = (member_names.get(sender_id) or mention_names.get(sender_id)
                        or sender_data.get("name") or "")
        grp = triage.classify(text, sender_guess)
        if any(keyword in text.casefold() for keyword in wanted_keywords):
            grp = "important"
        elif mentions and grp == "chatter":
            grp = "important"
        if grp == "chatter":
            continue
        display_text = _display_text(text, mentions)
        prepared.append((item, display_text, sender_data, is_user, sender_id, grp))
        if is_user and sender_id:
            wanted_sender_ids.add(sender_id)

    member_names.update(mention_names)
    if known_names is not None:
        known_names.update(member_names)
    profiles = {}
    profile_blocked = False
    scope_warned = False
    for sender_id in wanted_sender_ids:
        if profile_blocked:
            break
        try:
            profile = _user_profile(token, sender_id, "open_id")
        except FeishuScopeError as exc:
            if warnings is not None and not scope_warned:
                warnings.append(str(exc))
                scope_warned = True
            continue
        except FeishuPermissionError as exc:
            profile_blocked = True
            if warnings is not None:
                warnings.append(str(exc))
            continue
        profiles[sender_id] = profile
        if profile["name"]:
            member_names.setdefault(sender_id, profile["name"])

    bot_profile = _bot_profile(token)
    out = []
    for item, text, sender_data, is_user, sender_id, grp in prepared:
        ts_ms = int(item.get("create_time") or time.time() * 1000)
        ts = datetime.datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M")
        sender = _sender_name(sender_data, member_names)
        sender_avatar = profiles.get(sender_id, {}).get("avatar_url", "")
        if not is_user and sender_data.get("sender_type") == "app":
            sender = bot_profile["name"]
            sender_id = bot_profile["open_id"]
            sender_avatar = bot_profile["avatar_url"]
        out.append({"sender": sender, "sender_id": sender_id,
                    "sender_avatar": sender_avatar, "grp": grp,
                    "ts": ts, "text": text.strip()[:1500],
                    "dedup": f"feishu:{item.get('message_id', '')}"})
    out.reverse()
    return out
