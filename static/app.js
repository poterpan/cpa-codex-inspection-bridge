const form = document.querySelector("#settingsForm");
const statusText = document.querySelector("#statusText");
const runsBody = document.querySelector("#runsBody");
const accountsBody = document.querySelector("#accountsBody");
const summaryTiles = document.querySelector("#summaryTiles");
const detailMeta = document.querySelector("#detailMeta");
const toast = document.querySelector("#toast");
const languageSelect = document.querySelector("#languageSelect");

const fields = [
  "cpa_base_url",
  "cpa_management_key",
  "interval_minutes",
  "auto_start",
  "concurrency",
  "timeout_seconds",
  "quota_threshold",
  "notify_on_success",
  "notify_on_abnormal",
  "telegram_enabled",
  "telegram_bot_token",
  "telegram_chat_id",
  "telegram_api_base",
  "bark_enabled",
  "bark_server",
  "bark_device_key",
  "bark_group",
];

const summaryKeys = ["total", "healthy", "zero_quota", "full_quota", "invalid", "probe_failed"];
const languageStorageKey = "cpa-inspection-bridge-language";

const translations = {
  en: {
    "app.title": "CPA Codex Inspection Bridge",
    "status.loading": "Loading status...",
    "status.running": "Inspection running",
    "status.idle": "Idle",
    "status.schedulerActive": "scheduler active",
    "status.schedulerStopped": "scheduler stopped",
    "status.nextRun": "next run {time}",
    "status.lastError": "last error: {error}",
    "actions.runNow": "Run now",
    "actions.testNotification": "Test notification",
    "actions.save": "Save",
    "actions.refresh": "Refresh",
    "sections.settings": "Settings",
    "sections.history": "History",
    "sections.runDetail": "Run detail",
    "fields.cpaBaseUrl": "CPA-compatible API Base URL",
    "fields.managementKey": "Management key",
    "fields.intervalMinutes": "Interval minutes",
    "fields.concurrency": "Concurrency",
    "fields.timeoutSeconds": "Timeout seconds",
    "fields.quotaThreshold": "Quota threshold",
    "fields.autoStart": "Run shortly after startup",
    "fields.notifySuccess": "Notify successful clean runs",
    "fields.notifyAbnormal": "Notify abnormal runs",
    "fields.telegramEnabled": "Enable Telegram",
    "fields.telegramToken": "Bot token",
    "fields.telegramChatId": "Chat ID",
    "fields.telegramApiBase": "API base",
    "fields.barkEnabled": "Enable Bark",
    "fields.barkServer": "Bark server",
    "fields.barkDeviceKey": "Device key",
    "fields.barkGroup": "Group",
    "table.id": "ID",
    "table.status": "Status",
    "table.started": "Started",
    "table.total": "Total",
    "table.abnormal": "Abnormal",
    "table.recommended": "Recommended",
    "table.account": "Account",
    "table.classification": "Class",
    "table.used": "Used",
    "table.action": "Action",
    "table.reason": "Reason",
    "toast.settingsSaved": "Settings saved",
    "toast.inspectionStarted": "Inspection started",
    "toast.notificationSent": "Notification test sent",
    "toast.notificationFailed": "Notification test failed: {error}",
    "toast.notificationNoEnabled": "Enable Telegram or Bark before testing notifications.",
    "toast.notificationSkipped": "Notification test skipped: {error}",
    "run.recommended": "disable {disable}, enable {enable}",
    "run.detailMeta": "#{id} | {status} | {time}",
    "summary.total": "total",
    "summary.healthy": "healthy",
    "summary.zero_quota": "zero quota",
    "summary.full_quota": "full quota",
    "summary.invalid": "invalid",
    "summary.probe_failed": "probe failed",
    "statusValue.success": "success",
    "statusValue.partial": "partial",
    "statusValue.failed": "failed",
    "statusValue.running": "running",
    "statusValue.healthy": "healthy",
    "statusValue.zero_quota": "zero quota",
    "statusValue.full_quota": "full quota",
    "statusValue.invalid": "invalid",
    "statusValue.probe_failed": "probe failed",
    "statusValue.unknown": "unknown",
    "action.keep": "keep",
    "action.disable": "disable",
    "action.enable": "enable",
    "action.delete": "delete",
  },
  "zh-TW": {
    "app.title": "CPA Codex 巡檢橋接服務",
    "status.loading": "正在載入狀態...",
    "status.running": "巡檢執行中",
    "status.idle": "閒置中",
    "status.schedulerActive": "排程已啟用",
    "status.schedulerStopped": "排程已停止",
    "status.nextRun": "下次執行 {time}",
    "status.lastError": "上次錯誤：{error}",
    "actions.runNow": "立即巡檢",
    "actions.testNotification": "測試通知",
    "actions.save": "儲存",
    "actions.refresh": "重新整理",
    "sections.settings": "設定",
    "sections.history": "巡檢紀錄",
    "sections.runDetail": "巡檢明細",
    "fields.cpaBaseUrl": "CPA 相容 API Base URL",
    "fields.managementKey": "管理金鑰",
    "fields.intervalMinutes": "巡檢間隔（分鐘）",
    "fields.concurrency": "巡檢並發數",
    "fields.timeoutSeconds": "逾時秒數",
    "fields.quotaThreshold": "額度門檻",
    "fields.autoStart": "服務啟動後自動執行一次",
    "fields.notifySuccess": "無異常完成時也推送通知",
    "fields.notifyAbnormal": "異常巡檢時推送通知",
    "fields.telegramEnabled": "啟用 Telegram",
    "fields.telegramToken": "Bot Token",
    "fields.telegramChatId": "Chat ID",
    "fields.telegramApiBase": "API Base",
    "fields.barkEnabled": "啟用 Bark",
    "fields.barkServer": "Bark 伺服器",
    "fields.barkDeviceKey": "Device Key",
    "fields.barkGroup": "群組",
    "table.id": "ID",
    "table.status": "狀態",
    "table.started": "開始時間",
    "table.total": "總數",
    "table.abnormal": "異常",
    "table.recommended": "建議處理",
    "table.account": "帳號",
    "table.classification": "分類",
    "table.used": "用量",
    "table.action": "建議動作",
    "table.reason": "原因",
    "toast.settingsSaved": "設定已儲存",
    "toast.inspectionStarted": "巡檢已開始",
    "toast.notificationSent": "測試通知已送出",
    "toast.notificationFailed": "測試通知失敗：{error}",
    "toast.notificationNoEnabled": "請先啟用 Telegram 或 Bark，再測試通知。",
    "toast.notificationSkipped": "測試通知已略過：{error}",
    "run.recommended": "停用 {disable}，啟用 {enable}",
    "run.detailMeta": "#{id} | {status} | {time}",
    "summary.total": "總數",
    "summary.healthy": "健康",
    "summary.zero_quota": "週額度用盡",
    "summary.full_quota": "短期額度滿",
    "summary.invalid": "失效",
    "summary.probe_failed": "探測失敗",
    "statusValue.success": "成功",
    "statusValue.partial": "部分成功",
    "statusValue.failed": "失敗",
    "statusValue.running": "執行中",
    "statusValue.healthy": "健康",
    "statusValue.zero_quota": "週額度用盡",
    "statusValue.full_quota": "短期額度滿",
    "statusValue.invalid": "失效",
    "statusValue.probe_failed": "探測失敗",
    "statusValue.unknown": "未知",
    "action.keep": "保留",
    "action.disable": "停用",
    "action.enable": "啟用",
    "action.delete": "刪除",
  },
};

let currentLanguage = resolveInitialLanguage();

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

function t(key, params = {}) {
  const template = translations[currentLanguage]?.[key] ?? translations.en[key] ?? key;
  return template.replace(/\{(\w+)\}/g, (_, name) => params[name] ?? "");
}

function hasTranslation(key) {
  return Boolean(translations[currentLanguage]?.[key] ?? translations.en[key]);
}

function resolveInitialLanguage() {
  const saved = window.localStorage.getItem(languageStorageKey);
  if (saved && translations[saved]) return saved;
  return navigator.language.toLowerCase().startsWith("zh") ? "zh-TW" : "en";
}

function applyLanguage() {
  document.documentElement.lang = currentLanguage;
  languageSelect.value = currentLanguage;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toast.hidden = true;
  }, 3600);
}

function fillForm(settings) {
  for (const key of fields) {
    const input = form.elements[key];
    if (!input) continue;
    if (input.type === "checkbox") {
      input.checked = Boolean(settings[key]);
    } else {
      input.value = settings[key] ?? "";
    }
  }
}

function readForm() {
  const payload = {};
  for (const key of fields) {
    const input = form.elements[key];
    if (!input) continue;
    if (input.type === "checkbox") {
      payload[key] = input.checked;
    } else if (input.type === "number") {
      payload[key] = Number(input.value);
    } else {
      payload[key] = input.value;
    }
  }
  return payload;
}

async function loadConfig() {
  fillForm(await api("/api/config"));
}

async function loadStatus() {
  const status = await api("/api/status");
  const parts = [
    status.running ? t("status.running") : t("status.idle"),
    status.scheduler_running ? t("status.schedulerActive") : t("status.schedulerStopped"),
  ];
  if (status.next_run_at_ms) {
    parts.push(t("status.nextRun", { time: formatTime(status.next_run_at_ms) }));
  }
  if (status.last_scheduler_error) {
    parts.push(t("status.lastError", { error: status.last_scheduler_error }));
  }
  statusText.textContent = parts.join(" | ");
}

async function loadRuns() {
  const payload = await api("/api/runs?limit=50");
  runsBody.innerHTML = "";
  for (const run of payload.runs) {
    const row = document.createElement("tr");
    const summary = run.summary || {};
    row.innerHTML = `
      <td>#${run.id}</td>
      <td>${badge(run.status, "statusValue")}</td>
      <td>${formatTime(run.started_at_ms)}</td>
      <td>${summary.total ?? 0}</td>
      <td>${summary.abnormal ?? 0}</td>
      <td>${t("run.recommended", { disable: summary.disable ?? 0, enable: summary.enable ?? 0 })}</td>
    `;
    row.addEventListener("click", () => loadRun(run.id));
    runsBody.appendChild(row);
  }
  if (payload.runs[0]) {
    await loadRun(payload.runs[0].id);
  }
}

async function loadRun(id) {
  const payload = await api(`/api/runs/${id}`);
  const run = payload.run;
  const summary = run.summary || {};
  detailMeta.textContent = t("run.detailMeta", {
    id: run.id,
    status: translateValue("statusValue", run.status),
    time: formatTime(run.started_at_ms),
  });
  summaryTiles.innerHTML = summaryKeys.map((key) => `
    <div class="tile">
      <strong>${summary[key] ?? 0}</strong>
      <span>${t(`summary.${key}`)}</span>
    </div>
  `).join("");
  accountsBody.innerHTML = "";
  for (const item of run.accounts || []) {
    const row = document.createElement("tr");
    const used = item.used_percent == null ? "-" : `${Number(item.used_percent).toFixed(1)}%`;
    row.innerHTML = `
      <td>${escapeHtml(item.display_account || item.file_name || item.auth_index || "-")}</td>
      <td>${badge(item.classification, "statusValue")}</td>
      <td>${used}</td>
      <td>${escapeHtml(translateValue("action", item.recommended_action || "keep"))}</td>
      <td>${escapeHtml(item.action_reason || item.error || "")}</td>
    `;
    accountsBody.appendChild(row);
  }
}

function badge(value, namespace) {
  const raw = String(value || "-");
  const text = escapeHtml(namespace ? translateValue(namespace, raw) : raw);
  return `<span class="badge ${escapeHtml(raw)}">${text}</span>`;
}

function translateValue(namespace, value) {
  const key = `${namespace}.${value}`;
  return hasTranslation(key) ? t(key) : value;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

function formatTime(ms) {
  if (!ms) return "-";
  return new Date(Number(ms)).toLocaleString(currentLanguage);
}

languageSelect.addEventListener("change", async () => {
  currentLanguage = languageSelect.value;
  window.localStorage.setItem(languageStorageKey, currentLanguage);
  applyLanguage();
  await refreshAll();
});

document.querySelector("#saveButton").addEventListener("click", async () => {
  await api("/api/config", { method: "PUT", body: JSON.stringify(readForm()) });
  await loadConfig();
  await loadStatus();
  showToast(t("toast.settingsSaved"));
});

document.querySelector("#runNowButton").addEventListener("click", async (event) => {
  event.currentTarget.disabled = true;
  try {
    await api("/api/run-now", { method: "POST" });
    showToast(t("toast.inspectionStarted"));
    window.setTimeout(refreshAll, 1500);
  } finally {
    event.currentTarget.disabled = false;
  }
});

document.querySelector("#testNotifyButton").addEventListener("click", async () => {
  const draft = readForm();
  if (!draft.telegram_enabled && !draft.bark_enabled) {
    showToast(t("toast.notificationNoEnabled"));
    return;
  }
  await api("/api/config", { method: "PUT", body: JSON.stringify(draft) });
  await loadConfig();
  await loadStatus();
  const payload = await api("/api/notifications/test", { method: "POST" });
  const attempts = payload.attempts || [];
  const failed = attempts.filter((item) => item.status === "failed");
  const skipped = attempts.filter((item) => item.status === "skipped");
  if (failed.length) {
    showToast(t("toast.notificationFailed", { error: failed[0].error }));
  } else if (skipped.length) {
    showToast(t("toast.notificationSkipped", { error: skipped[0].error }));
  } else {
    showToast(t("toast.notificationSent"));
  }
});

document.querySelector("#refreshButton").addEventListener("click", refreshAll);

async function refreshAll() {
  await Promise.all([loadStatus(), loadRuns()]);
}

async function boot() {
  applyLanguage();
  try {
    await loadConfig();
    await refreshAll();
    window.setInterval(loadStatus, 5000);
    window.setInterval(loadRuns, 30000);
  } catch (error) {
    showToast(error.message);
  }
}

boot();
