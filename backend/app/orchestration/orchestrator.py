"""Single orchestration entry point for session, idempotency, lock, and graph."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Literal, cast

from app.contracts.request import ChatRequest, IdentityContext
from app.contracts.session import AnswerSnapshot
from app.observability.audit import SafeAuditLogger
from app.orchestration.graph import ChatBIGraph
from app.orchestration.progress import AnalysisProgressReporter, ProgressCallback
from app.orchestration.state import ChatBIState
from app.persistence.answer_repository import AnswerRepository
from app.persistence.errors import TurnCancelled
from app.persistence.idempotency_repository import IdempotencyRepository
from app.persistence.locks import SessionLockRepository
from app.persistence.session_repository import SessionRepository

type OrchestrationStatus = Literal[
    "PLANNED", "COMPILED", "ANALYZED", "COMPLETED", "RUNNING", "FAILED", "CANCELLED"
]


@dataclass(frozen=True, slots=True)
class OrchestrationResult:
    status: OrchestrationStatus
    session_id: str
    turn_id: str
    answer: AnswerSnapshot | None = None
    state: ChatBIState | None = None


class ChatBIOrchestrator:
    def __init__(
        self,
        *,
        graph: ChatBIGraph,
        sessions: SessionRepository,
        answers: AnswerRepository,
        idempotency: IdempotencyRepository,
        locks: SessionLockRepository,
        lock_lease_seconds: int = 120,
        turn_timeout_seconds: float = 90,
        audit: SafeAuditLogger | None = None,
    ) -> None:
        self.graph = graph
        self.sessions = sessions
        self.answers = answers
        self.idempotency = idempotency
        self.locks = locks
        self.lock_lease_seconds = max(30, lock_lease_seconds)
        if turn_timeout_seconds <= 0:
            raise ValueError("turn timeout must be positive")
        self.turn_timeout_seconds = turn_timeout_seconds
        self.audit = audit or SafeAuditLogger()

    async def run(
        self,
        identity: IdentityContext,
        request: ChatRequest,
        *,
        correlation_id: str,
        fixture_id: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> OrchestrationResult:
        reporter = (
            AnalysisProgressReporter(progress_callback) if progress_callback is not None else None
        )
        if reporter is not None:
            await reporter.started()
        if request.session_id is None:
            session = self.sessions.create_session(identity.subject_id)
            request = request.model_copy(update={"session_id": session.object_id})
        else:
            session = self.sessions.get_session(identity.subject_id, request.session_id)
        claim = self.idempotency.begin(identity.subject_id, session.object_id, request)
        if claim.outcome == "COMPLETED":
            if claim.answer_id is None:
                raise RuntimeError("completed idempotency record has no answer")
            if reporter is not None:
                await reporter.replayed()
            return OrchestrationResult(
                status="COMPLETED",
                session_id=session.object_id,
                turn_id=claim.turn_id,
                answer=self.answers.get_answer(identity.subject_id, claim.answer_id),
            )
        if claim.outcome == "RUNNING":
            if reporter is not None:
                await reporter.running_elsewhere()
            return OrchestrationResult(
                status="RUNNING",
                session_id=session.object_id,
                turn_id=claim.turn_id,
            )
        if claim.outcome == "FAILED":
            if reporter is not None:
                await reporter.finish(cast(ChatBIState, {"terminal_status": "FAILED"}))
            return OrchestrationResult(
                status="FAILED",
                session_id=session.object_id,
                turn_id=claim.turn_id,
            )

        self.locks.acquire(
            identity.subject_id,
            session.object_id,
            claim.turn_id,
            lease_seconds=self.lock_lease_seconds,
        )
        heartbeat = asyncio.create_task(
            self._heartbeat_lock(identity.subject_id, session.object_id, claim.turn_id)
        )
        self.audit.emit(
            "turn_run",
            correlation_id=correlation_id,
            session_id=session.object_id,
            turn_id=claim.turn_id,
            status="started",
        )
        initial: ChatBIState = {
            "request": request,
            "identity": identity,
            "correlation_id": correlation_id,
            "turn_id": claim.turn_id,
        }
        if fixture_id is not None:
            initial["fixture_id"] = fixture_id
        try:
            async with asyncio.timeout(self.turn_timeout_seconds):
                state = await self._await_with_heartbeat(
                    self._invoke_graph(initial, claim.turn_id, reporter), heartbeat
                )
            answer = state.get("answer_snapshot")
            if state.get("terminal_status") in {
                "QUERY_PLAN_FAILED",
                "GATEWAY_FAILED",
                "DATA_QA_FAILED",
            }:
                error_codes = [item.code for item in state.get("errors", ())]
                self.sessions.mark_turn_failed(
                    identity.subject_id,
                    claim.turn_id,
                    error={"codes": error_codes},
                    retryable=False,
                )
                self.idempotency.mark_failed(identity.subject_id, claim.turn_id, retryable=False)
                return OrchestrationResult(
                    status="FAILED",
                    session_id=session.object_id,
                    turn_id=claim.turn_id,
                    state=state,
                )
            status: OrchestrationStatus = (
                "COMPLETED"
                if answer is not None
                else "ANALYZED"
                if state.get("terminal_status") == "DATASET_READY"
                else "COMPILED"
                if state.get("terminal_status") == "COMPILED"
                else "PLANNED"
            )
            self.audit.emit(
                "turn_run",
                correlation_id=correlation_id,
                session_id=session.object_id,
                turn_id=claim.turn_id,
                status=status.casefold(),
            )
            return OrchestrationResult(
                status=status,
                session_id=session.object_id,
                turn_id=claim.turn_id,
                answer=answer,
                state=state,
            )
        except TurnCancelled:
            self.audit.emit(
                "turn_run",
                correlation_id=correlation_id,
                session_id=session.object_id,
                turn_id=claim.turn_id,
                status="cancelled",
            )
            return OrchestrationResult(
                status="CANCELLED",
                session_id=session.object_id,
                turn_id=claim.turn_id,
            )
        except asyncio.CancelledError:
            self.sessions.mark_turn_cancelled(identity.subject_id, claim.turn_id)
            raise
        except TimeoutError:
            self.audit.emit(
                "turn_run",
                correlation_id=correlation_id,
                session_id=session.object_id,
                turn_id=claim.turn_id,
                status="failed",
                error_type="TurnTimeout",
            )
            self.sessions.mark_turn_failed(
                identity.subject_id,
                claim.turn_id,
                error={"code": "TURN_TIMEOUT"},
                retryable=True,
            )
            self.idempotency.mark_failed(identity.subject_id, claim.turn_id, retryable=True)
            return OrchestrationResult(
                status="FAILED",
                session_id=session.object_id,
                turn_id=claim.turn_id,
            )
        except BaseException as error:
            self.audit.emit(
                "turn_run",
                correlation_id=correlation_id,
                session_id=session.object_id,
                turn_id=claim.turn_id,
                status="failed",
                error_type=type(error).__name__,
            )
            error_payload = {"code": "ORCHESTRATION_FAILED", "type": type(error).__name__}
            self.sessions.mark_turn_failed(
                identity.subject_id,
                claim.turn_id,
                error=error_payload,
                retryable=False,
            )
            self.idempotency.mark_failed(identity.subject_id, claim.turn_id, retryable=False)
            raise
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
            self.locks.release(identity.subject_id, session.object_id, claim.turn_id)

    async def _heartbeat_lock(self, subject_id: str, session_id: str, turn_id: str) -> None:
        interval = max(5, self.lock_lease_seconds // 3)
        while True:
            await asyncio.sleep(interval)
            self.locks.heartbeat(
                subject_id,
                session_id,
                turn_id,
                lease_seconds=self.lock_lease_seconds,
            )

    @staticmethod
    async def _await_with_heartbeat(
        operation: Coroutine[Any, Any, ChatBIState],
        heartbeat: asyncio.Task[None],
    ) -> ChatBIState:
        graph_task: asyncio.Task[ChatBIState] = asyncio.create_task(operation)
        try:
            done, _ = await asyncio.wait(
                {graph_task, heartbeat}, return_when=asyncio.FIRST_COMPLETED
            )
            if heartbeat in done:
                error = heartbeat.exception()
                if error is not None:
                    raise error
                raise RuntimeError("session lock heartbeat stopped unexpectedly")
            return await graph_task
        finally:
            if not graph_task.done():
                graph_task.cancel()
                with suppress(asyncio.CancelledError):
                    await graph_task

    async def _invoke_graph(
        self,
        initial: ChatBIState,
        turn_id: str,
        reporter: AnalysisProgressReporter | None,
    ) -> ChatBIState:
        config: Any = {"configurable": {"thread_id": turn_id}}
        if reporter is None:
            result: dict[str, Any] = await self.graph.ainvoke(initial, config=config)
            return cast(ChatBIState, result)

        accumulated: dict[str, Any] = dict(initial)
        async for chunk in self.graph.astream(initial, config=config, stream_mode="updates"):
            if not isinstance(chunk, dict):
                continue
            for node, update in chunk.items():
                if not isinstance(node, str) or not isinstance(update, dict):
                    continue
                accumulated.update(update)
                await reporter.after_node(node, cast(ChatBIState, accumulated))
        state = cast(ChatBIState, accumulated)
        await reporter.finish(state)
        return state

    async def resume_pending(
        self,
        identity: IdentityContext,
        turn_id: str,
        *,
        correlation_id: str,
    ) -> OrchestrationResult:
        """Resume an owned RUNNING checkpoint or retry an explicitly retryable failure."""

        turn = self.sessions.get_turn(identity.subject_id, turn_id)
        if turn.status == "FAILED":
            if not turn.retryable:
                return OrchestrationResult(
                    status="FAILED",
                    session_id=turn.session_id,
                    turn_id=turn.turn_id,
                )
            return await self.run(
                identity,
                self.sessions.request_from_turn(turn),
                correlation_id=correlation_id,
            )
        if turn.status != "RUNNING":
            raise ValueError(f"turn is not recoverable: {turn.status}")

        self.locks.acquire(
            identity.subject_id,
            turn.session_id,
            turn_id,
            lease_seconds=self.lock_lease_seconds,
        )
        heartbeat = asyncio.create_task(
            self._heartbeat_lock(identity.subject_id, turn.session_id, turn_id)
        )
        try:
            resume_input = cast(ChatBIState, None)
            resumed = self.graph.ainvoke(
                resume_input, config={"configurable": {"thread_id": turn_id}}
            )
            async with asyncio.timeout(self.turn_timeout_seconds):
                state = await self._await_with_heartbeat(
                    cast(Coroutine[Any, Any, ChatBIState], resumed), heartbeat
                )
            answer = state.get("answer_snapshot")
            status: OrchestrationStatus = (
                "COMPLETED"
                if answer is not None
                else "ANALYZED"
                if state.get("terminal_status") == "DATASET_READY"
                else "COMPILED"
                if state.get("terminal_status") == "COMPILED"
                else "PLANNED"
            )
            return OrchestrationResult(
                status=status,
                session_id=turn.session_id,
                turn_id=turn_id,
                answer=answer,
                state=state,
            )
        except TurnCancelled:
            return OrchestrationResult(
                status="CANCELLED",
                session_id=turn.session_id,
                turn_id=turn_id,
            )
        except asyncio.CancelledError:
            self.sessions.mark_turn_cancelled(identity.subject_id, turn_id)
            raise
        except TimeoutError:
            self.sessions.mark_turn_failed(
                identity.subject_id,
                turn_id,
                error={"code": "TURN_TIMEOUT"},
                retryable=True,
            )
            self.idempotency.mark_failed(identity.subject_id, turn_id, retryable=True)
            return OrchestrationResult(
                status="FAILED",
                session_id=turn.session_id,
                turn_id=turn_id,
            )
        except BaseException as error:
            error_payload = {"code": "RECOVERY_FAILED", "type": type(error).__name__}
            self.sessions.mark_turn_failed(
                identity.subject_id,
                turn_id,
                error=error_payload,
                retryable=True,
            )
            self.idempotency.mark_failed(identity.subject_id, turn_id, retryable=True)
            raise
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
            self.locks.release(identity.subject_id, turn.session_id, turn_id)
