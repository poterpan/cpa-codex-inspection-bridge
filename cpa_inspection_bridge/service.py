from __future__ import annotations

import threading
import time
from typing import Any

from .db import Database
from .inspector import Inspector
from .notifier import Notifier


class BridgeService:
    def __init__(self, db: Database):
        self.db = db
        self._run_lock = threading.Lock()
        self._scheduler_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._next_run_at_ms: int | None = None
        self._last_scheduler_error = ""

    def start_scheduler(self) -> None:
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            return
        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True, name="inspection-scheduler")
        self._scheduler_thread.start()

    def stop_scheduler(self) -> None:
        self._stop_event.set()
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)

    def run_async(self, trigger_type: str = "manual") -> bool:
        if self._run_lock.locked():
            return False
        thread = threading.Thread(target=self.run_once, args=(trigger_type,), daemon=True, name="inspection-run")
        thread.start()
        return True

    def run_once(self, trigger_type: str = "manual") -> int:
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError("inspection is already running")
        run_id = self.db.create_run(trigger_type)
        status = "success"
        summary: dict[str, Any] = {}
        results: list[dict[str, Any]] = []
        error = ""
        try:
            settings = self.db.get_settings()
            results, summary = Inspector(settings).inspect()
            if summary.get("probe_failed", 0) or summary.get("unknown", 0):
                status = "partial"
            attempts = Notifier(settings).send_run_summary(run_id, status, summary, results)
            self.db.insert_account_results(run_id, results)
            self.db.insert_notification_attempts(run_id, attempts)
            return run_id
        except Exception as exc:
            status = "failed"
            error = str(exc)
            summary = summary or {"total": len(results), "abnormal": len(results)}
            return run_id
        finally:
            self.db.finish_run(run_id, status, summary, error)
            self._run_lock.release()

    def status(self) -> dict[str, Any]:
        thread_alive = bool(self._scheduler_thread and self._scheduler_thread.is_alive())
        return {
            "running": self._run_lock.locked(),
            "scheduler_running": thread_alive,
            "next_run_at_ms": self._next_run_at_ms,
            "last_scheduler_error": self._last_scheduler_error,
        }

    def reschedule_now(self) -> None:
        settings = self.db.get_settings()
        self._next_run_at_ms = int(time.time() * 1000) + settings.interval_minutes * 60 * 1000

    def _scheduler_loop(self) -> None:
        settings = self.db.get_settings()
        if settings.auto_start:
            self._next_run_at_ms = int(time.time() * 1000) + 2000
        else:
            self._next_run_at_ms = int(time.time() * 1000) + settings.interval_minutes * 60 * 1000
        while not self._stop_event.wait(1):
            settings = self.db.get_settings()
            now = int(time.time() * 1000)
            if self._next_run_at_ms is None:
                self._next_run_at_ms = now + settings.interval_minutes * 60 * 1000
            if now < self._next_run_at_ms:
                continue
            if self._run_lock.locked():
                self._next_run_at_ms = now + 60 * 1000
                continue
            if not settings.cpa_base_url or not settings.cpa_management_key:
                self._last_scheduler_error = "CPA-compatible API base URL and management key are required"
                self._next_run_at_ms = now + 60 * 1000
                continue
            try:
                self.run_once("scheduled")
                self._last_scheduler_error = ""
            except Exception as exc:
                self._last_scheduler_error = str(exc)
            finally:
                refreshed = self.db.get_settings()
                self._next_run_at_ms = int(time.time() * 1000) + refreshed.interval_minutes * 60 * 1000
