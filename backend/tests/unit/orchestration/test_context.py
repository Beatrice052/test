"""New analysis, follow-up, clarification, and new-session inheritance boundaries."""

from datetime import UTC, datetime

from app.contracts.analysis import AnswerStatus, TurnKind
from app.contracts.common import Provenance, semantic_hash
from app.contracts.request import ChatRequest
from app.contracts.session import ActiveAnalyticalContext, SessionContext
from app.orchestration.context import ContextTurnRouter


def _session(*, active: bool) -> SessionContext:
    now = datetime(2026, 8, 1, tzinfo=UTC)
    context = (
        ActiveAnalyticalContext(
            analytical_base_answer_id="ans_previous",
            dataset_ids=("sub_message",),
            metric_ids=("message_record_count.v1",),
            filter_summary=("channel=EMAIL",),
            time_summary="2026-07",
        )
        if active
        else ActiveAnalyticalContext()
    )
    return SessionContext(
        object_id="ses_context",
        created_at=now,
        content_hash=semantic_hash({"active": active}),
        provenance=Provenance(producer="tests.context"),
        subject_id="subject-a",
        title="test",
        version=0,
        active_context=context,
        latest_answer_id="ans_previous" if active else None,
        updated_at=now,
    )


def _request(message: str) -> ChatRequest:
    return ChatRequest(
        session_id="ses_context",
        message=message,
        client_turn_id=f"client-{semantic_hash(message)[7:19]}",
    )


def test_new_session_and_new_topic_do_not_inherit_filters() -> None:
    router = ContextTurnRouter()
    new_session_decision = router.decide(_request("查询7月"), _session(active=False))
    assert new_session_decision.turn_kind == TurnKind.NEW_ANALYSIS
    assert router.planner_context(_session(active=False), new_session_decision).filter_summary == ()

    new_topic_decision = router.decide(_request("新问题: 查询6月"), _session(active=True))
    assert new_topic_decision.turn_kind == TurnKind.NEW_ANALYSIS
    # Agent A receives the bounded active context and decides whether this is a new topic.
    assert router.planner_context(_session(active=True), new_topic_decision).filter_summary
    finalized = router.finalize(TurnKind.NEW_TOPIC, _session(active=True))
    assert finalized.execution_mode == "new_query"
    assert finalized.analytical_base_answer_id is None


def test_filter_followup_inherits_only_active_session_context() -> None:
    router = ContextTurnRouter()
    session = _session(active=True)
    decision = router.decide(_request("只看SMS"), session)
    assert decision.reason_codes == ("PENDING_AGENT_A_CLASSIFICATION",)
    assert router.planner_context(session, decision) == session.active_context
    finalized = router.finalize(TurnKind.FILTER_CHANGE, session)
    assert finalized.execution_mode == "requery"
    assert finalized.analytical_base_answer_id == "ans_previous"


def test_reuse_guard_forces_requery_without_changing_agent_a_turn_kind() -> None:
    router = ContextTurnRouter()
    finalized = router.finalize(TurnKind.PRESENTATION_CHANGE, _session(active=True))
    guarded = router.require_requery(finalized)

    assert guarded.turn_kind == TurnKind.PRESENTATION_CHANGE
    assert guarded.execution_mode == "requery"
    assert guarded.analytical_base_answer_id == "ans_previous"
    assert "REUSE_DATA_SIGNATURE_CHANGED" in guarded.reason_codes
    assert guarded.provenance.source_ids == (finalized.object_id,)


def test_pending_clarification_routes_reply_as_clarification() -> None:
    decision = ContextTurnRouter().decide(
        _request("消息记录数"),
        _session(active=True),
        latest_answer_status=AnswerStatus.CLARIFICATION_REQUIRED,
    )
    assert decision.turn_kind == TurnKind.CLARIFICATION
