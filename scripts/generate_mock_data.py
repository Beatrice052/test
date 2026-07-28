from __future__ import annotations

import json
from calendar import monthrange
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "mock_data"
TIMEZONE = ZoneInfo("Asia/Hong_Kong")
MONTHS = [(2026, 6), (2026, 7), (2026, 8)]
CHANNELS = ["SMS", "Email", "WhatsApp"]
ROUTES = ["ROUTE_A", "ROUTE_B", "ROUTE_C"]
PROVIDERS = ["PROVIDER_ALPHA", "PROVIDER_BETA", "PROVIDER_GAMMA"]
STATUSES = ["SENT", "INPROGRESS", "FAILED", "ACKFAIL", "QUEUED", None]
STATUS_CODES = ["CM-30047", "CT-50012", "CU-R00008", None]


def status_variant(value: str | None, sequence: int) -> str | None:
    if value is None:
        return None
    if sequence % 11 == 0:
        return f" {value.lower()} "
    if sequence % 7 == 0:
        return value.lower()
    return value


def generate_month(year: int, month: int) -> list[dict]:
    records: list[dict] = []
    days = monthrange(year, month)[1]
    sequence = 0
    for day in range(1, days + 1):
        for channel_index, channel in enumerate(CHANNELS):
            for copy_index in range(2):
                sequence += 1
                canonical_status = STATUSES[
                    (day + channel_index * 2 + copy_index) % len(STATUSES)
                ]
                route = ROUTES[(day + channel_index + copy_index) % len(ROUTES)]
                timestamp = datetime(
                    year,
                    month,
                    day,
                    8 + channel_index * 3 + copy_index,
                    (day * 7 + copy_index * 13) % 60,
                    tzinfo=TIMEZONE,
                )
                records.append(
                    {
                        "_index": f"tbl_os_sub_message_{year:04d}_{month:02d}",
                        "docId": f"mock-{year:04d}{month:02d}-{sequence:04d}",
                        "createdTime": timestamp.isoformat(),
                        "status": status_variant(canonical_status, sequence),
                        "statusCode": STATUS_CODES[
                            (day + channel_index + copy_index) % len(STATUS_CODES)
                        ],
                        "Status": canonical_status,
                        "pushStatus": "PUSHED" if sequence % 4 else "PUSH_PENDING",
                        "letterStatus": "DELIVERED" if sequence % 5 else "LETTER_PENDING",
                        "ackFlag": "Y" if sequence % 3 else "N",
                        "channel": channel,
                        "route": route,
                        "providerName": PROVIDERS[channel_index],
                        "retryCount": sequence % 3,
                        "latencyMs": 80 + (day * 17 + channel_index * 41) % 900,
                        "subjectText": f"Synthetic {channel} notification",
                        "diagnosticText": f"Synthetic diagnostic {route}",
                        "deliveryMeta": {
                            "attemptId": f"attempt-{sequence:04d}",
                            "region": "SYNTHETIC",
                        },
                        "messageBody": "SYNTHETIC BLOCKED MESSAGE BODY",
                        "customerName": "SYNTHETIC CUSTOMER",
                        "phoneNumber": "00000000000",
                        "emailAddress": "synthetic@example.invalid",
                        "bankAccount": "SYNTHETIC-ACCOUNT",
                        "customerId": f"synthetic-customer-{sequence % 9}",
                        "mappingOnlyFlag": sequence % 2 == 0,
                    }
                )
    return records


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for year, month in MONTHS:
        index = f"tbl_os_sub_message_{year:04d}_{month:02d}"
        records = generate_month(year, month)
        path = OUTPUT_DIR / f"{index}.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        print(f"{index}: {len(records)} records")


if __name__ == "__main__":
    main()
