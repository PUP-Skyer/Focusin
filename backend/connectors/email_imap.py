# -*- coding: utf-8 -*-
"""邮箱连接器：标准 IMAP over SSL（QQ邮箱/163/Gmail/Outlook 通用）。
只读模式（readonly=True），只拉取订阅清单里的文件夹、最近 14 天、每夹最近 50 封。"""
import base64
import datetime
import email
import email.utils
import imaplib
import re

IMAP_PRESETS = {}  # host → default port


def _mutf7_decode(raw: bytes) -> str:
    """IMAP 文件夹名的 modified UTF-7 解码（中文文件夹支持）。"""
    s = raw.decode("ascii", "replace")
    out, i = [], 0
    while i < len(s):
        if s[i] == "&":
            j = s.find("-", i)
            if j == -1:
                out.append(s[i:])
                break
            chunk = s[i + 1:j]
            if chunk == "":
                out.append("&")
            else:
                b64 = (chunk + "===").encode("ascii")
                out.append(base64.b64decode(b64).decode("utf-16-be", "replace"))
            i = j + 1
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _parse_list_line(line):
    """从 LIST 响应行提取原始文件夹名（ascii-safe）。"""
    if not line:
        return None
    m = re.match(rb'\((?P<flags>[^)]*)\)\s+(?P<delim>"[^"]*"|\S+)\s+(?P<name>.+)$', line)
    if not m:
        return None
    name = m.group("name").strip()
    if name.startswith(b'"') and name.endswith(b'"'):
        name = name[1:-1].replace(b'\\"', b'"').replace(b"\\\\", b"\\")
    return name


def _connect(creds):
    host = creds.get("host", "").strip()
    port = int(creds.get("port") or 993)
    return imaplib.IMAP4_SSL(host, port, timeout=20)


def test(creds):
    with _connect(creds) as m:
        m.login(creds["username"], creds["password"])
        m.logout()
    return {"ok": True, "note": "IMAP 登录成功"}


def discover(creds):
    """返回邮箱文件夹元数据（不取信件内容）。"""
    with _connect(creds) as m:
        m.login(creds["username"], creds["password"])
        typ, data = m.list()
    convs = []
    for line in data or []:
        raw = _parse_list_line(line)
        if raw is None:
            continue
        title = _mutf7_decode(raw)
        # 跳过服务端垃圾/草稿文件夹，减少噪音；订阅页仍可见全部文件夹
        convs.append({"conv_key": raw.decode("ascii", "replace"), "conv_title": title})
    return convs


def _body_text(msg, limit=1500):
    parts = []
    if msg.is_multipart():
        for p in msg.walk():
            if p.get_content_type() == "text/plain" and not p.get_filename():
                parts.append(p)
        part = parts[0] if parts else None
    else:
        part = msg if msg.get_content_type() == "text/plain" else None
    if part is None:
        return ""
    payload = part.get_payload(decode=True) or b""
    charset = part.get_content_charset() or "utf-8"
    try:
        text = payload.decode(charset, "replace")
    except (LookupError, UnicodeDecodeError):
        text = payload.decode("gbk", "replace")
    return text.strip()[:limit]


def fetch_conversation(creds, conv_key, conv_title):
    """拉取单个已订阅文件夹最近 14 天的信件（最多 50 封）。"""
    quoted = '"' + conv_key.replace("\\", "\\\\").replace('"', '\\"') + '"'
    since = (datetime.date.today() - datetime.timedelta(days=14)
             ).strftime("%d-%b-%Y")
    out = []
    with _connect(creds) as m:
        m.login(creds["username"], creds["password"])
        typ, _ = m.select(quoted.encode("ascii", "replace"), readonly=True)
        if typ != "OK":
            return out
        typ, data = m.search(None, f"SINCE {since}")
        if typ != "OK":
            return out
        uids = (data[0] or b"").split()[-50:]
        for uid in uids:
            typ, msg_data = m.uid("FETCH", uid, "(BODY.PEEK[])")
            if typ != "OK":
                continue
            raw = b"".join(x[1] for x in msg_data if isinstance(x, tuple))
            try:
                msg = email.message_from_bytes(raw)
            except Exception:  # noqa: BLE001
                continue
            subject = str(msg.get("Subject", "(无主题)")).strip()
            display, addr = email.utils.parseaddr(str(msg.get("From", "")))
            sender = display or addr or "(未知发件人)"
            dt = email.utils.parsedate_to_datetime(msg.get("Date", "")) \
                if msg.get("Date") else None
            ts = dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else ""
            body = _body_text(msg)
            text = f"{subject}\n{body}".strip()
            if not text:
                continue
            out.append({"sender": sender, "ts": ts or datetime.datetime.now()
                        .strftime("%Y-%m-%d %H:%M"), "text": text,
                        "dedup": f"imap:{creds.get('host')}:{creds.get('username')}"
                                 f":{conv_key}:{uid.decode()}"})
        m.close()
    return out
