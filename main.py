"""
main.py
CLI entrypoint for NEXUS. Run: python main.py
Provides an interactive REPL to talk to the agent and test all phases.
"""
import sys
import logging
import os
from pathlib import Path

# Make sure the project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import get_config
from core.agent import NexusAgent

# ── Logging setup ──
cfg = get_config()
log_file = Path(os.path.expanduser(cfg.get("logging.file", "~/.nexus/nexus.log")))
log_file.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, cfg.get("logging.level", "INFO")),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr) if "--verbose" in sys.argv else logging.NullHandler(),
    ],
)


def main():
    try:
        from rich.console import Console
        from rich.prompt import Prompt
        from rich.panel import Panel
        console = Console()
        rich = True
    except ImportError:
        console = None
        rich = False

    def out(text, style=""):
        if rich:
            console.print(text, style=style)
        else:
            print(text)

    out("\n[bold cyan]NEXUS OS Bot[/] — initializing...\n" if rich else "\nNEXUS OS Bot — initializing...\n")

    agent = NexusAgent()
    health = agent.health()

    if not health["ollama_alive"]:
        out("[bold red]⚠ Ollama is not running.[/]" if rich else "WARNING: Ollama is not running.")
        out("Start it with:  ollama serve" )
        out("Then pull a model:  ollama pull phi3:mini\n")
    else:
        models = ", ".join(health["available_models"]) or "none"
        out(f"Ollama: [green]online[/]  Models: {models}" if rich else f"Ollama: online  Models: {models}")
        out(f"Active model: [cyan]{health['router']['selected_model']}[/]" if rich else f"Active model: {health['router']['selected_model']}")

    out(f"Tools loaded: {health['tools_loaded']}")
    out("\nType your request, or 'exit' to quit. Try: 'what OS am I on?' or 'list my home directory'\n")

    session = "cli"
    try:
        while True:
            if rich:
                user = Prompt.ask("[bold green]You[/]")
            else:
                user = input("You: ")

            if user.strip().lower() in ("exit", "quit", "q"):
                break
            if not user.strip():
                continue
            if user.strip().lower() == "/health":
                out(str(agent.health()))
                continue
            if user.strip().lower() == "/reindex":
                from os_control import directory_index
                idx = directory_index.rebuild()
                agent.memory.set_fact("directory_summary", directory_index.summarize(idx))
                out(f"Directory index rebuilt: {idx.get('total_entries', 0)} entries")
                continue
            if user.strip().lower() == "/index":
                from os_control import directory_index
                out(directory_index.cache_info())
                continue

            reply = agent.chat(user, session=session)
            if rich:
                console.print(Panel(reply, title="NEXUS", border_style="cyan"))
            else:
                print(f"\nNEXUS: {reply}\n")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        agent.shutdown()
        out("\n[dim]NEXUS shut down.[/]" if rich else "\nNEXUS shut down.")


if __name__ == "__main__":
    main()
