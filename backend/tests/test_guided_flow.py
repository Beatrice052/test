from app.models import BuildDraftRequest
from app.services import GuidedIntakeOrchestrator


def question_cards(response):
    return [card for card in response.assistant_cards if card.type == "question"]


def build_create(orchestrator: GuidedIntakeOrchestrator, intake_id: str, requirement: str):
    return orchestrator.build_draft(
        intake_id,
        BuildDraftRequest(mode="CREATE_NEW", requirement=requirement),
    )


def apply_answer(orchestrator: GuidedIntakeOrchestrator, intake_id: str, question_id: str, answer: str):
    preview_response = orchestrator.parse_answer(intake_id, question_id, answer)
    preview_id = preview_response.assistant_cards[0].action_preview["preview_id"]
    return orchestrator.apply_preview(intake_id, preview_id)


def test_metadata_and_question_group_config_load():
    orchestrator = GuidedIntakeOrchestrator()
    assert len(orchestrator.metadata.get_all_fields()) == 33
    assert orchestrator.metadata.get_field("channel")["domain_object"] == "use_case_channel_rule_list"
    assert orchestrator.group_registry.get_group("qg_business_scenario")["primary_decision"] == "confirm_message_trigger_conditions"
    assert orchestrator.group_registry.groups_for_field("cost_center_id")[0]["group_id"] == "qg_sms_sender_billing"


def test_analyze_requirement_returns_candidates_before_draft():
    orchestrator = GuidedIntakeOrchestrator()
    response = orchestrator.analyze_requirement(
        "INTAKE-A1",
        "Create an investment cart expiry reminder for customers on mobile phone.",
    )
    assert response.candidates
    assert response.assistant_cards[-1].question_id == "q_reference_choice"
    assert "INTAKE-A1" not in orchestrator.sessions.sessions


def test_ac1_ac2_trigger_question_is_clean_and_not_unrelated_aggregation():
    orchestrator = GuidedIntakeOrchestrator()
    response = build_create(orchestrator, "INTAKE-AC2", "Create a new SMS message for wealth product planning.")
    question = question_cards(response)[0]
    assert question.group_id == "qg_business_scenario"
    assert question.focus_fields == ["message_trigger_conditions"]
    assert "project" not in question.question.lower()
    assert "owner" not in question.question.lower()
    assert "delivery mode" not in question.question.lower()


def test_ac3_delivery_mode_risk_group_after_trigger():
    orchestrator = GuidedIntakeOrchestrator()
    build_create(orchestrator, "INTAKE-AC3", "Create a new SMS message for wealth product planning.")
    applied = apply_answer(
        orchestrator,
        "INTAKE-AC3",
        "q_business_scenario",
        "Send when the customer starts wealth product planning.",
    )
    question = [card for card in applied["assistant_cards"] if card.type == "question"][0]
    assert question.group_id == "qg_delivery_mode_risk"
    assert set(question.focus_fields).issubset({"delivery_mode", "high_risk_flag", "delivery_schedule"})
    assert "sender" not in question.question.lower()
    assert "project" not in question.question.lower()


def test_ac4_ac5_ac6_channel_specific_fields_are_gated_by_channel():
    orchestrator = GuidedIntakeOrchestrator()
    response = build_create(
        orchestrator,
        "INTAKE-AC4",
        "Create a use case to notify customers when their products mature soon.",
    )
    question = question_cards(response)[0]
    assert question.group_id == "qg_channel_priority"
    assert "cost_center_id" not in question.focus_fields
    assert "app_name" not in question.focus_fields
    assert question.group_id not in {"qg_sms_sender_billing", "qg_push_app_route"}


def test_ac7_project_ownership_is_final_stage():
    orchestrator = GuidedIntakeOrchestrator()
    response = build_create(orchestrator, "INTAKE-AC7", "Create a new SMS message for wealth product planning.")
    question = question_cards(response)[0]
    assert question.group_id != "qg_project_ownership_final"
    assert "project_name" not in question.focus_fields
    assert "message_owner" not in question.focus_fields


def test_ac8_action_preview_hides_dependent_channel_changes():
    orchestrator = GuidedIntakeOrchestrator()
    response = orchestrator.build_draft(
        "INTAKE-AC8",
        BuildDraftRequest(
            mode="EDIT_REFERENCE",
            requirement="Use this reference, but send Email only.",
            selected_reference_use_case_id="M1004",
        ),
    )
    question = question_cards(response)[0]
    assert question.group_id == "qg_reference_delta_review"

    preview_response = orchestrator.parse_answer("INTAKE-AC8", question.question_id, "Use Email only.")
    preview_card = preview_response.assistant_cards[0]
    updates = preview_card.action_preview["user_facing_updates"]
    assert [update["field_name"] for update in updates] == ["channel"]
    assert all(update["field_name"] not in {"cost_center_id", "Send_to_China_flag", "sender", "push_optin_flag"} for update in updates)
    internal_impacts = orchestrator.sessions.get("INTAKE-AC8").current_action_preview.internal_impact_plan.impacts
    assert internal_impacts
    assert any(impact.affected_field in {"cost_center_id", "Send_to_China_flag", "sender", "sender_name", "router"} for impact in internal_impacts)


def test_ac9_email_setup_includes_metadata_hint():
    orchestrator = GuidedIntakeOrchestrator()
    build_create(
        orchestrator,
        "INTAKE-AC9",
        "Create an Email message when a customer wealth product matures soon.",
    )
    apply_answer(orchestrator, "INTAKE-AC9", "q_business_scenario", "Send when the customer's wealth product matures soon.")
    apply_answer(orchestrator, "INTAKE-AC9", "q_delivery_mode_risk", "Batch, not high risk, no 7*24.")
    apply_answer(orchestrator, "INTAKE-AC9", "q_business_identity", "WPB, use case name is Wealth Product Maturity Reminder.")
    session = orchestrator.sessions.get("INTAKE-AC9")
    question = session.active_question_state
    assert question.group_id == "qg_email_route_sender"
    assert "self-identifiable" in question.why_asking or "hangseng" in question.why_asking.lower()


def test_ac10_next_question_after_preview_comes_from_planner():
    orchestrator = GuidedIntakeOrchestrator()
    build_create(orchestrator, "INTAKE-AC10", "Create a new SMS message for wealth product planning.")
    applied = apply_answer(
        orchestrator,
        "INTAKE-AC10",
        "q_business_scenario",
        "Send when customer starts wealth product planning.",
    )
    question = [card for card in applied["assistant_cards"] if card.type == "question"][0]
    assert question.group_id == "qg_delivery_mode_risk"
    assert question.group_id != "qg_missing_required"
    runtime_states = orchestrator.planner.last_runtime_states
    selected = [state for state in runtime_states if state["chosen"]]
    assert selected
    assert selected[0]["group_id"] == "qg_delivery_mode_risk"
    assert selected[0]["ask_when_results"]
    assert not any(state["group_id"] == "qg_project_ownership_final" and state["chosen"] for state in runtime_states)


def test_parser_scope_blocks_unrelated_updates():
    orchestrator = GuidedIntakeOrchestrator()
    build_create(orchestrator, "INTAKE-SCOPE", "Create a new SMS message for wealth product planning.")
    preview_response = orchestrator.parse_answer(
        "INTAKE-SCOPE",
        "q_business_scenario",
        "Send when customer starts planning. Project name is Wealth Project and source system is PEGA.",
    )
    updates = preview_response.assistant_cards[0].action_preview["user_facing_updates"]
    fields = {update["field_name"] for update in updates}
    assert "message_trigger_conditions" in fields
    assert "project_name" not in fields
    assert "source_system" not in fields


def test_group_question_does_not_repeat_already_confirmed_field():
    orchestrator = GuidedIntakeOrchestrator()
    build_create(orchestrator, "INTAKE-NOREPEAT", "Create a new SMS message for wealth product planning.")
    apply_answer(
        orchestrator,
        "INTAKE-NOREPEAT",
        "q_business_scenario",
        "Send when customer starts wealth product planning.",
    )
    response = orchestrator.update_field("INTAKE-NOREPEAT", "delivery_mode", "BATCH")
    question = [card for card in response["assistant_cards"] if card.type == "question"][0]
    assert question.group_id == "qg_delivery_mode_risk"
    assert "delivery_mode" not in question.focus_fields
    assert "Delivery Mode" not in question.question
    assert "High Risk" in question.question
    assert "Is 7*24" in question.question


def test_select_options_are_sent_to_frontend_fields():
    orchestrator = GuidedIntakeOrchestrator()
    response = build_create(orchestrator, "INTAKE-OPTIONS", "Create a new SMS message for wealth product planning.")
    channel = next(field for field in response.modules["channel"].fields if field.name == "channel")
    delivery_mode = next(field for field in response.modules["business"].fields if field.name == "delivery_mode")
    assert channel.value == "SMS"
    assert any(option["value"] == "SMS" for option in channel.options)
    assert any(option["value"] == "BATCH" for option in delivery_mode.options)
