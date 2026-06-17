from __future__ import annotations

from typing import Any


JSON_ONLY_SYSTEM = (
    "You are an expert AI copilot for MDC requirement intake. "
    "You convert business language into structured use-case fields. "
    "Return valid JSON only. Do not include markdown, commentary, or extra keys."
)


def build_requirement_extraction_messages(requirement: str, metadata_context: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": JSON_ONLY_SYSTEM},
        {
            "role": "user",
            "content": (
                "Task: extract all fields that can be confidently inferred from the user's requirement.\n"
                "Do not ask follow-up questions here. Do not invent values.\n"
                "If the user explicitly mentions a channel such as SMS, Email, Push, WeChat, or Letter, extract it.\n"
                "If the user implies a channel indirectly, extract it with lower confidence and explain the evidence.\n"
                "Use only field_name values from the metadata.\n\n"
                "Output JSON schema:\n"
                "{\n"
                '  "candidates": [\n'
                '    {"field_name": "string", "value": "string | string[] | number | boolean", "confidence": 0.0, "evidence": "short quote or paraphrase", "reason": "why this maps to the field"}\n'
                "  ],\n"
                '  "unmapped_signals": {"signal_name": "value"},\n'
                '  "summary": "one sentence summary of understood business intent"\n'
                "}\n\n"
                f"Field metadata:\n{metadata_context}\n\n"
                f"Requirement:\n{requirement}"
            ),
        },
    ]


def build_answer_parse_messages(
    question: dict[str, Any],
    answer: str,
    draft_context: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": JSON_ONLY_SYSTEM},
        {
            "role": "user",
            "content": (
                "Task: parse the user's latest answer into direct user-facing field updates.\n"
                "Only update fields related to the active question focus_fields unless the answer explicitly corrects another field.\n"
                "Do not include hidden dependency-derived fields; those are handled by the dependency engine later.\n"
                "Normalize channel values to an array using uppercase values, for example [\"SMS\"] or [\"SMS\", \"EMAIL\"].\n\n"
                "Output JSON schema:\n"
                "{\n"
                '  "updates": {"field_name": "value"},\n'
                '  "confidence": 0.0,\n'
                '  "evidence": "short quote or paraphrase from answer",\n'
                '  "reason": "why the update is safe to preview"\n'
                "}\n\n"
                f"Active question:\n{question}\n\n"
                f"Current draft context:\n{draft_context}\n\n"
                f"User answer:\n{answer}"
            ),
        },
    ]


def build_question_wording_messages(
    question: dict[str, Any],
    metadata_context: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": JSON_ONLY_SYSTEM},
        {
            "role": "user",
            "content": (
                "Task: rewrite the next assistant question so it is clear, business-friendly, and concise.\n"
                "Do not expose internal dependency rules or hidden fields.\n"
                "Keep the same question_id, focus_fields, and intent; only improve wording.\n\n"
                "Output JSON schema:\n"
                "{\n"
                '  "title": "short title",\n'
                '  "question": "direct question to the business user",\n'
                '  "why_asking": "business reason visible to the user",\n'
                '  "answer_hints": ["optional concise hint"]\n'
                "}\n\n"
                f"Question draft:\n{question}\n\n"
                f"Metadata context:\n{metadata_context}"
            ),
        },
    ]


def build_next_question_messages(
    draft_context: dict[str, Any],
    open_fields: list[dict[str, Any]],
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": JSON_ONLY_SYSTEM},
        {
            "role": "user",
            "content": (
                "Task: choose the single best next assistant question for guided requirement intake.\n"
                "A good question may cover multiple related fields in one natural business prompt.\n"
                "Group fields when they belong to the same user intent, for example basic setup, trigger/audience, channel setup, sender/routing, or launch governance.\n"
                "Prioritize groups that unblock user-facing understanding: channel, audience, trigger, owner, sender setup.\n"
                "If a field was explicitly extracted from the user's requirement with high confidence, do not ask it again.\n"
                "If a field is low confidence or conflicts with a reference use case, ask it before dependent setup fields.\n"
                "Do not ask for hidden or not-applicable fields.\n\n"
                "Output JSON schema:\n"
                "{\n"
                '  "should_ask": true,\n'
                '  "question_id": "q_field_name",\n'
                '  "title": "short title",\n'
                '  "question": "question to ask user",\n'
                '  "question_type": "FREE_TEXT | SINGLE_CHOICE",\n'
                '  "focus_fields": ["one_or_more_related_field_names"],\n'
                '  "options": [{"label": "string", "value": "string"}],\n'
                '  "why_asking": "visible business reason",\n'
                '  "priority_score": 0\n'
                "}\n\n"
                f"Current draft context:\n{draft_context}\n\n"
                f"Open user-facing fields:\n{open_fields}"
            ),
        },
    ]
