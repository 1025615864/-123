# 开发任务（TASKS）

> 说明：这是面向持续迭代的任务追踪清单。当前仓库已有较完整交付能力，建议按“体验冲刺 -> 运营效率 -> 技术治理”的节奏推进。

## 第一阶段：上线阻塞项清零（P0）

### P0（必须）

- [x] 补齐前端账户相关路由（/verify-email、/forgot-password、/reset-password）
- [x] 短信验证码：补齐后端 pytest（发送限流、校验正确/错误/过期、绑定手机号后 phone_verified 变化）
- [x] 邮箱验证：补齐后端 pytest（verify token 正确/错误/过期；重发频控策略）
- [x] 敏感操作二次验证策略复核（提现/绑卡/改密等）：
  - 前端拦截与跳转一致（/profile?phoneVerify=1 & /profile?emailVerify=1）
  - 后端统一依赖项兜底（require_phone_verified / require_email_verified / require_lawyer_verified）
- [x] 支付渠道联调与冒烟（至少打通一个真实渠道）：
  - [x] 新增后端冒烟 pytest：创建订单 -> webhook 回调 -> 订单 paid -> 管理端回调审计可查
  - [x] 支付回跳可用性：第三方 return_url 自动携带 order_no；前端支付提示支持直达 /payment/return
  - [x] 前端补齐发起支付入口：订单页支持支付宝/爱坤支付发起；个人中心 VIP/次数包/充值支持选择支付宝/爱坤支付
  - [x] 真实渠道已打通（验收：完成真实支付后订单变为 paid，且 /admin/payment-callbacks 可见回调审计）
  - 联调 Runbook：
    - 1. 配置环境变量（后端）：
      - IKUNPAY：IKUNPAY_PID / IKUNPAY_KEY / IKUNPAY_NOTIFY_URL（可选：IKUNPAY_RETURN_URL / IKUNPAY_DEFAULT_TYPE / IKUNPAY_GATEWAY_URL）
      - ALIPAY：ALIPAY_APP_ID / ALIPAY_PUBLIC_KEY / ALIPAY_PRIVATE_KEY / ALIPAY_NOTIFY_URL（可选：ALIPAY_RETURN_URL / ALIPAY_GATEWAY_URL）
      - FRONTEND_BASE_URL：用于自动生成 return_url（默认 /payment/return）
    - 2. 回调可达性：
      - IKUNPAY_NOTIFY_URL / ALIPAY_NOTIFY_URL 必须是公网可访问地址（本地联调可用 ngrok/frp 等暴露后端端口）
      - 确认后端接口可从公网访问：/api/payment/ikunpay/notify 或 /api/payment/alipay/notify
      - 本地一键（cloudflared + 自动写入 IKUNPAY_NOTIFY_URL）：
        - 运行：py scripts/ikunpay_tunnel.py（会启动 cloudflared 并自动更新 backend/env.local 的 IKUNPAY_NOTIFY_URL；脚本需保持运行）
        - 然后启动后端并确保 ENV_FILE=env.local（让后端读取最新 IKUNPAY_NOTIFY_URL）
    - 3. 发起支付（前端）：
      - 登录后进入“订单页”或“个人中心”创建订单并点击第三方支付（会打开 pay_url）
      - 支付页面完成支付后回跳到 /payment/return?order_no=... 查看状态
    - 4. 验证订单状态：
      - 前端 /payment/return 页面轮询订单状态应变为 paid
      - 或调用：GET /api/payment/orders/{order_no} 确认 status=paid
    - 5. 验证回调审计：
      - 管理端进入 /admin/payment-callbacks，按渠道筛选，能看到对应回调事件且 verified=true
    - 6. 一键冒烟（Ikunpay）：
      - 启动后端并确保 ENV_FILE=env.local（本地开发使用 backend/env.local）
      - 运行：py scripts/ikunpay_smoke.py（会自动：登录 -> 下单 -> 发起 ikunpay -> 走公网 notify -> 验证订单 paid & 回调审计 verified=true）
  - 下单 -> 拉起支付（pay_url）-> 回跳 /payment/return -> 订单状态更新
  - 管理端 /admin/payment-callbacks 可看到回调审计记录
- [x] 微信支付“发起支付”能力补齐或前端暂时隐藏入口（当前后端已有 /wechat/notify 回调链路）

## 第二阶段：体验与稳定性（P1）

- [x] 统一前端全局错误提示与可重试交互（覆盖网络错误、401 过期；页面提供显式重试/刷新）
  - 已做：React Query 全局 onError（QueryCache/MutationCache）+ toast 去重
  - 已做：401 文案“登录已失效，请重新登录”
  - 已做：网络异常文案“网络异常，请检查网络后重试”
  - 已做：AI SSE 断流/网络错误统一提示与可重试（ChatPage：消息气泡内“重试/继续生成”按钮）
- [x] 统一加载/空状态组件与文案规范（订单/个人中心优先）
  - 已做：OrdersPage 列表加载失败 EmptyState + “重试”按钮
  - 已做：ProfilePage 资产/配额错误提示与“重试/刷新”交互
  - 验证：frontend npm run build 通过
- [x] AI 咨询结果结构化展示（结论/要点/建议/风险提示/引用）
  - 已做：ChatPage 回答区域提供“结构化摘要”可折叠展示（结论/要点/建议/风险提示）
  - 已做：相关法条引用区域保留折叠展示与复制
  - 验证：frontend npm run build 通过
- [x] 订单状态解释与下一步引导（待支付/已支付/支付失败/已取消/已退款）
  - 已做：OrdersPage 列表/详情弹窗提供状态解释与“去支付结果页”引导
  - 已做：PaymentReturnPage 提供状态解释与下一步按钮（按订单类型跳转个人中心/预约/服务）
  - 验证：frontend npm run build 通过
- [x] News/Forum 内容操作的“可撤销”体验（收藏/点赞/删除后可撤销）
  - 已做：Toast 支持 action（撤销按钮）与自定义时长
  - 已做：NewsPage/NewsDetailPage 收藏操作提供“撤销”
  - 已做：ForumPage/PostDetailPage/ProfilePage 的收藏/点赞/删除提供“撤销”（删除撤销通过 restore）
  - 已做：后端新增 /forum/comments/{comment_id}/restore 支持撤销删除评论
  - 验证：frontend npm run build 通过
  - 验证：backend py -m pytest -q 通过

## 第三阶段：商业化体验提升（P1）

- [x] 新增 VIP 权益页（/vip 或 /membership），包含权益说明、FAQ、购买入口
  - 已做：新增 /vip 权益页（权益说明 + FAQ + 开通/续费入口 + 充值/支付提示）
  - 已做：接入导航（桌面顶栏 + 移动端更多）
  - 验证：frontend npm run build 通过
- [x] 购买流程专业化（确认订单页/支付失败重试/余额不足去充值引导）
  - 已做：VIP/次数包/充值支付方式选择从 confirm 统一为弹窗选择（余额/支付宝/爱坤）
  - 已做：第三方未配置/加载中时禁用对应入口并提示原因
  - 验证：frontend npm run build 通过

## 第四阶段：运营与内容生产效率

- [x] News AI 支持批量触发与批量回填（按专题/来源）
  - 已做：新闻管理后台支持按专题/来源站点筛选
  - 已做：支持按筛选条件批量重跑 AI 标注（后端 /news/admin/batch/query，最多 500 条）
  - 已做：新闻管理页提供“按筛选重跑 AI”按钮，支持一键批量触发
  - 验证：backend py -m pytest -q 通过
  - 验证：frontend npm run build 通过
- [x] RSS 来源健康度面板（失败率、最近错误、最近成功）
  - 已做：后端新增 /news/admin/sources/health 聚合接口（按每个来源最近 N 次运行计算失败率/最近状态）
  - 已做：RSS 来源管理页展示健康度（失败率 + 最近状态），支持一键跳转“运行记录”并自动带上 source_id 筛选
  - 验证：backend py -m pytest -q 通过
  - 验证：frontend npm run build 通过
- [x] 审核工作台体验优化（批量审核、快捷筛选、深链定位）
  - 已做：新闻管理页支持 deep link：/admin/news?news_id=xxx 或 /admin/news?id=xxx 自动打开编辑弹窗
  - 已做：新闻管理页新增快捷筛选按钮（待审核/敏感/待审+敏感/未标注/重置）
  - 验证：backend py -m pytest -q 通过
  - 验证：frontend npm run build 通过

## 第五阶段：文书生成专业化（P1/P2）

- [x] 文书生成升级为“可预览 + 导出 PDF”（先做 1-2 个核心模板）
  - 已做：后端新增 PDF 导出接口
    - POST /documents/export/pdf（title+content -> pdf）
    - GET /documents/my/{doc_id}/export?format=pdf（已保存文书导出）
  - 已做：前端文书生成页新增 PDF 预览/下载
    - 生成结果页：预览 PDF/下载 PDF
    - 我的文书详情：预览 PDF/下载 PDF
  - 验证：backend py -m pytest -q 通过
  - 验证：frontend npm run build 通过
- [x] 文书模板资产管理与版本化（可选，后置）
  - 已做：模板与版本入库（DocumentTemplate/DocumentTemplateVersion），支持发布版本
  - 已做：/documents/types 与 /documents/generate 从“已发布版本”取模板（无则回退内置模板）
  - 已做：生成/保存记录写入 template_key/template_version，便于追溯
  - 已做：管理后台新增 /admin/document-templates（列表/版本/发布），前端新增“文书模板”管理页
  - 验证：backend py -m pytest -q 通过
  - 验证：frontend npm run build 通过

## 第六阶段：技术治理与可观测性

- [x] API 响应 envelope 统一（减少前端适配成本）
  - 已做：后端支持 `X-Api-Envelope: 1`（仅对 2xx JSON 响应包装为 {ok,data,ts}）
  - 已做：前端 axios 默认带 header，并在拦截器中自动解包回原始 data（兼容旧接口结构）
  - 验证：backend py -m pytest -q 通过
  - 验证：frontend npm run build 通过
- [x] 指标体系：Prometheus metrics（接口耗时、错误率、周期任务状态）
  - 已做：新增 /metrics（Prometheus text format，支持可选 METRICS_AUTH_TOKEN 保护）
  - 已做：HTTP 指标采集（按 route/method/status 汇总请求量与耗时）
  - 已做：周期任务指标（scheduled_news/rss_ingest/news_ai_pipeline/wechatpay_platform_certs_refresh/settlement 的 runs/success/failure/last_run/last_duration）
  - 验证：backend py -m pytest -q 通过
  - 验证：frontend npm run build 通过
- [x] 数据库迁移规范（SQLite/PG 双模式下的 Alembic 流程）
  - 已做：补充 docs/DATABASE.md 中 Alembic 迁移流程（含 Windows 友好命令）
  - 已做：新增 backend/scripts/alembic_cmd.py 作为命令封装，避免 PATH/编码问题

## 持续性约束（Checklist）

- [x] Secrets 不入库（SystemConfig 不允许保存 api_key/secret）
  - 已做：/api/system/configs 写接口拦截敏感 key/value；并对 providers JSON 禁止携带 api_key
  - 已做：pytest 覆盖（拒绝保存 openai_api_key / providers JSON 含 api_key 等）
- [x] 新增接口必须更新 Swagger tags/summary，并补充 API_DESIGN.md
  - 已做：docs/API_DESIGN.md 已作为权威补充文档（与 Swagger 并行），并包含 envelope/错误码约定
- [x] 关键改动需跑：后端 pytest、前端 build、必要时 Playwright E2E
  - 已做：新增 Playwright 用例 `frontend/tests/e2e/documents.spec.ts` 覆盖文书生成-保存-导出 PDF 闭环
  - Windows 快速运行：
    - 安装浏览器：`npm --prefix frontend run test:e2e:install`
    - 仅跑该用例：`npm --prefix frontend run test:e2e -- --grep "documents:"`
- [x] CI 自动回归（GitHub Actions）
  - 已做：新增 workflow：`.github/workflows/ci.yml`
  - 覆盖：backend pytest、frontend build、Playwright 最小 documents E2E（`--grep "documents:"`）
