# Helm Chart: baixing-assistant

本 Chart 用于在 Kubernetes 上部署 **百姓助手**（backend + frontend + ingress）。

- backend：容器端口 `8000`
- frontend：Nginx 容器端口 `3000`
- ingress：默认 `/api` -> backend，`/` -> frontend

> 注意：本 Chart 仅提供“可用骨架”，适合团队后续按规范扩展（镜像仓库鉴权、HPA、ExternalSecrets、Prometheus 等）。

---

## 1. 前置条件

- Kubernetes 集群
- Ingress Controller（建议 nginx ingress）
- 已构建并推送镜像：
  - backend 镜像
  - frontend 镜像

---

## 2. 安装/升级

Chart 路径：`helm/baixing-assistant`

### 2.1 准备 values（推荐方式）

建议你为不同环境准备独立 values 文件（不要提交包含 secrets 的 values 到仓库）：

- `values.prod.yaml`
- `values.staging.yaml`

仓库内提供一份可直接复制的示例（不含 secrets，仅占位符）：

- `values.prod.example.yaml`
- `values.externalsecret.example.yaml`
- `values.subcharts.example.yaml`

最少需要填的项：

- `image.backend.repository` / `image.backend.tag`
- `image.frontend.repository` / `image.frontend.tag`
- `ingress.host`（以及 `ingress.tls.secretName`，如果启用 TLS）

后端 secrets 选一种方式即可：

- Chart 内置 Secret（默认）：填写 `backend.secret.*`（`DATABASE_URL/JWT_SECRET_KEY/PAYMENT_WEBHOOK_SECRET/REDIS_URL/OPENAI_API_KEY`）
- 复用已有 Secret：填写 `backend.existingSecretName`
- ExternalSecrets：填写 `backend.externalSecret.*`

示例（片段）：

```yaml
image:
  backend:
    repository: your-registry/baixing-backend
    tag: "1.0.0"
  frontend:
    repository: your-registry/baixing-frontend
    tag: "1.0.0"

backend:
  secret:
    DATABASE_URL: "postgresql+asyncpg://user:pass@postgres:5432/baixing_law"
    JWT_SECRET_KEY: "replace_me_long_and_random"
    PAYMENT_WEBHOOK_SECRET: "replace_me_long"
    REDIS_URL: "redis://:password@redis:6379/0"
    OPENAI_API_KEY: "sk-xxxx"

ingress:
  enabled: true
  className: nginx
  host: yourdomain.com
  tls:
    enabled: true
    secretName: yourdomain-tls
```

### 2.2 安装

```bash
helm upgrade --install baixing-assistant ./helm/baixing-assistant \
  -n baixing \
  --create-namespace \
  -f values.prod.yaml
```

### 2.3 升级

```bash
helm upgrade baixing-assistant ./helm/baixing-assistant \
  -n baixing \
  -f values.prod.yaml
```

### 2.4 卸载

```bash
helm uninstall baixing-assistant -n baixing
```

---

## 5. CI 校验（Helm）

如果你本机没有安装 Helm，也可以通过 CI 自动校验 Chart 是否可渲染：

- `.github/workflows/ci.yml` -> `helm-validate` job（`helm lint` + `helm template`）

如果你希望把 Helm 校验作为合并门禁（推荐）：

- `.github/workflows/ci.yml` -> `required-checks` job（聚合依赖 `helm-validate/backend-test/frontend-build`）
- 在 GitHub Branch Protection 的 Required Status Check 里勾选 `required-checks`

---

## 3. Secrets 与安全策略（必须遵守）

- **Secrets 不入库**：
  - `OPENAI_API_KEY`、`JWT_SECRET_KEY/SECRET_KEY`、`PAYMENT_WEBHOOK_SECRET`、Redis 密码等必须由 K8s Secret/ExternalSecrets 注入。
  - 不要通过管理后台 SystemConfig 保存任何 API Key/secret（后端会拒绝写入）。

本 Chart 支持三种方式提供后端 secrets（任选其一）：

- Chart 内置 Secret（默认）：由 `backend.secret.*` 生成 Secret
- 复用已有 Secret：设置 `backend.existingSecretName`
- ExternalSecrets（示例，默认关闭）：设置 `backend.externalSecret.enabled=true` 并配置 `secretStoreRef` 与 `remoteRefs`，由 ExternalSecret 生成目标 Secret

> 注意：ExternalSecrets 需要集群已安装 external-secrets CRD/controller；本仓库仅提供示例模板（默认关闭）。

---

## 4. 生产提示

- 生产若要启用 News AI 周期任务：

  - 确保 `backend.config.NEWS_AI_ENABLED=true`
  - 确保 `backend.secret.REDIS_URL` 可用（`DEBUG=false` 且 Redis 不可用时 pipeline 会被禁用）

- 发布后冒烟：
  - 参考：`../../docs/_archive/PROJECT_REPORT.md`
  - 建议直接运行：`../../scripts/smoke-news-ai.sh` 或 `../../scripts/smoke-news-ai.ps1`

---

## 6. 可选子 chart（示例）

Chart 已声明可选依赖（默认关闭）：

- `redis.enabled=true`：使用 bitnami/redis 子 chart
- `postgresql.enabled=true`：使用 bitnami/postgresql 子 chart

> 注意：启用子 chart 后，你仍需要根据集群实际情况设置 `backend.secret.DATABASE_URL` / `backend.secret.REDIS_URL` 指向正确的服务地址。

最小 values 示例（仅演示开关与连接串写法，实际 service/secret 名以集群内资源为准）：

```yaml
redis:
  enabled: true

postgresql:
  enabled: true

backend:
  secret:
    REDIS_URL: "redis://:<redis_password>@<release>-redis-master:6379/0"
    DATABASE_URL: "postgresql+asyncpg://postgres:<postgres_password>@<release>-postgresql:5432/postgres"
```

其中 `<release>` 是 Helm release name（`helm upgrade --install <release> ...` 的第一个参数）。按 Bitnami 默认命名，通常可推导：

- Redis Service：`<release>-redis-master`
- Postgres Service：`<release>-postgresql`

例如你执行：`helm upgrade --install baixing-assistant ./helm/baixing-assistant ...` 时，通常会是：

- Redis Service：`baixing-assistant-redis-master`
- Postgres Service：`baixing-assistant-postgresql`

最终以 `kubectl get svc` 为准。

另外，Bitnami chart 通常默认开启认证并把凭证存到 Secret 中（以 `kubectl get secret` 为准）。常见情况下：

- Redis Secret：`<release>-redis`
- Postgres Secret：`<release>-postgresql`

常见 Secret data key：

- Redis：`redis-password`
- Postgres：
  - `postgres-password`（`postgres` 超级用户密码）
  - `password`（当你设置了 `postgresql.auth.username` 时，该用户的密码）

你可以用类似下面方式查看（示例，仅供排障；注意不要把真实密码贴到工单/群里）：

```bash
kubectl -n <ns> get secret <release>-redis -o jsonpath='{.data.redis-password}' | base64 -d
kubectl -n <ns> get secret <release>-postgresql -o jsonpath='{.data.postgres-password}' | base64 -d
```

如果你想自定义 Postgres 用户/库名，通常可以在 values 里设置（以 Bitnami chart 文档为准）：

- `postgresql.auth.username`
- `postgresql.auth.database`
- `postgresql.auth.postgresPassword` / `postgresql.auth.password`
