from __future__ import annotations

import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cpa_inspection_bridge.config import Settings, merge_settings
from cpa_inspection_bridge.db import Database
from cpa_inspection_bridge.notifier import looks_like_telegram_bot_token, looks_like_telegram_chat_id
from cpa_inspection_bridge.service import BridgeService


MANAGEMENT_KEY = "test-management-key"
TELEGRAM_TOKEN = "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789"


class MockCPAHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if not self.authorized():
            self.write_json({"error": "unauthorized"}, status=401)
            return
        if self.path == "/v0/management/auth-files":
            self.write_json(
                {
                    "files": [
                        {
                            "name": "codex-healthy.json",
                            "auth_index": "codex-healthy",
                            "provider": "codex",
                            "account": "healthy@example.test",
                            "disabled": False,
                        },
                        {
                            "name": "codex-full.json",
                            "auth_index": "codex-full",
                            "provider": "codex",
                            "account": "full@example.test",
                            "disabled": False,
                        },
                        {
                            "name": "claude.json",
                            "auth_index": "claude-1",
                            "provider": "claude",
                        },
                    ]
                }
            )
            return
        self.write_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        if not self.authorized():
            self.write_json({"error": "unauthorized"}, status=401)
            return
        if self.path != "/v0/management/api-call":
            self.write_json({"error": "not found"}, status=404)
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        used = 20 if payload.get("authIndex") == "codex-healthy" else 100
        self.write_json(
            {
                "status_code": 200,
                "body": {
                    "rate_limit": {
                        "allowed": used < 100,
                        "limit_reached": used >= 100,
                        "primary_window": {
                            "limit_window_seconds": 604800,
                            "used_percent": used,
                        },
                        "secondary_window": {
                            "limit_window_seconds": 18000,
                            "used_percent": 10,
                        },
                    }
                },
            }
        )

    def authorized(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {MANAGEMENT_KEY}"

    def write_json(self, payload: dict, status: int = 200) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    current = Settings(telegram_bot_token=TELEGRAM_TOKEN)
    masked = current.public_dict()["telegram_bot_token"]
    merged = merge_settings(current, {"telegram_bot_token": masked})
    assert merged.telegram_bot_token == TELEGRAM_TOKEN
    assert looks_like_telegram_bot_token(TELEGRAM_TOKEN)
    assert not looks_like_telegram_bot_token(masked)
    assert looks_like_telegram_chat_id("123456789")
    assert looks_like_telegram_chat_id("-1001234567890")
    assert looks_like_telegram_chat_id("@channelusername")
    assert not looks_like_telegram_chat_id("my_bot_name")

    server = ThreadingHTTPServer(("127.0.0.1", 0), MockCPAHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    with tempfile.TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "bridge.db")
        db.save_settings(
            Settings(
                cpa_base_url=base_url,
                cpa_management_key=MANAGEMENT_KEY,
                notify_on_success=False,
                notify_on_abnormal=False,
                auto_start=False,
            )
        )
        service = BridgeService(db)
        run_id = service.run_once("smoke")
        run = db.get_run(run_id)

    server.shutdown()
    assert run is not None
    assert run["status"] == "success", run
    assert run["summary"]["total"] == 2, run
    assert run["summary"]["healthy"] == 1, run
    assert run["summary"]["zero_quota"] == 1, run
    assert len(run["accounts"]) == 2, run
    print("smoke ok")


if __name__ == "__main__":
    main()
