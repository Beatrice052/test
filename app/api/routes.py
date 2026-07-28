from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.agent.service import ChatBIAgent
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    SemanticReportResponse,
    SessionResetRequest,
    SessionResetResponse,
)
from app.config.settings import Settings
from app.semantic.models import CompilationResult, CompiledSemanticModel
from app.sessions.store import InMemorySessionStore

router = APIRouter(prefix="/api")


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _sessions(request: Request) -> InMemorySessionStore:
    return request.app.state.session_store


def _agent(request: Request) -> ChatBIAgent:
    return request.app.state.chatbi_agent


def _semantic(request: Request) -> CompiledSemanticModel:
    return request.app.state.semantic_compilation.model


def _compilation(request: Request) -> CompilationResult:
    return request.app.state.semantic_compilation


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = _settings(request)
    model = _semantic(request)
    connection_status = request.app.state.connection_status
    return HealthResponse(
        app_name=settings.app_name,
        phase=(
            "external-mock-complete"
            if settings.data_source_mode == "mock"
            else "internal-connected"
        ),
        data_source_mode=settings.data_source_mode,
        connection_status=connection_status,
        index_scope=settings.index_scope_label,
        default_time_from=settings.default_time_from.isoformat(),
        default_time_to=settings.default_time_to.isoformat(),
        business_timezone=settings.business_timezone,
        semantic_model_version=model.model_version,
        capabilities={
            "chat_contract": True,
            "session_store": True,
            "semantic_compiler": True,
            "query_execution": True,
            "multi_month": True,
            "multi_turn_clarification": True,
            "evidence": True,
            "structured_llm": request.app.state.llm_mode == "structured_llm",
            "generic_opensearch_api": False,
            "ppl": False,
        },
    )


@router.get("/admin/semantic/report", response_model=SemanticReportResponse)
def semantic_report(request: Request) -> SemanticReportResponse:
    compilation = _compilation(request)
    return SemanticReportResponse(
        model_version=compilation.model.model_version,
        import_status=compilation.report.status,
        report=compilation.report.model_dump(mode="json"),
    )


@router.post("/session/reset", response_model=SessionResetResponse)
def reset_session(payload: SessionResetRequest, request: Request) -> SessionResetResponse:
    state = _sessions(request).reset(payload.session_id)
    return SessionResetResponse(session_id=state.session_id)


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    settings = _settings(request)
    if len(payload.message) > settings.max_message_chars:
        raise HTTPException(
            status_code=422,
            detail="message exceeds configured maximum length",
        )
    return _agent(request).answer(payload)
