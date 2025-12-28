# CI 模板（GitHub Actions）

> 目标：给接手同事一份可复制粘贴的 CI 工作流模板。
>
> 说明：这里提供 3 类 job：后端测试、前端构建、（可选）E2E、（可选）post-deploy 冒烟。

## 0. 仓库已落地的实际工作流文件（优先使用）

本仓库已经包含可直接使用的 GitHub Actions 工作流文件（通常不需要再根据下面模板从零创建）：

- `.github/workflows/ci.yml`：主 CI（backend pytest + frontend build + docker build + code quality + security scan + deploy 提示）
- `.github/workflows/type-check.yml`：pyright 类型检查
- `.github/workflows/post-deploy-smoke.yml`：部署后冒烟（调用 `../scripts/smoke-news-ai.sh`，需要配置 GitHub Secrets）

## 0.1 将 Helm lint 设为“必需检查”（Branch Protection）

仓库的 `.github/workflows/ci.yml` 已包含：

- `helm-validate`：包含 `helm lint`（以及 `helm template` 渲染校验）
- `required-checks`：聚合校验 job（依赖 `helm-validate/backend-test/frontend-build`）

要让 `helm lint` 成为合并门禁：

- 在 GitHub：`Settings -> Branches -> Branch protection rules`
- 对目标分支开启 `Require status checks to pass before merging`
- 在 Required checks 列表中勾选：`required-checks`

下面章节保留“模板”是为了：

- 便于快速理解每个 job 的关键步骤
- 便于你们后续按团队规范做裁剪/拆分

---

## 1. backend pytest（必选）

```yaml
name: Backend Test
on:
  push:
  pull_request:

jobs:
  backend-test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run pytest
        env:
          # 测试默认会用 sqlite，并自动进入测试模式
          DEBUG: "true"
        run: |
          python -m pytest -q
```

---

## 2. frontend build（必选）

```yaml
name: Frontend Build
on:
  push:
  pull_request:

jobs:
  frontend-build:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install deps
        run: npm ci

      - name: Build
        env:
          VITE_API_BASE_URL: /api
        run: npm run build
```

---

## 3. Playwright E2E（推荐：staging 或 nightly）

> 说明：项目的 Playwright 配置会自动启动前端 dev server + 后端 uvicorn。
>
> 注意：E2E 会涉及网络端口占用、浏览器依赖等，建议在 staging/夜间跑。

```yaml
name: E2E (Playwright)
on:
  workflow_dispatch:
  schedule:
    - cron: "0 18 * * *" # 每天 UTC 18:00（北京时间 02:00）

jobs:
  e2e:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      # Python（给 Playwright webServer 启动 backend 用）
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install backend deps
        working-directory: backend
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      # Node（运行 Playwright）
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install frontend deps
        working-directory: frontend
        run: npm ci

      - name: Install Playwright browser
        working-directory: frontend
        run: npx playwright install --with-deps chromium

      - name: Run E2E
        working-directory: frontend
        env:
          # 如需复用已存在服务可设置：E2E_REUSE_EXISTING=1
          # 默认不设置，让 Playwright 自己起服务
          E2E_REUSE_EXISTING: "0"
        run: npm run test:e2e

      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: frontend/playwright-report
```

---

## 4. post-deploy 冒烟（可选，需生产 Secrets 支持）

> 说明：如果你希望部署后自动跑一遍冒烟，建议在 CI/CD 的 deploy 阶段后执行。
>
> 你需要准备：
>
> - `BASE_URL`（例如 https://yourdomain.com）
> - `ADMIN_TOKEN`（管理员 JWT）
>
> 推荐直接调用仓库脚本：`../scripts/smoke-news-ai.sh`（比复制粘贴 curl 更稳）。

示例结构（伪代码式）：

```yaml
name: Post Deploy Smoke
on:
  workflow_dispatch:

jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Smoke
        env:
          BASE_URL: ${{ secrets.BASE_URL }}
          ADMIN_TOKEN: ${{ secrets.ADMIN_TOKEN }}
        run: |
          set -euo pipefail
          chmod +x ./scripts/smoke-news-ai.sh
          BASE_URL="${BASE_URL}" ADMIN_TOKEN="${ADMIN_TOKEN}" STRICT=0 ./scripts/smoke-news-ai.sh
```
