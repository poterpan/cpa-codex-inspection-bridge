# CPA Codex 巡檢橋接服務

繁體中文 | [English](README.md)

這是一個給 CPA / CPA Manager 相容部署使用的臨時 Codex 帳號巡檢橋接服務。

它設計給上游專案內建的定時巡檢任務系統正式發布前使用。Bridge 只會呼叫相容的 CPA management API，把巡檢歷史存在 SQLite，並把摘要推送到 Telegram 或 Bark。

## 功能範圍

- 使用 CPA / CPA Manager 相容的 management API：
  - `GET /v0/management/auth-files`
  - `POST /v0/management/api-call`
- 透過相容的 management API 呼叫 ChatGPT Codex usage endpoint：
  - `https://chatgpt.com/backend-api/wham/usage`
- 使用 SQLite 儲存巡檢紀錄、帳號結果與通知嘗試紀錄。
- 提供本機控制頁，可設定參數、手動巡檢、查看歷史與明細。
- 控制頁支援 English / 繁體中文切換。
- 支援 Telegram Bot API 與 Bark 推送。
- 只巡檢與通知，不會停用、啟用、刪除或修改帳號。

## 快速開始

```bash
cp .env.example .env
# 第一次啟動前請先編輯 .env。
python3 app.py
```

打開：

```text
http://127.0.0.1:8766
```

SQLite 資料庫會建立在：

```text
data/inspection_bridge.db
```

## Docker

如果你想把 bridge 當成小服務常駐，建議使用 Docker。

```bash
cp .env.example .env
# 第一次啟動前請先編輯 .env。
cp docker-compose.example.yml docker-compose.yml
docker compose up -d --build
```

打開：

```text
http://127.0.0.1:8766
```

如果相容的 CPA 服務跑在 Docker host，而不是同一個 Compose network 裡，可以設定：

```text
CPA_BASE_URL=http://host.docker.internal:3000
```

執行資料會透過 Compose volume 存在 `./data`。

## 單次執行模式

如果想用 cron 或 launchd 讓程式跑一次就結束：

```bash
python3 app.py --once
```

## 控制頁

控制頁可以設定：

- CPA 相容 Management API Base URL 與管理金鑰
- 巡檢間隔、逾時、並發數與額度門檻
- Telegram 通知設定
- Bark 通知設定
- 無異常完成與異常巡檢時的推送策略

測試通知按鈕只會發送到已啟用的渠道。如果 Telegram 或 Bark 已填憑證但沒有勾選啟用，測試會被略過，UI 會顯示原因。

`CPA_BASE_URL` 可以是任何能提供相容 CPA management API routes 的入口，包含 admin/reverse-proxy 網域。只要這兩個路徑能搭配管理金鑰正常使用即可：

```text
/v0/management/auth-files
/v0/management/api-call
```

Secrets 會存在本機 SQLite。API 回應與 UI 只會顯示遮罩後的值。

`.env` 只會在 `data/inspection_bridge.db` 還沒有保存 settings 時，用來初始化 SQLite 設定。之後一般會透過控制頁修改設定。如果要重新用 `.env` 初始化，請先停止服務並移除或移動 `data/` 目錄。

## 排程

預設 daemon 模式內建排程器。請用你偏好的 service manager 讓它常駐。

cron 單次執行範例：

```cron
0 */4 * * * cd /path/to/CPA-Manager-Inspection-Cron && /usr/bin/python3 app.py --once
```

macOS 的 launchd 範例放在 `examples/launchd`。

## 驗證

執行內建 smoke test：

```bash
PYTHONPATH=. python3 -B tests/smoke_bridge.py
```

這個測試會啟動一個假的相容 CPA management API，跑一次巡檢，確認分類邏輯，並檢查歷史是否寫入 SQLite。

## Bark

使用 Bark 公共服務：

```text
BARK_SERVER=https://api.day.app
BARK_DEVICE_KEY=your-device-key
```

如果你有自架 Bark，請把 `BARK_SERVER` 設為你的伺服器網址。

## Telegram

用 BotFather 建立 bot，把 token 放到 `TELEGRAM_BOT_TOKEN`，並把 `TELEGRAM_CHAT_ID` 設為目標 chat ID。

如果是私訊推送，請先對 bot 傳一次 `/start` 再測試。如果是群組推送，請把 bot 加入群組，並使用群組的 chat ID。

## 臨時工具定位

等上游官方 scheduler 與通知實作正式發布後，這個 bridge 可以移除。它刻意避免與官方任務系統重疊，也不需要 CPA Manager 的 `feat/codex-inspection-tasks` branch。
