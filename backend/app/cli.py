"""Administrative CLI; agents never receive these capabilities."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from app.contracts.common import Provenance, StrictModel, semantic_hash
from app.contracts.semantic import FieldMaturity, MappingSnapshot
from app.gateway.bindings import MappingRequest
from app.gateway.capability_probe import McpCapabilityProbe
from app.gateway.config import load_mcp_runtime_config
from app.gateway.mcp import McpOpenSearchGateway
from app.gateway.mcp_transport import OfficialMcpTransport
from app.llm.cutover import evaluate_real_llm_cutover
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.semantic.compiler import SemanticCompileError, compile_semantic_package
from app.semantic.mapping import flatten_mapping_snapshot
from app.semantic.package import CompiledSemanticPackage
from app.settings import get_settings


class LLMProbeResponse(StrictModel):
    status: Literal["ok"]


def _semantic_compile(args: argparse.Namespace) -> int:
    input_dir = args.input_dir or args.field_catalog.parent
    try:
        result = compile_semantic_package(
            input_dir,
            args.output_dir,
            field_catalog_path=args.field_catalog,
            mapping_path=args.mapping,
            profile_path=args.profile,
            metric_registry_path=args.metric_registry,
        )
    except SemanticCompileError as error:
        print(
            json.dumps(
                {"status": "FAILED", "error": str(error), "exit_code": error.exit_code},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return error.exit_code
    print(
        json.dumps(
            {
                "status": result.report.status,
                "package_version": result.manifest.package_version,
                "field_count": len(result.fields),
                "output_dir": str(result.output_dir),
                "exit_code": result.exit_code,
            },
            ensure_ascii=False,
        )
    )
    return result.exit_code


async def _mcp_probe_async(args: argparse.Namespace) -> int:
    transport_config, bindings = load_mcp_runtime_config(args.config)
    transport = OfficialMcpTransport(transport_config)
    try:
        await transport.connect()
        tools = await transport.list_tools()
        report = McpCapabilityProbe().probe(bindings, tools)
        health_status = "NOT_CONFIGURED"
        health_tool = report.resolved_bindings.get("health")
        if health_tool is not None:
            try:
                result = await transport.call_tool(health_tool, {})
                is_error = bool(
                    result.get("isError", False)
                    if isinstance(result, dict)
                    else getattr(result, "isError", False)
                )
                health_status = "FAILED" if is_error else "PASSED"
            except Exception:
                health_status = "FAILED"
        configured_forbidden = tuple(
            sorted(set(bindings.tool_bindings.values()).intersection(bindings.forbidden_tools))
        )
        ready = report.ready and health_status == "PASSED" and not configured_forbidden
        payload = {
            "status": "PASSED" if ready else "FAILED",
            "transport": transport_config.transport,
            "server_name": transport.server_name,
            "server_version": transport.server_version,
            "detected_tool_names": sorted(tool.name for tool in tools),
            "required_bindings": {
                capability: report.resolved_bindings.get(capability, "MISSING")
                for capability in report.required_capabilities
            },
            "missing_capabilities": list(report.missing_capabilities),
            "input_schema_compatibility": {
                "execute_search_query_dsl": report.query_dsl_mode,
                "issues": list(report.issues),
            },
            "health_result": health_status,
            "forbidden_binding_check": {
                "passed": not configured_forbidden and not report.forbidden_bindings,
                "configured_forbidden": list(configured_forbidden),
                "probe_forbidden": list(report.forbidden_bindings),
            },
            "credentials_in_report": False,
            "probed_at": datetime.now(UTC).isoformat(),
        }
        _emit_json(payload, args.output)
        return 0 if ready else 2
    finally:
        await transport.close()


def _mcp_probe(args: argparse.Namespace) -> int:
    try:
        return asyncio.run(_mcp_probe_async(args))
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error_type": type(error).__name__,
                    "credentials_in_report": False,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


def _build_smoke_queries(
    *,
    time_field: str,
    channel_field: str,
    status_field: str,
    from_inclusive: str,
    to_exclusive: str,
    timezone: str,
) -> dict[str, dict[str, object]]:
    safe_field = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,255}$")
    for field in (time_field, channel_field, status_field):
        if not safe_field.fullmatch(field):
            raise ValueError("smoke field names must be safe physical paths")
    start = datetime.fromisoformat(from_inclusive.replace("Z", "+00:00"))
    end = datetime.fromisoformat(to_exclusive.replace("Z", "+00:00"))
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError("smoke range must be timezone-aware and half-open")
    time_filter: dict[str, object] = {
        "range": {time_field: {"gte": from_inclusive, "lt": to_exclusive}}
    }
    base: dict[str, object] = {
        "size": 0,
        "track_total_hits": True,
        "timeout": "10s",
        "query": time_filter,
    }
    return {
        "count_narrow_range": dict(base),
        "channel_aggregation": {
            **base,
            "aggs": {"by_channel": {"terms": {"field": channel_field, "size": 50}}},
        },
        "channel_status_aggregation": {
            **base,
            "aggs": {
                "by_channel": {
                    "terms": {"field": channel_field, "size": 50},
                    "aggs": {"by_status": {"terms": {"field": status_field, "size": 50}}},
                }
            },
        },
        "multi_month_aggregation": {
            **base,
            "aggs": {
                "by_month": {
                    "date_histogram": {
                        "field": time_field,
                        "calendar_interval": "month",
                        "time_zone": timezone,
                        "min_doc_count": 0,
                    },
                    "aggs": {"by_channel": {"terms": {"field": channel_field, "size": 50}}},
                }
            },
        },
    }


def _tool_result_failed(result: object) -> bool:
    return bool(
        result.get("isError", False)
        if isinstance(result, dict)
        else getattr(result, "isError", False)
    )


def _search_smoke_summary(payload: object, raw_size: int) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError("smoke search response must be a JSON object")
    if payload.get("timed_out") is True:
        raise RuntimeError("smoke search timed out")
    shards = payload.get("_shards", payload.get("shards", {}))
    if not isinstance(shards, dict):
        raise ValueError("smoke search shard summary is invalid")
    failed = shards.get("failed", 0)
    if not isinstance(failed, int) or isinstance(failed, bool) or failed != 0:
        raise RuntimeError("smoke search has failed shards")
    hits = payload.get("hits", {})
    total: int | None = None
    if isinstance(hits, dict):
        total_value = hits.get("total")
        if isinstance(total_value, int) and not isinstance(total_value, bool):
            total = total_value
        elif isinstance(total_value, dict):
            candidate = total_value.get("value")
            if isinstance(candidate, int) and not isinstance(candidate, bool):
                total = candidate
    aggregations = payload.get("aggregations", {})
    bucket_count = 0
    if isinstance(aggregations, dict):
        for aggregation in aggregations.values():
            if isinstance(aggregation, dict) and isinstance(aggregation.get("buckets"), list):
                bucket_count += len(aggregation["buckets"])
    took = payload.get("took", 0)
    return {
        "status": "PASSED",
        "took_ms": took if isinstance(took, int) else None,
        "shards": {str(key): value for key, value in shards.items()},
        "total": total,
        "top_level_bucket_count": bucket_count,
        "raw_size_bytes": raw_size,
        "response_hash": semantic_hash(payload),
    }


async def _mcp_smoke_async(args: argparse.Namespace) -> int:
    safe_index = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,254}$")
    indices = tuple(args.index)
    if not indices or any(not safe_index.fullmatch(index) for index in indices):
        raise ValueError("smoke requires explicit safe index names; wildcards are forbidden")
    queries = _build_smoke_queries(
        time_field=args.time_field,
        channel_field=args.channel_field,
        status_field=args.status_field,
        from_inclusive=args.from_inclusive,
        to_exclusive=args.to_exclusive,
        timezone=args.timezone,
    )
    transport_config, bindings = load_mcp_runtime_config(args.config)
    transport = OfficialMcpTransport(transport_config)
    try:
        await transport.connect()
        gateway = McpOpenSearchGateway(transport=transport, bindings=bindings)
        capability = await gateway.probe()
        if not capability.ready:
            raise RuntimeError("required MCP bindings are not ready")

        health_result = await transport.call_tool(capability.resolved_bindings["health"], {})
        if _tool_result_failed(health_result):
            raise RuntimeError("MCP health tool failed")
        list_tool = capability.resolved_bindings["list_indices"]
        for index in indices:
            listed = await transport.call_tool(list_tool, {"index": index})
            if _tool_result_failed(listed):
                raise RuntimeError("MCP list-index tool failed")
        mapping = await gateway.get_mapping(
            MappingRequest(dataset_id=args.dataset, indices=indices)
        )

        search_tool = capability.resolved_bindings["execute_search"]
        checks: dict[str, object] = {}
        for name, query in queries.items():
            query_input: object = query
            if capability.query_dsl_mode == "string":
                query_input = json.dumps(query, ensure_ascii=False, sort_keys=True)
            result = await transport.call_tool(
                search_tool,
                {"index": ",".join(indices), "query_dsl": query_input, "format": "json"},
            )
            if _tool_result_failed(result):
                raise RuntimeError(f"MCP smoke search failed: {name}")
            payload, raw_size = gateway._decode(result)
            checks[name] = _search_smoke_summary(payload, raw_size)
        report = {
            "status": "PASSED",
            "transport": transport_config.transport,
            "server_name": transport.server_name,
            "server_version": transport.server_version,
            "dataset_id": args.dataset,
            "indices": list(indices),
            "mapping_hash": mapping.raw_mapping_hash,
            "time_range": {
                "from_inclusive": args.from_inclusive,
                "to_exclusive": args.to_exclusive,
                "timezone": args.timezone,
            },
            "queries": queries,
            "checks": checks,
            "credentials_in_report": False,
            "smoked_at": datetime.now(UTC).isoformat(),
        }
        _emit_json(report, args.output)
        return 0
    finally:
        await transport.close()


def _mcp_smoke(args: argparse.Namespace) -> int:
    try:
        return asyncio.run(_mcp_smoke_async(args))
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error_type": type(error).__name__,
                    "credentials_in_report": False,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


async def _llm_probe_async(args: argparse.Namespace) -> int:
    settings = get_settings()
    if settings.chatbi_llm_base_url is None or settings.chatbi_llm_model is None:
        raise ValueError("CHATBI_LLM_BASE_URL and CHATBI_LLM_MODEL are required")
    client = OpenAICompatibleLLMClient(
        base_url=settings.chatbi_llm_base_url,
        model=settings.chatbi_llm_model,
        api_key=settings.chatbi_llm_api_key,
    )
    response = await client.generate(
        operation="semantic_query_rewrite",
        system_prompt='Return exactly one schema-valid object with status "ok".',
        input_payload={"probe": "configuration_only", "business_data_included": False},
        output_schema=LLMProbeResponse,
        timeout_seconds=settings.chatbi_llm_timeout_seconds,
        correlation_id=f"llm-probe-{uuid4().hex}",
    )
    payload = {
        "status": "PASSED" if response.status == "ok" else "FAILED",
        "adapter": "openai_compatible",
        "model": settings.chatbi_llm_model,
        "business_data_included": False,
        "credentials_in_report": False,
        "probed_at": datetime.now(UTC).isoformat(),
    }
    _emit_json(payload, args.output)
    return 0


def _llm_probe(args: argparse.Namespace) -> int:
    try:
        return asyncio.run(_llm_probe_async(args))
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error_type": type(error).__name__,
                    "credentials_in_report": False,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


def _llm_cutover_check(args: argparse.Namespace) -> int:
    try:
        settings = get_settings()
        report = evaluate_real_llm_cutover(
            settings,
            app_source_root=Path(__file__).resolve().parent,
        )
        _emit_json(report.model_dump(mode="json"), args.output)
        return 0 if report.status == "PASSED" else 2
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error_type": type(error).__name__,
                    "credentials_in_report": False,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


async def _snapshot_mapping_async(args: argparse.Namespace) -> int:
    transport_config, bindings = load_mcp_runtime_config(args.config)
    transport = OfficialMcpTransport(transport_config)
    try:
        await transport.connect()
        gateway = McpOpenSearchGateway(transport=transport, bindings=bindings)
        report = await gateway.probe()
        if not report.ready:
            raise RuntimeError("required MCP bindings are not ready")
        indices = tuple(args.index or ())
        if args.index_pattern is not None:
            indices = await gateway.list_indices(args.index_pattern)
        snapshot = await gateway.get_mapping(
            MappingRequest(dataset_id=args.dataset, indices=indices)
        )
        mapping_tool = report.resolved_bindings["get_mapping"]
        snapshot = snapshot.model_copy(
            update={
                "provenance": Provenance(
                    producer="semantic.mapping",
                    source_ids=snapshot.provenance.source_ids,
                    source_hashes=snapshot.provenance.source_hashes,
                    metadata={
                        **snapshot.provenance.metadata,
                        "transport": transport_config.transport,
                        "tool": mapping_tool,
                        "server_name": transport.server_name,
                        "server_version": transport.server_version,
                    },
                )
            }
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(f"{args.output.suffix}.tmp")
        temporary.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(args.output)
        print(
            json.dumps(
                {
                    "status": "PASSED",
                    "dataset_id": snapshot.dataset_id,
                    "indices": list(snapshot.indices),
                    "mapping_hash": snapshot.raw_mapping_hash,
                    "field_count": len(snapshot.fields),
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        await transport.close()


def _snapshot_mapping(args: argparse.Namespace) -> int:
    try:
        return asyncio.run(_snapshot_mapping_async(args))
    except Exception as error:
        print(
            json.dumps(
                {"status": "FAILED", "error_type": type(error).__name__},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


def _load_mapping_snapshot(path: Path, dataset_id: str) -> MappingSnapshot:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and {"object_id", "fields", "raw_mapping_hash"}.issubset(raw):
        snapshot = MappingSnapshot.model_validate(raw, strict=False)
        if snapshot.dataset_id != dataset_id:
            raise ValueError("mapping snapshot dataset_id does not match --dataset")
        return snapshot
    if not isinstance(raw, dict):
        raise ValueError("mapping snapshot must be a JSON object")
    return flatten_mapping_snapshot(raw, dataset_id=dataset_id)


async def _snapshot_profile_async(args: argparse.Namespace) -> int:
    mapping = _load_mapping_snapshot(args.mapping, args.dataset)
    package = CompiledSemanticPackage(args.semantic_package)
    allowed_source_paths = tuple(
        sorted(
            field.source_path
            for field in package.fields()
            if field.dataset_id == args.dataset
            and field.maturity != FieldMaturity.BLOCKED
            and field.security.model_visible
            and field.security.aggregatable
        )
    )
    transport_config, bindings = load_mcp_runtime_config(args.config)
    transport = OfficialMcpTransport(transport_config)
    try:
        await transport.connect()
        gateway = McpOpenSearchGateway(transport=transport, bindings=bindings)
        report = await gateway.probe()
        if not report.ready:
            raise RuntimeError("required MCP bindings are not ready")
        profile = await gateway.profile_fields(
            mapping,
            allowed_source_paths=allowed_source_paths,
            max_fields=args.max_fields,
            sample_value_limit=args.sample_value_limit,
        )
        profile = profile.model_copy(
            update={
                "provenance": Provenance(
                    producer="semantic.profiler",
                    source_ids=profile.provenance.source_ids,
                    source_hashes=profile.provenance.source_hashes,
                    metadata={
                        **profile.provenance.metadata,
                        "transport": transport_config.transport,
                        "tool": report.resolved_bindings["execute_search"],
                        "server_name": transport.server_name,
                        "server_version": transport.server_version,
                        "raw_documents_included": False,
                    },
                )
            }
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(f"{args.output.suffix}.tmp")
        temporary.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(args.output)
        print(
            json.dumps(
                {
                    "status": "PASSED",
                    "dataset_id": profile.dataset_id,
                    "indices": list(profile.indices),
                    "profiled_field_count": len(profile.fields),
                    "raw_documents_included": False,
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        await transport.close()


def _snapshot_profile(args: argparse.Namespace) -> int:
    try:
        return asyncio.run(_snapshot_profile_async(args))
    except Exception as error:
        print(
            json.dumps(
                {"status": "FAILED", "error_type": type(error).__name__},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


def _emit_json(payload: Mapping[str, object], output: Path | None) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chatbi")
    commands = parser.add_subparsers(dest="command", required=True)

    semantic = commands.add_parser("semantic")
    semantic_commands = semantic.add_subparsers(dest="semantic_command", required=True)
    compile_parser = semantic_commands.add_parser("compile")
    source_group = compile_parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--input-dir", type=Path)
    source_group.add_argument("--field-catalog", type=Path)
    compile_parser.add_argument("--mapping", type=Path)
    compile_parser.add_argument("--profile", type=Path)
    compile_parser.add_argument("--metric-registry", type=Path)
    compile_parser.add_argument(
        "--output-dir", "--output", dest="output_dir", type=Path, required=True
    )
    compile_parser.set_defaults(handler=_semantic_compile)

    snapshot_parser = semantic_commands.add_parser("snapshot-mapping")
    snapshot_parser.add_argument("--config", type=Path, required=True)
    snapshot_parser.add_argument("--dataset", required=True)
    snapshot_index = snapshot_parser.add_mutually_exclusive_group(required=True)
    snapshot_index.add_argument("--index", action="append")
    snapshot_index.add_argument("--index-pattern")
    snapshot_parser.add_argument("--output", type=Path, required=True)
    snapshot_parser.set_defaults(handler=_snapshot_mapping)

    profile_parser = semantic_commands.add_parser("snapshot-profile")
    profile_parser.add_argument("--config", type=Path, required=True)
    profile_parser.add_argument("--dataset", required=True)
    profile_parser.add_argument("--mapping", type=Path, required=True)
    profile_parser.add_argument("--semantic-package", type=Path, required=True)
    profile_parser.add_argument("--max-fields", type=int, default=100)
    profile_parser.add_argument("--sample-value-limit", type=int, default=5)
    profile_parser.add_argument("--output", type=Path, required=True)
    profile_parser.set_defaults(handler=_snapshot_profile)

    mcp = commands.add_parser("mcp")
    mcp_commands = mcp.add_subparsers(dest="mcp_command", required=True)
    probe_parser = mcp_commands.add_parser("probe")
    probe_parser.add_argument("--config", type=Path, required=True)
    probe_parser.add_argument("--output", type=Path)
    probe_parser.set_defaults(handler=_mcp_probe)

    smoke_parser = mcp_commands.add_parser("smoke")
    smoke_parser.add_argument("--config", type=Path, required=True)
    smoke_parser.add_argument("--dataset", required=True)
    smoke_parser.add_argument("--index", action="append", required=True)
    smoke_parser.add_argument("--time-field", required=True)
    smoke_parser.add_argument("--channel-field", required=True)
    smoke_parser.add_argument("--status-field", required=True)
    smoke_parser.add_argument("--from", dest="from_inclusive", required=True)
    smoke_parser.add_argument("--to", dest="to_exclusive", required=True)
    smoke_parser.add_argument("--timezone", default="Asia/Hong_Kong")
    smoke_parser.add_argument("--output", type=Path, required=True)
    smoke_parser.set_defaults(handler=_mcp_smoke)

    llm = commands.add_parser("llm")
    llm_commands = llm.add_subparsers(dest="llm_command", required=True)
    llm_probe_parser = llm_commands.add_parser("probe")
    llm_probe_parser.add_argument("--output", type=Path)
    llm_probe_parser.set_defaults(handler=_llm_probe)
    llm_cutover_parser = llm_commands.add_parser("cutover-check")
    llm_cutover_parser.add_argument("--output", type=Path)
    llm_cutover_parser.set_defaults(handler=_llm_cutover_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
