"""Lifecycle-managed transport implemented with the official Python MCP SDK."""

from __future__ import annotations

from contextlib import AsyncExitStack
from datetime import timedelta
from pathlib import Path
from typing import Literal, cast

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

from app.contracts.common import JsonValue, StrictModel
from app.gateway.bindings import ToolDescriptor
from app.gateway.errors import GatewayCapabilityError


class McpConnectionConfig(StrictModel):
    transport: Literal["stdio", "streamable_http", "sse_legacy"]
    endpoint: str | None = None
    command: str | None = None
    args: tuple[str, ...] = ()
    cwd: Path | None = None
    environment: dict[str, str] | None = None
    call_timeout_seconds: float = 35


class OfficialMcpTransport:
    def __init__(self, config: McpConnectionConfig) -> None:
        self.config = config
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self.server_name: str | None = None
        self.server_version: str | None = None

    async def connect(self) -> None:
        if self._session is not None:
            return
        stack = AsyncExitStack()
        try:
            if self.config.transport == "stdio":
                if not self.config.command:
                    raise GatewayCapabilityError("MCP stdio command is missing")
                streams = await stack.enter_async_context(
                    stdio_client(
                        StdioServerParameters(
                            command=self.config.command,
                            args=list(self.config.args),
                            env=self.config.environment,
                            cwd=self.config.cwd,
                        )
                    )
                )
                read_stream, write_stream = streams
            elif self.config.transport == "streamable_http":
                if not self.config.endpoint:
                    raise GatewayCapabilityError("MCP HTTP endpoint is missing")
                streams = await stack.enter_async_context(
                    streamable_http_client(self.config.endpoint)
                )
                read_stream, write_stream, _ = streams
            else:
                if not self.config.endpoint:
                    raise GatewayCapabilityError("MCP SSE endpoint is missing")
                streams = await stack.enter_async_context(sse_client(self.config.endpoint))
                read_stream, write_stream = streams
            session = await stack.enter_async_context(
                ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timedelta(seconds=self.config.call_timeout_seconds),
                )
            )
            initialized = await session.initialize()
            server_info = initialized.serverInfo
            self.server_name = server_info.name
            self.server_version = server_info.version
        except BaseException:
            await stack.aclose()
            raise
        self._stack = stack
        self._session = session

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None

    async def __aenter__(self) -> OfficialMcpTransport:
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def list_tools(self) -> tuple[ToolDescriptor, ...]:
        session = self._require_session()
        descriptors: list[ToolDescriptor] = []
        cursor: str | None = None
        while True:
            result = await session.list_tools(cursor=cursor)
            descriptors.extend(
                ToolDescriptor(
                    name=tool.name,
                    input_schema=cast(dict[str, JsonValue], tool.inputSchema),
                )
                for tool in result.tools
            )
            cursor = result.nextCursor
            if cursor is None:
                return tuple(descriptors)

    async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
        return await self._require_session().call_tool(name, arguments=arguments)

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise GatewayCapabilityError("official MCP transport is not connected")
        return self._session
