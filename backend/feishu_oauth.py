import json
import time
import urllib.error
import urllib.parse
import urllib.request

import db
import secure_store

AUTHORIZE_URL = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
TOKEN_URL = "https://accounts.feishu.cn/oauth/v3/token"
USER_INFO_URL = "https://open.feishu.cn/open-apis/authen/v1/user_info"
SETTINGS_KEY = "oauth:feishu"
SCOPES = (
    "im:chat:readonly",
    "im:chat.members:read",
    "im:message:readonly",
    "im:message.group_msg",
    "im:message.group_msg:get_as_user",
    "contact:contact.base:readonly",
    "contact:user.base:readonly",
)


def _post_form(url, payload):
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            error = json.loads(exc.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            error = {}
        message = error.get("error_description") or error.get("msg") or str(exc)
        raise RuntimeError(message) from exc


def _get_user_info(access_token):
    request = urllib.request.Request(
        USER_INFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read())
    if payload.get("code", 0) != 0:
        raise RuntimeError(payload.get("msg") or "获取飞书用户信息失败")
    return payload.get("data") or {}


def build_authorize_url(app_id, redirect_uri, state):
    query = urllib.parse.urlencode({
        "client_id": app_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(SCOPES),
        "state": state,
        "prompt": "consent",
    })
    return f"{AUTHORIZE_URL}?{query}"


def exchange_code(creds, code, redirect_uri):
    payload = _post_form(TOKEN_URL, {
        "grant_type": "authorization_code",
        "client_id": creds["app_id"],
        "client_secret": creds["app_secret"],
        "code": code,
        "redirect_uri": redirect_uri,
    })
    if payload.get("code", 0) != 0 or not payload.get("access_token"):
        raise RuntimeError(payload.get("error_description") or payload.get("msg") or "授权失败")
    return payload


def _refresh(creds, refresh_token):
    payload = _post_form(TOKEN_URL, {
        "grant_type": "refresh_token",
        "client_id": creds["app_id"],
        "client_secret": creds["app_secret"],
        "refresh_token": refresh_token,
    })
    if payload.get("code", 0) != 0 or not payload.get("access_token"):
        raise RuntimeError(payload.get("error_description") or payload.get("msg") or "刷新授权失败")
    return payload


def _save(creds, token_payload, user=None):
    now = int(time.time())
    session = {
        "app_id": creds["app_id"],
        "access_token": secure_store.protect_text(token_payload["access_token"]),
        "refresh_token": "",
        "expires_at": now + int(token_payload.get("expires_in") or 7200),
        "refresh_expires_at": 0,
        "scope": token_payload.get("scope") or "",
        "user": user or {},
        "updated_at": now,
    }
    if token_payload.get("refresh_token"):
        session["refresh_token"] = secure_store.protect_text(token_payload["refresh_token"])
        session["refresh_expires_at"] = now + int(token_payload.get("refresh_token_expires_in") or 0)
    db.set_setting(SETTINGS_KEY, json.dumps(session, ensure_ascii=False))


def authorize(creds, code, redirect_uri):
    token_payload = exchange_code(creds, code, redirect_uri)
    user = _get_user_info(token_payload["access_token"])
    _save(creds, token_payload, user)
    return user


def load():
    raw = db.get_setting(SETTINGS_KEY, "")
    if not raw:
        return None
    try:
        session = json.loads(raw)
        if session.get("access_token"):
            session["access_token"] = secure_store.unprotect_text(session["access_token"])
        if session.get("refresh_token"):
            session["refresh_token"] = secure_store.unprotect_text(session["refresh_token"])
        return session
    except (ValueError, TypeError, RuntimeError, OSError):
        return None


def clear():
    db.ex("DELETE FROM settings WHERE key=?", (SETTINGS_KEY,))


def get_access_token(creds):
    session = load()
    if not session or session.get("app_id") != creds.get("app_id"):
        return ""
    now = int(time.time())
    if int(session.get("expires_at") or 0) > now + 60:
        return session.get("access_token") or ""
    refresh_token = session.get("refresh_token") or ""
    if not refresh_token or int(session.get("refresh_expires_at") or 0) <= now:
        return ""
    try:
        token_payload = _refresh(creds, refresh_token)
        user = session.get("user") or {}
        _save(creds, token_payload, user)
        return token_payload["access_token"]
    except RuntimeError:
        return ""


def status(creds):
    session = load()
    if not session or session.get("app_id") != creds.get("app_id"):
        return {"authorized": False, "user": None}
    now = int(time.time())
    access_token = get_access_token(creds)
    user = session.get("user") or {}
    return {
        "authorized": bool(access_token),
        "expired": not bool(access_token),
        "expires_at": int(session.get("expires_at") or 0),
        "scope": session.get("scope") or "",
        "user": {
            "name": user.get("name") or "",
            "avatar_url": user.get("avatar_url") or user.get("avatar_middle") or "",
            "open_id": user.get("open_id") or "",
            "tenant_key": user.get("tenant_key") or "",
        },
    }
