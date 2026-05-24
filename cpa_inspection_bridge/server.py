from __future__ import annotations

import json
from http import HTTPStatus
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .config import merge_settings
from .db import Database
from .notifier import Notifier
from .service import BridgeService


class ControlServer:
    def __init__(self, host: str, port: int, db: Database, service: BridgeService):
        self.host = host
        self.port = port
        self.db = db
        self.service = service
        static_dir = Path(__file__).resolve().parent.parent / "static"
        handler = self._make_handler(static_dir)
        self.httpd = ThreadingHTTPServer((host, port), handler)

    def serve_forever(self) -> None:
        self.httpd.serve_forever()

    def shutdown(self) -> None:
        self.httpd.shutdown()

    def _make_handler(self, static_dir: Path):
        db = self.db
        service = self.service

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(static_dir), **kwargs)

            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path == "/api/status":
                    self.send_json(service.status())
                    return
                if parsed.path == "/api/config":
                    self.send_json(db.get_settings().public_dict())
                    return
                if parsed.path == "/api/runs":
                    query = parse_qs(parsed.query)
                    limit = int(query.get("limit", ["50"])[0])
                    self.send_json({"runs": db.list_runs(limit)})
                    return
                if parsed.path.startswith("/api/runs/"):
                    run_id = parse_int_path(parsed.path, "/api/runs/")
                    if run_id is None:
                        self.send_error(HTTPStatus.NOT_FOUND)
                        return
                    run = db.get_run(run_id)
                    if run is None:
                        self.send_error(HTTPStatus.NOT_FOUND)
                        return
                    self.send_json({"run": run})
                    return
                if parsed.path == "/":
                    self.path = "/index.html"
                super().do_GET()

            def do_PUT(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path != "/api/config":
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                payload = self.read_json()
                settings = merge_settings(db.get_settings(), payload)
                db.save_settings(settings)
                service.reschedule_now()
                self.send_json(settings.public_dict())

            def do_POST(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path == "/api/run-now":
                    started = service.run_async("manual")
                    status = HTTPStatus.ACCEPTED if started else HTTPStatus.CONFLICT
                    self.send_json({"started": started}, status=status)
                    return
                if parsed.path == "/api/notifications/test":
                    settings = db.get_settings()
                    notifier = Notifier(settings)
                    attempts = []
                    if settings.telegram_enabled:
                        attempts.append(notifier._attempt("telegram", lambda: notifier.send_telegram("CPA Codex inspection bridge test notification")))
                    elif settings.telegram_bot_token or settings.telegram_chat_id:
                        attempts.append({
                            "channel": "telegram",
                            "status": "skipped",
                            "error": "telegram is configured but disabled",
                            "response_summary": "",
                        })
                    if settings.bark_enabled:
                        attempts.append(notifier._attempt("bark", lambda: notifier.send_bark("CPA Codex Inspection", "Inspection bridge test notification")))
                    elif settings.bark_device_key:
                        attempts.append({
                            "channel": "bark",
                            "status": "skipped",
                            "error": "bark is configured but disabled",
                            "response_summary": "",
                        })
                    self.send_json({"attempts": attempts})
                    return
                self.send_error(HTTPStatus.NOT_FOUND)

            def read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0") or "0")
                if length <= 0:
                    return {}
                raw = self.rfile.read(length)
                return json.loads(raw.decode("utf-8"))

            def send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
                raw = json.dumps(payload, ensure_ascii=True).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, format: str, *args: Any) -> None:
                return

        return Handler


def parse_int_path(path: str, prefix: str) -> int | None:
    if not path.startswith(prefix):
        return None
    tail = path[len(prefix) :].strip("/")
    if not tail:
        return None
    try:
        return int(tail)
    except ValueError:
        return None
