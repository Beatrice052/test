"""Excel/CSV import and metadata sanitization tests."""

from pathlib import Path

from app.semantic.sources import CsvFieldDescriptionAdapter, ExcelFieldDescriptionAdapter

ROOT = Path(__file__).resolve().parents[4]
INPUT = ROOT / "semantic-input" / "mock"


def test_excel_and_csv_column_aliases_produce_same_catalog() -> None:
    excel_rows = ExcelFieldDescriptionAdapter(
        INPUT / "field_descriptions.xlsx"
    ).load_field_descriptions()
    csv_rows = CsvFieldDescriptionAdapter(
        INPUT / "field_descriptions.csv"
    ).load_field_descriptions()

    assert len(excel_rows) == len(csv_rows) == 11
    assert [row.field_path for row in excel_rows] == [row.field_path for row in csv_rows]
    assert excel_rows[1].aliases == ("Channel", "渠道", "发送渠道")


def test_description_instruction_is_sanitized_as_untrusted_data() -> None:
    rows = ExcelFieldDescriptionAdapter(INPUT / "field_descriptions.xlsx").load_field_descriptions()
    injected = next(row for row in rows if row.field_path == "free_text")

    assert "ignore previous rules" not in injected.description
    assert "system prompt" not in injected.description
    assert "CODE_FENCE_REMOVED" in injected.sanitizer_events
    assert "INSTRUCTION_PATTERN_REMOVED" in injected.sanitizer_events
    assert injected.original_description_hash.startswith("sha256:")
