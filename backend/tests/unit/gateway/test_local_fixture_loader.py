"""The local-os loader expands only the three signed-in Mock indices."""

import json
import runpy
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[4]


def test_fixture_expands_to_deterministic_document_counts() -> None:
    module = runpy.run_path(str(ROOT / "scripts" / "load_local_opensearch.py"))
    documents = cast(Any, module["_documents"])
    fixture = json.loads(
        (ROOT / "fixtures" / "gateway" / "sub_message_rows.json").read_text(encoding="utf-8")
    )

    expanded = documents(fixture)

    assert {key: len(value) for key, value in expanded.items()} == {
        "tbl_os_sub_message_2026_05": 53,
        "tbl_os_sub_message_2026_06": 61,
        "tbl_os_sub_message_2026_07": 155,
    }
    first_id, first_document = expanded["tbl_os_sub_message_2026_07"][0]
    assert len(first_id) == 24
    assert first_document["channel"] == "SMS"
    assert first_document["message_id"].startswith("mock-")
