from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import Settings


class Notifier:
    def __init__(self, settings: Settings):
        self.settings = settings

    def should_notify(self, status: str, summary: dict[str, Any]) -> bool:
        abnormal = status != "success" or int(summary.get("abnormal") or 0) > 0
        if abnormal and self.settings.notify_on_abnormal:
            return True
        if not abnormal and self.settings.notify_on_success:
            return True
        return False

    def send_run_summary(self, run_id: int, status: str, summary: dict[str, Any], results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.should_notify(status, summary):
            return []
        title = f"CPA Codex inspection #{run_id}: {status}"
        body = render_body(summary, results)
        attempts = []
        if self.settings.telegram_enabled:
            attempts.append(self._attempt("telegram", lambda: self.send_telegram(f"{title}\n\n{body}")))
        if self.settings.bark_enabled:
            attempts.append(self._attempt("bark", lambda: self.send_bark(title, body)))
        return attempts

    def _attempt(self, channel: str, fn) -> dict[str, Any]:
        try:
            response_summary = fn()
            return {"channel": channel, "status": "success", "response_summary": response_summary, "error": ""}
        except Exception as exc:
            return {"channel": channel, "status": "failed", "response_summary": "", "error": str(exc)}

    def send_telegram(self, text: str) -> str:
        token = self.settings.telegram_bot_token.strip()
        chat_id = self.settings.telegram_chat_id.strip()
        if not token or not chat_id:
            raise RuntimeError("telegram bot token and chat id are required")
        api_base = self.settings.telegram_api_base.strip().rstrip("/") or "https://api.telegram.org"
        endpoint = f"{api_base}/bot{token}/sendMessage"
        return post_json(endpoint, {"chat_id": chat_id, "text": text})

    def send_bark(self, title: str, body: str) -> str:
        device_key = self.settings.bark_device_key.strip()
        if not device_key:
            raise RuntimeError("bark device key is required")
        server = self.settings.bark_server.strip().rstrip("/") or "https://api.day.app"
        endpoint = f"{server}/push"
        payload = {
            "device_key": device_key,
            "title": title,
            "body": body,
            "group": self.settings.bark_group or "CPA Codex Inspection",
        }
        return post_json(endpoint, payload)


def render_body(summary: dict[str, Any], results: list[dict[str, Any]]) -> str:
    lines = [
        f"Total: {summary.get('total', 0)}",
        f"Healthy: {summary.get('healthy', 0)}",
        f"Zero quota: {summary.get('zero_quota', 0)}",
        f"Full quota: {summary.get('full_quota', 0)}",
        f"Invalid: {summary.get('invalid', 0)}",
        f"Probe failed: {summary.get('probe_failed', 0)}",
        f"Unknown: {summary.get('unknown', 0)}",
        f"Recommended: disable {summary.get('disable', 0)}, enable {summary.get('enable', 0)}, keep {summary.get('keep', 0)}",
    ]
    abnormal = [
        item
        for item in results
        if item.get("classification") in {"zero_quota", "full_quota", "invalid", "probe_failed", "unknown"}
        or item.get("recommended_action") in {"disable", "enable", "delete"}
    ][:10]
    if abnormal:
        lines.append("")
        lines.append("First abnormal accounts:")
        for item in abnormal:
            account = item.get("display_account") or item.get("file_name") or item.get("auth_index") or "-"
            classification = item.get("classification") or "unknown"
            action = item.get("recommended_action") or "keep"
            used = item.get("used_percent")
            used_text = "-" if used is None else f"{float(used):.1f}%"
            lines.append(f"- {account}: {classification}, {used_text}, action={action}")
    return "\n".join(lines)


def post_json(endpoint: str, payload: dict[str, Any]) -> str:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            text = response.read(2048).decode("utf-8", errors="replace").strip()
            return text[:500] or f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        detail = exc.read(2048).decode("utf-8", errors="replace")
        raise RuntimeError(f"notification request failed: HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"notification request failed: {exc.reason}") from exc
