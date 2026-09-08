from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .__main__ import _tasks_from_payload
from .continuation import build_continuation_plan
from .coordinator import CoordinationError, build_plan


def coordinate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CoordinationError("request body must be a JSON object")

    tasks = _tasks_from_payload(payload)
    budget = payload.get("budget", 12_000)
    completed = payload.get("completed", [])
    if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
        raise CoordinationError("budget must be a positive integer")
    if not isinstance(completed, list) or not all(isinstance(item, str) for item in completed):
        raise CoordinationError("completed must be an array of task IDs")

    if completed:
        return build_continuation_plan(
            tasks,
            completed_task_ids=completed,
            global_budget=budget,
        ).to_dict()
    return build_plan(tasks, global_budget=budget).to_dict()


class CoordinatorHandler(BaseHTTPRequestHandler):
    server_version = "AnthropicAgentCoordinator/1.0"

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._json(200, {"status": "ok"})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/coordinate":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_048_576:
                raise CoordinationError("request body must be between 1 byte and 1 MiB")
            payload = json.loads(self.rfile.read(length))
            self._json(200, coordinate_payload(payload))
        except (CoordinationError, json.JSONDecodeError, ValueError) as exc:
            self._json(400, {"error": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        return


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    ThreadingHTTPServer((host, port), CoordinatorHandler).serve_forever()
