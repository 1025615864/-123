# 上传与存储（UPLOAD_STORAGE）

本模块描述上传 API、local/S3 两种存储方式以及 URL/安全约定。

## 1. API

Router：`backend/app/routers/upload.py`

- `POST /api/upload/avatar`（登录）
- `GET /api/upload/avatars/{filename}`

- `POST /api/upload/image`（登录）
- `GET /api/upload/images/{filename}`

- `POST /api/upload/file`（登录）
- `GET /api/upload/files/{filename}`

## 2. 文件限制与安全

- 头像/图片：

  - 允许类型：`jpg/png/gif/webp`
  - 最大：2MB
  - 通过文件头魔数检测扩展名（避免只信 content-type）

- 附件：
  - 白名单 content-type（pdf/office/zip/audio/video 等）
  - 最大：10MB
  - 文件名严格正则校验，防目录穿越

## 3. Local 模式

实现：`backend/app/services/storage_service.py:LocalStorageProvider`

- 落地目录：`backend/uploads/<category>/...`
- 返回 URL：`/api/upload/<category>/<filename>`
- `GET` 直接 `FileResponse` 返回文件

## 4. S3 模式

实现：`backend/app/services/storage_service.py:S3CompatibleStorageProvider`

- `STORAGE_PROVIDER=s3`
- `put_bytes` 上传到 `bucket/prefix/category/filename`
- `GET` 通过 `get_download_url()` 返回 public url，并使用 307 跳转

## 5. 常见坑

- 前端/反代要允许大文件上传（Nginx `client_max_body_size`）
- S3 public url 需要确保 CDN/权限策略正确

详见：

- 配置参考：`docs/guides/CONFIG_REFERENCE.md`
- 排障：`docs/guides/TROUBLESHOOTING.md`
