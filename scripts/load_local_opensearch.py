"""Load the signed-in aggregate fixture as deterministic documents into local OpenSearch."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

SAFE_INDEX = re.compile(r"^tbl_os_sub_message_2026_(05|06|07)$")


def _documents(
    fixture: dict[str, Any],
) -> dict[str, list[tuple[str, dict[str, object]]]]:
    by_index: dict[str, list[tuple[str, dict[str, object]]]] = {}
    rows = fixture.get("rows")
    if not isinstance(rows, list):
        raise TypeError("fixture rows must be a list")
    for row_number, row in enumerate(rows):
        if not isinstance(row, dict):
            raise TypeError("fixture row must be an object")
        timestamp = str(row["sub_message.event_time"])
        month = datetime.fromisoformat(timestamp).strftime("%m")
        index = f"tbl_os_sub_message_2026_{month}"
        if not SAFE_INDEX.fullmatch(index):
            raise ValueError(f"fixture resolved to disallowed index: {index}")
        count = int(row["record_count"])
        if count < 0 or count > 10_000:
            raise ValueError("fixture record_count is outside the local loader budget")
        for ordinal in range(count):
            identity = f"{index}:{row_number}:{ordinal}"
            document_id = hashlib.sha256(identity.encode()).hexdigest()[:24]
            document: dict[str, object] = {
                "event_time": timestamp,
                "channel": row.get("sub_message.channel"),
                "status": row.get("sub_message.status"),
                "message_id": f"mock-{document_id}",
                "recipient_id": f"mock-recipient-{ordinal % 17:02d}",
                "send_attempt": 1,
                "latency_ms": row.get("sub_message.latency_ms"),
                "error_code": row.get("sub_message.error_code"),
                "route": "MOCK_PRIMARY",
                "free_text": "signed-in local fixture",
                "metadata": [{"provider": "mock-provider"}],
            }
            by_index.setdefault(index, []).append((document_id, document))
    return by_index


def _wait_ready(client: httpx.Client, base_url: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            response = client.get(f"{base_url}/_cluster/health")
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise TimeoutError("local OpenSearch did not become ready")


def load(
    *, base_url: str, mapping_path: Path, fixture_path: Path, timeout_seconds: float
) -> dict[str, int]:
    raw_mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    indices = raw_mapping.get("indices")
    if not isinstance(indices, dict):
        raise TypeError("mapping snapshot indices are missing")
    documents = _documents(json.loads(fixture_path.read_text(encoding="utf-8")))
    counts: dict[str, int] = {}
    with httpx.Client(timeout=30) as client:
        _wait_ready(client, base_url, timeout_seconds)
        for index, body in sorted(indices.items()):
            if not isinstance(index, str) or not SAFE_INDEX.fullmatch(index):
                raise ValueError(f"refusing to manage unexpected local index: {index}")
            if not isinstance(body, dict):
                raise TypeError("mapping index body is invalid")
            existing = client.head(f"{base_url}/{index}")
            if existing.status_code == 200:
                deleted = client.delete(f"{base_url}/{index}")
                deleted.raise_for_status()
            elif existing.status_code != 404:
                existing.raise_for_status()
            created = client.put(f"{base_url}/{index}", json={"mappings": body["mappings"]})
            created.raise_for_status()

            lines: list[str] = []
            for document_id, document in documents.get(index, []):
                lines.append(json.dumps({"index": {"_index": index, "_id": document_id}}))
                lines.append(json.dumps(document, ensure_ascii=False, separators=(",", ":")))
            if lines:
                bulk = client.post(
                    f"{base_url}/_bulk?refresh=true",
                    content="\n".join(lines) + "\n",
                    headers={"Content-Type": "application/x-ndjson"},
                )
                bulk.raise_for_status()
                if bulk.json().get("errors") is True:
                    raise RuntimeError(f"bulk load failed for {index}")
            count_response = client.get(f"{base_url}/{index}/_count")
            count_response.raise_for_status()
            actual = int(count_response.json()["count"])
            expected = len(documents.get(index, []))
            if actual != expected:
                raise RuntimeError(f"fixture count mismatch for {index}: {actual} != {expected}")
            counts[index] = actual
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.getenv("OPENSEARCH_URL", "http://opensearch:9200"))
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=120)
    args = parser.parse_args()
    counts = load(
        base_url=args.url.rstrip("/"),
        mapping_path=args.mapping,
        fixture_path=args.fixture,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps({"status": "PASSED", "counts": counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
