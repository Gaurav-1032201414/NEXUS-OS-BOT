"""
os_control/file_ops.py
Safe file system operations. Every function returns a human-readable string
(success or error) so the agent can report back naturally.
Includes a safety guard against operating outside allowed roots.
"""
import os
import shutil
import logging
from pathlib import Path

logger = logging.getLogger("nexus.fileops")

# Directories the agent is allowed to touch destructively. Expand as you trust it.
# By default: user's home and /tmp. Reads are allowed anywhere.
_SAFE_ROOTS = [str(Path.home()), "/tmp", os.getcwd()]


def _expand(path: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(path))).resolve()


def _is_safe_write(path: Path) -> bool:
    sp = str(path)
    return any(sp.startswith(str(Path(root).resolve())) for root in _SAFE_ROOTS)


def create_file(path: str, content: str = "") -> str:
    p = _expand(path)
    if not _is_safe_write(p):
        return f"Refused: '{p}' is outside allowed directories ({_SAFE_ROOTS})"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Created file '{p}' ({len(content)} bytes)"
    except Exception as e:
        return f"Error creating file: {e}"


def read_file(path: str, max_bytes: int = 50_000) -> str:
    p = _expand(path)
    try:
        if not p.exists():
            return f"File not found: '{p}'"
        if p.stat().st_size > max_bytes:
            data = p.read_text(encoding="utf-8", errors="replace")[:max_bytes]
            return f"(truncated to {max_bytes} bytes)\n{data}"
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"


def append_file(path: str, content: str) -> str:
    p = _expand(path)
    if not _is_safe_write(p):
        return f"Refused: '{p}' is outside allowed directories"
    try:
        with open(p, "a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended {len(content)} bytes to '{p}'"
    except Exception as e:
        return f"Error appending: {e}"


def delete_file(path: str) -> str:
    p = _expand(path)
    if not _is_safe_write(p):
        return f"Refused: '{p}' is outside allowed directories"
    try:
        if p.is_dir():
            return f"'{p}' is a directory. Use delete_directory instead."
        if not p.exists():
            return f"File not found: '{p}'"
        p.unlink()
        return f"Deleted '{p}'"
    except Exception as e:
        return f"Error deleting: {e}"


def move_file(src: str, dst: str) -> str:
    sp, dp = _expand(src), _expand(dst)
    if not _is_safe_write(sp) or not _is_safe_write(dp):
        return "Refused: source or destination outside allowed directories"
    try:
        shutil.move(str(sp), str(dp))
        return f"Moved '{sp}' → '{dp}'"
    except Exception as e:
        return f"Error moving: {e}"


def copy_file(src: str, dst: str) -> str:
    sp, dp = _expand(src), _expand(dst)
    if not _is_safe_write(dp):
        return f"Refused: destination '{dp}' outside allowed directories"
    try:
        if sp.is_dir():
            shutil.copytree(str(sp), str(dp))
        else:
            shutil.copy2(str(sp), str(dp))
        return f"Copied '{sp}' → '{dp}'"
    except Exception as e:
        return f"Error copying: {e}"


def list_dir(path: str = ".") -> str:
    p = _expand(path)
    try:
        if not p.exists():
            return f"Directory not found: '{p}'"
        entries = []
        for item in sorted(p.iterdir()):
            kind = "DIR " if item.is_dir() else "FILE"
            size = "" if item.is_dir() else f" ({item.stat().st_size} B)"
            entries.append(f"  [{kind}] {item.name}{size}")
        if not entries:
            return f"'{p}' is empty"
        return f"Contents of '{p}':\n" + "\n".join(entries)
    except Exception as e:
        return f"Error listing: {e}"


def make_directory(path: str) -> str:
    p = _expand(path)
    if not _is_safe_write(p):
        return f"Refused: '{p}' outside allowed directories"
    try:
        p.mkdir(parents=True, exist_ok=True)
        return f"Created directory '{p}'"
    except Exception as e:
        return f"Error: {e}"


def search_files(directory: str, pattern: str, max_results: int = 50) -> str:
    p = _expand(directory)
    try:
        matches = list(p.rglob(pattern))[:max_results]
        if not matches:
            return f"No files matching '{pattern}' in '{p}'"
        return f"Found {len(matches)} match(es):\n" + "\n".join(f"  {m}" for m in matches)
    except Exception as e:
        return f"Error searching: {e}"


def file_info(path: str) -> str:
    p = _expand(path)
    try:
        if not p.exists():
            return f"Not found: '{p}'"
        st = p.stat()
        import datetime
        mod = datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
        return (f"'{p}'\n  Type: {'directory' if p.is_dir() else 'file'}\n"
                f"  Size: {st.st_size} bytes\n  Modified: {mod}\n"
                f"  Permissions: {oct(st.st_mode)[-3:]}")
    except Exception as e:
        return f"Error: {e}"
