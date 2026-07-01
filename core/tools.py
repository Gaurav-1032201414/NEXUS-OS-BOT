"""
core/tools.py
Defines every action NEXUS can take, in the JSON schema format Ollama/OpenAI
expect for function calling. Each tool maps a name → (schema, python callable).
The agent picks a tool by name; we dispatch to the matching function.
"""
import json
import logging

from os_control import (
    file_ops, process_manager, screen_control, clipboard, system_info,
)
from os_control.platform_layer import get_platform

logger = logging.getLogger("nexus.tools")


# ──────────────────────────────────────────────────────────
# Tool implementations — each takes **kwargs, returns a string
# ──────────────────────────────────────────────────────────

def _t_create_file(path, content="", **_):
    return file_ops.create_file(path, content)

def _t_read_file(path, **_):
    return file_ops.read_file(path)

def _t_append_file(path, content, **_):
    return file_ops.append_file(path, content)

def _t_delete_file(path, **_):
    return file_ops.delete_file(path)

def _t_move_file(src, dst, **_):
    return file_ops.move_file(src, dst)

def _t_copy_file(src, dst, **_):
    return file_ops.copy_file(src, dst)

def _t_list_dir(path=".", **_):
    return file_ops.list_dir(path)

def _t_make_directory(path, **_):
    return file_ops.make_directory(path)

def _t_search_files(directory, pattern, **_):
    return file_ops.search_files(directory, pattern)

def _t_file_info(path, **_):
    return file_ops.file_info(path)

def _t_list_processes(limit=20, sort_by="memory", **_):
    return process_manager.list_processes(limit, sort_by)

def _t_find_process(name, **_):
    return process_manager.find_process(name)

def _t_kill_process(identifier, **_):
    return process_manager.kill_process(str(identifier))

def _t_launch_app(app_name, **_):
    return process_manager.launch_app(app_name)

def _t_open_url(url, **_):
    return get_platform().open_url(url)

def _t_open_file_default(path, **_):
    return get_platform().open_file(path)

def _t_set_volume(level, **_):
    return get_platform().set_volume(level)

def _t_set_brightness(level, **_):
    return get_platform().set_brightness(level)

def _t_notify(title, message, **_):
    return get_platform().notify(title, message)

def _t_list_windows(**_):
    return "\n".join(get_platform().list_windows())

def _t_focus_window(title, **_):
    return get_platform().focus_window(title)

def _t_lock_screen(**_):
    return get_platform().lock_screen()

def _t_screenshot(**_):
    return screen_control.screenshot()

def _t_click(x, y, button="left", **_):
    return screen_control.click_at(x, y, button)

def _t_type_text(text, **_):
    return screen_control.type_text(text)

def _t_press_key(key, **_):
    return screen_control.press_key(key)

def _t_hotkey(keys, **_):
    parts = keys if isinstance(keys, list) else str(keys).split("+")
    return screen_control.hotkey(*parts)

def _t_get_clipboard(**_):
    return clipboard.get_clipboard()

def _t_set_clipboard(text, **_):
    return clipboard.set_clipboard(text)

def _t_system_info(**_):
    return system_info.summary_text()

def _t_top_processes(n=5, **_):
    procs = system_info.top_processes(n)
    return json.dumps(procs, indent=2)


# ──────────────────────────────────────────────────────────
# Tool registry: name → {"fn": callable, "schema": {...}}
# Schema follows the OpenAI/Ollama function-calling format.
# ──────────────────────────────────────────────────────────

def _schema(name, description, properties=None, required=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }


_STR = {"type": "string"}
_INT = {"type": "integer"}


REGISTRY = {
    # ── File operations ──
    "create_file": {"fn": _t_create_file, "schema": _schema(
        "create_file", "Create a new file with optional text content.",
        {"path": _STR, "content": _STR}, ["path"])},
    "read_file": {"fn": _t_read_file, "schema": _schema(
        "read_file", "Read and return the contents of a text file.",
        {"path": _STR}, ["path"])},
    "append_file": {"fn": _t_append_file, "schema": _schema(
        "append_file", "Append text to the end of an existing file.",
        {"path": _STR, "content": _STR}, ["path", "content"])},
    "delete_file": {"fn": _t_delete_file, "schema": _schema(
        "delete_file", "Delete a file (not a directory).",
        {"path": _STR}, ["path"])},
    "move_file": {"fn": _t_move_file, "schema": _schema(
        "move_file", "Move or rename a file.",
        {"src": _STR, "dst": _STR}, ["src", "dst"])},
    "copy_file": {"fn": _t_copy_file, "schema": _schema(
        "copy_file", "Copy a file or directory to a new location.",
        {"src": _STR, "dst": _STR}, ["src", "dst"])},
    "list_dir": {"fn": _t_list_dir, "schema": _schema(
        "list_dir", "List the contents of a directory.",
        {"path": _STR})},
    "make_directory": {"fn": _t_make_directory, "schema": _schema(
        "make_directory", "Create a new directory (and parents).",
        {"path": _STR}, ["path"])},
    "search_files": {"fn": _t_search_files, "schema": _schema(
        "search_files", "Recursively search for files matching a glob pattern.",
        {"directory": _STR, "pattern": _STR}, ["directory", "pattern"])},
    "file_info": {"fn": _t_file_info, "schema": _schema(
        "file_info", "Get size, type, and modified time of a file or directory.",
        {"path": _STR}, ["path"])},

    # ── Process management ──
    "list_processes": {"fn": _t_list_processes, "schema": _schema(
        "list_processes", "List running processes sorted by memory or cpu.",
        {"limit": _INT, "sort_by": {"type": "string", "enum": ["memory", "cpu"]}})},
    "find_process": {"fn": _t_find_process, "schema": _schema(
        "find_process", "Find running processes by name.",
        {"name": _STR}, ["name"])},
    "kill_process": {"fn": _t_kill_process, "schema": _schema(
        "kill_process", "Terminate a process by PID or name.",
        {"identifier": _STR}, ["identifier"])},
    "launch_app": {"fn": _t_launch_app, "schema": _schema(
        "launch_app", "Launch a GUI application by name.",
        {"app_name": _STR}, ["app_name"])},

    # ── System / desktop ──
    "open_url": {"fn": _t_open_url, "schema": _schema(
        "open_url", "Open a URL in the default web browser.",
        {"url": _STR}, ["url"])},
    "open_file_default": {"fn": _t_open_file_default, "schema": _schema(
        "open_file_default", "Open a file with its default application.",
        {"path": _STR}, ["path"])},
    "set_volume": {"fn": _t_set_volume, "schema": _schema(
        "set_volume", "Set system audio volume (0-100).",
        {"level": _INT}, ["level"])},
    "set_brightness": {"fn": _t_set_brightness, "schema": _schema(
        "set_brightness", "Set screen brightness (0-100).",
        {"level": _INT}, ["level"])},
    "notify": {"fn": _t_notify, "schema": _schema(
        "notify", "Show a desktop notification.",
        {"title": _STR, "message": _STR}, ["title", "message"])},
    "list_windows": {"fn": _t_list_windows, "schema": _schema(
        "list_windows", "List titles of all open windows.")},
    "focus_window": {"fn": _t_focus_window, "schema": _schema(
        "focus_window", "Bring a window to the foreground by title.",
        {"title": _STR}, ["title"])},
    "lock_screen": {"fn": _t_lock_screen, "schema": _schema(
        "lock_screen", "Lock the screen.")},

    # ── Screen / input ──
    "screenshot": {"fn": _t_screenshot, "schema": _schema(
        "screenshot", "Capture a screenshot of the full screen.")},
    "click": {"fn": _t_click, "schema": _schema(
        "click", "Click the mouse at screen coordinates.",
        {"x": _INT, "y": _INT, "button": {"type": "string", "enum": ["left", "right", "middle"]}},
        ["x", "y"])},
    "type_text": {"fn": _t_type_text, "schema": _schema(
        "type_text", "Type text using simulated keyboard input.",
        {"text": _STR}, ["text"])},
    "press_key": {"fn": _t_press_key, "schema": _schema(
        "press_key", "Press a single key (e.g. enter, esc, tab).",
        {"key": _STR}, ["key"])},
    "hotkey": {"fn": _t_hotkey, "schema": _schema(
        "hotkey", "Press a key combination, e.g. 'ctrl+c'.",
        {"keys": _STR}, ["keys"])},

    # ── Clipboard ──
    "get_clipboard": {"fn": _t_get_clipboard, "schema": _schema(
        "get_clipboard", "Read the current clipboard contents.")},
    "set_clipboard": {"fn": _t_set_clipboard, "schema": _schema(
        "set_clipboard", "Write text to the clipboard.",
        {"text": _STR}, ["text"])},

    # ── Info ──
    "system_info": {"fn": _t_system_info, "schema": _schema(
        "system_info", "Get a summary of the host system (OS, CPU, RAM).")},
    "top_processes": {"fn": _t_top_processes, "schema": _schema(
        "top_processes", "Get the top N processes by memory usage.",
        {"n": _INT})},
}


def all_schemas() -> list[dict]:
    """Return the list of tool schemas for the LLM."""
    return [t["schema"] for t in REGISTRY.values()]


def dispatch(name: str, arguments: dict) -> str:
    """Execute a tool by name with the given arguments dict."""
    tool = REGISTRY.get(name)
    if not tool:
        return f"Unknown tool: '{name}'"
    try:
        logger.info(f"Executing tool: {name}({arguments})")
        return str(tool["fn"](**arguments))
    except TypeError as e:
        return f"Tool '{name}' called with wrong arguments: {e}"
    except Exception as e:
        logger.exception(f"Tool {name} crashed")
        return f"Tool '{name}' error: {e}"


def tool_names() -> list[str]:
    return list(REGISTRY.keys())


# ──────────────────────────────────────────────────────────
# Phase 3: Browser tools (registered lazily — one shared session)
# ──────────────────────────────────────────────────────────

_browser_instance = None

def _get_browser():
    global _browser_instance
    if _browser_instance is None:
        from browser.browser_agent import BrowserAgent
        from core.config import get_config
        cfg = get_config()
        _browser_instance = BrowserAgent(
            headless=cfg.get("browser.headless", False),
            timeout_ms=cfg.get("browser.timeout", 30000),
        )
    return _browser_instance

def _t_browse(url, **_):
    return _get_browser().navigate(url)

def _t_browser_text(max_chars=3000, **_):
    return _get_browser().get_text(max_chars)

def _t_browser_click(selector, **_):
    return _get_browser().click(selector)

def _t_browser_fill(selector, value, **_):
    return _get_browser().fill(selector, value)

def _t_browser_screenshot(**_):
    return _get_browser().screenshot()

def _t_web_search(query, **_):
    return _get_browser().search(query)

def _t_browser_close(**_):
    return _get_browser().close()


REGISTRY.update({
    "browse": {"fn": _t_browse, "schema": _schema(
        "browse", "Open a URL in an automated browser and report the page title.",
        {"url": _STR}, ["url"])},
    "browser_text": {"fn": _t_browser_text, "schema": _schema(
        "browser_text", "Extract the visible text from the currently open browser page.",
        {"max_chars": _INT})},
    "browser_click": {"fn": _t_browser_click, "schema": _schema(
        "browser_click", "Click an element on the page by CSS selector.",
        {"selector": _STR}, ["selector"])},
    "browser_fill": {"fn": _t_browser_fill, "schema": _schema(
        "browser_fill", "Fill a form field (by CSS selector) with text.",
        {"selector": _STR, "value": _STR}, ["selector", "value"])},
    "browser_screenshot": {"fn": _t_browser_screenshot, "schema": _schema(
        "browser_screenshot", "Take a screenshot of the current browser page.")},
    "web_search": {"fn": _t_web_search, "schema": _schema(
        "web_search", "Search the web (DuckDuckGo) and return result text.",
        {"query": _STR}, ["query"])},
    "browser_close": {"fn": _t_browser_close, "schema": _schema(
        "browser_close", "Close the automated browser session.")},
})


# ──────────────────────────────────────────────────────────
# Phase 5: Voice tools — let the agent speak proactively
# ──────────────────────────────────────────────────────────

def _t_speak(text, **_):
    from voice import tts
    return tts.speak(text)

def _t_voice_status(**_):
    from voice import voice_loop
    return str(voice_loop.diagnostics())


REGISTRY.update({
    "speak": {"fn": _t_speak, "schema": _schema(
        "speak", "Speak text aloud through the speakers using text-to-speech.",
        {"text": _STR}, ["text"])},
    "voice_status": {"fn": _t_voice_status, "schema": _schema(
        "voice_status", "Check whether speech input/output are available.")},
})


# ──────────────────────────────────────────────────────────
# Directory index tools — query the cached filesystem map
# ──────────────────────────────────────────────────────────

def _t_search_index(query, **_):
    from os_control import directory_index
    idx = directory_index.build_index(force=False)
    matches = directory_index.find(idx, query)
    if not matches:
        return (f"No cached matches for '{query}'. The index may be incomplete — "
                f"use search_files for a live filesystem search.")
    return f"Cached index matches for '{query}':\n" + "\n".join(f"  {m}" for m in matches)

def _t_rebuild_index(**_):
    from os_control import directory_index
    idx = directory_index.rebuild()
    return f"Directory index rebuilt: {idx.get('total_entries', 0)} entries indexed."

def _t_index_info(**_):
    from os_control import directory_index
    return directory_index.cache_info()


REGISTRY.update({
    "search_index": {"fn": _t_search_index, "schema": _schema(
        "search_index", "Search the cached directory index for files/folders by name. "
        "Fast, but may be incomplete — use search_files for an exhaustive live search.",
        {"query": _STR}, ["query"])},
    "rebuild_index": {"fn": _t_rebuild_index, "schema": _schema(
        "rebuild_index", "Re-scan the user's directories and rebuild the cached index. "
        "Use when files have changed since the last scan.")},
    "index_info": {"fn": _t_index_info, "schema": _schema(
        "index_info", "Report when the directory index was last built and its size.")},
})


# Watcher status tool — see what the last periodic scan detected
def _t_recent_changes(**_):
    # The agent holds the watcher; expose its last diff if available.
    try:
        from os_control import directory_index
        result = directory_index.refresh_if_changed()
        if not result["changed"]:
            return "No new files or directories since the last index update."
        lines = []
        if result["added"]:
            lines.append(f"Added ({len(result['added'])}): " + ", ".join(result["added"][:20]))
        if result["removed"]:
            lines.append(f"Removed ({len(result['removed'])}): " + ", ".join(result["removed"][:20]))
        return "\n".join(lines)
    except Exception as e:
        return f"Could not check recent changes: {e}"


REGISTRY.update({
    "recent_changes": {"fn": _t_recent_changes, "schema": _schema(
        "recent_changes", "Check for files/folders added or removed since the last "
        "directory index update, and refresh the index.")},
})
