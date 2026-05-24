# CPA Codex Inspection Bridge

[繁體中文](README.zh-TW.md) | English

A small temporary Codex account inspection bridge for CPA / CPA Manager compatible deployments.

It is designed for the gap before the upstream project ships a built-in scheduled inspection
task system. The bridge talks only to compatible CPA management APIs, stores history in SQLite,
and sends summary notifications to Telegram and/or Bark.

## Scope

- Uses CPA / CPA Manager compatible management APIs:
  - `GET /v0/management/auth-files`
  - `POST /v0/management/api-call`
- Calls ChatGPT Codex usage endpoint through the compatible management API:
  - `https://chatgpt.com/backend-api/wham/usage`
- Stores run history, account results, and notification attempts in SQLite.
- Provides a local control page for settings, manual runs, history, and run details.
- Supports English and Traditional Chinese in the control page.
- Sends notifications through Telegram Bot API and Bark.
- Does not disable, enable, delete, or modify accounts.

## Quick Start

```bash
cp .env.example .env
# Edit .env before the first start.
python3 app.py
```

Open:

```text
http://127.0.0.1:8766
```

The SQLite database is created at:

```text
data/inspection_bridge.db
```

## Docker

Docker is recommended when you want to keep the bridge running as a small service.

```bash
cp .env.example .env
# Edit .env before the first start.
cp docker-compose.example.yml docker-compose.yml
docker compose up -d --build
```

Open:

```text
http://127.0.0.1:8766
```

If the compatible CPA service is running on the Docker host rather than inside the same Compose network, set:

```text
CPA_BASE_URL=http://host.docker.internal:3000
```

Runtime data is stored in `./data` through the Compose volume.

## One-Shot Mode

For cron or launchd jobs that should run once and exit:

```bash
python3 app.py --once
```

## Control Page

The control page lets you configure:

- CPA-compatible Management API Base URL and management key
- inspection interval, timeout, concurrency, and quota threshold
- Telegram notification settings
- Bark notification settings
- notification behavior for clean and abnormal runs

`CPA_BASE_URL` can be any endpoint that serves compatible CPA management API routes, including
an admin/reverse-proxy domain, as long as these paths work with the management key:

```text
/v0/management/auth-files
/v0/management/api-call
```

Secrets are stored locally in SQLite. API responses and the UI show masked values.

Environment variables from `.env` seed the SQLite configuration only when
`data/inspection_bridge.db` has no saved settings yet. After that, the control page is the
normal place to edit settings. To re-seed from `.env`, stop the service and remove or move the
`data/` directory.

## Scheduling

The default daemon mode includes an internal scheduler. Keep it running with your preferred
service manager.

Example cron one-shot cadence:

```cron
0 */4 * * * cd /path/to/CPA-Manager-Inspection-Cron && /usr/bin/python3 app.py --once
```

For macOS, a launchd plist is included in `examples/launchd`.

## Verification

Run the built-in smoke test:

```bash
PYTHONPATH=. python3 -B tests/smoke_bridge.py
```

The test starts a fake compatible CPA management API, runs one inspection, verifies classification, and
checks that history is written to SQLite.

## Bark

Use the public Bark server:

```text
BARK_SERVER=https://api.day.app
BARK_DEVICE_KEY=your-device-key
```

For self-hosted Bark, set `BARK_SERVER` to your server URL.

## Telegram

Create a bot with BotFather, put its token in `TELEGRAM_BOT_TOKEN`, and set
`TELEGRAM_CHAT_ID` to the target chat ID.

## Temporary By Design

Once the upstream project ships its official scheduler and notification implementation, this
bridge can be removed. It intentionally avoids overlapping with the official task system and
does not require CPA Manager's `feat/codex-inspection-tasks` branch.
