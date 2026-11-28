import os
from pathlib import Path

import db

SENSITIVE_DIRS = {".ssh", ".aws", ".azure", ".gnupg", ".kube"}
SENSITIVE_FILES = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials", "credentials.json"}
SENSITIVE_SUFFIXES = {".pem", ".key", ".pfx", ".p12"}
SYSTEM_DIRS = {
    Path("C:/Windows"), Path("C:/Program Files"), Path("C:/Program Files (x86)"),
    Path("C:/ProgramData")
}


def _system_path(path):
    resolved = Path(path).resolve()
    return any(resolved == item or item in resolved.parents for item in SYSTEM_DIRS)


def grant_workspace(path, access="read"):
    access = "write" if access == "write" else "read"
    candidate = Path(str(path or "").strip()).expanduser()
    if not candidate.is_absolute():
        raise ValueError("请输入本地目录的绝对路径")
    resolved = candidate.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError("目录不存在或不是文件夹")
    if resolved == Path(resolved.anchor) or _system_path(resolved):
        raise ValueError("不允许授权系统根目录或系统目录")
    if _is_sensitive(resolved):
        raise ValueError("不允许授权密钥或凭据目录")
    name = resolved.name or str(resolved)
    db.ex("INSERT INTO workspaces(name,path,access,created_at,updated_at) VALUES(?,?,?,?,?) "
          "ON CONFLICT(path) DO UPDATE SET name=excluded.name, access=excluded.access, updated_at=excluded.updated_at",
          (name, str(resolved), access, db.now_iso(), db.now_iso()))
    return db.q("SELECT * FROM workspaces WHERE path=?", (str(resolved),))[0]


def list_workspaces():
    return db.q("SELECT * FROM workspaces ORDER BY updated_at DESC, id DESC")


def set_access(workspace_id, access):
    access = "write" if access == "write" else "read"
    db.ex("UPDATE workspaces SET access=?, updated_at=? WHERE id=?",
          (access, db.now_iso(), workspace_id))
    rows = db.q("SELECT * FROM workspaces WHERE id=?", (workspace_id,))
    return rows[0] if rows else None


def remove_workspace(workspace_id):
    db.ex("DELETE FROM workspaces WHERE id=?", (workspace_id,))


def describe_workspaces():
    rows = list_workspaces()
    if not rows:
        return "尚未授权本地工作区。"
    return "\n".join(
        f"- {row['name']}｜{row['path']}｜{'可编辑（写入仍需审批）' if row['access'] == 'write' else '只读'}"
        for row in rows
    )


def _is_sensitive(path):
    return any(part.lower() in SENSITIVE_DIRS for part in path.parts) or \
        any(part.lower() in SENSITIVE_FILES or part.lower().startswith(".env") or
            Path(part).suffix.lower() in SENSITIVE_SUFFIXES for part in path.parts)


def _within(path, root):
    try:
        return os.path.commonpath([str(path), str(root)]) == str(root)
    except ValueError:
        return False


def resolve_target(workspace_id, path, write=False):
    rows = db.q("SELECT * FROM workspaces WHERE id=?", (workspace_id,)) if workspace_id else list_workspaces()
    if not rows:
        raise ValueError("尚未授权本地工作区")
    requested = Path(str(path or "").strip()).expanduser()
    if requested.is_absolute():
        matches = [row for row in rows if _within(requested.resolve(), Path(row["path"]).resolve())]
        if not matches:
            raise ValueError("目标不在已授权的工作区内")
        row = matches[0]
        target = requested.resolve()
    else:
        if workspace_id:
            row = rows[0]
        elif len(rows) == 1:
            row = rows[0]
        else:
            raise ValueError("多个工作区下相对路径需要指定 workspace_id")
        target = (Path(row["path"]).resolve() / requested).resolve()
    root = Path(row["path"]).resolve()
    if not _within(target, root):
        raise ValueError("目标越过已授权目录边界")
    if write and row["access"] != "write":
        raise ValueError("该工作区仅授权只读")
    if _is_sensitive(target.relative_to(root)):
        raise ValueError("敏感文件默认禁止访问")
    return row, target


def list_directory(workspace_id, path="."):
    row, target = resolve_target(workspace_id, path)
    if not target.exists() or not target.is_dir():
        raise ValueError("目标不是可读取的目录")
    entries = []
    for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))[:100]:
        if _is_sensitive(child.relative_to(Path(row["path"]).resolve())):
            continue
        entries.append({"name": child.name, "type": "folder" if child.is_dir() else "file",
                        "size": child.stat().st_size if child.is_file() else None})
    return {"workspace": row["name"], "path": str(target), "entries": entries}


def read_text(workspace_id, path):
    row, target = resolve_target(workspace_id, path)
    if not target.exists() or not target.is_file():
        raise ValueError("文件不存在")
    if target.stat().st_size > 512 * 1024:
        raise ValueError("文件超过 512KB，请指定更小的文件")
    return {"workspace": row["name"], "path": str(target),
            "content": target.read_text(encoding="utf-8", errors="replace")}


def write_text(workspace_id, path, content):
    row, target = resolve_target(workspace_id, path, write=True)
    if len(str(content or "")) > 1024 * 1024:
        raise ValueError("单次写入内容超过 1MB")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(str(content or ""), encoding="utf-8")
    return {"workspace": row["name"], "path": str(target), "bytes": target.stat().st_size}
