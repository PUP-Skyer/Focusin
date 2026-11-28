import mimetypes
import re
import uuid
from pathlib import Path

import db

BASE = Path(__file__).resolve().parent / "uploads"
MAX_FILE_SIZE = 20 * 1024 * 1024
MAX_TOTAL_SIZE = 100 * 1024 * 1024
MAX_FILES = 200
TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".vue", ".json", ".csv",
    ".yaml", ".yml", ".toml", ".xml", ".html", ".css", ".log", ".ini", ".cfg"
}
SENSITIVE_NAMES = {".env", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
SENSITIVE_SUFFIXES = {".pem", ".key", ".pfx", ".p12"}


def _safe_session(session_id):
    value = re.sub(r"[^a-zA-Z0-9_-]", "", str(session_id or "legacy"))[:64]
    return value or "legacy"


def _safe_relative(filename):
    normalized = str(filename or "").replace("\\", "/")
    parts = [part for part in normalized.split("/") if part not in ("", ".", "..")]
    if not parts:
        raise ValueError("文件名无效")
    if any(":" in part or "\x00" in part for part in parts):
        raise ValueError("文件名包含无效字符")
    if any(part.lower() in SENSITIVE_NAMES or part.lower().startswith(".env") or
           Path(part).suffix.lower() in SENSITIVE_SUFFIXES for part in parts):
        return None
    return parts


def save_uploads(session_id, files):
    session_id = _safe_session(session_id)
    batch_id = uuid.uuid4().hex
    root = BASE / session_id / batch_id
    records = []
    skipped = 0
    total = 0

    for index, item in enumerate(files[:MAX_FILES]):
        filename, fileobj = item
        relative = _safe_relative(filename)
        if relative is None:
            skipped += 1
            continue
        fileobj.seek(0, 2)
        size = fileobj.tell()
        fileobj.seek(0)
        if size > MAX_FILE_SIZE:
            raise ValueError(f"文件 {relative[-1]} 超过 20MB")
        total += size
        if total > MAX_TOTAL_SIZE:
            raise ValueError("本次上传超过 100MB")
        target = root.joinpath(*relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as out:
            while True:
                chunk = fileobj.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        mime = getattr(fileobj, "content_type", "") or mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        kind = "folder" if len(relative) > 1 else "file"
        group_key = relative[0] if kind == "folder" else ""
        storage_key = target.relative_to(BASE).as_posix()
        db.ex("INSERT INTO chat_attachments(session_id,name,relative_path,mime,size,storage_key,kind,group_key,created_at) "
              "VALUES(?,?,?,?,?,?,?,?,?)",
              (session_id, relative[-1], "/".join(relative), mime, size, storage_key,
               kind, group_key, db.now_iso()))
        records.append(db.q("SELECT * FROM chat_attachments WHERE storage_key=?", (storage_key,))[0])

    if len(files) > MAX_FILES:
        skipped += len(files) - MAX_FILES
    return {"attachments": records, "skipped": skipped}


def _storage_path(storage_key):
    path = (BASE / storage_key).resolve()
    if BASE.resolve() not in path.parents:
        raise ValueError("附件路径无效")
    return path


def get_attachment(attachment_id, session_id):
    rows = db.q("SELECT * FROM chat_attachments WHERE id=? AND session_id=?",
                (attachment_id, session_id))
    return rows[0] if rows else None


def read_attachment_text(attachment_id, session_id, limit=4000):
    row = get_attachment(attachment_id, session_id)
    if not row:
        return "附件不存在或不属于当前会话。"
    path = _storage_path(row["storage_key"])
    if path.suffix.lower() not in TEXT_EXTENSIONS or row["size"] > 1024 * 1024:
        return f"已找到附件 {row['name']}（{row['size']} 字节），当前仅支持文本类文件内容读取。"
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:limit]


def build_context(attachment_ids, session_id, total_limit=12000):
    wanted = {int(value) for value in attachment_ids or [] if str(value).isdigit()}
    if not wanted:
        return ""
    rows = db.q("SELECT * FROM chat_attachments WHERE session_id=? ORDER BY id", (session_id,))
    chunks = []
    used = 0
    for row in rows:
        if row["id"] not in wanted:
            continue
        header = f"附件：{row['relative_path']}（{row['mime']}，{row['size']} 字节）"
        if row["size"] <= 1024 * 1024 and Path(row["name"]).suffix.lower() in TEXT_EXTENSIONS:
            content = read_attachment_text(row["id"], session_id, 4000)
            body = f"{header}\n{content}"
        else:
            body = header
        remaining = total_limit - used
        if remaining <= 0:
            break
        chunks.append(body[:remaining])
        used += len(chunks[-1])
    return "\n\n".join(chunks)


def delete_attachments(attachment_ids, session_id):
    wanted = {int(value) for value in attachment_ids or [] if str(value).isdigit()}
    rows = db.q("SELECT * FROM chat_attachments WHERE session_id=?", (session_id,))
    deleted = 0
    for row in rows:
        if row["id"] not in wanted:
            continue
        try:
            _storage_path(row["storage_key"]).unlink(missing_ok=True)
        except OSError:
            pass
        db.ex("DELETE FROM chat_attachments WHERE id=?", (row["id"],))
        deleted += 1
    return deleted
