"""OpenAI-compatible structured-output adapter with no tool surface."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from pydantic import SecretStr, ValidationError

from app.llm.client import ALLOWED_OPERATIONS, OutputModel


class LLMAdapterError(RuntimeError):
    """Stable adapter failure that never embeds response bodies or credentials."""


class OpenAICompatibleLLMClient:
    """Call one approved chat-completions endpoint with a strict JSON Schema response."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: SecretStr | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        normalized_url = base_url.rstrip("/")
        if not normalized_url or not model.strip():
            raise ValueError("LLM base URL and model are required")
        self.endpoint = (
            normalized_url
            if normalized_url.endswith("/chat/completions")
            else f"{normalized_url}/chat/completions"
        )
        self.model = model.strip()
        self._api_key = api_key
        self._transport = transport

    async def generate(
        self,
        *,
        operation: str,
        system_prompt: str,
        input_payload: dict[str, object],
        output_schema: type[OutputModel],
        timeout_seconds: float,
        correlation_id: str,
    ) -> OutputModel:
        if operation not in ALLOWED_OPERATIONS:
            raise ValueError(f"operation is not allowed: {operation}")
        schema_name = re.sub(r"[^a-zA-Z0-9_-]", "_", f"{operation}_{output_schema.__name__}")[:64]
        request_payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        input_payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                },
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": output_schema.model_json_schema(),
                },
            },
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Correlation-ID": correlation_id,
        }
        if self._api_key is not None and self._api_key.get_secret_value():
            headers["Authorization"] = f"Bearer {self._api_key.get_secret_value()}"
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=httpx.Timeout(timeout_seconds),
            ) as client:
                response = await client.post(self.endpoint, headers=headers, json=request_payload)
                response.raise_for_status()
                payload = response.json()
            content = self._extract_content(payload)
            return output_schema.model_validate_json(content, strict=True)
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise LLMAdapterError("LLM endpoint is unavailable") from error
        except httpx.HTTPStatusError as error:
            raise LLMAdapterError(
                f"LLM endpoint returned HTTP {error.response.status_code}"
            ) from error
        except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as error:
            raise LLMAdapterError(
                "LLM response failed strict structured-output validation"
            ) from error

    @staticmethod
    def _extract_content(payload: Any) -> str:
        if not isinstance(payload, dict):
            raise TypeError("response root must be an object")
        choices = payload["choices"]
        if not isinstance(choices, list) or not choices:
            raise TypeError("response choices are missing")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise TypeError("response choice is invalid")
        message = choice["message"]
        if not isinstance(message, dict):
            raise TypeError("response message is invalid")
        content = message["content"]
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str):
                        text_parts.append(text)
            if text_parts:
                return "".join(text_parts)
        raise TypeError("response message content is invalid")
