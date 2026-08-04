"""Run frontend E2E against an in-process static server on Windows or Linux."""

from __future__ import annotations

import functools
import http.server
import os
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


class _ReusableThreadingServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True


def main() -> int:
    if not (DIST / "index.html").is_file():
        print("frontend/dist is missing; run npm run build first", file=sys.stderr)
        return 2
    handler = functools.partial(_QuietHandler, directory=str(DIST))
    try:
        server = _ReusableThreadingServer(("127.0.0.1", 4173), handler)
    except OSError as exc:
        print(f"cannot bind E2E server to 127.0.0.1:4173: {exc}", file=sys.stderr)
        return 2
    thread = threading.Thread(target=server.serve_forever, name="chatbi-e2e-http", daemon=True)
    thread.start()
    executable = (
        FRONTEND / "node_modules" / ".bin" / ("playwright.cmd" if os.name == "nt" else "playwright")
    )
    try:
        completed = subprocess.run(
            [str(executable), "test", *sys.argv[1:]],
            cwd=FRONTEND,
            check=False,
        )
        return completed.returncode
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
