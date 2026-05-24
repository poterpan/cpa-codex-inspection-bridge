from __future__ import annotations

import base64
import concurrent.futures
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import Settings


CODEX_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
FIVE_HOUR_WINDOW_SECONDS = 18000
WEEK_WINDOW_SECONDS = 604800
QUOTA_BODY_PATTERNS = ("quota exhausted", "limit reached", "payment_required")


@dataclass
class Account:
    file_name: str
    auth_index: str
    account_id: str
    display_account: str
    provider: str
    disabled: bool
    raw: dict[str, Any]


class Inspector:
    def __init__(self, settings: Settings):
        self.settings = settings

    def inspect(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        files = self.fetch_auth_files()
        accounts = [account for account in (to_account(item) for item in files) if account.provider == "codex"]
        accounts.sort(key=lambda account: (account.file_name, account.display_account))

        results: list[dict[str, Any]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.settings.concurrency) as executor:
            futures = [executor.submit(self.inspect_account, account) for account in accounts]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        results.sort(key=lambda item: (item.get("file_name", ""), item.get("display_account", "")))
        summary = build_summary(results)
        return results, summary

    def fetch_auth_files(self) -> list[dict[str, Any]]:
        payload = http_json(
            "GET",
            management_url(self.settings.cpa_base_url, "/v0/management/auth-files"),
            headers=management_headers(self.settings),
            timeout=self.settings.timeout_seconds,
        )
        files = payload.get("files", [])
        if not isinstance(files, list):
            raise RuntimeError("auth-files response missing files array")
        return [item for item in files if isinstance(item, dict)]

    def inspect_account(self, account: Account) -> dict[str, Any]:
        result = {
            "file_name": account.file_name,
            "auth_index": account.auth_index,
            "account_id": account.account_id,
            "display_account": account.display_account,
            "provider": account.provider,
            "disabled_before": account.disabled,
            "status": "success",
            "status_code": None,
            "used_percent": None,
            "classification": "unknown",
            "recommended_action": "keep",
            "action_reason": "",
            "error": "",
            "rate_limit": None,
            "raw": None,
        }
        if not account.auth_index:
            result.update(
                {
                    "status": "unknown",
                    "classification": "unknown",
                    "action_reason": "missing auth_index; keeping account",
                    "error": "missing auth_index",
                }
            )
            return result

        try:
            api_result = self.call_codex_usage(account)
        except Exception as exc:
            result.update(
                {
                    "status": "failed",
                    "classification": "probe_failed",
                    "action_reason": "probe failed; keeping account",
                    "error": str(exc),
                }
            )
            return result

        result["status_code"] = api_result["status_code"]
        result["raw"] = api_result["raw"]
        result["rate_limit"] = api_result["rate_limit"]
        result["used_percent"] = api_result["used_percent"]
        classification, action, reason = classify_result(account, api_result, self.settings.quota_threshold)
        result["classification"] = classification
        result["recommended_action"] = action
        result["action_reason"] = reason
        if classification == "probe_failed":
            result["status"] = "failed"
        elif classification == "unknown":
            result["status"] = "unknown"
        return result

    def call_codex_usage(self, account: Account) -> dict[str, Any]:
        api_headers = {
            "Authorization": "Bearer $TOKEN$",
            "Content-Type": "application/json",
            "User-Agent": "codex_cli_rs/0.76.0 (Debian 13.0.0; x86_64) WindowsTerminal",
        }
        if account.account_id:
            api_headers["Chatgpt-Account-Id"] = account.account_id
        request_payload = {
            "authIndex": account.auth_index,
            "method": "GET",
            "url": CODEX_USAGE_URL,
            "header": api_headers,
        }
        response = http_json(
            "POST",
            management_url(self.settings.cpa_base_url, "/v0/management/api-call"),
            headers=management_headers(self.settings),
            data=request_payload,
            timeout=self.settings.timeout_seconds,
        )
        status_code = read_status_code(response.get("status_code", response.get("statusCode")))
        if status_code is None:
            raise RuntimeError("api-call response missing status_code")

        body_value = response.get("body")
        body_text = normalize_body_text(body_value)
        body_json = parse_json_value(body_value, body_text)
        rate_limit = first_dict(body_json.get("rate_limit"), body_json.get("rateLimit")) if isinstance(body_json, dict) else None
        used_percent = derive_used_percent(rate_limit)
        quota = status_code == 402 or is_rate_limit_reached(rate_limit)
        lowered = body_text.lower()
        if any(pattern in lowered for pattern in QUOTA_BODY_PATTERNS):
            quota = True
        if used_percent is not None and used_percent >= 100:
            quota = True

        return {
            "status_code": status_code,
            "body_text": body_text,
            "used_percent": used_percent,
            "quota": quota,
            "rate_limit": rate_limit,
            "raw": response,
        }


def classify_result(account: Account, api_result: dict[str, Any], threshold: float) -> tuple[str, str, str]:
    status_code = int(api_result.get("status_code") or 0)
    if status_code == 401:
        return "invalid", "keep", "api returned 401; account is invalid but bridge only notifies"
    rate_limit = api_result.get("rate_limit")
    if isinstance(rate_limit, dict):
        weekly = pick_window(rate_limit, WEEK_WINDOW_SECONDS)
        weekly_used = window_used_percent(weekly)
        five_hour = pick_window(rate_limit, FIVE_HOUR_WINDOW_SECONDS)
        five_hour_used = window_used_percent(five_hour)
        if weekly is not None and weekly_used is not None:
            if weekly_used >= threshold or api_result.get("quota"):
                if account.disabled:
                    return "zero_quota", "keep", "weekly quota reached threshold; account is already disabled"
                return "zero_quota", "disable", "weekly quota reached threshold; disable is recommended"
            if account.disabled:
                return "healthy", "enable", "weekly quota is available; re-enable is recommended"
            if five_hour_used is not None and five_hour_used >= threshold:
                return "full_quota", "keep", "5-hour quota reached threshold but weekly quota remains available"
            return "healthy", "keep", "weekly quota remains available"

    used_percent = api_result.get("used_percent")
    if api_result.get("quota") or (used_percent is not None and used_percent >= threshold):
        if account.disabled:
            return "zero_quota", "keep", "quota reached threshold; account is already disabled"
        return "zero_quota", "disable", "quota reached threshold; disable is recommended"
    if 200 <= status_code < 300:
        if account.disabled:
            return "healthy", "enable", "account is healthy; re-enable is recommended"
        return "healthy", "keep", "no action needed"
    return "unknown", "keep", "status cannot be safely classified"


def build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "total": len(results),
        "healthy": 0,
        "zero_quota": 0,
        "full_quota": 0,
        "invalid": 0,
        "probe_failed": 0,
        "unknown": 0,
        "keep": 0,
        "disable": 0,
        "enable": 0,
        "delete": 0,
        "abnormal": 0,
    }
    for item in results:
        classification = item.get("classification") or "unknown"
        if classification in summary:
            summary[classification] += 1
        else:
            summary["unknown"] += 1
        action = item.get("recommended_action") or "keep"
        if action in ("keep", "disable", "enable", "delete"):
            summary[action] += 1
        else:
            summary["keep"] += 1
    summary["abnormal"] = summary["zero_quota"] + summary["full_quota"] + summary["invalid"] + summary["probe_failed"] + summary["unknown"]
    return summary


def management_url(base_url: str, path: str) -> str:
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def management_headers(settings: Settings) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "CPA-Manager-Inspection-Bridge/0.1",
    }
    if settings.cpa_management_key:
        headers["Authorization"] = f"Bearer {settings.cpa_management_key}"
    return headers


def http_json(method: str, url: str, headers: dict[str, str] | None = None, data: Any = None, timeout: int = 20) -> dict[str, Any]:
    body = None if data is None else json.dumps(data).encode("utf-8")
    request = urllib.request.Request(url, data=body, method=method.upper(), headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read(2048).decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def to_account(file: dict[str, Any]) -> Account:
    file_name = first_non_empty(read_string(file, "name"), read_string(file, "id"), normalize_auth_index(file.get("auth_index")), normalize_auth_index(file.get("authIndex")))
    auth_index = first_non_empty(normalize_auth_index(file.get("auth_index")), normalize_auth_index(file.get("authIndex")))
    display = first_non_empty(read_string(file, "account"), read_string(file, "email"), read_string(file, "label"), file_name, auth_index, "-")
    return Account(
        file_name=file_name,
        auth_index=auth_index,
        account_id=resolve_chatgpt_account_id(file),
        display_account=display,
        provider=first_non_empty(read_string(file, "provider"), read_string(file, "type")).lower(),
        disabled=read_disabled(file),
        raw=file,
    )


def resolve_chatgpt_account_id(record: dict[str, Any]) -> str:
    for key in ("chatgpt_account_id", "chatgptAccountId", "account_id", "accountId"):
        value = read_string(record, key)
        if value:
            return value
    for key in ("metadata", "attributes"):
        nested = record.get(key)
        if isinstance(nested, dict):
            value = resolve_chatgpt_account_id(nested)
            if value:
                return value
    for key in ("id_token", "idToken"):
        value = extract_account_id_from_token(record.get(key))
        if value:
            return value
    return ""


def extract_account_id_from_token(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return first_non_empty(read_string(value, "chatgpt_account_id"), read_string(value, "chatgptAccountId"), read_string(value, "account_id"), read_string(value, "accountId"))
    text = str(value).strip()
    if not text:
        return ""
    if text.startswith("{"):
        parsed = parse_json_value(text, text)
        if isinstance(parsed, dict):
            return extract_account_id_from_token(parsed)
    parts = text.split(".")
    if len(parts) < 2:
        return ""
    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = base64.urlsafe_b64decode(padded.encode("ascii"))
        parsed = json.loads(payload.decode("utf-8"))
    except Exception:
        return ""
    return extract_account_id_from_token(parsed)


def read_string(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def read_disabled(record: dict[str, Any]) -> bool:
    status = first_non_empty(read_string(record, "status"), read_string(record, "state")).lower()
    if status in ("disabled", "inactive"):
        return True
    return truthy(record.get("disabled"))


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def first_non_empty(*values: str) -> str:
    for value in values:
        text = str(value or "").strip()
        if text and text != "<nil>":
            return text
    return ""


def normalize_auth_index(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text == "<nil>" else text


def read_status_code(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def normalize_body_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=True)


def parse_json_value(value: Any, text: str) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def first_dict(*values: Any) -> dict[str, Any] | None:
    for value in values:
        if isinstance(value, dict):
            return value
    return None


def derive_used_percent(rate_limit: dict[str, Any] | None) -> float | None:
    if not isinstance(rate_limit, dict):
        return None
    candidates = [
        rate_limit.get("primary_window"),
        rate_limit.get("primaryWindow"),
        rate_limit.get("secondary_window"),
        rate_limit.get("secondaryWindow"),
    ]
    percentages = [value for value in (window_used_percent(item) for item in candidates) if value is not None]
    if not percentages:
        return None
    return max(percentages)


def is_rate_limit_reached(rate_limit: dict[str, Any] | None) -> bool:
    if not isinstance(rate_limit, dict):
        return False
    for key in ("limit_reached", "limitReached"):
        value = rate_limit.get(key)
        if isinstance(value, bool):
            return value
    allowed = rate_limit.get("allowed")
    if isinstance(allowed, bool):
        return not allowed
    return False


def pick_window(rate_limit: dict[str, Any], expected_seconds: int) -> dict[str, Any] | None:
    for key in ("primary_window", "primaryWindow", "secondary_window", "secondaryWindow"):
        window = rate_limit.get(key)
        if isinstance(window, dict) and window_seconds(window) == expected_seconds:
            return window
    return None


def window_seconds(window: dict[str, Any] | None) -> int | None:
    if not isinstance(window, dict):
        return None
    for key in ("limit_window_seconds", "limitWindowSeconds"):
        value = read_float(window.get(key))
        if value is not None:
            return int(value)
    return None


def window_used_percent(window: dict[str, Any] | None) -> float | None:
    if not isinstance(window, dict):
        return None
    for key in ("used_percent", "usedPercent"):
        value = read_float(window.get(key))
        if value is not None:
            return max(0.0, min(100.0, value))
    return None


def read_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def now_ms() -> int:
    return int(time.time() * 1000)
