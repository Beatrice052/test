"""Guard against unsafe patterns copied from the demo opensearch-agent architecture."""

import ast
from pathlib import Path

import yaml

from app.contracts.dashboard import DashboardSpec
from app.main import create_app

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
MCP_CONFIG = Path(__file__).resolve().parents[3] / "config" / "gateway.mcp.yaml"
FORBIDDEN_CALLS = {
    "AgentExecutor",
    "OpenAIFunctionsAgent",
    "create_react_agent",
    "create_openai_functions_agent",
}
FORBIDDEN_STRING_LITERALS = {
    "admin/admin",
    "plot.png",
    "GenericOpenSearchApiTool",
    "PPLQueryTool",
}


def _application_trees() -> list[tuple[Path, ast.AST]]:
    return [
        (path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        for path in APP_ROOT.rglob("*.py")
    ]


def test_no_free_agent_executor_or_react_factory() -> None:
    violations: list[str] = []
    for path, tree in _application_trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                if name in FORBIDDEN_CALLS:
                    violations.append(f"{path}:{node.lineno}:{name}")
    assert violations == []


def test_no_forbidden_tool_or_demo_credential_literals() -> None:
    violations: list[str] = []
    for path, tree in _application_trees():
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value in FORBIDDEN_STRING_LITERALS
            ):
                violations.append(f"{path}:{node.lineno}:{node.value}")
    assert violations == []


def test_public_api_has_no_raw_dsl_request_field() -> None:
    openapi = create_app().openapi()
    property_names = {
        property_name
        for schema in openapi.get("components", {}).get("schemas", {}).values()
        for property_name in schema.get("properties", {})
    }
    assert "raw_dsl" not in property_names


def test_agents_have_no_gateway_mcp_database_or_tool_imports() -> None:
    forbidden_prefixes = ("app.gateway", "app.persistence", "mcp", "opensearchpy")
    violations: list[str] = []
    for path in (APP_ROOT / "agents").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            imported: tuple[str, ...] = ()
            if isinstance(node, ast.Import):
                imported = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = (node.module,)
            for module in imported:
                if module.startswith(forbidden_prefixes):
                    violations.append(f"{path}:{node.lineno}:{module}")
    assert violations == []


def test_agents_depend_on_the_llm_protocol_not_a_concrete_mock_or_endpoint() -> None:
    forbidden_modules = {
        "app.llm.fixture",
        "app.llm.openai_compatible",
        "app.llm.recorded",
        "app.llm.rule_based",
    }
    violations: list[str] = []
    for path in (APP_ROOT / "agents").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            if module in forbidden_modules:
                violations.append(f"{path}:{node.lineno}:{module}")
    assert violations == []


def test_natural_language_chart_alias_parser_is_not_an_orchestration_decision_node() -> None:
    allowed = {
        APP_ROOT / "llm" / "rule_based.py",
        APP_ROOT / "presentation" / "chart_preferences.py",
    }
    violations: list[str] = []
    for path, tree in _application_trees():
        if path in allowed:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "parse_chart_preference":
                violations.append(f"{path}:{node.lineno}")
            if isinstance(node, ast.ImportFrom) and any(
                alias.name == "parse_chart_preference" for alias in node.names
            ):
                violations.append(f"{path}:{node.lineno}")
    assert violations == []


def test_structured_llm_interface_has_no_tool_parameter() -> None:
    tree = ast.parse(
        (APP_ROOT / "llm" / "client.py").read_text(encoding="utf-8"),
        filename="llm/client.py",
    )
    parameters = {
        argument.arg
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        for argument in (*node.args.args, *node.args.kwonlyargs)
    }
    assert not {"tool", "tools", "tool_choice", "mcp_tools"}.intersection(parameters)


def test_mcp_config_never_binds_forbidden_tools() -> None:
    raw = yaml.safe_load(MCP_CONFIG.read_text(encoding="utf-8"))
    mcp = raw["gateway"]["mcp"]
    bound_tools = set(mcp["tool_bindings"].values())
    forbidden_tools = set(mcp["forbidden_tools"])
    assert forbidden_tools == {"GenericOpenSearchApiTool", "PPLQueryTool"}
    assert bound_tools.isdisjoint(forbidden_tools)
    assert set(mcp["allowed_capabilities"]).issubset(mcp["tool_bindings"])


def test_dashboard_contract_has_no_executable_or_raw_rendering_fields() -> None:
    schema = DashboardSpec.model_json_schema()

    def property_names(value: object) -> set[str]:
        if isinstance(value, dict):
            names = (
                set(value.get("properties", {}))
                if isinstance(value.get("properties"), dict)
                else set()
            )
            return names.union(*(property_names(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(property_names(item) for item in value)) if value else set()
        return set()

    forbidden = {
        "raw_option",
        "formatter_function",
        "custom_series",
        "renderItem",
        "graphic",
        "javascript",
        "html",
    }
    assert property_names(schema).isdisjoint(forbidden)
