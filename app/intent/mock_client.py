from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.agent.contracts import (
    AnalysisPlan,
    AnalysisType,
    FilterConcept,
    RequestedOutput,
    TimeRange,
)
from app.config.settings import Settings
from app.intent.models import ConversationContext, IntentOutcome


class MockLLMClient:
    """Deterministic external-network intent adapter.

    It deliberately recognizes a bounded POC language and emits the same
    AnalysisPlan contract that a later internal structured-output LLM must use.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_analysis_plan(self, question: str, context: ConversationContext) -> IntentOutcome:
        normalized = question.strip()
        lowered = normalized.casefold()

        if context.pending_missing_slot is None and self._is_ambiguous_failure_request(lowered):
            return IntentOutcome(
                clarification_question="你希望按Channel、Route还是日期趋势查看失败情况？",
                clarification_slot="breakdown_dimension",
                clarification_choices=["channel", "route", "date_trend"],
            )

        time_range, used_default = self._parse_time_range(normalized)
        warnings = ["DEFAULT_TIME_RANGE"] if used_default else []

        metric_concepts: list[str] = []
        carrier_specific = any(
            token in normalized
            for token in [
                "中国移动",
                "移动",
                "中国电信",
                "电信",
                "中国联通",
                "联通",
            ]
        )
        if carrier_specific and ("failure rate" in lowered or "失败率" in normalized):
            metric_concepts.append("carrier_failure_rate")
        elif "failure rate" in lowered or "失败率" in normalized:
            metric_concepts.append("failure_rate")
        if "sla" in lowered:
            metric_concepts.append("sla")

        dimension_concepts: list[str] = []
        explicit_status_code = "statuscode" in lowered or "status_code" in lowered
        explicit_status = bool(
            re.search(
                r"(?<![A-Za-z0-9_])status(?![A-Za-z0-9_])",
                normalized,
                re.IGNORECASE,
            )
        )
        if "状态分布" in normalized or "按状态" in normalized:
            if explicit_status_code:
                dimension_concepts.append("statusCode")
            elif explicit_status:
                dimension_concepts.append("status")
            else:
                dimension_concepts.append("ambiguous_status")
        if (
            "channel" in lowered
            or "渠道" in normalized
            or self._contains_multiple_channels(normalized)
        ):
            dimension_concepts.append("channel")
        if "route" in lowered or "路由" in normalized:
            dimension_concepts.append("route")
        if any(token in normalized for token in ["每天", "每日", "日趋势", "按日期"]):
            dimension_concepts.append("date")
        if "不存在字段" in normalized or "nonexistent" in lowered:
            dimension_concepts.append("nonexistentField")
        if "消息正文" in normalized or "message body" in lowered:
            dimension_concepts.append("messageBody")

        filters: list[FilterConcept] = []
        channels = self._extract_channels(normalized)
        if channels:
            channel_values: list[str | int | float | bool | None] = list(channels)
            filters.append(FilterConcept(concept="channel", operator="in", values=channel_values))
        if any(token in normalized for token in ["失败记录", "失败情况"]) and not metric_concepts:
            filters.append(
                FilterConcept(
                    concept="status",
                    operator="in",
                    values=["FAILED", "ACKFAIL"],
                )
            )
        if "空结果" in normalized or "不存在的渠道" in normalized:
            filters.append(
                FilterConcept(
                    concept="channel",
                    operator="eq",
                    values=["__NO_MATCH__"],
                )
            )

        analysis_type = self._analysis_type(normalized, metric_concepts, dimension_concepts)
        requested_outputs = self._requested_outputs(analysis_type)
        comparison: dict[str, Any] | None = None
        if "同时" in normalized and "趋势" in normalized and "top" in lowered:
            if "channel" not in dimension_concepts:
                dimension_concepts.append("channel")
            comparison = {
                "additional_analysis": {
                    "query_type": "top_n",
                    "dimension": "channel",
                    "size": 10,
                }
            }

        return IntentOutcome(
            plan=AnalysisPlan(
                analysis_type=analysis_type,
                dataset_concept="sub_message",
                metric_concepts=metric_concepts,
                dimension_concepts=self._dedupe(dimension_concepts),
                filter_concepts=filters,
                time_range=time_range,
                comparison=comparison,
                requested_outputs=requested_outputs,
            ),
            warnings=warnings,
        )

    def summarize(self, question: str, prepared_data: dict, caveats: list[str]) -> str:
        rows = prepared_data.get("rows", [])
        totals = prepared_data.get("totals", {})
        if not rows and not totals:
            return "当前条件下没有数据。"
        if "failure_rate" in totals:
            rate = totals["failure_rate"]
            rendered = "无可计算值" if rate is None else f"{rate:.2f}%"
            return f"当前口径下总体 Failure Rate 为 {rendered}。"
        if "total_count" in totals:
            return f"当前条件下共有 {totals['total_count']} 条 OpenSearch 记录。"
        if rows:
            return f"已按请求生成 {len(rows)} 行分析结果。"
        return "分析已完成。"

    def _parse_time_range(self, question: str) -> tuple[TimeRange, bool]:
        timezone = ZoneInfo(self.settings.business_timezone)
        chinese_date_range = re.search(
            r"(\d{4})年(\d{1,2})月(\d{1,2})日"
            r"(?:\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?"
            r"\s*(?:至|到|~|—)\s*"
            r"(\d{4})年(\d{1,2})月(\d{1,2})日"
            r"(?:\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
            question,
        )
        if chinese_date_range:
            start = self._matched_datetime(chinese_date_range, 1, timezone)
            end = self._matched_datetime(chinese_date_range, 7, timezone)
            if chinese_date_range.group(10) is None:
                end += timedelta(days=1)
            return self._time_range(start, end, "absolute_date_range"), False

        iso_date_range = re.search(
            r"(\d{4})-(\d{1,2})-(\d{1,2})"
            r"(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?"
            r"\s*(?:至|到|~|—)\s*"
            r"(\d{4})-(\d{1,2})-(\d{1,2})"
            r"(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?",
            question,
        )
        if iso_date_range:
            start = self._matched_datetime(iso_date_range, 1, timezone)
            end = self._matched_datetime(iso_date_range, 7, timezone)
            if iso_date_range.group(10) is None:
                end += timedelta(days=1)
            return self._time_range(start, end, "absolute_date_range"), False

        range_match = re.search(
            r"(?:(\d{4})年)?(\d{1,2})月(?:\s*(?:至|到|-)\s*(?:(\d{4})年)?(\d{1,2})月)",
            question,
        )
        if range_match:
            start_year = int(range_match.group(1) or 2026)
            start_month = int(range_match.group(2))
            end_year = int(range_match.group(3) or start_year)
            end_month = int(range_match.group(4))
            start = datetime(start_year, start_month, 1, tzinfo=timezone)
            end = self._next_month(datetime(end_year, end_month, 1, tzinfo=timezone))
            return self._time_range(start, end, "absolute_month_range"), False

        chinese_date = re.search(
            r"(\d{4})年(\d{1,2})月(\d{1,2})日",
            question,
        )
        if chinese_date:
            start = datetime(
                int(chinese_date.group(1)),
                int(chinese_date.group(2)),
                int(chinese_date.group(3)),
                tzinfo=timezone,
            )
            return self._time_range(start, start + timedelta(days=1), "absolute_date"), False

        iso_date = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", question)
        if iso_date:
            start = datetime(
                int(iso_date.group(1)),
                int(iso_date.group(2)),
                int(iso_date.group(3)),
                tzinfo=timezone,
            )
            return self._time_range(start, start + timedelta(days=1), "absolute_date"), False

        month_match = re.search(r"(?:(\d{4})年)?(\d{1,2})月", question)
        if month_match:
            year = int(month_match.group(1) or 2026)
            month = int(month_match.group(2))
            start = datetime(year, month, 1, tzinfo=timezone)
            return self._time_range(start, self._next_month(start), "absolute_month"), False

        return (
            self._time_range(
                self.settings.default_time_from,
                self.settings.default_time_to,
                "configured_default",
            ),
            True,
        )

    @staticmethod
    def _time_range(start: datetime, end: datetime, range_type: str) -> TimeRange:
        return TimeRange(
            type=range_type,
            **{"from": start, "to": end},
            grain="day",
        )

    @staticmethod
    def _next_month(value: datetime) -> datetime:
        if value.month == 12:
            return value.replace(year=value.year + 1, month=1)
        return value.replace(month=value.month + 1)

    @staticmethod
    def _matched_datetime(match: re.Match[str], offset: int, timezone: ZoneInfo) -> datetime:
        return datetime(
            int(match.group(offset)),
            int(match.group(offset + 1)),
            int(match.group(offset + 2)),
            int(match.group(offset + 3) or 0),
            int(match.group(offset + 4) or 0),
            int(match.group(offset + 5) or 0),
            tzinfo=timezone,
        )

    @staticmethod
    def _is_ambiguous_failure_request(lowered: str) -> bool:
        return "最近的失败情况" in lowered or "看看失败情况" in lowered

    @staticmethod
    def _extract_channels(question: str) -> list[str]:
        lowered = question.casefold()
        channels: list[str] = []
        if "sms" in lowered:
            channels.append("SMS")
        if "email" in lowered:
            channels.append("Email")
        if "whatsapp" in lowered:
            channels.append("WhatsApp")
        return channels

    @classmethod
    def _contains_multiple_channels(cls, question: str) -> bool:
        return len(cls._extract_channels(question)) > 1

    @staticmethod
    def _analysis_type(
        question: str,
        metrics: list[str],
        dimensions: list[str],
    ) -> AnalysisType:
        lowered = question.casefold()
        has_date = "date" in dimensions
        if metrics:
            if has_date:
                return AnalysisType.METRIC_TREND
            if dimensions:
                return AnalysisType.METRIC_BREAKDOWN
            return AnalysisType.METRIC_SUMMARY
        if "top" in lowered or "最多" in question:
            return AnalysisType.TOP_N
        if has_date:
            return AnalysisType.DATE_HISTOGRAM
        if dimensions:
            return AnalysisType.TERMS_BREAKDOWN
        if any(token in question for token in ["数量", "多少", "一共", "总记录"]):
            return AnalysisType.COUNT
        return AnalysisType.COUNT

    @staticmethod
    def _requested_outputs(analysis_type: AnalysisType) -> list[RequestedOutput]:
        if analysis_type in {AnalysisType.COUNT, AnalysisType.METRIC_SUMMARY}:
            return [RequestedOutput.KPI, RequestedOutput.SUMMARY]
        return [
            RequestedOutput.TABLE,
            RequestedOutput.CHART,
            RequestedOutput.SUMMARY,
        ]

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))
