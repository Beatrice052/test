"""Build a hash-based Shadow reconciliation record without copying sensitive payloads."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

CLASSIFICATIONS = (
    "EXPECTED_SEMANTIC_FIX",
    "EXPECTED_TIMEZONE_FIX",
    "EXPECTED_COMPLETENESS_FIX",
    "METRIC_DEFINITION_DIFFERENCE",
    "DATA_CHANGE",
    "IMPLEMENTATION_BUG",
    "UNKNOWN_NEEDS_INVESTIGATION",
)
ARTIFACT_ARGUMENTS = (
    "analysis_plan",
    "query_plan",
    "compiled_dsl",
    "normalized_dataset",
    "metric_result",
    "dashboard_evidence",
)


def _file_record(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": path.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
    }


def _contains_keys(value: Any, required: set[str]) -> bool:
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        if required.issubset(keys):
            return True
        return any(_contains_keys(child, required) for child in value.values())
    if isinstance(value, list):
        return any(_contains_keys(child, required) for child in value)
    return False


def build_report(
    *,
    case_id: str,
    artifacts: dict[str, Path],
    old_result: Path | None,
    classification: str,
    business_verdict: str,
    require_ratio_evidence: bool,
) -> dict[str, object]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", case_id):
        raise ValueError("case_id is invalid")
    if set(artifacts) != set(ARTIFACT_ARGUMENTS):
        raise ValueError("all required Shadow artifacts must be supplied")
    if classification not in CLASSIFICATIONS:
        raise ValueError("Shadow classification is invalid")
    metric_payload = json.loads(artifacts["metric_result"].read_text(encoding="utf-8"))
    ratio_evidence_complete = _contains_keys(metric_payload, {"numerator", "denominator"})
    if require_ratio_evidence and not ratio_evidence_complete:
        raise ValueError("ratio metric evidence must contain numerator and denominator")
    artifact_records = {name: _file_record(path) for name, path in sorted(artifacts.items())}
    report: dict[str, object] = {
        "schema_version": "1.0",
        "case_id": case_id,
        "status": "RECORDED",
        "classification": classification,
        "business_verdict": business_verdict,
        "required_artifacts_complete": True,
        "ratio_evidence_complete": ratio_evidence_complete,
        "artifacts": artifact_records,
        "old_result": _file_record(old_result) if old_result is not None else None,
        "payloads_embedded": False,
        "credentials_embedded": False,
    }
    return report


def _markdown(report: dict[str, object]) -> str:
    artifacts = report["artifacts"]
    assert isinstance(artifacts, dict)
    lines = [
        f"# Shadow Reconciliation — {report['case_id']}",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Business verdict: `{report['business_verdict']}`",
        f"- Ratio evidence complete: `{report['ratio_evidence_complete']}`",
        f"- Old result supplied: `{report['old_result'] is not None}`",
        "- Payloads/credentials embedded: `false`",
        "",
        "| Artifact | SHA-256 | Bytes |",
        "|---|---|---:|",
    ]
    for name, raw_record in sorted(artifacts.items()):
        assert isinstance(raw_record, dict)
        lines.append(f"| {name} | `{raw_record['sha256']}` | {raw_record['size_bytes']} |")
    lines.extend(
        [
            "",
            "## Human review",
            "",
            "- [ ] Time range and timezone reconciled",
            "- [ ] Grain and completeness reconciled",
            "- [ ] Numerator/denominator/exclusions reconciled when applicable",
            "- [ ] Dataset totals reconciled",
            "- [ ] Dashboard and Evidence point to the reviewed artifacts",
            "- [ ] Business owner signed the verdict",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    for name in ARTIFACT_ARGUMENTS:
        parser.add_argument(f"--{name.replace('_', '-')}", dest=name, type=Path, required=True)
    parser.add_argument("--old-result", type=Path)
    parser.add_argument("--classification", choices=CLASSIFICATIONS, required=True)
    parser.add_argument(
        "--business-verdict", choices=("PASS", "FAIL", "NEEDS_REVIEW"), required=True
    )
    parser.add_argument("--require-ratio-evidence", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    artifacts = {name: getattr(args, name) for name in ARTIFACT_ARGUMENTS}
    report = build_report(
        case_id=args.case_id,
        artifacts=artifacts,
        old_result=args.old_result,
        classification=args.classification,
        business_verdict=args.business_verdict,
        require_ratio_evidence=args.require_ratio_evidence,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{args.case_id}.shadow.json"
    markdown_path = args.output_dir / f"{args.case_id}.shadow.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASSED",
                "json": str(json_path),
                "markdown": str(markdown_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
