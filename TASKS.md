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

## 第七阶段：发布与交付流程（P1）

- [ ] Release 规范化（tag / changelog / release note）
  - [ ] 约定版本号策略（SemVer）与发布节奏（例如每周/每两周）
  - [ ] `docs/CHANGELOG.md` 维护规则：Unreleased -> 版本号 -> 日期
  - [ ] 发布清单（Checklist）：本地回归、CI 全绿、数据迁移、回滚方案、变更通知
- [ ] GitHub Actions 增强：发布/制品产出
  - [ ] 新增 `release.yml`：tag 推送后自动生成 GitHub Release（从 CHANGELOG 提取）
  - [ ] 产出并上传构建产物（前端 dist / 后端 wheel 可选 / helm chart package 可选）
  - [ ] Docker 镜像构建与推送（GHCR），并写入版本号标签
- [ ] 环境与 Secrets 管理
  - [ ] 生产环境变量清单与示例（补充到 docs/TECH_SPEC.md 或 docs/README.md）
  - [ ] 将 CI 中用于 E2E 的测试 secrets 与生产 secrets 分离（避免误用）

## 第八阶段：回归覆盖扩展（P1/P2）

- [ ] Playwright E2E 扩展（在保持“最小闭环”稳定的前提下）
  - [ ] `auth:` 登录/注册/邮箱验证/找回密码最小闭环
  - [ ] `payment:` 下单->拉起支付->回跳->订单 paid（可用 mock/沙箱，保留真实渠道冒烟脚本）
  - [ ] `admin:` 新闻审核/配置的关键路径冒烟
- [ ] 前后端契约与兼容性
  - [ ] 对关键接口补充 Schema/contract 测试（尤其是支付、文书、用户验证）
  - [ ] 对 API envelope 切换行为补充边界用例（非 JSON/非 2xx/空响应）

## 第九阶段：稳定性与可观测性深化（P2）

- [ ] 指标与告警
  - [ ] Prometheus 告警规则（5xx、P95 延迟、周期任务失败率）
  - [ ] Grafana Dashboard（HTTP、News AI、支付回调、文书导出）
- [ ] 日志与追踪
  - [ ] 统一 request_id 贯穿（前端->后端->日志），并在文档中写明排障方法
  - [ ] 关键异常上报与降级策略（AI/支付/News AI）

## 第十阶段：产品体验与增长（P2）

- [ ] 新用户引导与转化
  - [ ] 新用户首次进入的引导（咨询/文书/资讯/订单）
  - [ ] “权益与配额”展示更明确：剩余次数、到期时间、消耗记录
- [ ] 反馈闭环
  - [ ] 反馈工单的管理端处理流（分配、状态流转、统计）
  - [ ] 常见问题（FAQ）与客服入口整合

## 第十一阶段：体验细节与后台配置增强（P1）

- [ ] 个人中心：VIP 标识与入口一致性
  - [ ] 个人中心添加 VIP 标识（已开通点亮，未开通置灰）
  - [ ] 标识旁新增按钮：已开通显示“续费”，未开通显示“开通”
  - [ ] 点击按钮跳转到 VIP 会员页（/vip）
  - [ ] 顶部导航“VIP 会员”跳转入口移除（避免入口重复与割裂）
- [ ] 个人中心：购买/支付弹窗交互优化
  - [ ] 各类购买弹窗统一在屏幕正中弹出（避免页面滚动过多导致弹窗位置影响观察）
  - [ ] 点击“购买/确认”后，支付方式选择不应直接在页面下方插入渲染
  - [ ] 目标交互：确认购买后将“当前选择弹窗”平移到左侧并保持可见，同时在其右侧紧接弹出“支付方式选择”
    - 便于中途切换购买物品与支付方式
    - 不遮挡关键信息且在长页面滚动场景下稳定可用
- [ ] 新闻页面：卡片布局一致性
  - [ ] 新闻列表页所有卡片高度/封面区域对齐（标题/摘要不同长度不影响整体栅格对齐）
  - [ ] 统一封面展示的占位与裁切策略（例如固定比例 + object-fit）
- [x] 后台内容上传能力：封面从“链接”升级为“上传”（并可扩展到其他模块）
  - [x] News/Topics 封面：后台编辑支持上传图片生成 URL（仍兼容手动填写链接）
  - [x] 将“上传-存储-返回访问 URL”的能力做成通用模块，其他需要图片/文件的模块同步接入
  - [x] 约束：校验文件类型/大小；前端上传进度与失败提示；后端存储路径与清理策略明确
- [x] 支付管理实用化：/admin/payment-callbacks 与渠道密钥维护
  - [x] 支付管理页支持替换/更新新的渠道密钥（不暴露敏感信息，仅支持覆盖更新与状态校验）
  - [x] 渠道配置状态更清晰：哪些字段缺失、哪些回调 URL 生效、最近验证时间与结果
  - [x] 支付回调审计的筛选/检索体验优化（按渠道/时间/订单号/流水号）
- [x] 初始化数据脚本完善
  - [x] 补齐一键初始化：管理员账号、默认 SystemConfig（非敏感项）、必要的模板/知识库示例数据
  - [x] 明确可重复执行策略（幂等/覆盖/跳过），并输出清晰日志
- [ ] 管理后台侧边栏信息架构整理
  - [ ] 侧边栏条目过多：将“相关设置”收敛为二级菜单/二级跳转并合并同类项
  - [ ] 目标：常用入口优先、低频设置收纳、层级清晰且不增加点击成本

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
  - 覆盖：backend pytest、frontend build、Playwright 最小 documents E2E（`--grep "documents:"`)
