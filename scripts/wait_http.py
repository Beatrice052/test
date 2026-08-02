"""Wait for a local verification endpoint without requiring curl."""

from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--timeout-seconds", type=float, default=30)
    args = parser.parse_args()
    deadline = time.monotonic() + args.timeout_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(args.url, timeout=2) as response:
                if 200 <= response.status < 300:
                    print(f"ready: {args.url}")
                    return 0
                last_error = f"HTTP {response.status}"
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = type(error).__name__
        time.sleep(0.5)
    print(f"not ready: {args.url} ({last_error})")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
