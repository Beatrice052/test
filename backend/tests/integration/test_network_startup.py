"""Verify that the ASGI application serves real HTTP traffic."""

import json
import socket
import threading
import urllib.request

import uvicorn

from app.main import create_app
from app.settings import AppSettings


def test_uvicorn_serves_mock_readiness_over_http() -> None:
    app = create_app(AppSettings(chatbi_llm_mode="fixture", chatbi_gateway_mode="mock"))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", log_level="error", lifespan="on"))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/v1/health/ready", timeout=5
            ) as response:
                payload = json.loads(response.read())

            assert response.status == 200
            assert payload["status"] == "ready"
            assert payload["profile"] == "mock"
        finally:
            server.should_exit = True
            thread.join(timeout=5)

    assert not thread.is_alive()
