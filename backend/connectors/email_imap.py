# -*- coding: utf-8 -*-
"""邮箱连接器：标准 IMAP over SSL（QQ邮箱/163/Gmail/Outlook 通用）。
只读模式（readonly=True），只拉取订阅清单里的文件夹、最近 14 天、每夹最近 50 封。"""
import base64
import datetime
import email
import email.header
import email.utils
import hashlib
import html
import imaplib
import os
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

BASE = os.path.dirname(os.path.abspath(__file__))
ATTACHMENT_DIR = os.path.join(BASE, "data", "attachments")

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


def _decode_header(value):
    if not value:
        return ""
    try:
        return str(email.header.make_header(email.header.decode_header(str(value))))
    except (LookupError, UnicodeDecodeError, ValueError):
        return str(value)


class _HTMLContent(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.text = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ("script", "style"):
            self.skip += 1
        elif tag == "a" and not self.skip:
            href = (dict(attrs).get("href") or "").strip()
            if href:
                self.links.append(href)
        elif tag == "br" and not self.skip:
            self.text.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        elif tag in ("p", "div", "li", "tr", "h1", "h2", "h3", "h4") and not self.skip:
            self.text.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)


def _part_text(part):
    payload = part.get_payload(decode=True) or b""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, "replace")
    except (LookupError, UnicodeDecodeError):
        return payload.decode("gb18030", "replace")


def _extract_links(values):
    links = []
    seen = set()
    for value in values:
        value = html.unescape(value or "")
        for match in re.findall(r"(?:https?://|mailto:)[^\s<>\"']+", value, re.I):
            url = match.strip().rstrip(".,;:!?，。；：！？、)]}）】》」』")
            try:
                scheme = urlsplit(url).scheme.lower()
            except ValueError:
                continue
            if scheme not in ("http", "https", "mailto") or url in seen:
                continue
            seen.add(url)
            links.append(url)
    return links


def _message_content(msg, limit=1500):
    plain, html_links, html_text = [], [], []
    for part in msg.walk():
        if part.get_filename() or part.is_multipart():
            continue
        content_type = part.get_content_type()
        if content_type == "text/plain":
            plain.append(_part_text(part))
        elif content_type == "text/html":
            raw = _part_text(part)
            parser = _HTMLContent()
            parser.feed(raw)
            html_links.extend(parser.links)
            html_text.append("".join(parser.text))
    body = "\n".join(plain).strip()
    if not body and html_text:
        body = re.sub(r"[ \t]+", " ", "\n".join(html_text))
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
    links = _extract_links(plain + html_text + html_links)
    return body[:limit], links


def _safe_filename(value):
    name = _decode_header(value).replace("\x00", "").strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name or "附件"


def _save_attachments(msg):
    attachments = []
    for part in msg.walk():
        filename = part.get_filename()
        if not filename and part.get_content_disposition() != "attachment":
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        storage_key = hashlib.sha256(payload).hexdigest()
        os.makedirs(ATTACHMENT_DIR, exist_ok=True)
        path = os.path.join(ATTACHMENT_DIR, storage_key)
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(payload)
        attachments.append({
            "filename": _safe_filename(filename),
            "mime": part.get_content_type() or "application/octet-stream",
            "size": len(payload),
            "storage_key": storage_key,
        })
    return attachments


def fetch_conversation(creds, conv_key, conv_title):
    """拉取单个已订阅文件夹最近 200 封信。"""
    quoted = '"' + conv_key.replace("\\", "\\\\").replace('"', '\\"') + '"'
    out = []
    with _connect(creds) as m:
        m.login(creds["username"], creds["password"])
        typ, _ = m.select(quoted.encode("ascii", "replace"), readonly=True)
        if typ != "OK":
            return out
        typ, data = m.uid("SEARCH", None, "ALL")
        if typ != "OK":
            return out
        uids = (data[0] or b"").split()[-200:]
        for uid in uids:
            typ, msg_data = m.uid("FETCH", uid, "(BODY.PEEK[])")
            if typ != "OK":
                continue
            raw = b"".join(x[1] for x in msg_data if isinstance(x, tuple))
            try:
                msg = email.message_from_bytes(raw)
            except Exception:  # noqa: BLE001
                continue
            subject = _decode_header(msg.get("Subject", "(无主题)")).strip()
            display, addr = email.utils.parseaddr(_decode_header(msg.get("From", "")))
            sender = _decode_header(display).strip() or addr or "(未知发件人)"
            dt = email.utils.parsedate_to_datetime(msg.get("Date", "")) \
                if msg.get("Date") else None
            ts = dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else ""
            body, links = _message_content(msg)
            attachments = _save_attachments(msg)
            text = f"{subject}\n{body}".strip()
            if not text:
                continue
            out.append({"sender": sender, "sender_id": addr, "ts": ts or datetime.datetime.now()
                        .strftime("%Y-%m-%d %H:%M"), "text": text,
                        "links": links, "attachments": attachments,
                        "dedup": f"imap:{creds.get('host')}:{creds.get('username')}"
                                 f":{conv_key}:{uid.decode()}"})
        m.close()
    return out
