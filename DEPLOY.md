# 百姓法律助手 - 部署文档

## 快速开始

### 开发环境

```bash
# 1. 克隆项目
git clone <repository-url>
cd 百姓助手

# 2. 启动后端
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# 3. 启动前端（新终端）
cd frontend
npm install
npm run dev
```

Windows 说明：

- 后端虚拟环境激活：`venv\Scripts\activate`
- 如果你使用 PowerShell，可能需要先允许脚本执行：`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### Docker 开发环境

```bash
# 启动所有服务
docker compose up -d

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

---

## 生产环境部署

### 前置条件

- Docker & Docker Compose
- 域名（可选）
- SSL 证书（可选）

### 步骤

#### 1. 配置环境变量

```bash
# 复制环境变量模板
cp env.example.txt .env

# 编辑配置
nano .env
```

**必须配置的变量：**

| 变量                 | 说明       | 示例                     |
| -------------------- | ---------- | ------------------------ |
| `POSTGRES_PASSWORD`  | 数据库密码 | `your_secure_password`   |
| `JWT_SECRET_KEY`     | JWT 密钥   | `随机字符串(32位以上)`   |
| `REDIS_PASSWORD`     | Redis 密码 | `redis_password`         |
| `CORS_ALLOW_ORIGINS` | 允许的域名 | `https://yourdomain.com` |

#### 2. 构建并启动

```bash
# 使用生产配置
docker compose -f docker-compose.prod.yml up -d --build

# 查看状态
docker compose -f docker-compose.prod.yml ps

# 查看日志
docker compose -f docker-compose.prod.yml logs -f backend
```

#### 3. 初始化数据库

```bash
# 进入后端容器
docker exec -it baixing_backend_prod bash

# 本项目在启动时会自动建表（init_db）。如果你启用了 Alembic（可选），可运行：
# alembic upgrade head
```

---

## 服务架构

```
┌─────────────────────────────────────────────────────┐
│                    Nginx (端口80/443)                │
│              前端静态文件 + API反向代理              │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│                 FastAPI后端 (端口8000)               │
│              API服务 + 速率限制 + JWT认证            │
└──────────┬──────────────────────────┬───────────────┘
           │                          │
           ▼                          ▼
    ┌──────────────┐          ┌──────────────┐
    │  PostgreSQL  │          │    Redis     │
    │   (数据库)    │          │   (缓存)     │
    └──────────────┘          └──────────────┘
```

---

## 监控与维护

### 健康检查

```bash
# API健康检查
curl http://localhost:8000/

# 数据库连接检查
docker exec baixing_db_prod pg_isready -U postgres
```

### 日志查看

```bash
# 后端日志
docker logs -f baixing_backend_prod

# 前端日志
docker logs -f baixing_frontend_prod

# 数据库日志
docker logs -f baixing_db_prod
```

### 数据库备份

```bash
# 备份
docker exec baixing_db_prod pg_dump -U postgres baixing_law > backup_$(date +%Y%m%d).sql

# 恢复
cat backup_20241201.sql | docker exec -i baixing_db_prod psql -U postgres baixing_law
```

---

## 常见问题

### Q: 容器启动失败？

检查日志：`docker-compose logs <service-name>`

### Q: 数据库连接失败？

确认数据库容器健康：`docker-compose ps`

### Q: API 返回 429 错误？

触发了速率限制，等待 1 分钟后重试

---

## 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker-compose -f docker-compose.prod.yml up -d --build

# 清理旧镜像
docker image prune -f
```
