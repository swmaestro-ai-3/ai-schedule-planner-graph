from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from backend.api import (
    OAuthRequiredError,
    create_plan_response,
    openai_connect_response,
    openai_status_response,
    replan_response,
)


class PlannerRequestHandler(BaseHTTPRequestHandler):
    server_version = "NextPlanPlannerAPI/0.1"

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        raw_body = self.rfile.read(length).decode("utf-8")
        return json.loads(raw_body)

    def do_OPTIONS(self) -> None:
        self._send_json(200, {"ok": True})

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"ok": True})
            return
        if self.path == "/api/openai/status":
            self._send_json(200, openai_status_response())
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            request = self._read_json()
            if self.path == "/api/plans":
                self._send_json(200, create_plan_response(request))
                return
            if self.path == "/api/replans":
                self._send_json(200, replan_response(request))
                return
            if self.path == "/api/openai/connect":
                self._send_json(200, openai_connect_response())
                return
            self._send_json(404, {"error": "not found"})
        except OAuthRequiredError as exc:
            self._send_json(401, {"error": str(exc), "code": "openai_oauth_required"})
        except Exception as exc:
            self._send_json(400, {"error": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), PlannerRequestHandler)
    print(f"Planner API listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
