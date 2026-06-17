from __future__ import annotations

import json
import os
import re
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel, Field, ValidationError

from .prompts import (
    build_answer_parse_messages,
    build_next_question_messages,
    build_question_wording_messages,
    build_requirement_extraction_messages,
)


class LLMFieldCandidate(BaseModel):
    field_name: str
    value: Any
    confidence: float = 0.8
    evidence: str = ""
    reason: str = ""


class LLMExtractionResult(BaseModel):
    candidates: list[LLMFieldCandidate] = Field(default_factory=list)
    unmapped_signals: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""


class LLMAnswerParseResult(BaseModel):
    updates: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.8
    evidence: str = ""
    reason: str = ""


class LLMQuestionWordingResult(BaseModel):
    title: str
    question: str
    why_asking: str
    answer_hints: list[str] = Field(default_factory=list)


class LLMNextQuestionResult(BaseModel):
    should_ask: bool = True
    question_id: str = ""
    title: str = ""
    question: str = ""
    question_type: str = "FREE_TEXT"
    focus_fields: list[str] = Field(default_factory=list)
    options: list[dict[str, str]] = Field(default_factory=list)
    why_asking: str = ""
    priority_score: float = 80


class LLMClient(Protocol):
    def extract_requirement(self, requirement: str, metadata_context: dict[str, Any]) -> LLMExtractionResult:
        ...

    def parse_answer(self, question: dict[str, Any], answer: str, draft_context: dict[str, Any]) -> LLMAnswerParseResult:
        ...

    def word_question(self, question: dict[str, Any], metadata_context: dict[str, Any]) -> LLMQuestionWordingResult:
        ...

    def plan_next_question(
        self,
        draft_context: dict[str, Any],
        open_fields: list[dict[str, Any]],
    ) -> LLMNextQuestionResult:
        ...

    def summarize_draft(self, draft_context: dict[str, Any]) -> str:
        ...


T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleLLMClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 45,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def extract_requirement(self, requirement: str, metadata_context: dict[str, Any]) -> LLMExtractionResult:
        return self._chat_json(
            build_requirement_extraction_messages(requirement, metadata_context),
            LLMExtractionResult,
        )

    def parse_answer(self, question: dict[str, Any], answer: str, draft_context: dict[str, Any]) -> LLMAnswerParseResult:
        return self._chat_json(
            build_answer_parse_messages(question, answer, draft_context),
            LLMAnswerParseResult,
        )

    def word_question(self, question: dict[str, Any], metadata_context: dict[str, Any]) -> LLMQuestionWordingResult:
        return self._chat_json(
            build_question_wording_messages(question, metadata_context),
            LLMQuestionWordingResult,
        )

    def plan_next_question(
        self,
        draft_context: dict[str, Any],
        open_fields: list[dict[str, Any]],
    ) -> LLMNextQuestionResult:
        return self._chat_json(
            build_next_question_messages(draft_context, open_fields),
            LLMNextQuestionResult,
        )

    def summarize_draft(self, draft_context: dict[str, Any]) -> str:
        messages = [
            {
                "role": "system",
                "content": "You summarize MDC requirement intake drafts. Return plain text only.",
            },
            {
                "role": "user",
                "content": f"Summarize this draft in one business sentence:\n{draft_context}",
            },
        ]
        content = self._chat(messages)
        return content.strip()

    def _chat_json(self, messages: list[dict[str, str]], model_type: type[T]) -> T:
        content = self._chat(messages, response_format={"type": "json_object"})
        payload = _loads_json_object(content)
        try:
            return model_type.model_validate(payload)
        except ValidationError as exc:
            raise RuntimeError(f"LLM returned JSON that does not match {model_type.__name__}: {exc}") from exc

    def _chat(self, messages: list[dict[str, str]], response_format: dict[str, str] | None = None) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
        }
        if response_format:
            body["response_format"] = response_format
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
            response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


class MockLLMClient:
    def extract_requirement(self, requirement: str, metadata_context: dict[str, Any]) -> LLMExtractionResult:
        text = requirement.lower()
        candidates: list[LLMFieldCandidate] = []

        def add(field_name: str, value: Any, confidence: float, evidence: str, reason: str) -> None:
            if any(item.field_name == field_name for item in candidates):
                return
            candidates.append(
                LLMFieldCandidate(
                    field_name=field_name,
                    value=value,
                    confidence=confidence,
                    evidence=evidence,
                    reason=reason,
                )
            )

        if any(token in text for token in ["wealth", "investment", "hase", "理财", "投资"]):
            add("line_of_business", "WPB", 0.9, "wealth/investment/理财/投资", "The requirement belongs to wealth or investment messaging.")
        if "email" in text:
            add("channel", ["EMAIL"], 0.96, "email", "The user explicitly mentioned Email.")
        elif "sms" in text:
            add("channel", ["SMS"], 0.96, "SMS", "The user explicitly mentioned SMS.")
        elif any(token in text for token in ["push", "notification", "mobile app"]):
            add("channel", ["PUSH"], 0.92, "push/mobile app", "The user requested a push-style notification.")
        elif any(token in text for token in ["mobile phone", "phone", "手机"]):
            add("channel", ["SMS"], 0.78, "mobile phone/手机", "Mobile phone implies SMS but should be confirmed.")
        if "daasc" in text:
            add("app_name", "DaaSC", 0.96, "DaaSC", "The user explicitly mentioned DaaSC.")
        if "cart" in text and ("expiry" in text or "expire" in text):
            add("use_case_name", "Investment cart expiry reminder", 0.9, "investment cart close to expiry", "Generated a concise use case name.")
            add("message_trigger_conditions", "Investment cart product close to expiry", 0.92, "close to expiry", "Extracted the trigger condition.")
        elif "mature" in text or "maturity" in text:
            add("use_case_name", "Wealth Product Maturity Reminder", 0.88, "products mature soon", "Generated a concise use case name.")
            add("message_trigger_conditions", "Customer wealth product will mature soon", 0.88, "products mature soon", "Extracted the trigger condition.")
        elif any(token in text for token in ["理财", "投资"]):
            add("use_case_name", "Wealth product message", 0.82, "理财/投资", "Generated a concise use case name from the product category.")
        if "high-risk" in text or "high risk" in text:
            add("high_risk_flag", "Y", 0.93, "high risk", "The user explicitly mentioned high risk.")
        elif "risk" not in text:
            add("high_risk_flag", "N", 0.7, "no high risk wording", "No high-risk wording was found.")
        if "real-time" in text or "realtime" in text:
            add("delivery_mode", "REALTIME", 0.9, "real-time", "The user explicitly mentioned realtime.")
        elif "batch" in text:
            add("delivery_mode", "BATCH", 0.82, "batch", "The user explicitly mentioned batch.")

        return LLMExtractionResult(
            candidates=candidates,
            summary="I extracted the business intent and any explicit field values from the requirement.",
        )

    def parse_answer(self, question: dict[str, Any], answer: str, draft_context: dict[str, Any]) -> LLMAnswerParseResult:
        text = answer.lower()
        focus_fields = question.get("focus_fields") or []
        updates: dict[str, Any] = {}

        if "channel" in focus_fields or "channel" in question.get("intent_type", ""):
            if "both" in text or ("sms" in text and "email" in text):
                updates["channel"] = ["SMS", "EMAIL"]
            elif "email" in text:
                updates["channel"] = ["EMAIL"]
            elif "sms" in text:
                updates["channel"] = ["SMS"]
            elif "push" in text:
                updates["channel"] = ["PUSH"]
        if "line_of_business" in focus_fields:
            if "wpb" in text or "wealth" in text:
                updates["line_of_business"] = "WPB"
            elif "cmb" in text:
                updates["line_of_business"] = "CMB"
        if "use_case_name" in focus_fields:
            value = _extract_labeled_value(answer, ["use case name", "name"])
            if value:
                updates["use_case_name"] = value
            elif "wealth product" in text:
                updates["use_case_name"] = "Wealth Product Maturity Reminder"

        if "project_name" in focus_fields:
            value = _extract_labeled_value(answer, ["project", "project name"])
            if value:
                updates["project_name"] = value
        if "source_system" in focus_fields:
            value = _extract_labeled_value(answer, ["source system", "source"])
            if value:
                updates["source_system"] = value.upper()
            elif "pega" in text:
                updates["source_system"] = "PEGA"
            elif "daasc" in text:
                updates["source_system"] = "DaaSC"
        if "delivery_mode" in focus_fields:
            if "time critical" in text or "timecritical" in text or "otp" in text:
                updates["delivery_mode"] = "TIMECRITICAL"
            elif "real-time" in text or "realtime" in text or "real time" in text:
                updates["delivery_mode"] = "REALTIME"
            elif "batch" in text:
                updates["delivery_mode"] = "BATCH"
        if "high_risk_flag" in focus_fields:
            if "not high risk" in text or "non-high-risk" in text or "non high risk" in text:
                updates["high_risk_flag"] = "N"
            elif "high risk" in text or "high-risk" in text:
                updates["high_risk_flag"] = "Y"
        if "message_owner" in focus_fields:
            value = _extract_labeled_value(answer, ["message owner", "owner"])
            if value:
                updates["message_owner"] = value
        if "delivery_schedule" in focus_fields:
            if "not 24" in text or "not 7*24" in text or "not 24/7" in text or "no 7*24" in text or "no 24/7" in text or "business hour" in text:
                updates["delivery_schedule"] = "N"
            elif "7*24" in text or "24/7" in text or "24x7" in text:
                updates["delivery_schedule"] = "Y"
        if "message_trigger_conditions" in focus_fields:
            value = _extract_labeled_value(answer, ["trigger", "condition", "business event"])
            updates["message_trigger_conditions"] = value or answer.strip()
        if "app_name" in focus_fields:
            if "daasc" in text:
                updates["app_name"] = "DaaSC"
            elif "investex" in text:
                updates["app_name"] = "InvestEx"
            elif "dbb" in text:
                updates["app_name"] = "DBB"
        if "sender" in focus_fields:
            value = _extract_labeled_value(answer, ["sender", "sender id", "sender address"])
            if value:
                updates["sender"] = value
        if "cost_center_id" in focus_fields:
            value = _extract_labeled_value(answer, ["cost center", "cost center id"])
            if value:
                updates["cost_center_id"] = value

        return LLMAnswerParseResult(
            updates=updates,
            confidence=0.9 if updates else 0.45,
            evidence=answer,
            reason="Parsed the answer into focused field updates.",
        )

    def word_question(self, question: dict[str, Any], metadata_context: dict[str, Any]) -> LLMQuestionWordingResult:
        focus = question.get("focus_fields") or []
        field_hint = metadata_context.get("business_hint", "")
        title = question.get("title") or "Confirm details"
        raw_question = question.get("question") or "Please provide the required details."
        if "message_trigger_conditions" in focus:
            title = "Confirm trigger"
            raw_question = "What business event should trigger this message?"
        elif "sender_name" in focus:
            raw_question = "Which email sender name should be shown to the customer?"
        elif "sender" in focus:
            raw_question = "What sender ID, sender address, or sender domain should be used for this channel?"
        elif "router" in focus:
            raw_question = "Which router or vendor path should be used for the selected channel?"
        return LLMQuestionWordingResult(
            title=title,
            question=raw_question,
            why_asking=question.get("why_asking") or field_hint or "This is needed to complete the use case.",
            answer_hints=[field_hint] if field_hint else [],
        )

    def plan_next_question(
        self,
        draft_context: dict[str, Any],
        open_fields: list[dict[str, Any]],
    ) -> LLMNextQuestionResult:
        if not open_fields:
            return LLMNextQuestionResult(should_ask=False)
        channel = next((field for field in open_fields if field["field_name"] == "channel"), None)
        if channel and (not channel.get("value") or channel.get("requires_confirmation")):
            return LLMNextQuestionResult(
                question_id="q_channel_confirm",
                title="Confirm delivery channel",
                question="Which channel should be used for this message?",
                question_type="SINGLE_CHOICE",
                focus_fields=["channel"],
                options=[
                    {"label": "SMS", "value": "SMS"},
                    {"label": "Email", "value": "EMAIL"},
                    {"label": "Mobile Push", "value": "PUSH"},
                    {"label": "SMS + Email", "value": "SMS,EMAIL"},
                ],
                why_asking="Channel must be clear before sender setup and routing fields are finalized.",
                priority_score=100,
            )

        trigger_and_basic = [
            field["field_name"]
            for field in open_fields
            if field["field_name"] in {"message_trigger_conditions", "project_name", "source_system", "delivery_mode", "message_owner", "delivery_schedule"}
        ]
        if "message_trigger_conditions" in trigger_and_basic:
            return LLMNextQuestionResult(
                question_id="q_trigger_and_basic_setup",
                title="Confirm trigger and setup",
                question=(
                    "When should this message be sent, and can you share any known setup details "
                    "such as project name, source system, delivery mode, message owner, or 7*24 requirement?"
                ),
                question_type="FREE_TEXT",
                focus_fields=trigger_and_basic,
                why_asking="One answer can fill the trigger and several setup fields before we move to channel-specific details.",
                priority_score=95,
            )

        push_setup = [
            field["field_name"]
            for field in open_fields
            if field["field_name"] in {"app_name", "sender", "router"}
        ]
        if push_setup:
            return LLMNextQuestionResult(
                question_id="q_push_setup",
                title="Confirm push setup",
                question="For this push message, which app should receive it, and do you already know the sender or router setup?",
                question_type="FREE_TEXT",
                focus_fields=push_setup,
                why_asking="Push setup fields are related, so one answer can complete several channel details.",
                priority_score=92,
            )

        sms_setup = [
            field["field_name"]
            for field in open_fields
            if field["field_name"] in {"sender", "cost_center_id", "Send_to_China_flag"}
        ]
        if sms_setup:
            return LLMNextQuestionResult(
                question_id="q_sms_setup",
                title="Confirm SMS setup",
                question="For SMS delivery, what sender ID and cost center should be used, and does it need to send to China numbers?",
                question_type="FREE_TEXT",
                focus_fields=sms_setup,
                why_asking="These SMS setup values are related and can be confirmed together.",
                priority_score=90,
            )

        basic_setup = [
            field["field_name"]
            for field in open_fields
            if field["field_name"] in {"project_name", "source_system", "delivery_mode", "message_owner", "delivery_schedule"}
        ]
        if basic_setup:
            return LLMNextQuestionResult(
                question_id="q_basic_setup",
                title="Confirm basic setup",
                question="Please share the project name, source system, delivery mode, message owner, and 7*24 requirement if you know them.",
                question_type="FREE_TEXT",
                focus_fields=basic_setup,
                why_asking="These fields describe ownership and operating setup, so they are easier to confirm together.",
                priority_score=85,
            )

        field = open_fields[0]
        display_name = field.get("display_name") or field["field_name"]
        return LLMNextQuestionResult(
            question_id=f"q_{field['field_name']}",
            title=f"Confirm {display_name}",
            question=f"Please provide {display_name}.",
            question_type="FREE_TEXT",
            focus_fields=[field["field_name"]],
            why_asking=field.get("help") or f"{display_name} is required for this setup.",
            priority_score=80,
        )

    def summarize_draft(self, draft_context: dict[str, Any]) -> str:
        master = draft_context.get("use_case_master", {})
        rules = draft_context.get("use_case_channel_rule_list", [])
        lob = master.get("line_of_business", "LOB pending")
        name = master.get("use_case_name", "use case")
        channels = ", ".join(rule.get("channel", "") for rule in rules) or "channel pending"
        return f"{lob} {name} delivered by {channels}."


def create_llm_client() -> LLMClient:
    provider = os.getenv("INTAKE_LLM_PROVIDER", "mock").lower()
    if provider == "openai_compatible":
        base_url = os.getenv("INTAKE_LLM_BASE_URL")
        api_key = os.getenv("INTAKE_LLM_API_KEY")
        model = os.getenv("INTAKE_LLM_MODEL")
        if not base_url or not api_key or not model:
            raise RuntimeError("INTAKE_LLM_BASE_URL, INTAKE_LLM_API_KEY, and INTAKE_LLM_MODEL are required.")
        return OpenAICompatibleLLMClient(base_url=base_url, api_key=api_key, model=model)
    return MockLLMClient()


def _extract_labeled_value(text: str, labels: list[str]) -> str:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*(?:is|=|:)\s*([^,;.，。]+)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _loads_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("LLM response must be a JSON object.")
    return value
