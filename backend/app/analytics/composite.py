"""Merge all deterministic composite pages before declaring completeness."""

from __future__ import annotations

from typing import Any, cast

from app.contracts.execution import RawSearchResult, ShardSummary


class CompositeMergeError(ValueError):
    pass


class CompositeResultMerger:
    def merge(self, pages: tuple[RawSearchResult, ...]) -> RawSearchResult:
        if not pages:
            raise CompositeMergeError("at least one composite page is required")
        if len({item.query_id for item in pages}) != 1:
            raise CompositeMergeError("composite pages belong to different queries")
        root_name, first_root = self._root(pages[0])
        all_buckets: list[Any] = []
        seen: set[str] = set()
        for page in pages:
            page_root_name, root = self._root(page)
            if page_root_name != root_name:
                raise CompositeMergeError("composite root changed between pages")
            buckets = root.get("buckets")
            if not isinstance(buckets, list):
                raise CompositeMergeError("composite buckets must be an array")
            for bucket in buckets:
                if not isinstance(bucket, dict):
                    raise CompositeMergeError("composite bucket must be an object")
                key = repr(sorted(cast(dict[str, Any], bucket.get("key", {})).items()))
                if key in seen:
                    raise CompositeMergeError("duplicate composite key across pages")
                seen.add(key)
                all_buckets.append(bucket)
        last_root = self._root(pages[-1])[1]
        if first_root.get("after_key") is not None and last_root.get("after_key") is not None:
            raise CompositeMergeError("last composite page still has after_key")
        merged_root = {**first_root, "buckets": all_buckets}
        merged_root.pop("after_key", None)
        shards = ShardSummary(
            total=max(item.shards.total for item in pages),
            successful=min(item.shards.successful for item in pages),
            skipped=max(item.shards.skipped for item in pages),
            failed=max(item.shards.failed for item in pages),
        )
        return pages[0].model_copy(
            update={
                "took_ms": sum(item.took_ms for item in pages),
                "timed_out": any(item.timed_out for item in pages),
                "shards": shards,
                "aggregations": {root_name: merged_root},
                "raw_size_bytes": sum(item.raw_size_bytes for item in pages),
                "gateway_metadata": {
                    **pages[0].gateway_metadata,
                    "composite_complete": True,
                    "composite_pages": len(pages),
                },
            }
        )

    @staticmethod
    def _root(page: RawSearchResult) -> tuple[str, dict[str, Any]]:
        roots = [
            (name, value)
            for name, value in page.aggregations.items()
            if isinstance(value, dict) and "buckets" in value
        ]
        if len(roots) != 1:
            raise CompositeMergeError("expected exactly one composite root")
        return roots[0]
