"""
File: main.py

Purpose:
Convenience entrypoint so the backend can be started with:

    cd backend
    python main.py --reload

The application itself lives in backend/src/main.py and uses package-relative
imports (`backend.src.*`), so it must be imported as part of the `backend`
package rather than executed as a loose script. This file puts the repository
root on sys.path and hands uvicorn the import string.

The sys.path setup is deliberately at module scope, not inside main(): with
--reload, uvicorn respawns via multiprocessing "spawn", and the child process
re-imports this file as __main__ before loading the app. If the path were only
patched inside main(), the reloaded worker would fail to import backend.src.

Equivalent, and still supported:
    uvicorn backend.src.main:app --reload      # from the repository root
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BACKEND_DIR = Path(__file__).resolve().parent


def main() -> None:
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Run the Manos AI backend")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument(
        "--reload", action="store_true", help="Restart on source changes (development)"
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
    )
    args = parser.parse_args()

    uvicorn.run(
        "backend.src.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        # Watch only backend sources; without this the reloader also walks
        # data/, venv/ and frontend/node_modules and restarts on index writes.
        reload_dirs=[str(BACKEND_DIR / "src")] if args.reload else None,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
