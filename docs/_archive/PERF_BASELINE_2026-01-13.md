# 性能基线（Perf Baseline）

日期：2026-01-13

## 1. 目的

建立关键接口的延迟基线（P95 为主），用于后续回归对照：

- `chat`
- `documents`
- `payment callback`（以支付模块关键接口近似）
- `news ingest admin`

> 说明：本次为“最小版基线”。重点在方法可复现、结果可对比，不追求压测强度。

---

## 2. 环境与前置

- OS：Windows
- Backend：本机 `uvicorn`（单进程）
- DB：SQLite（独立基线库）
- AI：使用 `X-E2E-Mock-AI: 1` 走后端内置的 E2E mock 路径（避免真实外部请求）

基线 DB：`backend/data/perf_baseline_20260113.db`

---

## 3. 测试方法

- 每个接口：顺序请求 N 次（避免并发引入噪声）
- 统计：P50 / P95 / P99
- 仅统计 HTTP 2xx 成功请求

---

## 4. 被测接口

| 模块              | 接口                                                         | 说明                                                           |
| ----------------- | ------------------------------------------------------------ | -------------------------------------------------------------- |
| chat              | `POST /api/ai/chat/stream`                                   | AI 流式对话（带 `X-E2E-Mock-AI: 1`）                           |
| documents         | `POST /api/documents/generate`                               | 文书生成                                                       |
| payment           | `GET /api/payment/admin/callback-events?page=1&page_size=50` | 支付回调事件查询（管理员接口，近似 payment callback 运维路径） |
| news ingest admin | `GET /api/news/admin/ingest-runs?page=1&page_size=20`        | 管理端采集运行记录                                             |

---

## 5. 测试结果

执行参数：`runs=10`、`warmup=1`

统计结果（ms）：

| name                            |   P50 |   P95 |   P99 | count |
| ------------------------------- | ----: | ----: | ----: | ----: |
| `ai_chat_stream`                | 30.71 | 32.32 | 32.35 |    10 |
| `documents_generate`            | 31.47 | 39.15 | 40.71 |    10 |
| `payment_admin_callback_events` | 30.69 | 32.40 | 33.23 |    10 |
| `news_admin_ingest_runs`        | 31.24 | 32.34 | 32.35 |    10 |

原始采样 JSON：

- `docs/_archive/PERF_BASELINE_2026-01-13.json`

---

## 6. 复现命令（Windows）

### 6.1 准备独立基线 DB（可复用，不影响主库）

```powershell
$env:DEBUG='1'
$env:DATABASE_URL='sqlite+aiosqlite:///./data/perf_baseline_20260113.db'
py scripts/seed_data.py --apply-default-config
```

### 6.2 启动后端（端口 8003）

```powershell
$env:DEBUG='1'
$env:DATABASE_URL='sqlite+aiosqlite:///./data/perf_baseline_20260113.db'
py -m uvicorn app.main:app --host 127.0.0.1 --port 8003
```

### 6.3 运行基线脚本

说明：

- 仓库默认开启 API 限流（如 AI 20/min、文书 10/min）。
- `backend/scripts/perf_baseline.py` 会在遇到 `429` 时按响应头退避等待，但**不会把等待时间计入采样耗时**（仅统计成功请求耗时）。

```powershell
py backend/scripts/perf_baseline.py --base-url http://127.0.0.1:8003 --runs 10 --warmup 1 --output-json docs/_archive/PERF_BASELINE_2026-01-13.json
```

### 6.4 关闭后端

在运行 uvicorn 的窗口按 `Ctrl + C`。
