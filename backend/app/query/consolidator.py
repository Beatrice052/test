"""Merge only logically identical steps; dependent or incompatible steps remain separate."""

from app.contracts.query import QueryStep


class QueryConsolidator:
    def consolidate(self, steps: tuple[QueryStep, ...]) -> tuple[QueryStep, ...]:
        consolidated: list[QueryStep] = []
        for step in steps:
            match = next(
                (
                    existing
                    for existing in consolidated
                    if self._merge_key(existing) == self._merge_key(step)
                    and not existing.depends_on
                    and not step.depends_on
                ),
                None,
            )
            if match is None:
                consolidated.append(step)
                continue
            index = consolidated.index(match)
            consolidated[index] = match.model_copy(
                update={
                    "purpose_task_ids": tuple(
                        dict.fromkeys((*match.purpose_task_ids, *step.purpose_task_ids))
                    ),
                    "measures": tuple(dict.fromkeys((*match.measures, *step.measures))),
                    "field_measures": tuple(
                        dict.fromkeys((*match.field_measures, *step.field_measures))
                    ),
                    "estimated_buckets": max(match.estimated_buckets, step.estimated_buckets),
                    "required": match.required or step.required,
                }
            )
        return tuple(consolidated)

    @staticmethod
    def _merge_key(step: QueryStep) -> tuple[object, ...]:
        return (
            step.dataset_id,
            step.index_patterns,
            step.time_range,
            step.time_field_id,
            step.filters,
            step.dimensions,
            step.grain,
            step.timeout_ms,
        )
