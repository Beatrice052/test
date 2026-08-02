"""The external package contains no core placeholders or committed credentials."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE_ROOTS = (ROOT / "backend" / "app", ROOT / "frontend" / "src", ROOT / "scripts")
TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".json",
    ".yaml",
    ".yml",
    ".md",
    ".env",
    ".ps1",
    ".sh",
}


def _text_files() -> list[Path]:
    excluded = {".cache", ".venv", "node_modules", "dist", ".git"}
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not excluded.intersection(path.parts)
        and (path.suffix.lower() in TEXT_SUFFIXES or path.name == ".env.example")
        and path.name not in {"uv.lock", "package-lock.json"}
    ]


def test_core_has_no_todo_fixme_or_not_implemented_placeholder() -> None:
    token = re.compile(r"\b(?:TO" + r"DO|FIX" + r"ME|NotImplementedError)\b")
    violations = [
        str(path.relative_to(ROOT))
        for core in CORE_ROOTS
        for path in core.rglob("*")
        if path.is_file()
        and path.suffix.lower() in TEXT_SUFFIXES
        and token.search(path.read_text(encoding="utf-8"))
    ]
    assert violations == []


def test_no_real_secret_or_private_key_is_committed() -> None:
    high_confidence = (
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
        re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
    )
    assignment = re.compile(
        r"(?m)^(?:CHATBI_LLM_API_KEY|OPENSEARCH_PASSWORD|AWS_SECRET_ACCESS_KEY)=(.+)$"
    )
    violations: list[str] = []
    for path in _text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in high_confidence):
            violations.append(str(path.relative_to(ROOT)))
        for match in assignment.finditer(text):
            value = match.group(1).strip()
            if value and not value.startswith(("<", "${", "[REDACTED]")):
                violations.append(str(path.relative_to(ROOT)))
    assert violations == []
    assert not (ROOT / ".env").exists()
