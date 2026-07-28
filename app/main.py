from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.agent.service import ChatBIAgent
from app.api.routes import router as api_router
from app.config.settings import Settings, get_settings
from app.gateway.base import OpenSearchGateway
from app.gateway.mock import MockOpenSearchGateway
from app.gateway.models import GatewayCapabilities, GatewayFault
from app.intent.mock_client import MockLLMClient
from app.intent.models import LLMClient
from app.semantic.compiler import SemanticCompiler, SemanticSourcePaths
from app.semantic.models import CompilationResult
from app.sessions.store import InMemorySessionStore

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent


def create_app(
    settings: Settings | None = None,
    *,
    gateway: OpenSearchGateway | None = None,
    llm_client: LLMClient | None = None,
    semantic_compilation: CompilationResult | None = None,
    semantic_source_paths: SemanticSourcePaths | None = None,
    semantic_sources_synthetic: bool = True,
    gateway_fault: GatewayFault = GatewayFault.NONE,
    gateway_capabilities: GatewayCapabilities | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    compilation = semantic_compilation or SemanticCompiler(
        semantic_source_paths or SemanticSourcePaths.from_project_root(PROJECT_ROOT),
        business_timezone=runtime_settings.business_timezone,
        model_version=runtime_settings.semantic_model_version,
        synthetic_sources=semantic_sources_synthetic,
    ).compile_to_directory(PROJECT_ROOT / "runtime")
    if compilation.model.model_version != runtime_settings.semantic_model_version:
        raise RuntimeError(
            "injected semantic model version does not match CHATBI_SEMANTIC_MODEL_VERSION"
        )
    sessions = InMemorySessionStore(
        ttl_seconds=runtime_settings.session_ttl_seconds,
        capacity=runtime_settings.session_capacity,
        max_messages=runtime_settings.session_max_messages,
    )
    runtime_gateway = gateway or _default_gateway(
        runtime_settings,
        fault=gateway_fault,
        capabilities=gateway_capabilities,
    )
    runtime_llm = llm_client or _default_llm(runtime_settings)

    app = FastAPI(
        title=runtime_settings.app_name,
        version="1.0.0",
        description="Controlled Mock-first OpenSearch ChatBI POC",
    )
    app.state.settings = runtime_settings
    app.state.semantic_compilation = compilation
    app.state.session_store = sessions
    app.state.gateway = runtime_gateway
    app.state.connection_status = (
        "mock" if runtime_settings.data_source_mode == "mock" else "connected"
    )
    app.state.llm_mode = runtime_settings.intent_backend
    app.state.chatbi_agent = ChatBIAgent(
        settings=runtime_settings,
        model=compilation.model,
        gateway=runtime_gateway,
        sessions=sessions,
        llm_client=runtime_llm,
    )

    app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=APP_DIR / "templates")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home(request: Request) -> HTMLResponse:
        is_mock = runtime_settings.data_source_mode == "mock"
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "app_name": runtime_settings.app_name,
                "data_source_mode": runtime_settings.data_source_mode,
                "data_source_label": ("Mock OpenSearch" if is_mock else "Connected OpenSearch MCP"),
                "connection_label": "Mock Connected" if is_mock else "MCP Connected",
                "index_scope": runtime_settings.index_scope_label,
                "available_indices": runtime_gateway.list_indices(),
                "default_time_range": runtime_settings.default_time_range_label,
                "business_timezone": runtime_settings.business_timezone,
                "semantic_model_version": compilation.model.model_version,
                "phase": ("External Mock Complete" if is_mock else "Internal Connected"),
            },
        )

    app.include_router(api_router)
    return app


def _default_gateway(
    settings: Settings,
    *,
    fault: GatewayFault,
    capabilities: GatewayCapabilities | None,
) -> OpenSearchGateway:
    if settings.data_source_mode != "mock":
        raise RuntimeError("CHATBI_DATA_SOURCE_MODE=mcp requires an injected MCPOpenSearchGateway")
    return MockOpenSearchGateway(
        PROJECT_ROOT / "mock_data",
        PROJECT_ROOT / "semantic_sources" / "mock_mapping.json",
        fault=fault,
        capabilities=capabilities,
    )


def _default_llm(settings: Settings) -> LLMClient:
    if settings.intent_backend != "mock":
        raise RuntimeError("CHATBI_INTENT_BACKEND=structured_llm requires an injected LLMClient")
    return MockLLMClient(settings)


app = create_app()
