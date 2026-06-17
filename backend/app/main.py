from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import AnalyzeRequirementRequest, ApplyPreviewRequest, BuildDraftRequest, ParseAnswerRequest, UpdateFieldRequest
from .services import GuidedIntakeOrchestrator


app = FastAPI(title="Requirement Intake Guided Backend MVP", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = GuidedIntakeOrchestrator()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/intake/{intake_id}/requirement/analyze")
def analyze_requirement(intake_id: str, body: AnalyzeRequirementRequest):
    try:
        return orchestrator.analyze_requirement(intake_id, body.requirement)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# Frontend-compatible contract used by src/api/realClient.ts
@app.post("/api/intake/{intake_id}/draft/build")
def build_draft(intake_id: str, body: BuildDraftRequest):
    try:
        return orchestrator.build_draft(intake_id, body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/intake/{intake_id}/assistant/parse-answer")
def parse_answer(intake_id: str, body: ParseAnswerRequest):
    try:
        return orchestrator.parse_answer(intake_id, body.question_id, body.answer)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/intake/{intake_id}/assistant/apply-preview")
def apply_preview(intake_id: str, body: ApplyPreviewRequest):
    try:
        return orchestrator.apply_preview(intake_id, body.preview_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/intake/{intake_id}/fields/{field_name}")
def update_field(intake_id: str, field_name: str, body: UpdateFieldRequest):
    try:
        return orchestrator.update_field(intake_id, field_name, body.value)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/intake/{intake_id}/validate")
def validate(intake_id: str):
    try:
        return orchestrator.validate(intake_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/intake/{intake_id}/export-for-ac")
def export_for_ac(intake_id: str):
    try:
        return orchestrator.export_for_ac(intake_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# Spec-style guided aliases for backend evolution.
@app.post("/api/intake/guided/create-new")
def guided_create_new(body: dict):
    intake_id = body.get("intake_id") or "INTAKE-001"
    request = BuildDraftRequest(mode="CREATE_NEW", requirement=body["requirement"])
    return orchestrator.build_draft(intake_id, request)


@app.post("/api/intake/guided/edit-reference")
def guided_edit_reference(body: dict):
    intake_id = body.get("intake_id") or "INTAKE-001"
    request = BuildDraftRequest(
        mode="EDIT_REFERENCE",
        requirement=body["requirement"],
        selected_reference_use_case_id=body.get("reference_use_case_id") or body.get("selected_reference_use_case_id"),
    )
    return orchestrator.build_draft(intake_id, request)


@app.post("/api/intake/{intake_id}/guided/answer")
def guided_answer(intake_id: str, body: ParseAnswerRequest):
    return parse_answer(intake_id, body)


@app.post("/api/intake/{intake_id}/guided/apply-preview")
def guided_apply_preview(intake_id: str, body: ApplyPreviewRequest):
    return apply_preview(intake_id, body)


@app.post("/api/intake/{intake_id}/guided/validate")
def guided_validate(intake_id: str):
    return validate(intake_id)


@app.post("/api/intake/{intake_id}/guided/export-for-ac")
def guided_export_for_ac(intake_id: str):
    return export_for_ac(intake_id)
