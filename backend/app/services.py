from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .models import (
    ActionPreviewUpdate,
    ActiveQuestionState,
    AnalyzeRequirementResponse,
    AssistantCard,
    BlockingIssue,
    BuildDraftRequest,
    BuildDraftResponse,
    ExtractedSignals,
    FieldCandidate,
    FormField,
    FormModule,
    GuidedDraftState,
    GuidedFieldState,
    GuidedIntakeSession,
    InternalImpact,
    InternalImpactPlan,
    ParseAnswerResponse,
    ReferenceUseCase,
    StoredActionPreview,
    UseCaseDomainDraft,
    UseCaseCandidate,
    ValidationResult,
    now_utc,
)
from .llm import LLMClient, create_llm_client


CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


MODULE_MAP = {
    "Basic Info": ("business", "Business Context"),
    "Extension Info": ("audience", "Audience & Trigger"),
    "Delivery Channel": ("channel", "Channel & Content"),
    "Opt-In Flag": ("compliance", "Compliance & Launch"),
    "Bounce Back": ("compliance", "Compliance & Launch"),
}


SOURCE_TO_FRONTEND = {
    "EMPTY": "Default",
    "USER_CONFIRMED": "User confirmed",
    "USER_INPUT": "User confirmed",
    "REQUIREMENT_EXTRACTION": "From requirement",
    "REFERENCE_USE_CASE": "From reference",
    "DEFAULT": "Default",
    "DEPENDENCY_DERIVED": "Default",
    "SYSTEM_GENERATED": "Default",
}


STATUS_TO_FRONTEND = {
    "EMPTY": "Optional",
    "PREFILLED": "AI Prefilled",
    "CONFIRMED": "Confirmed",
    "NEEDS_CONFIRMATION": "Needs Confirmation",
    "CONFLICT": "Needs Confirmation",
    "MISSING_REQUIRED": "Missing Required",
    "NOT_APPLICABLE": "Not Applicable",
    "GENERATED": "AI Prefilled",
}


class MetadataRegistry:
    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self.config_dir = config_dir
        self.metadata: dict[str, Any] = {}
        self.rules: dict[str, Any] = {}
        self.fields_by_name: dict[str, dict[str, Any]] = {}
        self.fields_by_module: dict[str, list[dict[str, Any]]] = {}

    def load(self) -> None:
        self.metadata = json.loads((self.config_dir / "use_case_metadata.json").read_text(encoding="utf-8"))
        self.rules = json.loads((self.config_dir / "dependency_rules.json").read_text(encoding="utf-8"))
        fields = self.metadata.get("fields", [])
        if len(fields) != 33:
            raise RuntimeError(f"Expected 33 metadata fields, got {len(fields)}")
        for field in fields:
            self.fields_by_name[field["field_name"]] = field
            self.fields_by_module.setdefault(field["module"], []).append(field)

    def get_field(self, field_name: str) -> dict[str, Any]:
        return self.fields_by_name[field_name]

    def get_all_fields(self) -> list[dict[str, Any]]:
        return list(self.fields_by_name.values())

    def get_option_set(self, option_set_name: str | None) -> list[dict[str, Any]]:
        if not option_set_name:
            return []
        value = self.metadata.get("option_sets", {}).get(option_set_name, [])
        return value if isinstance(value, list) else []

    def options_for_field(self, field_name: str) -> list[dict[str, Any]]:
        field = self.fields_by_name.get(field_name)
        if not field:
            return []
        option_set_name = field.get("options_ref") or field.get("option_set")
        options = self.get_option_set(option_set_name)
        if options:
            return options
        inline = field.get("options")
        return inline if isinstance(inline, list) else []

    def answer_hint(self, field_name: str) -> str:
        field = self.fields_by_name[field_name]
        guidance = field.get("answer_guidance") or {}
        return guidance.get("business_hint") or field.get("business_description") or ""

    def llm_context(self) -> dict[str, Any]:
        fields: list[dict[str, Any]] = []
        for field in self.get_all_fields():
            fields.append(
                {
                    "field_name": field["field_name"],
                    "display_name": field["display_name"],
                    "module": field["module"],
                    "domain_object": field["domain_object"],
                    "required_level": field.get("required_level"),
                    "business_description": field.get("business_description", ""),
                    "answer_guidance": field.get("answer_guidance", {}),
                    "option_set": self.options_for_field(field["field_name"]),
                }
            )
        return {"fields": fields, "option_sets": self.metadata.get("option_sets", {})}


class QuestionGroupConfigRegistry:
    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self.config_dir = config_dir
        self.config: dict[str, Any] = {}
        self.groups: list[dict[str, Any]] = []
        self.groups_by_id: dict[str, dict[str, Any]] = {}

    def load(self) -> None:
        path = self.config_dir / "question_group_config.json"
        self.config = json.loads(path.read_text(encoding="utf-8"))
        self.groups = self.config.get("question_groups", [])
        self.groups_by_id = {group["group_id"]: group for group in self.groups}

    def get_groups(self) -> list[dict[str, Any]]:
        return self.groups

    def get_group(self, group_id: str) -> dict[str, Any]:
        return self.groups_by_id[group_id]

    def groups_for_field(self, field_name: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for group in self.groups:
            fields = set(group.get("focus_fields", [])) | set(group.get("related_fields", []))
            if field_name in fields:
                result.append(group)
        return result


class SessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[str, GuidedIntakeSession] = {}

    def save(self, session: GuidedIntakeSession) -> GuidedIntakeSession:
        session.updated_at = now_utc()
        self.sessions[session.intake_id] = session
        return session

    def get(self, intake_id: str) -> GuidedIntakeSession:
        if intake_id not in self.sessions:
            raise KeyError(f"Unknown intake_id: {intake_id}")
        return self.sessions[intake_id]


class ReferenceUseCaseRepository:
    def get(self, reference_id: str) -> dict[str, Any]:
        # MVP seed data. Replace this with real historical-use-case lookup later.
        if reference_id not in {"M1004", "REF-001", "RDP004"}:
            raise KeyError(f"Unknown reference use case: {reference_id}")
        return {
            "id": "M1004",
            "name": "RDP 004",
            "source_system": "PEGA",
            "line_of_business": "WPB",
            "use_case_name": "Investment cart expiry reminder",
            "project_name": "Investment cart expiry reminder",
            "message_trigger_conditions": "Investment products in HASE mobile app cart are close to expiry",
            "delivery_mode": "BATCH",
            "delivery_schedule": "Event based",
            "high_risk_flag": "N",
            "channel": ["SMS"],
            "priority": "0",
            "router": "HTCL_SVC_RT_SMS",
            "sender": "HASE",
            "cost_center_id": "25267613",
            "Send_to_China_flag": "N",
            "push_optin_flag": "Y",
        }

    def search_candidates(self, requirement: str, signals: ExtractedSignals) -> list[UseCaseCandidate]:
        # MVP mock retrieval. Replace with vector/SQL/metadata retrieval in the intranet backend.
        channel = signals.channel or "SMS"
        return [
            UseCaseCandidate(
                id="M1004",
                name="RDP 004",
                project="Investment cart expiry reminder",
                source_system="PEGA",
                lob=signals.lob or "WPB",
                channel="SMS",
                similarity="0.86",
                badge="Best match",
                reason="Same LOB and similar investment product expiry trigger. Historical channel is SMS, so channel needs user confirmation.",
            ),
            UseCaseCandidate(
                id="M2031",
                name="RDP 031",
                project="Wealth product maturity reminder",
                source_system="PEGA",
                lob=signals.lob or "WPB",
                channel=channel,
                similarity="0.72",
                badge="Possible match",
                reason="Related wealth product lifecycle reminder, but less aligned with HASE mobile app cart behavior.",
            ),
        ]


class RequirementExtractor:
    def __init__(self, llm: LLMClient, metadata: MetadataRegistry) -> None:
        self.llm = llm
        self.metadata = metadata

    def extract(self, requirement: str) -> tuple[list[FieldCandidate], ExtractedSignals]:
        llm_result = self.llm.extract_requirement(requirement, self.metadata.llm_context())
        candidates: list[FieldCandidate] = []

        for item in llm_result.candidates:
            if item.field_name not in self.metadata.fields_by_name:
                continue
            candidates.append(
                FieldCandidate(
                    field_name=item.field_name,
                    value=item.value,
                    normalized_value=item.value,
                    confidence=item.confidence,
                    source="REQUIREMENT_EXTRACTION",
                    evidence=item.evidence,
                    reason=item.reason or f"Detected from requirement: {item.evidence}",
                )
            )

        channel = next((c.value[0] for c in candidates if c.field_name == "channel" and c.value), None)
        lob = next((c.value for c in candidates if c.field_name == "line_of_business" and c.value), None)
        signals = ExtractedSignals(
            lob=lob,
            channel=channel,
            trigger=next((c.value for c in candidates if c.field_name == "message_trigger_conditions"), None),
            audience=llm_result.unmapped_signals.get("audience"),
        )
        return candidates, signals


class FieldStateBuilder:
    def __init__(self, metadata: MetadataRegistry) -> None:
        self.metadata = metadata

    def empty_states(self) -> dict[str, GuidedFieldState]:
        states: dict[str, GuidedFieldState] = {}
        for field in self.metadata.get_all_fields():
            required = field.get("required_level") == "Required"
            field_name = field["field_name"]
            states[field_name] = GuidedFieldState(
                field_name=field_name,
                display_name=field["display_name"],
                module=field["module"],
                domain_object=field["domain_object"],
                scope=field["scope"],
                required=required,
                required_now=required,
                applicable=not field.get("ui_behavior", {}).get("hide_when_not_applicable", False)
                or field["module"] in {"Basic Info", "Extension Info"},
                ui_status="MISSING_REQUIRED" if required else "EMPTY",
                resolution_status="UNRESOLVED_MISSING" if required else "RESOLVED",
                help=self.metadata.answer_hint(field_name),
                hidden=False,
            )
        return states

    def apply_candidate(self, states: dict[str, GuidedFieldState], candidate: FieldCandidate) -> None:
        state = states.get(candidate.field_name)
        if not state:
            return
        state.value = candidate.value
        state.normalized_value = candidate.normalized_value or candidate.value
        state.source = "REQUIREMENT_EXTRACTION" if candidate.source == "REQUIREMENT_EXTRACTION" else "REFERENCE_USE_CASE"
        state.ui_status = "PREFILLED"
        state.resolution_status = "RESOLVED_NEEDS_CONFIRMATION"
        state.requires_confirmation = candidate.confidence < 0.9
        state.applicable = True
        state.hidden = False
        state.business_reason = candidate.reason


class DependencyRuleEngine:
    CHANNEL_FIELDS = {
        "priority",
        "router",
        "tag",
        "Send_to_China_flag",
        "traffic_percentage",
        "sender",
        "sender_name",
        "app_name",
        "cost_center_id",
    }

    def __init__(self, metadata: MetadataRegistry) -> None:
        self.metadata = metadata

    def resolve(self, draft: GuidedDraftState) -> GuidedDraftState:
        states = deepcopy(draft.field_states)
        impacts = InternalImpactPlan()
        channels = normalize_channels(states.get("channel").value if states.get("channel") else None)

        for field_name in self.CHANNEL_FIELDS:
            if field_name in states:
                self._set_applicable(states[field_name], False, impacts, "CHANNEL_FIELD_DEFAULT_HIDDEN")

        if channels:
            for field_name in ["priority", "router"]:
                self._set_applicable(states[field_name], True, impacts, "CHANNEL_REQUIRES_CORE_FIELDS")
                self._set_required(states[field_name], True, impacts, "CHANNEL_REQUIRES_CORE_FIELDS")

        if "SMS" in channels:
            for field_name in ["cost_center_id", "Send_to_China_flag", "sender"]:
                self._set_applicable(states[field_name], True, impacts, "SMS_REQUIRED_FIELDS")
                self._set_required(states[field_name], True, impacts, "SMS_REQUIRED_FIELDS")
            self._suggest_if_empty(states["router"], "HTCL_SVC_RT_SMS", "SMS_ROUTER_RECOMMENDATION")
            if states["router"].value and "SMS" not in str(states["router"].value).upper():
                self._set_value(states["router"], "HTCL_SVC_RT_SMS", impacts, "SMS_ROUTER_RECOMMENDATION")
            self._suggest_if_empty(states["priority"], "0", "PRIORITY_REQUIRED_FOR_SELECTED_CHANNEL")
            self._suggest_if_empty(states["Send_to_China_flag"], "N", "SMS_REQUIRES_SEND_TO_CHINA_FLAG")

        if "EMAIL" in channels:
            for field_name in ["sender", "sender_name"]:
                self._set_applicable(states[field_name], True, impacts, "EMAIL_REQUIRED_FIELDS")
                self._set_required(states[field_name], True, impacts, "EMAIL_REQUIRED_FIELDS")
            self._suggest_if_empty(states["router"], "PFP_EU_EMAIL", "EMAIL_ROUTER_RECOMMENDATION")
            if states["router"].value and "EMAIL" not in str(states["router"].value).upper():
                self._set_value(states["router"], "PFP_EU_EMAIL", impacts, "EMAIL_ROUTER_RECOMMENDATION")
            self._suggest_if_empty(states["priority"], "0", "PRIORITY_REQUIRED_FOR_SELECTED_CHANNEL")

        if "PUSH" in channels:
            for field_name in ["app_name", "router", "bounce_back"]:
                self._set_applicable(states[field_name], True, impacts, "PUSH_REQUIRED_FIELDS")
                self._set_required(states[field_name], True, impacts, "PUSH_REQUIRED_FIELDS")
            self._suggest_if_empty(states["priority"], "0", "PRIORITY_REQUIRED_FOR_SELECTED_CHANNEL")
            if states["router"].value and "PUSH" not in str(states["router"].value).upper():
                self._set_value(states["router"], "AWS_SG_SNS_PUSH", impacts, "PUSH_DAASC_ROUTER_RECOMMENDATION")

        if set(channels).intersection({"SMS", "MMS", "EMAIL", "WECHAT", "PUSH"}):
            self._set_value(states["push_optin_flag"], "Y", impacts, "OPT_IN_MASTER_GENERATED_BY_CHANNEL")
        else:
            self._set_value(states["push_optin_flag"], "N", impacts, "OPT_IN_MASTER_GENERATED_BY_CHANNEL")

        if states.get("bounce_back_next_channel") and states["bounce_back_next_channel"].value == "Y":
            self._set_applicable(states["unknown_bounce_back_status"], True, impacts, "BOUNCE_BACK_NEXT_CHANNEL")
            self._set_required(states["unknown_bounce_back_status"], True, impacts, "BOUNCE_BACK_NEXT_CHANNEL")
        elif "unknown_bounce_back_status" in states:
            self._set_applicable(states["unknown_bounce_back_status"], False, impacts, "BOUNCE_BACK_NEXT_CHANNEL")

        for state in states.values():
            if not state.applicable:
                if state.value not in (None, "", []):
                    impacts.impacts.append(
                        InternalImpact(
                            rule_id="NON_APPLICABLE_FIELD_CLEANUP",
                            affected_field=state.field_name,
                            old_value=state.value,
                            new_value="",
                            reason="Field is not applicable under the selected setup.",
                        )
                    )
                state.value = ""
                state.normalized_value = ""
                state.ui_status = "NOT_APPLICABLE"
                state.resolution_status = "NOT_APPLICABLE"
                state.required_now = False
                state.hidden = True
            elif state.required_now and is_empty(state.value):
                state.ui_status = "MISSING_REQUIRED"
                state.resolution_status = "UNRESOLVED_MISSING"
                state.hidden = False
            elif not is_empty(state.value):
                if state.source in {"USER_CONFIRMED", "USER_INPUT"}:
                    state.ui_status = "CONFIRMED"
                    state.resolution_status = "RESOLVED"
                elif state.source == "DEPENDENCY_DERIVED":
                    state.ui_status = "GENERATED"
                    state.resolution_status = "RESOLVED"
                else:
                    state.ui_status = "PREFILLED"
                    state.resolution_status = "RESOLVED_NEEDS_CONFIRMATION" if state.requires_confirmation else "RESOLVED"
                state.hidden = False
            else:
                state.ui_status = "EMPTY"
                state.resolution_status = "RESOLVED"
                state.hidden = False

        draft.field_states = states
        draft.internal_impact_plan = impacts
        draft.domain_draft = DomainDraftBuilder().build(draft)
        return draft

    def _set_applicable(self, state: GuidedFieldState, value: bool, impacts: InternalImpactPlan, rule_id: str) -> None:
        if state.applicable != value:
            impacts.impacts.append(
                InternalImpact(
                    rule_id=rule_id,
                    affected_field=state.field_name,
                    old_applicable=state.applicable,
                    new_applicable=value,
                    reason=f"{state.display_name} applicability changed by dependency rule.",
                )
            )
        state.applicable = value

    def _set_required(self, state: GuidedFieldState, value: bool, impacts: InternalImpactPlan, rule_id: str) -> None:
        if state.required_now != value:
            impacts.impacts.append(
                InternalImpact(
                    rule_id=rule_id,
                    affected_field=state.field_name,
                    old_required_now=state.required_now,
                    new_required_now=value,
                    reason=f"{state.display_name} requiredness changed by dependency rule.",
                )
            )
        state.required_now = value

    def _set_value(self, state: GuidedFieldState, value: Any, impacts: InternalImpactPlan, rule_id: str) -> None:
        if state.value != value:
            impacts.impacts.append(
                InternalImpact(
                    rule_id=rule_id,
                    affected_field=state.field_name,
                    old_value=state.value,
                    new_value=value,
                    reason=f"{state.display_name} generated by dependency rule.",
                )
            )
        state.value = value
        state.normalized_value = value
        state.source = "DEPENDENCY_DERIVED"

    def _suggest_if_empty(self, state: GuidedFieldState, value: Any, rule_id: str) -> None:
        if is_empty(state.value):
            state.value = value
            state.normalized_value = value
            state.source = "DEPENDENCY_DERIVED"


class DomainDraftBuilder:
    def build(self, draft: GuidedDraftState) -> UseCaseDomainDraft:
        result = UseCaseDomainDraft()
        states = draft.field_states
        channels = normalize_channels(states.get("channel").value if states.get("channel") else None)
        for field_name, state in states.items():
            if not state.applicable or is_empty(state.value):
                continue
            if state.domain_object == "use_case_master":
                result.use_case_master[field_name] = state.value
            elif state.domain_object == "use_case_extension":
                result.use_case_extension[field_name] = state.value
            elif state.domain_object == "opt_in_policy":
                result.opt_in_policy[field_name] = state.value
            elif state.domain_object == "bounce_back_policy":
                result.bounce_back_policy[field_name] = state.value

        for index, channel in enumerate(channels):
            rule = {"channel": channel, "priority": states.get("priority").value or str(index)}
            for field_name in [
                "router",
                "tag",
                "traffic_percentage",
                "sender",
                "sender_name",
                "app_name",
                "cost_center_id",
                "Send_to_China_flag",
            ]:
                state = states.get(field_name)
                if state and state.applicable and not is_empty(state.value):
                    rule[field_name] = state.value
            if rule.get("router") and "route" not in rule:
                rule["route"] = rule["router"]
            result.use_case_channel_rule_list.append(rule)
        return result


class ValidationEngine:
    def validate(self, draft: GuidedDraftState) -> ValidationResult:
        issues: list[BlockingIssue] = []
        for state in draft.field_states.values():
            if state.hidden or not state.applicable:
                continue
            if state.required_now and is_empty(state.value):
                issues.append(
                    BlockingIssue(
                        field_name=state.field_name,
                        display_name=state.display_name,
                        message=f"{state.display_name} is required.",
                    )
                )
        return ValidationResult(ready_for_ac=not issues, blocking_issues=issues, warnings=[])


class QuestionWordingService:
    def __init__(self, metadata: MetadataRegistry, llm: LLMClient) -> None:
        self.metadata = metadata
        self.llm = llm

    def build_question(
        self,
        group: dict[str, Any],
        draft: GuidedDraftState,
        focus_fields: list[str],
        score: float,
        dynamic_context: dict[str, Any] | None = None,
    ) -> ActiveQuestionState:
        dynamic_context = dynamic_context or {}
        template_context = self._template_context(group, draft, focus_fields, dynamic_context)
        title = group.get("title", "Confirm details")
        question = safe_format(group.get("question_template", ""), template_context)
        question = self._tailor_question_to_focus(group, draft, focus_fields, question)
        why = safe_format(group.get("assistant_context_template", ""), template_context)
        hints = self._relevant_hints(group, focus_fields)
        if hints:
            why = f"{why} {' '.join(hints[:2])}".strip()
        active = ActiveQuestionState(
            question_id=self._question_id(group),
            group_id=group["group_id"],
            intent_type=group.get("primary_decision", group["group_id"]),
            title=title,
            question=question,
            question_type="SINGLE_CHOICE" if group["group_id"] == "qg_channel_priority" else "FREE_TEXT",
            focus_fields=focus_fields,
            related_fields=list(group.get("related_fields", [])),
            options=self._options(group),
            why_asking=why,
            answer_hints=hints,
            priority_score=score,
        )
        return self._rewrite_wording(active, group, focus_fields)

    def _tailor_question_to_focus(
        self,
        group: dict[str, Any],
        draft: GuidedDraftState,
        focus_fields: list[str],
        default_question: str,
    ) -> str:
        group_fields = [field for field in group.get("focus_fields", []) if field in draft.field_states]
        if set(focus_fields) == set(group_fields) or not focus_fields:
            return default_question

        requested = self._display_list(draft, focus_fields)
        group_id = group["group_id"]

        if group_id == "qg_delivery_mode_risk":
            return f"Please confirm {requested} from an operation and risk perspective."
        if group_id == "qg_channel_priority":
            return f"Please confirm {requested} for the delivery channel decision."
        if group_id == "qg_business_identity":
            return f"Please confirm {requested} for the use case identity."
        if group_id == "qg_project_ownership_final":
            return f"Before finalizing, please provide {requested}."
        if group_id.startswith("qg_email"):
            return f"For Email delivery, please confirm {requested}."
        if group_id.startswith("qg_sms"):
            return f"For SMS delivery, please confirm {requested}."
        if group_id.startswith("qg_push"):
            return f"For Push Notification, please confirm {requested}."
        return f"Please confirm {requested}."

    def _display_list(self, draft: GuidedDraftState, field_names: list[str]) -> str:
        names = [draft.field_states[field].display_name for field in field_names]
        if not names:
            return "the remaining details"
        if len(names) == 1:
            return names[0]
        return ", ".join(names[:-1]) + f", and {names[-1]}"

    def _rewrite_wording(self, question: ActiveQuestionState, group: dict[str, Any], focus_fields: list[str]) -> ActiveQuestionState:
        try:
            wording = self.llm.word_question(
                question.model_dump(),
                {
                    "group_id": group["group_id"],
                    "primary_decision": group.get("primary_decision"),
                    "business_hint": question.why_asking,
                    "focus_fields": focus_fields,
                    "answer_hints": question.answer_hints,
                },
            )
            question.title = wording.title or question.title
            question.question = wording.question or question.question
            question.why_asking = wording.why_asking or question.why_asking
            question.answer_hints = wording.answer_hints or question.answer_hints
        except Exception:
            pass
        return question

    def _question_id(self, group: dict[str, Any]) -> str:
        mapping = {
            "qg_reference_delta_review": "q_reference_delta_review",
            "qg_business_scenario": "q_business_scenario",
            "qg_business_identity": "q_business_identity",
            "qg_delivery_mode_risk": "q_delivery_mode_risk",
            "qg_channel_priority": "q_channel_priority",
            "qg_email_route_sender": "q_email_route_sender",
            "qg_sms_routing_strategy": "q_sms_routing_strategy",
            "qg_sms_sender_billing": "q_sms_sender_billing",
            "qg_push_app_route": "q_push_app_route",
            "qg_project_ownership_final": "q_project_ownership_final",
        }
        return mapping.get(group["group_id"], f"q_{group['group_id'].removeprefix('qg_')}")

    def _template_context(
        self,
        group: dict[str, Any],
        draft: GuidedDraftState,
        focus_fields: list[str],
        dynamic_context: dict[str, Any],
    ) -> dict[str, Any]:
        context = dict(dynamic_context)
        if focus_fields:
            state = draft.field_states[focus_fields[0]]
            context.setdefault("field_display_name", state.display_name)
            context.setdefault("business_reason", state.help or state.business_reason or "this affects the use case setup")
        context.setdefault("reference_value", dynamic_context.get("reference_value", "the reference value"))
        context.setdefault("requirement_value", dynamic_context.get("requirement_value", "the new requirement value"))
        return context

    def _relevant_hints(self, group: dict[str, Any], focus_fields: list[str]) -> list[str]:
        hints = list(group.get("answer_hints", []))
        for field_name in focus_fields:
            if field_name in self.metadata.fields_by_name:
                hint = self.metadata.answer_hint(field_name)
                if hint and hint not in hints:
                    hints.append(hint)
        return hints

    def _options(self, group: dict[str, Any]) -> list[dict[str, str]]:
        if group["group_id"] == "qg_channel_priority":
            return [
                {"label": "SMS", "value": "SMS"},
                {"label": "Email", "value": "EMAIL"},
                {"label": "Mobile Push", "value": "PUSH"},
                {"label": "SMS + Email", "value": "SMS,EMAIL"},
            ]
        return []


class ActiveQuestionPlanner:
    CHANNEL_DETAIL_GROUPS = {
        "qg_email_route_sender",
        "qg_sms_routing_strategy",
        "qg_sms_sender_billing",
        "qg_push_app_route",
        "qg_push_callback",
        "qg_letter_route",
        "qg_other_channel_route",
        "qg_bounce_next_channel",
    }

    def __init__(
        self,
        metadata: MetadataRegistry,
        group_registry: QuestionGroupConfigRegistry,
        wording: QuestionWordingService,
    ) -> None:
        self.metadata = metadata
        self.group_registry = group_registry
        self.wording = wording

    def plan(self, draft: GuidedDraftState) -> ActiveQuestionState | None:
        self.last_runtime_states: list[dict[str, Any]] = []
        candidates: list[tuple[float, int, dict[str, Any], list[str], dict[str, Any]]] = []
        for index, group in enumerate(self.group_registry.get_groups()):
            result = self._evaluate_group(group, draft)
            if not result:
                continue
            score, focus_fields, dynamic_context = result
            candidates.append((score, index, group, focus_fields, dynamic_context))
        if not candidates:
            return None
        score, _, group, focus_fields, dynamic_context = sorted(candidates, key=lambda item: (-item[0], item[1]))[0]
        for runtime in self.last_runtime_states:
            runtime["chosen"] = runtime["group_id"] == group["group_id"] and runtime["focus_fields"] == focus_fields
        return self.wording.build_question(group, draft, focus_fields, score, dynamic_context)

    def _evaluate_group(self, group: dict[str, Any], draft: GuidedDraftState) -> tuple[float, list[str], dict[str, Any]] | None:
        runtime = self._runtime_state(group, draft)
        self.last_runtime_states.append(runtime)
        if draft.mode not in group.get("mode_scope", []):
            runtime["skip_reasons"].append("mode_scope_not_matched")
            return None
        group_id = group["group_id"]
        if group_id == "qg_reference_delta_review":
            result = self._reference_delta_candidate(group, draft)
            runtime["eligible"] = bool(result)
            if result:
                runtime["score"], runtime["focus_fields"], runtime["dynamic_context"] = result
            return result
        if self._skip_when_matches(group, draft):
            runtime["skip_reasons"].append("skip_when_matched")
            return None
        if not self._prerequisites_met(group, draft):
            runtime["skip_reasons"].append("prerequisite_missing")
            return None
        ask_when_results = runtime["ask_when_results"]
        if ask_when_results and not any(ask_when_results.values()):
            runtime["skip_reasons"].append("ask_when_not_matched")
            return None
        if (
            group_id not in {"qg_business_scenario", "qg_channel_priority"}
            and not self._scenario_resolved_or_skippable(draft)
        ):
            runtime["skip_reasons"].append("business_scenario_unresolved")
            return None
        if group_id in self.CHANNEL_DETAIL_GROUPS and not self._channel_priority_resolved(draft):
            runtime["skip_reasons"].append("channel_priority_prerequisite_missing")
            return None
        if group_id == "qg_project_ownership_final" and not self._core_delivery_complete(draft):
            runtime["skip_reasons"].append("final_review_too_early")
            return None
        if group_id == "qg_business_identity" and not self._scenario_resolved_or_skippable(draft):
            runtime["skip_reasons"].append("business_scenario_unresolved")
            return None

        selected_channels = self._selected_channels(draft)
        if group_id.startswith("qg_email") and "EMAIL" not in selected_channels:
            runtime["skip_reasons"].append("email_not_selected")
            return None
        if group_id.startswith("qg_sms") and "SMS" not in selected_channels:
            runtime["skip_reasons"].append("sms_not_selected")
            return None
        if group_id.startswith("qg_push") and "PUSH" not in selected_channels:
            runtime["skip_reasons"].append("push_not_selected")
            return None
        if group_id == "qg_letter_route" and "LETTER" not in selected_channels:
            runtime["skip_reasons"].append("letter_not_selected")
            return None
        if group_id == "qg_other_channel_route" and not set(selected_channels).intersection({"MMS", "WHATSAPP", "WECHAT", "TWOWAYSMS"}):
            runtime["skip_reasons"].append("simple_route_channel_not_selected")
            return None
        if group_id == "qg_bounce_next_channel" and len(selected_channels) < 2 and not self._requirement_mentions_fallback(draft):
            runtime["skip_reasons"].append("fallback_not_relevant")
            return None

        focus_fields = self._focus_fields_for_group(group, draft)
        if not focus_fields:
            runtime["skip_reasons"].append("no_focus_field_needs_decision")
            return None
        if any(field == "push_optin_flag" for field in focus_fields):
            runtime["skip_reasons"].append("generated_field_not_askable")
            return None
        if any(field in group.get("excluded_fields", []) for field in focus_fields):
            runtime["skip_reasons"].append("excluded_field_in_focus")
            return None

        score = float(group.get("priority_score_boost", 50))
        runtime["score_reasons"].append(f"priority_score_boost={score}")
        if any(self._state_needs_input(draft.field_states[field]) for field in focus_fields):
            score += 25
            runtime["score_reasons"].append("needs_input=+25")
        if any(draft.field_states[field].requires_confirmation for field in focus_fields):
            score += 20
            runtime["score_reasons"].append("requires_confirmation=+20")
        if group_id == "qg_channel_priority" and not selected_channels:
            score += 40
            runtime["score_reasons"].append("channel_missing=+40")
        if group_id == "qg_channel_priority" and selected_channels and "channel" not in focus_fields:
            score -= 50
            runtime["score_reasons"].append("channel_already_confirmed=-50")
        focus_fields = focus_fields[: int(group.get("max_focus_fields", 3))]
        runtime["eligible"] = True
        runtime["score"] = score
        runtime["focus_fields"] = focus_fields
        return score, focus_fields, {}

    def _runtime_state(self, group: dict[str, Any], draft: GuidedDraftState) -> dict[str, Any]:
        return {
            "group_id": group["group_id"],
            "primary_decision": group.get("primary_decision"),
            "ask_when": list(group.get("ask_when", [])),
            "skip_when": list(group.get("skip_when", [])),
            "prerequisites": list(group.get("prerequisites", [])),
            "ask_when_results": self._evaluate_ask_when(group, draft),
            "skip_reasons": [],
            "score_reasons": [],
            "eligible": False,
            "chosen": False,
            "score": 0,
            "focus_fields": [],
            "dynamic_context": {},
        }

    def _evaluate_ask_when(self, group: dict[str, Any], draft: GuidedDraftState) -> dict[str, bool]:
        return {condition: self._condition_matches(condition, group, draft) for condition in group.get("ask_when", [])}

    def _skip_when_matches(self, group: dict[str, Any], draft: GuidedDraftState) -> bool:
        return any(self._condition_matches(condition, group, draft) for condition in group.get("skip_when", []))

    def _prerequisites_met(self, group: dict[str, Any], draft: GuidedDraftState) -> bool:
        for prerequisite in group.get("prerequisites", []):
            text = prerequisite.lower()
            if "qg_business_scenario" in text and not self._scenario_resolved_or_skippable(draft):
                return False
            if "qg_channel_priority" in text and not self._channel_priority_resolved(draft):
                return False
            if "delivery_mode and high_risk_flag" in text:
                for field_name in ["delivery_mode", "high_risk_flag"]:
                    state = draft.field_states.get(field_name)
                    if state and self._state_needs_input(state):
                        return False
            if "core delivery groups" in text and not self._core_delivery_complete(draft):
                return False
        return True

    def _condition_matches(self, condition: str, group: dict[str, Any], draft: GuidedDraftState) -> bool:
        text = condition.lower()
        if "mode = edit_reference" in text:
            return draft.mode == "EDIT_REFERENCE"
        if "mode = create_new" in text:
            return draft.mode == "CREATE_NEW"
        if "no reference snapshot" in text:
            return not draft.reference_snapshot
        if "reference snapshot" in text and "exists" in text:
            return bool(draft.reference_snapshot)
        if "unresolved_conflict" in text or "conflict" in text:
            return bool(draft.diff_from_reference)
        if "channel contains email" in text:
            return "EMAIL" in self._selected_channels(draft)
        if "channel contains sms" in text:
            return "SMS" in self._selected_channels(draft)
        if "channel contains push" in text:
            return "PUSH" in self._selected_channels(draft)
        if "channel contains letter" in text:
            return "LETTER" in self._selected_channels(draft)
        if "multiple channels selected" in text:
            return len(self._selected_channels(draft)) > 1
        if "user mentions fallback" in text:
            return self._requirement_mentions_fallback(draft)
        if "core delivery setup is mostly complete" in text:
            return self._core_delivery_complete(draft)
        if "all reference conflicts are resolved" in text:
            return bool(draft.diff_from_reference) and all(
                draft.field_states.get(item["field_name"]) and draft.field_states[item["field_name"]].source in {"USER_CONFIRMED", "USER_INPUT"}
                for item in draft.diff_from_reference
            )
        if "channel is confirmed" in text:
            return self._channel_priority_resolved(draft)
        for field_name in group.get("focus_fields", []) + group.get("related_fields", []):
            if field_name not in draft.field_states:
                continue
            state = draft.field_states[field_name]
            if f"{field_name} is missing" in text:
                return is_empty(state.value)
            if f"{field_name} requires confirmation" in text:
                return state.requires_confirmation
            if f"{field_name} is confirmed" in text:
                return not self._state_needs_input(state) and not is_empty(state.value)
        return False

    def _reference_delta_candidate(self, group: dict[str, Any], draft: GuidedDraftState) -> tuple[float, list[str], dict[str, Any]] | None:
        if draft.mode != "EDIT_REFERENCE" or not draft.diff_from_reference:
            return None
        for diff in draft.diff_from_reference:
            field_name = diff["field_name"]
            state = draft.field_states.get(field_name)
            if state and state.source not in {"USER_CONFIRMED", "USER_INPUT"}:
                return (
                    float(group.get("priority_score_boost", 120)) + 60,
                    [field_name],
                    {
                        "reference_value": value_to_string(diff.get("reference_value")),
                        "requirement_value": value_to_string(diff.get("requirement_value")),
                    },
                )
        return None

    def _focus_fields_for_group(self, group: dict[str, Any], draft: GuidedDraftState) -> list[str]:
        fields: list[str] = []
        for field_name in group.get("focus_fields", []):
            if field_name not in draft.field_states:
                continue
            state = draft.field_states[field_name]
            if not state.applicable or state.hidden:
                continue
            if self._state_needs_input(state) or is_empty(state.value):
                fields.append(field_name)
        if group["group_id"] == "qg_channel_priority":
            channel_state = draft.field_states.get("channel")
            if channel_state and (not normalize_channels(channel_state.value) or channel_state.requires_confirmation):
                fields.insert(0, "channel")
            priority_state = draft.field_states.get("priority")
            if priority_state and priority_state.applicable and is_empty(priority_state.value) and "priority" not in fields:
                fields.append("priority")
        return unique_list(fields)

    def _state_needs_input(self, state: GuidedFieldState) -> bool:
        return (
            state.resolution_status in {"UNRESOLVED_MISSING", "UNRESOLVED_LOW_CONFIDENCE", "UNRESOLVED_CONFLICT"}
            or state.ui_status in {"MISSING_REQUIRED", "NEEDS_CONFIRMATION", "CONFLICT"}
            or state.requires_confirmation
            or (state.required_now and is_empty(state.value))
        )

    def _selected_channels(self, draft: GuidedDraftState) -> list[str]:
        state = draft.field_states.get("channel")
        return normalize_channels(state.value if state else None)

    def _channel_priority_resolved(self, draft: GuidedDraftState) -> bool:
        channel_state = draft.field_states.get("channel")
        if not channel_state or not normalize_channels(channel_state.value):
            return False
        return not channel_state.requires_confirmation and channel_state.resolution_status != "UNRESOLVED_CONFLICT"

    def _scenario_resolved_or_skippable(self, draft: GuidedDraftState) -> bool:
        state = draft.field_states.get("message_trigger_conditions")
        return bool(state and not is_empty(state.value) and not state.requires_confirmation and state.resolution_status != "UNRESOLVED_CONFLICT")

    def _core_delivery_complete(self, draft: GuidedDraftState) -> bool:
        blockers = ["message_trigger_conditions", "delivery_mode", "high_risk_flag", "delivery_schedule", "channel"]
        for field_name in blockers:
            state = draft.field_states.get(field_name)
            if state and state.applicable and self._state_needs_input(state):
                return False
        return True

    def _requirement_mentions_fallback(self, draft: GuidedDraftState) -> bool:
        text = draft.raw_requirement.lower()
        return any(token in text for token in ["fallback", "retry", "next channel", "unknown status", "bounce"])


class AnswerParser:
    def __init__(self, llm: LLMClient, group_registry: QuestionGroupConfigRegistry) -> None:
        self.llm = llm
        self.group_registry = group_registry

    def parse(self, session: GuidedIntakeSession, question_id: str, answer: str) -> dict[str, Any]:
        llm_result = self.llm.parse_answer(
            session.active_question_state.model_dump() if session.active_question_state else {"question_id": question_id},
            answer,
            session.draft_state.domain_draft.model_dump(),
        )
        if llm_result.updates:
            return self._filter_updates(session, llm_result.updates)

        text = answer.lower()
        active = session.active_question_state
        focus = active.focus_fields if active else []
        updates: dict[str, Any] = {}

        if question_id in {"q_channel_confirm", "q_channel_conflict"} or "channel" in focus:
            if "both" in text or ("sms" in text and "email" in text):
                updates["channel"] = ["SMS", "EMAIL"]
            elif "email" in text:
                updates["channel"] = ["EMAIL"]
            elif "push" in text or "mobile push" in text:
                updates["channel"] = ["PUSH"]
            elif "sms" in text or "mobile phone" in text:
                updates["channel"] = ["SMS"]

        if "service" in text:
            updates.setdefault("message_trigger_conditions", session.draft_state.field_states.get("message_trigger_conditions").value)
        if "marketing" in text:
            updates["high_risk_flag"] = "N"

        for field_name in focus:
            if field_name not in updates and question_id == f"q_{field_name}":
                updates[field_name] = answer.strip()

        return self._filter_updates(session, updates)

    def _filter_updates(self, session: GuidedIntakeSession, updates: dict[str, Any]) -> dict[str, Any]:
        active = session.active_question_state
        if not active:
            return {field: value for field, value in updates.items() if field in session.draft_state.field_states}
        allowed = set(active.focus_fields)
        try:
            group = self.group_registry.get_group(active.group_id)
            allowed.update(self._scope_to_fields(group.get("parser_update_scope", []), session))
            allowed.update(field for field in group.get("related_fields", []) if field in session.draft_state.field_states)
        except KeyError:
            pass
        filtered: dict[str, Any] = {}
        for field_name, value in updates.items():
            if field_name in allowed and field_name in session.draft_state.field_states:
                filtered[field_name] = value
        return filtered

    def _scope_to_fields(self, scopes: list[str], session: GuidedIntakeSession) -> set[str]:
        fields: set[str] = set()
        for scope in scopes:
            if scope in session.draft_state.field_states:
                fields.add(scope)
                continue
            for field_name in session.draft_state.field_states:
                if f".{field_name}" in scope or f"[{field_name}]" in scope:
                    fields.add(field_name)
            if "strongly_related_fields_only" == scope:
                fields.update(session.active_question_state.focus_fields if session.active_question_state else [])
            if "use_case_name_if_clear" == scope:
                fields.add("use_case_name")
        return fields


class AssistantCardBuilder:
    def question_card(self, question: ActiveQuestionState) -> AssistantCard:
        return AssistantCard(
            type="question",
            title=question.title,
            group_id=question.group_id,
            question_id=question.question_id,
            question=question.question,
            question_type=question.question_type,
            options=question.options,
            focus_fields=question.focus_fields,
            why_asking=question.why_asking,
            priority="P0" if question.priority_score >= 100 else "P1",
        )

    def action_preview_card(self, preview: StoredActionPreview) -> AssistantCard:
        return AssistantCard(
            type="action_preview",
            title="Action Preview",
            action_preview={
                "preview_id": preview.preview_id,
                "user_facing_updates": [update.model_dump() for update in preview.user_facing_updates],
                "follow_up_summary": preview.follow_up_summary,
            },
        )


class ResponseMapper:
    def __init__(self, extractor: RequirementExtractor, metadata: MetadataRegistry) -> None:
        self.extractor = extractor
        self.metadata = metadata

    def to_build_response(self, session: GuidedIntakeSession) -> BuildDraftResponse:
        _, signals = self.extractor.extract(session.raw_requirement)
        return BuildDraftResponse(
            intake_id=session.intake_id,
            mode=session.mode,
            requirement=session.raw_requirement,
            extracted_signals=signals,
            selected_reference=self._selected_reference(session),
            modules=self.to_modules(session.draft_state),
            assistant_cards=session.assistant_cards,
            validation=session.validation_state or ValidationResult(),
        )

    def to_modules(self, draft: GuidedDraftState) -> dict[str, FormModule]:
        grouped: dict[str, list[FormField]] = {}
        titles: dict[str, str] = {}
        for state in draft.field_states.values():
            module_id, title = MODULE_MAP.get(state.module, ("business", state.module))
            grouped.setdefault(module_id, []).append(self._field_to_form(state))
            titles[module_id] = title
        modules: dict[str, FormModule] = {}
        for module_id in ["business", "audience", "channel", "compliance"]:
            fields = grouped.get(module_id, [])
            visible = [field for field in fields if not field.hidden and field.status != "Not Applicable"]
            complete = len([field for field in visible if field.status in {"Confirmed", "AI Prefilled", "Reference Prefilled", "Optional"}])
            modules[module_id] = FormModule(
                id=module_id,
                title=titles.get(module_id, module_id.title()),
                complete=complete,
                total=len(visible),
                fields=fields,
            )
        return modules

    def _field_to_form(self, state: GuidedFieldState) -> FormField:
        return FormField(
            name=state.field_name,
            displayName=state.display_name,
            value=value_to_string(state.value),
            status=STATUS_TO_FRONTEND.get(state.ui_status, "Optional"),
            source=SOURCE_TO_FRONTEND.get(state.source, "Default"),
            help=state.help,
            required=state.required_now,
            hidden=state.hidden,
            options=self.metadata.options_for_field(state.field_name),
        )

    def _selected_reference(self, session: GuidedIntakeSession) -> ReferenceUseCase | None:
        snapshot = session.draft_state.reference_snapshot
        if not snapshot:
            return None
        channel = snapshot.get("channel", "")
        return ReferenceUseCase(
            id=snapshot.get("id", session.selected_reference_use_case_id or ""),
            name=snapshot.get("name", "Reference use case"),
            source_system=snapshot.get("source_system", ""),
            channel=value_to_string(channel),
            status="Conflicts found" if session.draft_state.diff_from_reference else "Loaded",
        )


class GuidedIntakeOrchestrator:
    def __init__(self) -> None:
        self.metadata = MetadataRegistry()
        self.metadata.load()
        self.group_registry = QuestionGroupConfigRegistry()
        self.group_registry.load()
        self.llm = create_llm_client()
        self.sessions = SessionRepository()
        self.references = ReferenceUseCaseRepository()
        self.extractor = RequirementExtractor(self.llm, self.metadata)
        self.field_builder = FieldStateBuilder(self.metadata)
        self.dependency = DependencyRuleEngine(self.metadata)
        self.validation = ValidationEngine()
        self.wording = QuestionWordingService(self.metadata, self.llm)
        self.planner = ActiveQuestionPlanner(self.metadata, self.group_registry, self.wording)
        self.parser = AnswerParser(self.llm, self.group_registry)
        self.cards = AssistantCardBuilder()
        self.mapper = ResponseMapper(self.extractor, self.metadata)

    def analyze_requirement(self, intake_id: str, requirement: str) -> AnalyzeRequirementResponse:
        candidates, signals = self.extractor.extract(requirement)
        retrieved = self.references.search_candidates(requirement, signals)
        cards = [
            AssistantCard(
                type="summary",
                title="Requirement understood",
                body="I extracted initial business signals from your requirement and found related historical use cases.",
            ),
            AssistantCard(
                type="question",
                title="Choose how to continue",
                question_id="q_reference_choice",
                question="Would you like to use one of the historical use cases as a reference, or create a brand-new use case?",
                question_type="SINGLE_CHOICE",
                options=[
                    {"label": f"Use {retrieved[0].name} as reference", "value": retrieved[0].id},
                    {"label": "Create a new use case", "value": "CREATE_NEW"},
                ],
                focus_fields=["reference_selection"],
                why_asking="The selected path determines whether historical values are inherited or the draft starts from requirement extraction only.",
                priority="P0",
            ),
        ]
        return AnalyzeRequirementResponse(
            intake_id=intake_id,
            requirement=requirement,
            extracted_signals=signals,
            candidates=retrieved,
            assistant_cards=cards,
        )

    def build_draft(self, intake_id: str, request: BuildDraftRequest) -> BuildDraftResponse:
        states = self.field_builder.empty_states()
        reference_snapshot = None
        if request.mode == "EDIT_REFERENCE" and request.selected_reference_use_case_id:
            reference_snapshot = self.references.get(request.selected_reference_use_case_id)
            for field_name, value in reference_snapshot.items():
                if field_name in states:
                    self.field_builder.apply_candidate(
                        states,
                        FieldCandidate(
                            field_name=field_name,
                            value=value,
                            normalized_value=value,
                            source="REFERENCE_USE_CASE",
                            evidence="reference use case",
                            reason="Inherited from selected reference use case.",
                        ),
                    )

        candidates, _ = self.extractor.extract(request.requirement)
        diff: list[dict[str, Any]] = []
        for candidate in candidates:
            current = states.get(candidate.field_name)
            if current and not is_empty(current.value) and normalize_compare(current.value) != normalize_compare(candidate.value):
                diff.append(
                    {
                        "field_name": candidate.field_name,
                        "reference_value": current.value,
                        "requirement_value": candidate.value,
                    }
                )
                if candidate.field_name == "channel":
                    current.ui_status = "CONFLICT"
                    current.resolution_status = "UNRESOLVED_CONFLICT"
                    current.requires_confirmation = True
                    continue
            self.field_builder.apply_candidate(states, candidate)

        draft = GuidedDraftState(
            mode=request.mode,
            raw_requirement=request.requirement,
            field_states=states,
            reference_snapshot=reference_snapshot,
            diff_from_reference=diff,
        )
        draft = self.dependency.resolve(draft)
        validation = self.validation.validate(draft)
        question = self._initial_question(draft, request.mode)
        assistant_cards = self._initial_cards(draft, question, request.mode)
        session = GuidedIntakeSession(
            intake_id=intake_id,
            mode=request.mode,
            raw_requirement=request.requirement,
            selected_reference_use_case_id=request.selected_reference_use_case_id,
            draft_state=draft,
            active_question_state=question,
            validation_state=validation,
            assistant_cards=assistant_cards,
        )
        self.sessions.save(session)
        return self.mapper.to_build_response(session)

    def parse_answer(self, intake_id: str, question_id: str, answer: str) -> ParseAnswerResponse:
        session = self.sessions.get(intake_id)
        updates = self.parser.parse(session, question_id, answer)
        preview = self._build_preview(session, updates)
        session.current_action_preview = preview
        session.assistant_cards = [self.cards.action_preview_card(preview)]
        self.sessions.save(session)
        return ParseAnswerResponse(user_message=answer, assistant_cards=session.assistant_cards)

    def apply_preview(self, intake_id: str, preview_id: str):
        session = self.sessions.get(intake_id)
        preview = session.current_action_preview
        if not preview or preview.preview_id != preview_id:
            raise KeyError(f"Unknown preview_id: {preview_id}")
        for field_name, value in preview.direct_updates.items():
            state = session.draft_state.field_states[field_name]
            state.value = value
            state.normalized_value = value
            state.source = "USER_CONFIRMED"
            state.requires_confirmation = False
            state.ui_status = "CONFIRMED"
            state.resolution_status = "RESOLVED"
            state.applicable = True
            state.hidden = False
        session.draft_state = self.dependency.resolve(session.draft_state)
        session.validation_state = self.validation.validate(session.draft_state)
        question = self.planner.plan(session.draft_state)
        session.active_question_state = question
        cards = [
            AssistantCard(
                type="summary",
                title="Preview applied",
                body="I applied the confirmed update and recalculated the draft.",
            )
        ]
        if question:
            cards.append(self.cards.question_card(question))
        session.assistant_cards = cards
        session.current_action_preview = None
        self.sessions.save(session)
        return {
            "modules": self.mapper.to_modules(session.draft_state),
            "assistant_cards": session.assistant_cards,
            "validation": session.validation_state,
        }

    def update_field(self, intake_id: str, field_name: str, value: Any):
        session = self.sessions.get(intake_id)
        if field_name not in session.draft_state.field_states:
            raise KeyError(f"Unknown field: {field_name}")
        state = session.draft_state.field_states[field_name]
        state.value = parse_field_value(field_name, value)
        state.normalized_value = state.value
        state.source = "USER_INPUT"
        state.requires_confirmation = False
        session.draft_state = self.dependency.resolve(session.draft_state)
        session.validation_state = self.validation.validate(session.draft_state)
        question = self.planner.plan(session.draft_state)
        session.active_question_state = question
        session.assistant_cards = [
            AssistantCard(
                type="summary",
                title="Field updated",
                body=f"{state.display_name} has been updated.",
            )
        ]
        if question:
            session.assistant_cards.append(self.cards.question_card(question))
        self.sessions.save(session)
        return {
            "modules": self.mapper.to_modules(session.draft_state),
            "assistant_cards": session.assistant_cards,
            "validation": session.validation_state,
        }

    def validate(self, intake_id: str) -> ValidationResult:
        session = self.sessions.get(intake_id)
        session.validation_state = self.validation.validate(session.draft_state)
        self.sessions.save(session)
        return session.validation_state

    def export_for_ac(self, intake_id: str) -> dict[str, Any]:
        session = self.sessions.get(intake_id)
        validation = self.validation.validate(session.draft_state)
        session.validation_state = validation
        self.sessions.save(session)
        domain = session.draft_state.domain_draft.model_dump()
        return {
            "ready_for_ac": validation.ready_for_ac,
            "confirmed_use_case": domain,
            "semantic_summary": self._semantic_summary(session),
        }

    def _initial_question(self, draft: GuidedDraftState, mode: str) -> ActiveQuestionState | None:
        return self.planner.plan(draft)

    def _initial_cards(self, draft: GuidedDraftState, question: ActiveQuestionState | None, mode: str) -> list[AssistantCard]:
        cards: list[AssistantCard] = []
        if mode == "EDIT_REFERENCE":
            cards.append(
                AssistantCard(
                    type="summary",
                    title="Reference use case loaded",
                    body="I used the selected historical use case as reference and prefilled matching fields.",
                )
            )
            if draft.diff_from_reference:
                diff = draft.diff_from_reference[0]
                cards.append(
                    AssistantCard(
                        type="finding",
                        title="Important difference found",
                        body=f"The requirement suggests {value_to_string(diff['requirement_value'])}, while the reference uses {value_to_string(diff['reference_value'])}.",
                    )
                )
        else:
            cards.append(
                AssistantCard(
                    type="summary",
                    title="New use case started",
                    body="I will create a new use case from your requirement instead of inheriting historical fields.",
                )
            )
        if question:
            cards.append(self.cards.question_card(question))
        return cards

    def _build_preview(self, session: GuidedIntakeSession, updates: dict[str, Any]) -> StoredActionPreview:
        direct_updates: dict[str, Any] = {}
        user_updates: list[ActionPreviewUpdate] = []
        for field_name, value in updates.items():
            if field_name not in session.draft_state.field_states:
                continue
            value = parse_field_value(field_name, value)
            state = session.draft_state.field_states[field_name]
            direct_updates[field_name] = value
            user_updates.append(
                ActionPreviewUpdate(
                    field_name=field_name,
                    display_name=state.display_name,
                    old_value=value_to_string(state.value) or "Not selected",
                    new_value=value_to_string(value),
                    reason="User confirmed this update.",
                )
            )
        internal_impact_plan = self._preview_internal_impacts(session, direct_updates)
        preview = StoredActionPreview(
            direct_updates=direct_updates,
            user_facing_updates=user_updates,
            internal_impact_plan=internal_impact_plan,
            follow_up_summary="After applying this, I will ask only for the next user-facing required field.",
        )
        return preview

    def _preview_internal_impacts(self, session: GuidedIntakeSession, direct_updates: dict[str, Any]) -> InternalImpactPlan:
        if not direct_updates:
            return InternalImpactPlan()
        draft = deepcopy(session.draft_state)
        for field_name, value in direct_updates.items():
            if field_name not in draft.field_states:
                continue
            state = draft.field_states[field_name]
            state.value = parse_field_value(field_name, value)
            state.normalized_value = state.value
            state.source = "USER_CONFIRMED"
            state.requires_confirmation = False
            state.ui_status = "CONFIRMED"
            state.resolution_status = "RESOLVED"
            state.applicable = True
            state.hidden = False
        resolved = self.dependency.resolve(draft)
        return resolved.internal_impact_plan

    def _semantic_summary(self, session: GuidedIntakeSession) -> str:
        draft = session.draft_state.domain_draft
        name = draft.use_case_master.get("use_case_name", "Use case")
        lob = draft.use_case_master.get("line_of_business", "LOB pending")
        channels = ", ".join(rule.get("channel", "") for rule in draft.use_case_channel_rule_list) or "channel pending"
        return f"{lob} {name} delivered by {channels}."


def build_question_text(state: GuidedFieldState) -> str:
    if state.field_name == "sender_name":
        return "Which email sender name should be shown to the customer?"
    if state.field_name == "sender":
        return "What sender ID, sender address, or sender domain should be used for this channel?"
    if state.field_name == "router":
        return "Which router or vendor path should be used for the selected channel?"
    if state.field_name == "cost_center_id":
        return "What SMS cost center ID should be used?"
    if state.field_name == "Send_to_China_flag":
        return "Will this SMS message need to be sent to China numbers?"
    if state.field_name == "app_name":
        return "Which mobile app should receive the push notification?"
    return f"Please provide {state.display_name}."


def normalize_channels(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value).replace("+", ",").replace("/", ",").split(",")
    result = []
    for item in raw:
        channel = str(item).strip().upper()
        if channel == "EMAIL ONLY":
            channel = "EMAIL"
        if channel == "MOBILE PUSH":
            channel = "PUSH"
        if channel and channel not in result:
            result.append(channel)
    return result


def parse_field_value(field_name: str, value: Any) -> Any:
    if field_name == "channel":
        return normalize_channels(value)
    return value


def value_to_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " + ".join(str(item) for item in value)
    return str(value)


def normalize_compare(value: Any) -> str:
    return value_to_string(value).upper().replace(" ", "")


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def unique_list(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def safe_format(template: str, context: dict[str, Any]) -> str:
    if not template:
        return ""
    try:
        return template.format(**context)
    except KeyError:
        return template
