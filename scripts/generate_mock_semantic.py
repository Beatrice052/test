#!/usr/bin/env python3
"""Generate the XLSX form of the checked-in Mock field catalog."""

from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "semantic-input" / "mock"
CSV_PATH = INPUT_DIR / "field_descriptions.csv"
XLSX_PATH = INPUT_DIR / "field_descriptions.xlsx"


def main() -> int:
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "field_descriptions"
    for row in rows:
        worksheet.append(row)
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    workbook.save(XLSX_PATH)
    print(f"generated {XLSX_PATH} with {len(rows) - 1} field rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
