"""
os_control/directory_index.py
Scans the user's important directories ONCE, builds a compact index, and caches
it to ~/.nexus/directory_index.json. Subsequent runs load the cache instantly.
Use rebuild() to force a fresh scan.

The index is deliberately compact (counts + top-level structure + notable files)
so it can be summarized into the agent's prompt without blowing up the context.
"""
import os
import json
import time
import logging
from pathlib import Path

logger = logging.getLogger("nexus.dirindex")

CACHE_PATH = Path(os.path.expanduser("~/.nexus/directory_index.json"))

# Directories worth indexing under the user's home. Skips noise like caches.
_DEFAULT_ROOTS = ["Desktop", "Documents", "Downloads", "Pictures",
                  "Music", "Videos", "Projects", "Code", "dev"]

# Folders to never descend into (noise / huge / irrelevant)
_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".cache",
    ".npm", ".cargo", "target", "dist", "build", ".mozilla", ".config",
    "snap", ".local", ".rustup", "site-packages", ".gradle", ".m2",
}

_MAX_DEPTH = 3          # how deep to recurse
_MAX_ENTRIES = 4000     # hard cap on indexed entries to keep it fast/compact


def _should_skip(name: str) -> bool:
    return name in _SKIP_DIRS or name.startswith(".")


def _scan_tree(root: Path, depth: int, counter: dict) -> dict:
    """Recursively build a compact tree. counter tracks the global entry cap."""
    node = {"dirs": {}, "files": [], "file_count": 0, "dir_count": 0}
    if depth > _MAX_DEPTH or counter["n"] >= _MAX_ENTRIES:
        return node
    try:
        entries = sorted(root.iterdir(), key=lambda p: p.name.lower())
    except (PermissionError, OSError):
        return node

    for entry in entries:
        if counter["n"] >= _MAX_ENTRIES:
            break
        try:
            if entry.is_dir():
                if _should_skip(entry.name):
                    continue
                node["dir_count"] += 1
                counter["n"] += 1
                node["dirs"][entry.name] = _scan_tree(entry, depth + 1, counter)
            elif entry.is_file():
                node["file_count"] += 1
                counter["n"] += 1
                # Only store filenames at shallow depths to stay compact
                if depth <= 1:
                    node["files"].append(entry.name)
        except (PermissionError, OSError):
            continue
    return node


def build_index(force: bool = False) -> dict:
    """Build (or load cached) directory index. Returns the index dict."""
    if CACHE_PATH.exists() and not force:
        try:
            data = json.loads(CACHE_PATH.read_text())
            logger.info(f"Loaded cached directory index ({data.get('total_entries', '?')} entries)")
            return data
        except Exception as e:
            logger.warning(f"Cache unreadable, rebuilding: {e}")

    index = scan_now()
    _write_cache(index)
    logger.info(f"Directory index built: {index['total_entries']} entries → {CACHE_PATH}")
    return index


def scan_now() -> dict:
    """Perform a fresh filesystem scan WITHOUT touching the cache. Returns the index."""
    home = Path.home()
    counter = {"n": 0}
    roots = {}

    for child in sorted(home.iterdir(), key=lambda p: p.name.lower()) if home.exists() else []:
        if counter["n"] >= _MAX_ENTRIES:
            break
        try:
            if child.is_dir() and not _should_skip(child.name):
                roots[child.name] = _scan_tree(child, 1, counter)
        except (PermissionError, OSError):
            continue

    return {
        "home": str(home),
        "scanned_at": time.time(),
        "total_entries": counter["n"],
        "roots": roots,
    }


def _write_cache(index: dict):
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(index, indent=2))
    except Exception as e:
        logger.warning(f"Could not write cache: {e}")


def _signature(index: dict) -> tuple:
    """
    A cheap fingerprint of the index structure (ignores scan timestamp).
    If two signatures match, nothing meaningful changed.
    """
    paths = set()

    def walk(node, prefix):
        for f in node.get("files", []):
            paths.add(f"{prefix}/{f}")
        for d, child in node.get("dirs", {}).items():
            dp = f"{prefix}/{d}"
            paths.add(dp + "/")
            walk(child, dp)

    for name, node in index.get("roots", {}).items():
        walk(node, name)
    return (index.get("total_entries", 0), frozenset(paths))


def diff(old: dict, new: dict) -> dict:
    """
    Compare two indexes and return what changed.
    Returns {"added": [...], "removed": [...], "changed": bool}.
    """
    def collect(index):
        paths = set()

        def walk(node, prefix):
            for f in node.get("files", []):
                paths.add(f"{prefix}/{f}")
            for d, child in node.get("dirs", {}).items():
                dp = f"{prefix}/{d}"
                paths.add(dp + "/")
                walk(child, dp)

        for name, node in index.get("roots", {}).items():
            walk(node, name)
        return paths

    old_paths = collect(old) if old else set()
    new_paths = collect(new) if new else set()
    added   = sorted(new_paths - old_paths)
    removed = sorted(old_paths - new_paths)
    return {
        "added":   added,
        "removed": removed,
        "changed": bool(added or removed),
    }


def refresh_if_changed() -> dict:
    """
    Scan now, compare to the cached index, and update the cache ONLY if something
    changed. Returns {"changed": bool, "added": [...], "removed": [...], "index": {...}}.
    This is what the background watcher calls on each interval.
    """
    old = {}
    if CACHE_PATH.exists():
        try:
            old = json.loads(CACHE_PATH.read_text())
        except Exception:
            old = {}

    new = scan_now()
    d = diff(old, new)

    if d["changed"] or not old:
        _write_cache(new)
        logger.info(
            f"Directory index updated: +{len(d['added'])} -{len(d['removed'])} "
            f"(total {new['total_entries']})"
        )
    return {**d, "index": new}


def rebuild() -> dict:
    """Force a fresh scan and overwrite the cache."""
    index = scan_now()
    _write_cache(index)
    logger.info(f"Directory index rebuilt: {index['total_entries']} entries")
    return index


def summarize(index: dict, max_chars: int = 1500) -> str:
    """
    Produce a compact text summary of the directory structure for the agent's
    system prompt. Lists top-level folders with their file/subfolder counts.
    """
    if not index or "roots" not in index:
        return "Directory index not available."

    lines = [f"User home: {index['home']}"]
    lines.append("Top-level directories (name: subdirs/files):")

    for name, node in sorted(index["roots"].items()):
        sub = ", ".join(sorted(node["dirs"].keys())[:8])
        sub_more = "…" if len(node["dirs"]) > 8 else ""
        lines.append(
            f"  ~/{name}/  ({node['dir_count']} dirs, {node['file_count']} files)"
            + (f" → {sub}{sub_more}" if sub else "")
        )

    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n  …(truncated)"
    return text


def find(index: dict, query: str, limit: int = 25) -> list[str]:
    """Search the cached index for paths matching a query substring."""
    q = query.lower()
    matches = []

    def walk(node, prefix):
        for fname in node.get("files", []):
            if q in fname.lower():
                matches.append(f"{prefix}/{fname}")
                if len(matches) >= limit:
                    return
        for dname, child in node.get("dirs", {}).items():
            dpath = f"{prefix}/{dname}"
            if q in dname.lower():
                matches.append(dpath + "/")
                if len(matches) >= limit:
                    return
            walk(child, dpath)
            if len(matches) >= limit:
                return

    home = index.get("home", "~")
    for name, node in index.get("roots", {}).items():
        walk(node, f"{home}/{name}")
        if len(matches) >= limit:
            break
    return matches


def cache_info() -> str:
    if not CACHE_PATH.exists():
        return "No directory index cached yet."
    try:
        data = json.loads(CACHE_PATH.read_text())
        import datetime
        when = datetime.datetime.fromtimestamp(data["scanned_at"]).isoformat(timespec="seconds")
        return f"Index: {data['total_entries']} entries, scanned {when}, cached at {CACHE_PATH}"
    except Exception as e:
        return f"Index cache error: {e}"
