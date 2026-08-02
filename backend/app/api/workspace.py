"""Owner-scoped Session, Turn, Answer, Dataset, Evidence, and Semantic APIs."""

# ruff: noqa: RUF001

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from app.api.dependencies import container, identity
from app.api.models import (
    ChatApiResponse,
    ChatErrorEnvelope,
    ChatProgressEnvelope,
    ChatResultEnvelope,
    DatasetRowsResponse,
    EvidenceView,
    SemanticCompileRequest,
    SemanticPackageResponse,
    SessionCreateRequest,
    SessionDetailResponse,
    SessionPatchRequest,
    TurnResponse,
)
from app.bootstrap import ApplicationContainer
from app.contracts.common import semantic_hash
from app.contracts.progress import AnalysisProgressEvent
from app.contracts.request import ChatRequest, IdentityContext
from app.contracts.session import AnswerSnapshot, SessionContext
from app.persistence.answer_repository import AnswerRepository
from app.persistence.ids import new_id
from app.persistence.serialization import load_json, load_time
from app.persistence.session_repository import SessionRepository
from app.presentation.evidence import EvidenceAccessPolicy, EvidenceExporter
from app.security.authorization import AuthorizationError, require_role
from app.semantic.compiler import compile_semantic_package

router = APIRouter(prefix="/api/v1", tags=["workspace"])
Identity = Annotated[IdentityContext, Depends(identity)]
Container = Annotated[ApplicationContainer, Depends(container)]


def _sessions(app: ApplicationContainer) -> SessionRepository:
    return SessionRepository(app.database)


def _answers(app: ApplicationContainer) -> AnswerRepository:
    return AnswerRepository(app.database)


def _turn_response(record: object) -> TurnResponse:
    from app.persistence.models import TurnRecord

    if not isinstance(record, TurnRecord):
        raise TypeError("turn record is invalid")
    error = load_json(record.error_json) if record.error_json is not None else None
    return TurnResponse(
        turn_id=record.turn_id,
        session_id=record.session_id,
        client_turn_id=record.client_turn_id,
        attempt=record.attempt,
        status=record.status,
        retryable=record.retryable,
        created_at=load_time(record.created_at),
        updated_at=load_time(record.updated_at),
        error=error if isinstance(error, dict) else None,
    )


@router.post("/sessions", response_model=SessionContext, status_code=201)
def create_session(body: SessionCreateRequest, subject: Identity, app: Container) -> SessionContext:
    return _sessions(app).create_session(subject.subject_id, title=body.title)


@router.get("/sessions", response_model=tuple[SessionContext, ...])
def list_sessions(
    subject: Identity,
    app: Container,
    include_archived: bool = False,
) -> tuple[SessionContext, ...]:
    return _sessions(app).list_sessions(subject.subject_id, include_archived=include_archived)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_session(session_id: str, subject: Identity, app: Container) -> SessionDetailResponse:
    session = _sessions(app).get_session(subject.subject_id, session_id)
    answers = _answers(app).list_answers(subject.subject_id, session_id)
    return SessionDetailResponse(session=session, answers=answers)


@router.patch("/sessions/{session_id}", response_model=SessionContext)
def patch_session(
    session_id: str,
    body: SessionPatchRequest,
    subject: Identity,
    app: Container,
) -> SessionContext:
    return _sessions(app).update_title(
        subject.subject_id,
        session_id,
        title=body.title,
        expected_version=body.expected_version,
    )


@router.post("/sessions/{session_id}/archive", response_model=SessionContext)
def archive_session(session_id: str, subject: Identity, app: Container) -> SessionContext:
    return _sessions(app).archive_session(subject.subject_id, session_id)


@router.post("/chat", response_model=ChatApiResponse)
async def chat(body: ChatRequest, subject: Identity, app: Container) -> ChatApiResponse:
    result = await app.orchestrator.run(
        subject,
        body,
        correlation_id=new_id("cor"),
    )
    return ChatApiResponse(
        status=result.status,
        session_id=result.session_id,
        turn_id=result.turn_id,
        answer=result.answer,
    )


def _sse(event: str, payload: str) -> str:
    return f"event: {event}\ndata: {payload}\n\n"


@router.post("/chat/stream", response_class=StreamingResponse)
async def chat_stream(
    body: ChatRequest,
    request: Request,
    subject: Identity,
    app: Container,
) -> StreamingResponse:
    """Stream safe graph progress, then the same immutable result as POST /chat."""

    async def events() -> AsyncIterator[str]:
        progress_queue: asyncio.Queue[AnalysisProgressEvent] = asyncio.Queue(maxsize=64)
        task = asyncio.create_task(
            app.orchestrator.run(
                subject,
                body,
                correlation_id=new_id("cor"),
                progress_callback=progress_queue.put,
            )
        )
        try:
            while not task.done() or not progress_queue.empty():
                if await request.is_disconnected():
                    return
                try:
                    progress = await asyncio.wait_for(progress_queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                envelope = ChatProgressEnvelope(progress=progress)
                yield _sse("progress", envelope.model_dump_json())

            result = await task
            response = ChatApiResponse(
                status=result.status,
                session_id=result.session_id,
                turn_id=result.turn_id,
                answer=result.answer,
            )
            yield _sse("result", ChatResultEnvelope(result=response).model_dump_json())
        except asyncio.CancelledError:
            raise
        except Exception:
            error = ChatErrorEnvelope(
                code="ORCHESTRATION_FAILED",
                message="本次分析未完成，请重试；如持续失败请联系管理员查看服务端日志。",
            )
            yield _sse("error", error.model_dump_json())
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/turns/{turn_id}", response_model=TurnResponse)
def get_turn(turn_id: str, subject: Identity, app: Container) -> TurnResponse:
    return _turn_response(_sessions(app).get_turn(subject.subject_id, turn_id))


@router.post("/turns/{turn_id}/cancel", response_model=TurnResponse)
def cancel_turn(turn_id: str, subject: Identity, app: Container) -> TurnResponse:
    return _turn_response(_sessions(app).cancel_turn(subject.subject_id, turn_id))


@router.get("/answers/{answer_id}", response_model=AnswerSnapshot)
def get_answer(answer_id: str, subject: Identity, app: Container) -> AnswerSnapshot:
    return _answers(app).get_answer(subject.subject_id, answer_id)


@router.get("/answers/{answer_id}/evidence", response_model=EvidenceView)
def get_evidence(answer_id: str, subject: Identity, app: Container) -> EvidenceView:
    answer = _answers(app).get_answer(subject.subject_id, answer_id)
    if answer.evidence_package is None:
        raise HTTPException(status_code=404, detail="evidence is not available")
    evidence = answer.evidence_package
    advanced = evidence.advanced if EvidenceAccessPolicy().allow_advanced(subject) else None
    return EvidenceView(
        evidence_id=evidence.object_id,
        business=evidence.business,
        advanced=advanced,
        redaction=evidence.redaction,
    )


@router.get("/answers/{answer_id}/debug")
def get_debug(answer_id: str, subject: Identity, app: Container) -> dict[str, object]:
    if not app.settings.chatbi_debug_api_enabled:
        raise HTTPException(status_code=404, detail="debug API is disabled")
    if not EvidenceAccessPolicy().allow_debug(subject):
        raise AuthorizationError("developer role is required")
    answer = _answers(app).get_answer(subject.subject_id, answer_id)
    return {
        "answer_id": answer.object_id,
        "content_hash": answer.content_hash,
        "provenance": answer.provenance.model_dump(mode="json"),
        "analysis_plan_id": answer.analysis_plan.object_id if answer.analysis_plan else None,
        "query_plan_id": answer.query_plan.object_id if answer.query_plan else None,
        "dataset_bundle_id": answer.dataset_bundle.object_id if answer.dataset_bundle else None,
    }


@router.get("/datasets/{dataset_id}/rows", response_model=DatasetRowsResponse)
def get_dataset_rows(
    dataset_id: str,
    subject: Identity,
    app: Container,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> DatasetRowsResponse:
    dataset = _answers(app).get_dataset(subject.subject_id, dataset_id)
    return DatasetRowsResponse(
        object_id=dataset.object_id,
        dataset_id=dataset.dataset_id,
        kind=dataset.kind,
        grain=dataset.grain,
        columns=dataset.columns,
        rows=dataset.rows[offset : offset + limit],
        offset=offset,
        limit=limit,
        total=len(dataset.rows),
        complete=dataset.complete,
        warnings=dataset.warnings,
    )


@router.get("/datasets/{dataset_id}/csv")
def get_dataset_csv(dataset_id: str, subject: Identity, app: Container) -> Response:
    dataset = _answers(app).get_dataset(subject.subject_id, dataset_id)
    if not EvidenceAccessPolicy().allow_csv(subject, dataset):
        raise AuthorizationError("dataset classification does not permit CSV export")
    csv_text = EvidenceExporter().dataset_csv(dataset)
    safe_name = "".join(item for item in dataset.dataset_id if item.isalnum() or item in {"-", "_"})
    return Response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.csv"'},
    )


@router.get("/semantic/packages/current", response_model=SemanticPackageResponse)
def semantic_current(app: Container) -> SemanticPackageResponse:
    package = app.semantic_package
    return SemanticPackageResponse(
        package_version=package.manifest.package_version,
        manifest_hash=semantic_hash(package.manifest),
        field_count=len(package.fields()),
        metric_count=len(package.metrics()),
        generated_at=package.manifest.compiled_at,
    )


@router.post("/admin/semantic/compile")
def semantic_compile(
    body: SemanticCompileRequest, subject: Identity, app: Container
) -> dict[str, object]:
    del body
    require_role(subject, "admin")
    output = app.settings.app_artifact_dir / "semantic-admin" / new_id("compile")
    result = compile_semantic_package(app.settings.chatbi_semantic_input_dir, output)
    return {
        "status": result.report.status,
        "package_version": result.manifest.package_version,
        "field_count": len(result.fields),
        "output_ref": output.name,
    }


@router.get("/admin/semantic/import-reports/{report_id}")
def semantic_import_report(report_id: str, subject: Identity, app: Container) -> dict[str, object]:
    require_role(subject, "admin")
    report = app.semantic_package.import_report()
    if report_id not in {report.object_id, "current"}:
        raise HTTPException(status_code=404, detail="import report not found")
    return report.model_dump(mode="json")
