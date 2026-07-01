"""
backend_entry.py
PyInstaller entry point for the bundled backend executable.
When frozen, running `nexus-backend` starts the FastAPI server exactly like
`python -m api.server`, but without needing Python installed on the target machine.
"""
import sys
import os
from pathlib import Path

# When frozen by PyInstaller, resources live next to the executable.
if getattr(sys, "frozen", False):
    base = Path(sys.executable).parent
    os.chdir(base)
    sys.path.insert(0, str(base))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    from api.server import run
    run()


if __name__ == "__main__":
    main()
