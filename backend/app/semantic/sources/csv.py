"""CSV field description adapter."""

import csv
from pathlib import Path

from app.contracts.semantic import FieldDescriptionRow
from app.semantic.sanitizer import DescriptionSanitizer
from app.semantic.sources.base import KnowledgeSourceError, build_description_row, resolve_columns


class CsvFieldDescriptionAdapter:
    def __init__(
        self,
        source_path: Path,
        *,
        encoding: str = "utf-8-sig",
        sanitizer: DescriptionSanitizer | None = None,
    ) -> None:
        self.source_path = source_path
        self.encoding = encoding
        self.sanitizer = sanitizer or DescriptionSanitizer()

    def load_field_descriptions(self) -> list[FieldDescriptionRow]:
        with self.source_path.open("r", encoding=self.encoding, newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if header is None:
                raise KnowledgeSourceError("field description CSV is empty")
            columns = resolve_columns(header)
            rows: list[FieldDescriptionRow] = []
            for source_row, values in enumerate(reader, start=2):
                parsed = build_description_row(
                    values, columns, source_row=source_row, sanitizer=self.sanitizer
                )
                if parsed is not None:
                    rows.append(parsed)
            return rows
