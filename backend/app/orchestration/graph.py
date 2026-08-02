"""The single low-level StateGraph; no AgentExecutor, supervisor, or tool loop."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.orchestration.nodes import Phase2Nodes
from app.orchestration.phase3_nodes import Phase3Nodes
from app.orchestration.phase4_nodes import Phase4Nodes
from app.orchestration.phase5_nodes import Phase5Nodes
from app.orchestration.state import ChatBIState

type ChatBIGraph = CompiledStateGraph[ChatBIState, None, ChatBIState, ChatBIState]


def build_phase2_graph(
    nodes: Phase2Nodes,
    *,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> ChatBIGraph:
    graph = StateGraph(ChatBIState)
    graph.add_node("validate_request", nodes.validate_request)
    graph.add_node("authorize_and_load_session", nodes.authorize_and_load_session)
    graph.add_node("retrieve_semantic_candidates", nodes.retrieve_semantic_candidates)
    graph.add_node("analyst_planner", nodes.analyst_planner)
    graph.add_node("validate_analysis_plan", nodes.validate_analysis_plan)
    graph.add_node("resolve_analysis", nodes.resolve_analysis)
    graph.add_node("persist_terminal", nodes.persist_terminal)
    graph.add_node("phase2_ready", nodes.phase2_ready)

    graph.add_edge(START, "validate_request")
    graph.add_edge("validate_request", "authorize_and_load_session")
    graph.add_edge("authorize_and_load_session", "retrieve_semantic_candidates")
    graph.add_edge("retrieve_semantic_candidates", "analyst_planner")
    graph.add_edge("analyst_planner", "validate_analysis_plan")
    graph.add_conditional_edges(
        "validate_analysis_plan",
        lambda state: state["analysis_route"],
        {
            "clarify": "persist_terminal",
            "unanswerable": "persist_terminal",
            "repair": "analyst_planner",
            "resolve": "resolve_analysis",
        },
    )
    graph.add_conditional_edges(
        "resolve_analysis",
        nodes.route_after_resolution,
        {"ready": "phase2_ready", "terminal": "persist_terminal"},
    )
    graph.add_edge("persist_terminal", END)
    graph.add_edge("phase2_ready", END)
    return graph.compile(checkpointer=checkpointer, name="chatbi_v6")


def build_phase3_graph(
    phase2: Phase2Nodes,
    phase3: Phase3Nodes,
    *,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> ChatBIGraph:
    graph = StateGraph(ChatBIState)
    graph.add_node("validate_request", phase2.validate_request)
    graph.add_node("authorize_and_load_session", phase2.authorize_and_load_session)
    graph.add_node("retrieve_semantic_candidates", phase2.retrieve_semantic_candidates)
    graph.add_node("analyst_planner", phase2.analyst_planner)
    graph.add_node("validate_analysis_plan", phase2.validate_analysis_plan)
    graph.add_node("resolve_analysis", phase2.resolve_analysis)
    graph.add_node("persist_terminal", phase2.persist_terminal)
    graph.add_node("logical_query_planner", phase3.logical_query_planner)
    graph.add_node("finalize_query_plan", phase3.finalize_query_plan)
    graph.add_node("compile_and_validate", phase3.compile_and_validate)
    graph.add_node("phase3_ready", phase3.phase3_ready)
    graph.add_node("phase3_failed", phase3.phase3_failed)

    graph.add_edge(START, "validate_request")
    graph.add_edge("validate_request", "authorize_and_load_session")
    graph.add_edge("authorize_and_load_session", "retrieve_semantic_candidates")
    graph.add_edge("retrieve_semantic_candidates", "analyst_planner")
    graph.add_edge("analyst_planner", "validate_analysis_plan")
    graph.add_conditional_edges(
        "validate_analysis_plan",
        lambda state: state["analysis_route"],
        {
            "clarify": "persist_terminal",
            "unanswerable": "persist_terminal",
            "repair": "analyst_planner",
            "resolve": "resolve_analysis",
        },
    )
    graph.add_conditional_edges(
        "resolve_analysis",
        phase2.route_after_resolution,
        {"ready": "logical_query_planner", "terminal": "persist_terminal"},
    )
    graph.add_edge("logical_query_planner", "finalize_query_plan")
    graph.add_conditional_edges(
        "finalize_query_plan",
        lambda state: state["query_route"],
        {
            "repair": "logical_query_planner",
            "compile": "compile_and_validate",
            "failed": "phase3_failed",
        },
    )
    graph.add_edge("compile_and_validate", "phase3_ready")
    graph.add_edge("persist_terminal", END)
    graph.add_edge("phase3_ready", END)
    graph.add_edge("phase3_failed", END)
    return graph.compile(checkpointer=checkpointer, name="chatbi_v6")


def build_phase4_graph(
    phase2: Phase2Nodes,
    phase3: Phase3Nodes,
    phase4: Phase4Nodes,
    *,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> ChatBIGraph:
    graph = StateGraph(ChatBIState)
    graph.add_node("validate_request", phase2.validate_request)
    graph.add_node("authorize_and_load_session", phase2.authorize_and_load_session)
    graph.add_node("retrieve_semantic_candidates", phase2.retrieve_semantic_candidates)
    graph.add_node("analyst_planner", phase2.analyst_planner)
    graph.add_node("validate_analysis_plan", phase2.validate_analysis_plan)
    graph.add_node("resolve_analysis", phase2.resolve_analysis)
    graph.add_node("persist_terminal", phase2.persist_terminal)
    graph.add_node("logical_query_planner", phase3.logical_query_planner)
    graph.add_node("finalize_query_plan", phase3.finalize_query_plan)
    graph.add_node("compile_and_validate", phase3.compile_and_validate)
    graph.add_node("phase3_failed", phase3.phase3_failed)
    graph.add_node("execute_and_analyze", phase4.execute_and_analyze)
    graph.add_node("phase4_ready", phase4.phase4_ready)
    graph.add_node("phase4_qa_failed", phase4.phase4_qa_failed)
    graph.add_node("phase4_gateway_failed", phase4.phase4_gateway_failed)

    graph.add_edge(START, "validate_request")
    graph.add_edge("validate_request", "authorize_and_load_session")
    graph.add_edge("authorize_and_load_session", "retrieve_semantic_candidates")
    graph.add_edge("retrieve_semantic_candidates", "analyst_planner")
    graph.add_edge("analyst_planner", "validate_analysis_plan")
    graph.add_conditional_edges(
        "validate_analysis_plan",
        lambda state: state["analysis_route"],
        {
            "clarify": "persist_terminal",
            "unanswerable": "persist_terminal",
            "repair": "analyst_planner",
            "resolve": "resolve_analysis",
        },
    )
    graph.add_conditional_edges(
        "resolve_analysis",
        phase2.route_after_resolution,
        {"ready": "logical_query_planner", "terminal": "persist_terminal"},
    )
    graph.add_edge("logical_query_planner", "finalize_query_plan")
    graph.add_conditional_edges(
        "finalize_query_plan",
        lambda state: state["query_route"],
        {
            "repair": "logical_query_planner",
            "compile": "compile_and_validate",
            "failed": "phase3_failed",
        },
    )
    graph.add_edge("compile_and_validate", "execute_and_analyze")
    graph.add_conditional_edges(
        "execute_and_analyze",
        lambda state: state["phase4_route"],
        {
            "ready": "phase4_ready",
            "qa_failed": "phase4_qa_failed",
            "failed": "phase4_gateway_failed",
        },
    )
    graph.add_edge("persist_terminal", END)
    graph.add_edge("phase3_failed", END)
    graph.add_edge("phase4_ready", END)
    graph.add_edge("phase4_qa_failed", END)
    graph.add_edge("phase4_gateway_failed", END)
    return graph.compile(checkpointer=checkpointer, name="chatbi_v6")


def build_phase5_graph(
    phase2: Phase2Nodes,
    phase3: Phase3Nodes,
    phase4: Phase4Nodes,
    phase5: Phase5Nodes,
    *,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> ChatBIGraph:
    graph = StateGraph(ChatBIState)
    graph.add_node("validate_request", phase2.validate_request)
    graph.add_node("authorize_and_load_session", phase2.authorize_and_load_session)
    graph.add_node("retrieve_semantic_candidates", phase2.retrieve_semantic_candidates)
    graph.add_node("analyst_planner", phase2.analyst_planner)
    graph.add_node("validate_analysis_plan", phase2.validate_analysis_plan)
    graph.add_node("resolve_analysis", phase2.resolve_analysis)
    graph.add_node("persist_terminal", phase2.persist_terminal)
    graph.add_node("logical_query_planner", phase3.logical_query_planner)
    graph.add_node("finalize_query_plan", phase3.finalize_query_plan)
    graph.add_node("compile_and_validate", phase3.compile_and_validate)
    graph.add_node("phase3_failed", phase3.phase3_failed)
    graph.add_node("execute_and_analyze", phase4.execute_and_analyze)
    graph.add_node("phase4_qa_failed", phase4.phase4_qa_failed)
    graph.add_node("phase4_gateway_failed", phase4.phase4_gateway_failed)
    graph.add_node("produce_answer", phase5.produce_answer)
    graph.add_node("reuse_answer", phase5.reuse_answer)
    graph.add_node("persist_forbidden", phase2.persist_forbidden)

    graph.add_edge(START, "validate_request")
    graph.add_edge("validate_request", "authorize_and_load_session")
    graph.add_conditional_edges(
        "authorize_and_load_session",
        lambda state: "forbidden" if state["request_policy"] == "forbidden" else "analyze",
        {
            "forbidden": "persist_forbidden",
            "analyze": "retrieve_semantic_candidates",
        },
    )
    graph.add_edge("retrieve_semantic_candidates", "analyst_planner")
    graph.add_edge("analyst_planner", "validate_analysis_plan")
    graph.add_conditional_edges(
        "validate_analysis_plan",
        lambda state: (
            "reuse"
            if state["analysis_route"] == "resolve"
            and state["turn_decision"].execution_mode == "reuse"
            else state["analysis_route"]
        ),
        {
            "clarify": "persist_terminal",
            "unanswerable": "persist_terminal",
            "repair": "analyst_planner",
            "resolve": "resolve_analysis",
            "reuse": "reuse_answer",
        },
    )
    graph.add_conditional_edges(
        "resolve_analysis",
        phase2.route_after_resolution,
        {"ready": "logical_query_planner", "terminal": "persist_terminal"},
    )
    graph.add_edge("logical_query_planner", "finalize_query_plan")
    graph.add_conditional_edges(
        "finalize_query_plan",
        lambda state: state["query_route"],
        {
            "repair": "logical_query_planner",
            "compile": "compile_and_validate",
            "failed": "phase3_failed",
        },
    )
    graph.add_edge("compile_and_validate", "execute_and_analyze")
    graph.add_conditional_edges(
        "execute_and_analyze",
        lambda state: state["phase4_route"],
        {
            "ready": "produce_answer",
            "qa_failed": "phase4_qa_failed",
            "failed": "phase4_gateway_failed",
        },
    )
    graph.add_edge("persist_terminal", END)
    graph.add_edge("phase3_failed", END)
    graph.add_edge("phase4_qa_failed", END)
    graph.add_edge("phase4_gateway_failed", END)
    graph.add_edge("produce_answer", END)
    graph.add_edge("reuse_answer", END)
    graph.add_edge("persist_forbidden", END)
    return graph.compile(checkpointer=checkpointer, name="chatbi_v6")
