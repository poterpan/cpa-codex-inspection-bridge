from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .config import Settings, settings_from_env


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("pragma journal_mode = wal")
        self._conn.execute("pragma foreign_keys = on")
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                create table if not exists settings (
                    id integer primary key check (id = 1),
                    data_json text not null,
                    updated_at_ms integer not null
                );

                create table if not exists runs (
                    id integer primary key autoincrement,
                    trigger_type text not null,
                    status text not null,
                    started_at_ms integer not null,
                    finished_at_ms integer,
                    duration_ms integer,
                    summary_json text not null default '{}',
                    error text not null default ''
                );

                create table if not exists account_results (
                    id integer primary key autoincrement,
                    run_id integer not null references runs(id) on delete cascade,
                    file_name text not null default '',
                    auth_index text not null default '',
                    account_id text not null default '',
                    display_account text not null default '',
                    provider text not null default '',
                    disabled_before integer not null default 0,
                    status text not null default '',
                    status_code integer,
                    used_percent real,
                    classification text not null default '',
                    recommended_action text not null default '',
                    action_reason text not null default '',
                    error text not null default '',
                    rate_limit_json text,
                    raw_json text,
                    created_at_ms integer not null
                );

                create table if not exists notification_attempts (
                    id integer primary key autoincrement,
                    run_id integer not null references runs(id) on delete cascade,
                    channel text not null,
                    status text not null,
                    error text not null default '',
                    response_summary text not null default '',
                    created_at_ms integer not null
                );

                create index if not exists idx_account_results_run on account_results(run_id);
                create index if not exists idx_notification_attempts_run on notification_attempts(run_id);
                create index if not exists idx_runs_started_at on runs(started_at_ms desc);
                """
            )
            if not self._conn.execute("select 1 from settings where id = 1").fetchone():
                self.save_settings(settings_from_env())

    def get_settings(self) -> Settings:
        with self._lock:
            row = self._conn.execute("select data_json from settings where id = 1").fetchone()
        if not row:
            return settings_from_env()
        data = json.loads(row["data_json"])
        baseline = asdict(settings_from_env())
        baseline.update({key: value for key, value in data.items() if key in baseline})
        return Settings(**baseline)

    def save_settings(self, settings: Settings) -> None:
        now = int(time.time() * 1000)
        with self._lock, self._conn:
            self._conn.execute(
                """
                insert into settings (id, data_json, updated_at_ms)
                values (1, ?, ?)
                on conflict(id) do update set
                    data_json = excluded.data_json,
                    updated_at_ms = excluded.updated_at_ms
                """,
                (json.dumps(asdict(settings), ensure_ascii=True), now),
            )

    def create_run(self, trigger_type: str) -> int:
        now = int(time.time() * 1000)
        with self._lock, self._conn:
            cur = self._conn.execute(
                "insert into runs (trigger_type, status, started_at_ms) values (?, 'running', ?)",
                (trigger_type, now),
            )
            return int(cur.lastrowid)

    def finish_run(self, run_id: int, status: str, summary: dict[str, Any], error: str = "") -> None:
        now = int(time.time() * 1000)
        with self._lock, self._conn:
            row = self._conn.execute("select started_at_ms from runs where id = ?", (run_id,)).fetchone()
            started = int(row["started_at_ms"]) if row else now
            self._conn.execute(
                """
                update runs
                set status = ?, finished_at_ms = ?, duration_ms = ?, summary_json = ?, error = ?
                where id = ?
                """,
                (
                    status,
                    now,
                    max(0, now - started),
                    json.dumps(summary, ensure_ascii=True),
                    error or "",
                    run_id,
                ),
            )

    def insert_account_results(self, run_id: int, results: list[dict[str, Any]]) -> None:
        if not results:
            return
        now = int(time.time() * 1000)
        rows = []
        for item in results:
            rows.append(
                (
                    run_id,
                    item.get("file_name", ""),
                    item.get("auth_index", ""),
                    item.get("account_id", ""),
                    item.get("display_account", ""),
                    item.get("provider", ""),
                    1 if item.get("disabled_before") else 0,
                    item.get("status", ""),
                    item.get("status_code"),
                    item.get("used_percent"),
                    item.get("classification", ""),
                    item.get("recommended_action", ""),
                    item.get("action_reason", ""),
                    item.get("error", ""),
                    json.dumps(item.get("rate_limit"), ensure_ascii=True) if item.get("rate_limit") is not None else None,
                    json.dumps(item.get("raw"), ensure_ascii=True) if item.get("raw") is not None else None,
                    now,
                )
            )
        with self._lock, self._conn:
            self._conn.executemany(
                """
                insert into account_results (
                    run_id, file_name, auth_index, account_id, display_account, provider,
                    disabled_before, status, status_code, used_percent, classification,
                    recommended_action, action_reason, error, rate_limit_json, raw_json, created_at_ms
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def insert_notification_attempts(self, run_id: int, attempts: list[dict[str, Any]]) -> None:
        if not attempts:
            return
        now = int(time.time() * 1000)
        rows = [
            (
                run_id,
                item.get("channel", ""),
                item.get("status", ""),
                item.get("error", ""),
                item.get("response_summary", ""),
                now,
            )
            for item in attempts
        ]
        with self._lock, self._conn:
            self._conn.executemany(
                """
                insert into notification_attempts (
                    run_id, channel, status, error, response_summary, created_at_ms
                ) values (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(200, int(limit)))
        with self._lock:
            rows = self._conn.execute(
                "select * from runs order by started_at_ms desc limit ?",
                (limit,),
            ).fetchall()
        return [run_to_dict(row) for row in rows]

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        with self._lock:
            run = self._conn.execute("select * from runs where id = ?", (run_id,)).fetchone()
            if not run:
                return None
            accounts = self._conn.execute(
                "select * from account_results where run_id = ? order by id asc",
                (run_id,),
            ).fetchall()
            notifications = self._conn.execute(
                "select * from notification_attempts where run_id = ? order by id asc",
                (run_id,),
            ).fetchall()
        result = run_to_dict(run)
        result["accounts"] = [account_to_dict(row) for row in accounts]
        result["notifications"] = [notification_to_dict(row) for row in notifications]
        return result


def run_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["summary"] = json.loads(data.pop("summary_json") or "{}")
    return data


def account_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["disabled_before"] = bool(data["disabled_before"])
    data["rate_limit"] = json.loads(data.pop("rate_limit_json")) if data.get("rate_limit_json") else None
    data["raw"] = json.loads(data.pop("raw_json")) if data.get("raw_json") else None
    return data


def notification_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)
