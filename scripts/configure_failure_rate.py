"""Enable failure_rate only from explicit, business-confirmed status groups."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def configure(
    *,
    input_dir: Path,
    success: tuple[str, ...],
    failure: tuple[str, ...],
    pending: tuple[str, ...],
    unknown: tuple[str, ...],
    null_group: str,
    minimum_denominator: int,
    owner: str,
) -> None:
    groups = {
        "success": set(success),
        "failure": set(failure),
        "pending": set(pending),
        "unknown": set(unknown),
    }
    if not groups["success"] or not groups["failure"]:
        raise ValueError("at least one success and failure status is required")
    all_values = [value for values in groups.values() for value in values]
    if len(all_values) != len(set(all_values)):
        raise ValueError("one status value cannot belong to multiple groups")
    if minimum_denominator < 1:
        raise ValueError("minimum denominator must be positive")
    if not owner.strip():
        raise ValueError("metric owner is required")

    values = {value: group for group, members in groups.items() for value in sorted(members)}
    dictionary = {
        "dictionary_id": "status_group",
        "version": "v1",
        "source_field_id": "sub_message.status",
        "values": values,
        "null_group": null_group,
        "owner": owner,
    }
    metric = {
        "metric_id": "failure_rate",
        "version": "v1",
        "level": "certified",
        "display_name": "失败率",
        "business_definition": "失败状态记录占 success 与 failure 正式分母记录的比例",
        "numerator": {"type": "filtered_count", "status_group": "failure"},
        "denominator": {
            "type": "filtered_count",
            "status_groups": ["success", "failure"],
        },
        "time_semantics": {
            "capability_id": "terminal_event_time",
            "timezone": "Asia/Hong_Kong",
        },
        "dimensions": ["channel", "day", "month"],
        "null_policy": f"exclude_and_report:{null_group}",
        "pending_policy": "exclude",
        "unknown_policy": "exclude_and_report",
        "minimum_denominator": minimum_denominator,
        "unit": "ratio",
        "precision": 4,
        "owner": owner,
        "formula_engine": "metric_engine",
    }
    values_path = input_dir / "values" / "status_group.v1.yaml"
    metric_path = input_dir / "metric_registry" / "failure_rate.v1.yaml"
    values_path.parent.mkdir(parents=True, exist_ok=True)
    metric_path.parent.mkdir(parents=True, exist_ok=True)
    values_path.write_text(
        yaml.safe_dump(dictionary, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    metric_path.write_text(
        yaml.safe_dump(metric, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    recipe_path = input_dir / "recipes" / "channel_overview.v1.yaml"
    recipe = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    metric_ids = list(recipe.get("metric_ids", []))
    if "failure_rate.v1" not in metric_ids:
        metric_ids.append("failure_rate.v1")
    recipe["metric_ids"] = metric_ids
    recipe_path.write_text(
        yaml.safe_dump(recipe, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--success-status", action="append", default=[], required=True)
    parser.add_argument("--failure-status", action="append", default=[], required=True)
    parser.add_argument("--pending-status", action="append", default=[])
    parser.add_argument("--unknown-status", action="append", default=[])
    parser.add_argument("--null-group", choices=["success", "failure", "pending", "unknown"])
    parser.add_argument("--minimum-denominator", type=int, required=True)
    parser.add_argument("--owner", required=True)
    args = parser.parse_args()
    if args.null_group is None:
        raise ValueError("--null-group requires an explicit business decision")
    configure(
        input_dir=args.input_dir,
        success=tuple(args.success_status),
        failure=tuple(args.failure_status),
        pending=tuple(args.pending_status),
        unknown=tuple(args.unknown_status),
        null_group=args.null_group,
        minimum_denominator=args.minimum_denominator,
        owner=args.owner,
    )
    print(
        json.dumps(
            {
                "status": "PASSED",
                "metric_id": "failure_rate.v1",
                "business_confirmation_required": True,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
