# Scripts

本目录用于放置项目的可执行脚本（运维/冒烟/辅助工具）。

---

## 1. News AI 一键冒烟

> 目标：发布后快速验证 News AI 链路是否可用（health -> status -> 创建新闻 -> AI rerun -> 轮询确认 -> 清理）。

### 1.1 Windows（PowerShell）

脚本：`smoke-news-ai.ps1`

用法：

```powershell
./scripts/smoke-news-ai.ps1 -BaseUrl "https://yourdomain.com" -AdminToken "<ADMIN_TOKEN>"
```

可选参数：

- `-PollSeconds <int>`：总轮询时长（默认 30）
- `-IntervalSeconds <int>`：轮询间隔秒数（默认 1）
- `-Strict`：严格模式（要求 `highlights/keywords` 非空才判定成功）

### 1.2 Linux/CI（bash）

脚本：`smoke-news-ai.sh`

用法：

```bash
chmod +x ./scripts/smoke-news-ai.sh
BASE_URL="https://yourdomain.com" \
ADMIN_TOKEN="<ADMIN_TOKEN>" \
./scripts/smoke-news-ai.sh
```

可选环境变量：

- `POLL_SECONDS`：总轮询时长（默认 30）
- `INTERVAL_SECONDS`：轮询间隔秒数（默认 1）
- `STRICT`：严格模式（`1/true/yes/on` 表示开启，要求 `highlights/keywords` 非空）

### 1.3 常见失败与排查

- **401/403**：管理员 token 不正确或过期。
- **404 /api/system/news-ai/status**：请确认后端已部署并且 API 前缀正确（通常前端通过 `/api` 反代到后端）。
- **一直轮询超时**：
  - 先在管理后台确认 LLM 与 providers 配置是否生效。
  - 再看 `GET /api/system/news-ai/status` 的 `recent_errors`。
  - 生产环境确认 `REDIS_URL` 可用（`DEBUG=false` 且 Redis 不通会禁用 News AI pipeline，但脚本走的是手动 rerun，一般仍可用于基本链路验证）。

### 1.4 GitHub Actions（部署后冒烟）

仓库已提供工作流：`/.github/workflows/post-deploy-smoke.yml`。

你需要在 GitHub 仓库的 Secrets（或 Environment=production 的 Secrets）中配置：

- `BASE_URL`：例如 `https://yourdomain.com`
- `ADMIN_TOKEN`：管理员 JWT

触发方式：GitHub Actions -> `Post Deploy Smoke` -> Run workflow。

可选输入（workflow inputs）：

- `strict`：`1` 表示严格模式（要求 highlights/keywords 非空）
- `poll_seconds`：轮询等待时间（默认 30）
- `interval_seconds`：轮询间隔（默认 1）
