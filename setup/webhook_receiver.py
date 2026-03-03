#!/usr/bin/env python3
"""Tiny HTTP webhook receiver for integration testing."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class WebhookHandler(BaseHTTPRequestHandler):
    server_version = "WebhookReceiver/0.1"

    def do_POST(self) -> None:  # noqa: N802 (http.server naming)
        allowed_paths = self.server.allowed_paths
        if self.path not in allowed_paths:
            self._respond(
                status=404,
                payload={
                    "ok": False,
                    "error": "not_found",
                    "allowed_paths": sorted(allowed_paths),
                },
            )
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b""
        body_text = body_bytes.decode("utf-8", errors="replace")

        parsed_body: Any = body_text
        if body_text:
            try:
                parsed_body = json.loads(body_text)
            except json.JSONDecodeError:
                parsed_body = body_text

        event = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "method": self.command,
            "path": self.path,
            "client_ip": self.client_address[0],
            "headers": dict(self.headers.items()),
            "body": parsed_body,
        }

        # Keep output machine-readable so logs can be parsed if needed.
        print(json.dumps(event, ensure_ascii=True), flush=True)

        self._respond(
            status=200,
            payload={
                "ok": True,
                "received_path": self.path,
                "received_status": (
                    parsed_body.get("status")
                    if isinstance(parsed_body, dict)
                    else None
                ),
            },
        )

    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
        if self.path == "/healthz":
            self._respond(status=200, payload={"ok": True})
            return
        self._respond(status=404, payload={"ok": False, "error": "not_found"})

    def log_message(self, format: str, *args: object) -> None:
        # Suppress default access logs to keep stdout focused on webhook events.
        return

    def _respond(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a lightweight webhook receiver for playbook testing."
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Address to bind to (default: 0.0.0.0).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=80,
        help="Port to bind to (default: 80).",
    )
    parser.add_argument(
        "--path",
        action="append",
        default=["/awx/logging"],
        help=(
            "Allowed webhook path (repeat flag for multiple paths). "
            "Default: /awx/logging."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    allowed_paths = {path if path.startswith("/") else f"/{path}" for path in args.path}
    server = ThreadingHTTPServer((args.host, args.port), WebhookHandler)
    server.allowed_paths = allowed_paths

    print(
        f"Listening on http://{args.host}:{args.port} "
        f"(allowed paths: {', '.join(sorted(allowed_paths))})",
        flush=True,
    )
    print("Health check endpoint: /healthz", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
