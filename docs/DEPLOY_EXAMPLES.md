# 部署示例（Deploy Examples）

> 目标：给接手同事一份“可直接抄”的部署样例。
>
> 说明：仓库已自带 `docker-compose.yml`（偏开发），本文提供更偏生产的示例与注意事项。

---

## 1. 生产部署关键点（先读）

- **Secrets 不入库**：
  - `OPENAI_API_KEY`、`JWT_SECRET_KEY/SECRET_KEY`、`PAYMENT_WEBHOOK_SECRET`、Redis 密码等必须走 env/Secret Manager。
  - 不要通过管理后台 SystemConfig 保存任何 API Key/secret（后端会拦截）。
- **生产启用 News AI 定时 pipeline 需要 Redis**：
  - `DEBUG=false` 且 Redis 未连接时，News AI pipeline 会被禁用（避免多副本重复执行）。
- **端口与职责**：
  - backend 容器默认监听 `8000`（见 `backend/Dockerfile`）。
  - frontend 是 Nginx 静态站点 + `/api` 反代到 backend（见 `frontend/nginx.conf`），默认监听 `3000`。

---

## 2. docker-compose（偏生产）示例：Postgres + Redis + Backend + Frontend

> 文件名建议：`docker-compose.prod.yml`

仓库已提供：`docker-compose.prod.yml`，你可以直接在仓库根目录准备 `.env` 后启动：

```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

如果你的 Docker 版本较旧，可改用：

```bash
docker-compose -f docker-compose.prod.yml --env-file .env up -d --build
```

```yaml
version: "3.8"

services:
  db:
    image: postgres:15-alpine
    container_name: baixing_db
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 10
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: baixing_redis
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 10
    restart: unless-stopped

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: baixing_backend
    environment:
      # 基础
      - DEBUG=false
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - PAYMENT_WEBHOOK_SECRET=${PAYMENT_WEBHOOK_SECRET}

      # CORS/前端
      - CORS_ALLOW_ORIGINS=${CORS_ALLOW_ORIGINS}
      - FRONTEND_BASE_URL=${FRONTEND_BASE_URL}
      - TRUSTED_PROXIES=${TRUSTED_PROXIES}

      # Redis（生产强烈建议）
      - REDIS_URL=${REDIS_URL}

      # News AI（周期任务）
      - NEWS_AI_ENABLED=true
      - NEWS_AI_INTERVAL_SECONDS=120

      # LLM（Secrets 必须从环境变量注入）
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENAI_BASE_URL=${OPENAI_BASE_URL}
      - AI_MODEL=${AI_MODEL}

    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8000:8000"
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        VITE_API_BASE_URL: /api
    container_name: baixing_frontend
    depends_on:
      - backend
    ports:
      - "3000:3000"
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### 2.1 配套的 `.env`（生产）示例（不要提交到仓库）

```dotenv
POSTGRES_USER=postgres
POSTGRES_PASSWORD=replace_me
POSTGRES_DB=baixing_law

JWT_SECRET_KEY=replace_me_long_and_random
PAYMENT_WEBHOOK_SECRET=replace_me_long

CORS_ALLOW_ORIGINS=https://yourdomain.com,https://admin.yourdomain.com
FRONTEND_BASE_URL=https://yourdomain.com
TRUSTED_PROXIES=[]

# Redis
REDIS_URL=redis://redis:6379/0

# LLM
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.openai.com/v1
AI_MODEL=deepseek-chat
```

### 2.2 访问方式

- 前端：`http://<host>:3000`
- 后端：`http://<host>:8000`（通常不直接暴露给公网，建议由网关/反代统一入口）
- API：前端 Nginx 已配置 `/api -> http://backend:8000`（见 `frontend/nginx.conf`）

---

## 3. 推荐的网关/反代（Nginx）示例

> 如果你希望把前端和 API 都通过同一个域名发布（推荐），可以在宿主机或网关层配置 Nginx。

示例（仅示意，不含 TLS 证书配置）：

```nginx
server {
  listen 80;
  server_name yourdomain.com;

  # 前端（直接转发到 frontend 容器）
  location / {
    proxy_pass http://127.0.0.1:3000;
    proxy_set_header Host $host;
  }

  # API（也可以不转发，直接让前端 nginx 的 /api 去代理 backend）
  location /api {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

---

## 4. 发布后必做（建议写入运维 SOP）

- 跑一键冒烟：`PROD_DEPLOY_AND_SMOKE_SOP.md`
- 检查 News AI 运维状态（管理员）：
  - `GET /api/system/news-ai/status`
- 如果生产多副本：
  - 必须确保 `REDIS_URL` 可用（否则周期任务会被禁用，或造成重复执行风险）。

---

## 5. Kubernetes（Helm + Ingress）示例

> 说明：这里提供“可抄”的示例片段（values + 常见模板结构）。
>
> 重点：Secrets 必须通过 K8s Secret 注入；生产启用 News AI pipeline 需要可用 Redis。

仓库已提供可直接使用的 Helm Chart：

- Chart 路径：`../helm/baixing-assistant`
- Chart 说明：`../helm/baixing-assistant/README.md`

最短安装/升级命令（示例）：

```bash
# 建议在仓库根目录执行
helm upgrade --install baixing-assistant ./helm/baixing-assistant \
  -n baixing \
  --create-namespace \
  -f values.prod.yaml
```

> 注意：`values.prod.yaml` 不要提交到仓库（包含 secrets）。
>
> 可参考示例（不含 secrets，仅占位符）：
>
> - `../helm/baixing-assistant/values.prod.example.yaml`
> - `../helm/baixing-assistant/values.externalsecret.example.yaml`
> - `../helm/baixing-assistant/values.subcharts.example.yaml`
>
> 如果你启用（示例）bitnami 子 chart（见 `values.subcharts.example.yaml`）：
>
> - 默认 Service 命名通常可按 release name 推导：
>   - Redis：`<release>-redis-master`
>   - Postgres：`<release>-postgresql`
> - Bitnami chart 通常默认开启认证，密码存放在 Secret（以 `kubectl get secret` 为准）：
>   - Redis Secret：`<release>-redis`（常见 key：`redis-password`）
>   - Postgres Secret：`<release>-postgresql`（常见 key：`postgres-password`；若设置了 `postgresql.auth.username` 也可能有 `password`）
> - 最终以 `kubectl get svc` / `kubectl get secret` 输出为准。
>
> CI 已包含 Helm 校验（`helm lint` + `helm template`）：见 `.github/workflows/ci.yml` 的 `helm-validate` job。

### 5.1 values.yaml（示例）

```yaml
image:
  backend:
    repository: your-registry/baixing-backend
    tag: "1.0.0"
  frontend:
    repository: your-registry/baixing-frontend
    tag: "1.0.0"

replicaCount:
  backend: 2
  frontend: 2

service:
  backendPort: 8000
  frontendPort: 3000

env:
  debug: "false"
  corsAllowOrigins: "https://yourdomain.com,https://admin.yourdomain.com"
  frontendBaseUrl: "https://yourdomain.com"
  trustedProxies: "[]"
  newsAiEnabled: "true"
  newsAiIntervalSeconds: "120"

secret:
  # 生产建议用 External Secrets / Vault / SOPS 管理
  databaseUrl: "postgresql+asyncpg://user:pass@postgres:5432/baixing_law"
  jwtSecretKey: "replace_me_long_and_random"
  paymentWebhookSecret: "replace_me_long"
  redisUrl: "redis://:password@redis:6379/0"
  openaiApiKey: "sk-xxxx"
  openaiBaseUrl: "https://api.openai.com/v1"
  aiModel: "deepseek-chat"

ingress:
  enabled: true
  className: nginx
  host: yourdomain.com
  tls:
    enabled: true
    secretName: yourdomain-tls
```

### 5.2 Secret（示例模板）

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: {{ .Release.Name }}-backend-secret
type: Opaque
stringData:
  DATABASE_URL: {{ .Values.secret.databaseUrl | quote }}
  JWT_SECRET_KEY: {{ .Values.secret.jwtSecretKey | quote }}
  PAYMENT_WEBHOOK_SECRET: {{ .Values.secret.paymentWebhookSecret | quote }}
  REDIS_URL: {{ .Values.secret.redisUrl | quote }}
  OPENAI_API_KEY: {{ .Values.secret.openaiApiKey | quote }}
  OPENAI_BASE_URL: {{ .Values.secret.openaiBaseUrl | quote }}
  AI_MODEL: {{ .Values.secret.aiModel | quote }}
```

### 5.3 ConfigMap（示例模板，非敏感）

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Release.Name }}-backend-config
data:
  DEBUG: {{ .Values.env.debug | quote }}
  CORS_ALLOW_ORIGINS: {{ .Values.env.corsAllowOrigins | quote }}
  FRONTEND_BASE_URL: {{ .Values.env.frontendBaseUrl | quote }}
  TRUSTED_PROXIES: {{ .Values.env.trustedProxies | quote }}
  NEWS_AI_ENABLED: {{ .Values.env.newsAiEnabled | quote }}
  NEWS_AI_INTERVAL_SECONDS: {{ .Values.env.newsAiIntervalSeconds | quote }}
```

### 5.4 Backend Deployment / Service（示例模板）

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-backend
spec:
  replicas: {{ .Values.replicaCount.backend }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}-backend
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}-backend
    spec:
      containers:
        - name: backend
          image: "{{ .Values.image.backend.repository }}:{{ .Values.image.backend.tag }}"
          ports:
            - containerPort: {{ .Values.service.backendPort }}
          envFrom:
            - secretRef:
                name: {{ .Release.Name }}-backend-secret
            - configMapRef:
                name: {{ .Release.Name }}-backend-config
          readinessProbe:
            httpGet:
              path: /health
              port: {{ .Values.service.backendPort }}
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: {{ .Values.service.backendPort }}
            initialDelaySeconds: 10
            periodSeconds: 20
---
apiVersion: v1
kind: Service
metadata:
  name: {{ .Release.Name }}-backend
spec:
  selector:
    app: {{ .Release.Name }}-backend
  ports:
    - name: http
      port: {{ .Values.service.backendPort }}
      targetPort: {{ .Values.service.backendPort }}
```

### 5.5 Frontend Deployment / Service（示例模板）

> frontend 镜像内部是 Nginx（监听 3000），并自带 `/api` 代理到 `http://backend:8000` 的配置（见 `frontend/nginx.conf`）。
>
> 如果你在 Ingress 已把 `/api` 转发到 backend，则前端的 `/api` 代理不会被用到（无冲突）。

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-frontend
spec:
  replicas: {{ .Values.replicaCount.frontend }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}-frontend
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}-frontend
    spec:
      containers:
        - name: frontend
          image: "{{ .Values.image.frontend.repository }}:{{ .Values.image.frontend.tag }}"
          ports:
            - containerPort: {{ .Values.service.frontendPort }}
          readinessProbe:
            httpGet:
              path: /
              port: {{ .Values.service.frontendPort }}
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: {{ .Release.Name }}-frontend
spec:
  selector:
    app: {{ .Release.Name }}-frontend
  ports:
    - name: http
      port: {{ .Values.service.frontendPort }}
      targetPort: {{ .Values.service.frontendPort }}
```

### 5.6 Ingress（示例模板：/api -> backend，/ -> frontend）

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ .Release.Name }}-ingress
spec:
  ingressClassName: {{ .Values.ingress.className }}
  tls:
    - hosts:
        - {{ .Values.ingress.host }}
      secretName: {{ .Values.ingress.tls.secretName }}
  rules:
    - host: {{ .Values.ingress.host }}
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: {{ .Release.Name }}-backend
                port:
                  number: {{ .Values.service.backendPort }}
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {{ .Release.Name }}-frontend
                port:
                  number: {{ .Values.service.frontendPort }}
```

### 5.7 发布后冒烟（K8s）

- 推荐直接跑脚本：
  - `../scripts/smoke-news-ai.sh`
  - `../scripts/smoke-news-ai.ps1`
- 文档入口：`PROD_DEPLOY_AND_SMOKE_SOP.md`
