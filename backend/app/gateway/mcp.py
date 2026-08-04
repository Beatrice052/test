"""Official-MCP-facing Gateway adapter with cached, validated tool bindings."""

from __future__ import annotations

import csv
import io
import json
import re
from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from fnmatch import fnmatchcase
from typing import Protocol, cast

from app.contracts.common import JsonScalar, JsonValue, Provenance, semantic_hash
from app.contracts.execution import RawSearchResult, ShardSummary
from app.contracts.query import CompiledQuery
from app.contracts.semantic import FieldProfile, FieldProfileSnapshot, MappingField, MappingSnapshot
from app.gateway.bindings import (
    GatewayBindings,
    GatewayHealth,
    MappingRequest,
    McpCapabilityReport,
    ToolDescriptor,
)
from app.gateway.capability_probe import McpCapabilityProbe
from app.gateway.errors import GatewayCapabilityError, GatewayProtocolError
from app.semantic.mapping import flatten_mapping_snapshot

_SAFE_INDEX_PATTERN = re.compile(r"^[A-Za-z0-9*?][A-Za-z0-9*?_.-]{0,254}$")


class McpTransport(Protocol):
    async def list_tools(self) -> tuple[ToolDescriptor, ...]: ...

    async def call_tool(self, name: str, arguments: dict[str, object]) -> object: ...


class McpOpenSearchGateway:
    def __init__(
        self,
        *,
        transport: McpTransport,
        bindings: GatewayBindings,
        max_raw_response_bytes: int = 10_000_000,
    ) -> None:
        self.transport = transport
        self.bindings = bindings
        self.max_raw_response_bytes = max_raw_response_bytes
        self.capabilities: McpCapabilityReport | None = None

    async def probe(self) -> McpCapabilityReport:
        report = McpCapabilityProbe().probe(self.bindings, await self.transport.list_tools())
        self.capabilities = report
        return report

    async def get_mapping(self, request: MappingRequest) -> MappingSnapshot:
        tool = self._tool("get_mapping")
        response = await self.transport.call_tool(tool, {"index": ",".join(request.indices)})
        payload, _ = self._decode(response)
        try:
            return MappingSnapshot.model_validate(payload, strict=False)
        except ValueError as error:
            if isinstance(payload, Mapping):
                try:
                    return flatten_mapping_snapshot(payload, dataset_id=request.dataset_id)
                except ValueError as mapping_error:
                    raise GatewayProtocolError(
                        "MCP mapping response cannot be normalized"
                    ) from mapping_error
            raise GatewayProtocolError("MCP mapping response is not an object") from error

    async def list_indices(self, index_pattern: str) -> tuple[str, ...]:
        if not _SAFE_INDEX_PATTERN.fullmatch(index_pattern):
            raise GatewayProtocolError("index discovery pattern contains unsafe characters")
        tool = self._tool("list_indices")
        response = await self.transport.call_tool(tool, {"index": index_pattern})
        payload, raw_size = self._decode(response)
        if raw_size > self.max_raw_response_bytes:
            raise GatewayProtocolError("MCP index response exceeds raw byte budget")
        names = tuple(
            sorted(
                name
                for name in self._extract_index_names(payload)
                if _SAFE_INDEX_PATTERN.fullmatch(name)
                and "*" not in name
                and "?" not in name
                and fnmatchcase(name, index_pattern)
            )
        )
        if not names:
            raise GatewayProtocolError("MCP index discovery returned no matching indices")
        return names

    async def profile_fields(
        self,
        snapshot: MappingSnapshot,
        *,
        allowed_source_paths: tuple[str, ...],
        max_fields: int = 100,
        sample_value_limit: int = 5,
    ) -> FieldProfileSnapshot:
        """Collect bounded aggregate profiles; no raw document is requested or returned."""

        if not 1 <= max_fields <= 200:
            raise ValueError("max_fields must be between 1 and 200")
        if not 0 <= sample_value_limit <= 10:
            raise ValueError("sample_value_limit must be between 0 and 10")
        allowed = set(allowed_source_paths)
        grouped: dict[str, list[MappingField]] = defaultdict(list)
        for field in snapshot.fields:
            if field.source_path in allowed and field.aggregatable:
                grouped[field.source_path].append(field)
        selected = tuple(
            self._profile_variant(grouped[source_path])
            for source_path in sorted(grouped)[:max_fields]
        )
        if not selected:
            raise GatewayProtocolError("no policy-approved aggregatable fields can be profiled")
        query = self._profile_query(selected, sample_value_limit=sample_value_limit)
        tool = self._tool("execute_search")
        query_input: object = query
        if self.capabilities is not None and self.capabilities.query_dsl_mode == "string":
            query_input = json.dumps(query, ensure_ascii=False, sort_keys=True)
        response = await self.transport.call_tool(
            tool,
            {
                "index": ",".join(snapshot.indices),
                "query_dsl": query_input,
                "format": "json",
            },
        )
        payload, raw_size = self._decode(response)
        if raw_size > self.max_raw_response_bytes:
            raise GatewayProtocolError("MCP profile response exceeds raw byte budget")
        if not isinstance(payload, dict) or not isinstance(payload.get("aggregations"), dict):
            raise GatewayProtocolError("MCP profile response has no aggregations object")
        total = self._hits_total(payload)
        profiles = self._parse_profiles(
            selected,
            cast(dict[str, object], payload["aggregations"]),
            document_count=total,
        )
        captured_at = datetime.now(UTC)
        query_hash = semantic_hash(query)
        content_hash = semantic_hash(
            {
                "dataset_id": snapshot.dataset_id,
                "indices": snapshot.indices,
                "mapping_content_hash": snapshot.content_hash,
                "fields": [item.model_dump(mode="json") for item in profiles],
                "profile_query_hash": query_hash,
            }
        )
        return FieldProfileSnapshot(
            object_id=f"fps_{content_hash.removeprefix('sha256:')[:16]}",
            created_at=captured_at,
            content_hash=content_hash,
            provenance=Provenance(
                producer="semantic.profiler",
                source_ids=(snapshot.object_id,),
                source_hashes={"mapping": snapshot.content_hash},
                metadata={"transport": "mcp", "raw_size_bytes": raw_size},
            ),
            dataset_id=snapshot.dataset_id,
            captured_at=captured_at,
            indices=snapshot.indices,
            mapping_content_hash=snapshot.content_hash,
            fields=profiles,
            profile_query_hash=query_hash,
        )

    async def execute_search(self, query: CompiledQuery) -> RawSearchResult:
        tool = self._tool("execute_search")
        if self.capabilities is None:
            raise GatewayCapabilityError("MCP capability probe has not run")
        query_dsl: object = query.query_dsl
        if self.capabilities.query_dsl_mode == "string":
            query_dsl = json.dumps(query.query_dsl, ensure_ascii=False, sort_keys=True)
        response = await self.transport.call_tool(
            tool,
            {
                "index": ",".join(query.indices),
                "query_dsl": query_dsl,
                "format": "json",
            },
        )
        payload, raw_size = self._decode(response)
        if raw_size > self.max_raw_response_bytes:
            raise GatewayProtocolError("MCP response exceeds raw byte budget")
        if isinstance(payload, list):
            return RawSearchResult(
                query_id=query.object_id,
                took_ms=0,
                timed_out=False,
                shards=ShardSummary(total=0, successful=0, skipped=0, failed=0),
                hits=tuple(cast(dict[str, JsonValue], row) for row in payload),
                aggregations={},
                raw_size_bytes=raw_size,
                gateway_metadata={"transport": "mcp", "tool": tool, "format": "csv"},
            )
        if not isinstance(payload, dict):
            raise GatewayProtocolError("MCP search response is not an object")
        shards = payload.get("_shards", payload.get("shards", {}))
        if not isinstance(shards, dict):
            raise GatewayProtocolError("MCP search response has invalid shard metadata")
        hits_payload = payload.get("hits", {})
        hits: tuple[dict[str, JsonValue], ...] = ()
        hits_total: int | None = None
        if isinstance(hits_payload, dict):
            raw_hits = hits_payload.get("hits", ())
            if isinstance(raw_hits, list):
                hits = tuple(cast(dict[str, JsonValue], item) for item in raw_hits)
            total = hits_payload.get("total")
            if isinstance(total, int):
                hits_total = total
            elif isinstance(total, dict) and isinstance(total.get("value"), int):
                hits_total = total["value"]
        aggregations = payload.get("aggregations", {})
        if not isinstance(aggregations, dict):
            raise GatewayProtocolError("MCP aggregations must be an object")
        return RawSearchResult(
            query_id=query.object_id,
            took_ms=self._nonnegative_int(payload.get("took", payload.get("took_ms", 0)), "took"),
            timed_out=bool(payload.get("timed_out", False)),
            shards=ShardSummary(
                total=self._nonnegative_int(shards.get("total", 0), "shards.total"),
                successful=self._nonnegative_int(shards.get("successful", 0), "shards.successful"),
                skipped=self._nonnegative_int(shards.get("skipped", 0), "shards.skipped"),
                failed=self._nonnegative_int(shards.get("failed", 0), "shards.failed"),
            ),
            hits_total=hits_total,
            aggregations=cast(dict[str, JsonValue], aggregations),
            hits=hits,
            raw_size_bytes=raw_size,
            gateway_metadata={"transport": "mcp", "tool": tool},
        )

    async def health(self) -> GatewayHealth:
        if self.capabilities is None:
            report = await self.probe()
        else:
            report = self.capabilities
        return GatewayHealth(
            ready=report.ready,
            mode="mcp",
            details={
                "missing_capabilities": list(report.missing_capabilities),
                "query_dsl_mode": report.query_dsl_mode,
            },
        )

    @staticmethod
    def _extract_index_names(payload: object) -> set[str]:
        names: set[str] = set()
        if isinstance(payload, str):
            names.add(payload)
        elif isinstance(payload, list):
            for item in payload:
                names.update(McpOpenSearchGateway._extract_index_names(item))
        elif isinstance(payload, dict):
            for key in ("index", "index_name", "name"):
                value = payload.get(key)
                if isinstance(value, str):
                    names.add(value)
            for key in ("indices", "rows", "items", "data"):
                if key in payload:
                    names.update(McpOpenSearchGateway._extract_index_names(payload[key]))
            if not names and payload and all(isinstance(value, dict) for value in payload.values()):
                names.update(str(key) for key in payload)
        return names

    @staticmethod
    def _profile_variant(variants: list[MappingField]) -> MappingField:
        return sorted(
            variants,
            key=lambda field: (
                field.mapping_type in {"text", "match_only_text"},
                not field.is_multifield,
                field.physical_path,
            ),
        )[0]

    @staticmethod
    def _profile_query(
        fields: tuple[MappingField, ...], *, sample_value_limit: int
    ) -> dict[str, object]:
        aggregations: dict[str, object] = {}
        numeric_types = {
            "integer",
            "long",
            "short",
            "byte",
            "double",
            "float",
            "half_float",
            "scaled_float",
        }
        for position, field in enumerate(fields):
            child_aggs: dict[str, object] = {
                "cardinality": {"cardinality": {"field": field.physical_path}},
                "non_null": {"value_count": {"field": field.physical_path}},
                "missing": {"missing": {"field": field.physical_path}},
            }
            if sample_value_limit:
                child_aggs["sample_values"] = {
                    "terms": {"field": field.physical_path, "size": sample_value_limit}
                }
            if field.mapping_type in numeric_types or field.mapping_type == "date":
                child_aggs["bounds"] = {"stats": {"field": field.physical_path}}
            wrapper: dict[str, object]
            if field.nested_path:
                wrapper = {"nested": {"path": field.nested_path}, "aggs": child_aggs}
            else:
                wrapper = {"filter": {"match_all": {}}, "aggs": child_aggs}
            aggregations[f"profile_{position:03d}"] = wrapper
        return {
            "size": 0,
            "track_total_hits": True,
            "timeout": "20s",
            "query": {"match_all": {}},
            "aggs": aggregations,
        }

    @classmethod
    def _parse_profiles(
        cls,
        fields: tuple[MappingField, ...],
        aggregations: dict[str, object],
        *,
        document_count: int,
    ) -> tuple[FieldProfile, ...]:
        profiles: list[FieldProfile] = []
        for position, field in enumerate(fields):
            wrapper = aggregations.get(f"profile_{position:03d}")
            if not isinstance(wrapper, dict):
                raise GatewayProtocolError("MCP profile response omitted a requested field")
            non_null = cls._aggregation_int(wrapper, "non_null", "value")
            missing = cls._aggregation_int(wrapper, "missing", "doc_count")
            cardinality = cls._aggregation_int(wrapper, "cardinality", "value")
            samples_body = wrapper.get("sample_values", {})
            buckets = samples_body.get("buckets", ()) if isinstance(samples_body, dict) else ()
            samples: list[JsonScalar] = []
            if isinstance(buckets, list):
                for bucket in buckets:
                    if isinstance(bucket, dict) and isinstance(
                        bucket.get("key"), str | int | float | bool
                    ):
                        samples.append(cast(JsonScalar, bucket["key"]))
            bounds = wrapper.get("bounds", {})
            minimum: JsonScalar = None
            maximum: JsonScalar = None
            if isinstance(bounds, dict):
                minimum = cast(JsonScalar, bounds.get("min_as_string", bounds.get("min")))
                maximum = cast(JsonScalar, bounds.get("max_as_string", bounds.get("max")))
            profiles.append(
                FieldProfile(
                    source_path=field.source_path,
                    physical_path=field.physical_path,
                    mapping_type=field.mapping_type,
                    document_count=document_count,
                    non_null_count=non_null,
                    missing_count=missing,
                    cardinality_estimate=cardinality,
                    cardinality_approximate=True,
                    sample_values=tuple(samples),
                    minimum=minimum,
                    maximum=maximum,
                )
            )
        return tuple(profiles)

    @staticmethod
    def _aggregation_int(wrapper: dict[str, object], name: str, value_key: str) -> int:
        value = wrapper.get(name)
        raw = value.get(value_key) if isinstance(value, dict) else None
        if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
            raise GatewayProtocolError(f"MCP profile response has invalid {name}.{value_key}")
        return raw

    @staticmethod
    def _hits_total(payload: dict[str, object]) -> int:
        hits = payload.get("hits")
        total: object = hits.get("total") if isinstance(hits, dict) else None
        if isinstance(total, dict):
            total = total.get("value")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise GatewayProtocolError("MCP profile response has invalid hits.total")
        return total

    def _tool(self, capability: str) -> str:
        report = self.capabilities
        if report is None or not report.ready:
            raise GatewayCapabilityError("MCP Gateway is not ready")
        try:
            return report.resolved_bindings[capability]
        except KeyError as error:
            raise GatewayCapabilityError(f"MCP capability is unavailable: {capability}") from error

    @classmethod
    def _decode(cls, response: object) -> tuple[object, int]:
        value = cls._unwrap_content(response)
        if isinstance(value, str):
            raw_size = len(value.encode("utf-8"))
            stripped = value.strip()
            for _ in range(2):
                try:
                    decoded = json.loads(stripped)
                except json.JSONDecodeError:
                    break
                if isinstance(decoded, str):
                    stripped = decoded
                    continue
                return decoded, raw_size
            reader = csv.DictReader(io.StringIO(value))
            rows = [dict(row) for row in reader]
            if reader.fieldnames and rows:
                return rows, raw_size
            raise GatewayProtocolError("MCP text response is neither JSON nor CSV")
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return value, len(serialized.encode("utf-8"))

    @staticmethod
    def _unwrap_content(response: object) -> object:
        if isinstance(response, dict) and isinstance(response.get("content"), list):
            texts = [
                block.get("text")
                for block in response["content"]
                if isinstance(block, dict)
                and block.get("type") == "text"
                and isinstance(block.get("text"), str)
            ]
            if len(texts) != 1:
                raise GatewayProtocolError("MCP response must contain exactly one text block")
            return texts[0]
        content = getattr(response, "content", None)
        if isinstance(content, list):
            texts = [getattr(block, "text", None) for block in content]
            texts = [item for item in texts if isinstance(item, str)]
            if len(texts) != 1:
                raise GatewayProtocolError("MCP response must contain exactly one text block")
            return texts[0]
        return response

    @staticmethod
    def _nonnegative_int(value: object, name: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise GatewayProtocolError(f"MCP response has invalid {name}")
        return value
