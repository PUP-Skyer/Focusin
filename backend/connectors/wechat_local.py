import datetime
import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def _materials(creds):
    root = Path(str(creds.get("db_dir") or "").strip()).expanduser()
    key_path = Path(str(creds.get("key_path") or "").strip()).expanduser()
    if not root.is_dir():
        raise ValueError("请提供包含微信数据库副本的文件夹")
    if not key_path.is_file():
        raise ValueError("请提供已有的密钥文件")
    if str(creds.get("authorized", "")).lower() not in ("true", "yes", "on", "1"):
        raise ValueError("请先确认你有权读取这些数据")
    key = key_path.read_text(encoding="utf-8").strip()
    key = re.sub(r"^[xX]'([0-9a-fA-F]+)'$", r"\1", key)
    if not re.fullmatch(r"[0-9a-fA-F]{64}|[0-9a-fA-F]{96}", key):
        raise ValueError("密钥文件须包含 64 或 96 位十六进制 raw key")
    return root.resolve(), key


def _connect(path, key):
    try:
        import sqlcipher3 as driver
    except ImportError as exc:
        raise RuntimeError("缺少 sqlcipher3 依赖，请安装 requirements.txt 中的运行依赖") from exc
    uri = path.resolve().as_uri() + "?mode=ro&immutable=1"
    conn = driver.connect(uri, uri=True)
    conn.row_factory = driver.Row
    try:
        conn.execute(f"PRAGMA key=\"x'{key}'\"")
        conn.execute("PRAGMA query_only=ON")
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return conn
    except Exception:
        conn.close()
        raise


def _local_files(root, pattern):
    files = []
    for candidate in root.glob(pattern):
        resolved = candidate.resolve()
        if resolved.parent == root and resolved.is_file():
            files.append(resolved)
    return sorted(files, key=lambda p: p.name)


def _contact_index(root, key):
    contacts = {}
    files = _local_files(root, "contact.db")
    if not files:
        return contacts
    conn = _connect(files[0], key)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(contact)")}
        if "username" not in columns:
            return contacts
        projection = ", ".join(f'"{name}"' if name in columns else "''"
                               for name in ("username", "nick_name", "remark"))
        for row in conn.execute(f"SELECT {projection} FROM contact"):
            username = str(row["username"] or "")
            if username:
                contacts[username] = str(row["remark"] or row["nick_name"] or username)
    finally:
        conn.close()
    return contacts


def _decode_content(row):
    value = row["message_content"]
    if value in (None, "", b""):
        value = row["compress_content"]
    if value is None:
        return ""
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, bytes):
        try:
            compression = int(row["WCDB_CT_message_content"] or 0)
        except (TypeError, ValueError):
            compression = 0
        if compression == 4 or value.startswith(b"\x28\xb5\x2f\xfd"):
            try:
                import zstandard
                value = zstandard.ZstdDecompressor().decompress(value)
            except ImportError as exc:
                raise RuntimeError("读取压缩微信正文需要 zstandard 依赖") from exc
        text = value.decode("utf-8", "replace")
    else:
        text = str(value)
    text = text.replace("\x00", "").strip()
    if text.startswith("<"):
        try:
            text = "".join(ET.fromstring(text).itertext()).strip()
        except ET.ParseError:
            pass
    return re.sub(r"[ \t]+", " ", text)


def _message_projection(conn, table):
    columns = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
    required = {"local_id", "local_type", "real_sender_id", "create_time"}
    if required - columns:
        raise ValueError("微信消息表字段不兼容")
    if not ({"message_content", "compress_content"} & columns):
        raise ValueError("微信消息表缺少正文字段")
    return ", ".join(f'"{name}"' if name in columns else f"NULL AS \"{name}\""
                     for name in ("local_id", "server_id", "local_type", "real_sender_id",
                                  "create_time", "message_content", "compress_content",
                                  "WCDB_CT_message_content"))


def test(creds):
    root, key = _materials(creds)
    session = _local_files(root, "session.db")
    if not session:
        raise ValueError("数据库文件夹中缺少 session.db")
    conn = _connect(session[0], key)
    try:
        conn.execute("SELECT username FROM SessionTable LIMIT 1").fetchone()
    finally:
        conn.close()
    return {"ok": True, "note": "本地数据库只读验证成功；未访问微信进程"}


def discover(creds):
    root, key = _materials(creds)
    session = _local_files(root, "session.db")
    if not session:
        raise ValueError("数据库文件夹中缺少 session.db")
    contacts = _contact_index(root, key)
    conn = _connect(session[0], key)
    try:
        rows = conn.execute("SELECT username FROM SessionTable ORDER BY sort_timestamp DESC").fetchall()
    finally:
        conn.close()
    out = []
    seen = set()
    for row in rows:
        username = str(row["username"] or "").strip()
        if not username or username in seen:
            continue
        seen.add(username)
        out.append({"conv_key": username, "conv_title": contacts.get(username, username)})
    return out


def fetch_conversation(creds, conv_key, conv_title):
    root, key = _materials(creds)
    username = str(conv_key or "").strip()
    if not username:
        return []
    contacts = _contact_index(root, key)
    table = "Msg_" + hashlib.md5(username.encode("utf-8")).hexdigest()
    source_id = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
    rows = []
    for source in _local_files(root, "message_*.db"):
        conn = _connect(source, key)
        try:
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                                  (table,)).fetchone()
            if not exists:
                continue
            senders = {}
            try:
                senders = {int(row["rowid"]): str(row["user_name"])
                           for row in conn.execute("SELECT rowid, user_name FROM Name2Id")}
            except Exception as exc:
                if "no such table" not in str(exc).lower() and "no such column" not in str(exc).lower():
                    raise
            fields = _message_projection(conn, table)
            query = (f'SELECT {fields} FROM "{table}" WHERE local_type=1 '
                     "ORDER BY create_time DESC, local_id DESC LIMIT 200")
            for row in conn.execute(query):
                text = _decode_content(row)
                if not text:
                    continue
                sender_id = senders.get(int(row["real_sender_id"] or 0), "")
                sender = contacts.get(sender_id, sender_id or "(未知发送者)")
                created = int(row["create_time"] or 0)
                ts = (datetime.datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M")
                      if created else datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
                server_id = int(row["server_id"] or 0)
                identity = f"server:{server_id}" if server_id > 0 else f"local:{row['local_id']}"
                rows.append({
                    "sender": sender,
                    "ts": ts,
                    "text": text,
                    "dedup": f"wechat:{source_id}:{source.name}:{username}:{identity}",
                    "_sort": (created, int(row["local_id"] or 0)),
                })
        finally:
            conn.close()
    rows.sort(key=lambda item: item["_sort"])
    for row in rows:
        row.pop("_sort", None)
    return rows[-200:]
