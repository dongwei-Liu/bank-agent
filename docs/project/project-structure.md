# Bank Agent 项目文件用途台账

> 本文件是项目长期记忆的一部分。每次增删、移动或重命名项目文件时必须同步更新。
> 最近核对日期：2026-11-02。

## 公共仓库发布范围（2026-11-02）

| 路径 | 归属模块与用途 | 生成物 |
| --- | --- | --- |
| GitHub `dongwei-Liu/bank-agent` | 当前项目公开源码仓库；仅从当前代码树建立初始历史，不包含既有 Private 源仓库提交历史 | 否 |
| 公开快照排除项 | `tools/vscode/` 含本机绝对路径，仅保留在本地源工作区；`.env`、`.runtime/`、虚拟环境、`node_modules/`、构建产物、本机 JDK/Gradle 和独立上游 `platform/fineract/` 均不属于公开源码快照 | — |
| 公开快照目录 | 277 个受管文件，按 `apps/backend`、`apps/frontend`、`docs`、`infrastructure`、`scripts`、`tests` 分组；目录用途见项目根目录 `README.md` | 否 |

## Agent 安全熔断与版本化评估集（2026-10-30）

| 路径 | 归属模块与用途 | 生成物 |
| --- | --- | --- |
| `apps/backend/agent/security.py` | Agent 写 Tool 的确定性分类；模型不能通过改名、提示词或参数移除写操作安全门控 | 否，人工维护源码 |
| `apps/backend/agent/evaluation.py` | 评估样本 Schema、六场景/安全数量门槛、95% 功能准确率与 100% 安全准确率评分 | 否，人工维护源码 |
| `scripts/testing/evaluate_agent.py` | 评估集结构验证与显式真实模型路由评估入口；默认不联网，真实运行要求费用确认参数并把报告写入被忽略的 `.runtime/` | 否，人工维护脚本 |
| `scripts/testing/probe_demo_prompts.py` | 从演示 Markdown 提取不重复提示词，逐条经认证持久化 Agent 会话执行并把原始回复写入被忽略的 `.runtime/`；不确认 Action、不提交 OTP、不启动 Banking Worker | 否，人工维护测试脚本 |
| `tests/evaluation/agent-routing-cases.jsonl` | 六类比赛场景 120 条功能路由样本与 30 条 Prompt Injection/越权样本；不含真实客户或银行数据 | 否，人工维护测试数据 |
| `tests/integration/test_agent_evaluation.py` | 评估集数量、唯一性、领域顺序和评分门槛回归 | 否，人工维护测试 |
| `docs/testing/agent-evaluation.md` | Agent 评估目标、120+30 样本、离线/真实模型命令、95%/100% 门槛、安全证据矩阵及未验收边界 | 否，人工维护文档 |
| `docs/security/security-design.md` | 比赛版安全架构；覆盖信任边界、身份隔离、Agent 白名单、GREEN/YELLOW/RED、幂等/核对、熔断、隐私、审计和 Demo 边界 | 否，人工维护文档 |
| `docs/security/self-assessment.md` | 当前控制证据、真实未验收边界、高/中优先级风险、不接受表述和最终安全放行清单 | 否，人工维护文档 |
| `docs/architecture/system-architecture.md` | React、FastAPI、两个 Worker、中端 PostgreSQL 与 Fineract 的职责、调用链、数据事实分层和部署拓扑 | 否，人工维护文档 |
| `docs/architecture/agent-and-policy.md` | 可信路由、按需 Tool 装配、私有结果、Action 风险、固定生日 DAG、故障恢复、安全熔断和评估算法 | 否，人工维护文档 |
| `docs/submission/project-summary.md` | 200 汉字以内作品简介草案；提交前按比赛表单规则复核字符数 | 否，人工维护文档 |
| `docs/submission/presentation-outline.md` | 10 分钟答辩 PPT 的时间分配、页面重点、真实性声明和备份页 | 否，人工维护文档 |
| `docs/submission/bank-agent-defense-deck-v1.pptx` | 11 页正式可编辑答辩演示文稿；视觉化系统架构、安全执行链、六场景、生日有限 DAG、验证证据与演示路径 | 否，正式参赛材料 |
| `docs/demo/demo-script.md` | 5 分钟演示脚本；覆盖余额、转账、账单、生日 DAG、攻击防护和故障应急 | 否，人工维护文档 |
| `docs/demo/rehearsal-checklist.md` | 三次完整计时彩排的环境、主流程、证据边界和记录模板 | 否，人工维护文档 |

既有 `agent/context.py`、`graph.py` 和 `api/agent.py` 注入 Agent 写操作安全门；`agent_conversation_service.py` 将连续敏感输入、Prompt Injection 和确定性权限失败按 10 分钟窗口计数，达到 5 次后仅锁定 Agent 写 Tool 15 分钟，普通认证只读接口不受影响。`test_agent_conversations.py` 与 `test_agent_routing.py` 覆盖熔断、只读可用和 Tool 执行前阻断。无数据库迁移或第三方依赖；复用 `0010` 已有 `security_events/security_locks`。

## 财富域 Agent 接入（2026-10-29）

| 路径 | 归属模块与用途 | 生成物 |
| --- | --- | --- |
| `apps/backend/agent/prompts/wealth.py` | 财富域 Prompt；限定 Fineract 原生 CNY 定存、每次申购重新测评、精确金融事实私有读取、RED Action 和整笔赎回边界 | 否，人工维护源码 |
| `apps/backend/agent/tools/wealth.py` | 财富域五个 Agent Tool；产品、推荐和本人持有查询生成私有分析快照，申购/赎回只创建可幂等恢复的 RED Action | 否，人工维护源码 |
| `tests/integration/test_agent_wealth.py` | 财富域 Agent 集成测试；验证产品/推荐/持有私有结果、结构化测评跳转、申购/赎回 RED Action、身份隔离、幂等和精确金额/利率/报价不进入模型边界 | 否，人工维护测试 |

既有文件同步调整：`agent/context.py` 注入定存 Service；`agent/registry.py`、`router.py`、`graph.py` 注册财富域并限制结构化事件后的模型继续执行；`schemas/agent.py` 增加风险测评与财富 Action 事件；`api/agent.py` 注入财富运行时依赖并为旧兼容入口提供确定性状态文字；`analysis_result_service.py` 保存并重验产品/持有依赖；`action_service.py` 按稳定键恢复既有 Action；前端 `api.ts` 与 `agent-panel.tsx` 展示本人私有产品/推荐/持有卡、风险测评入口和 RED Action。OpenAPI 快照随运行代码重生。本切片没有数据库迁移、第三方依赖、环境变量或常驻服务变化。

## 持久化 Agent 会话、安全上下文与 SSE（2026-10-28）

| 路径 | 归属模块与用途 | 生成物 |
| --- | --- | --- |
| `apps/backend/migrations/versions/0010_agent_conversations.py` | 中端持久化迁移；新增本人 Agent 会话、消息、Run、SSE 事件、安全事件和安全锁六类表，接在 `0009` 后，不修改 Fineract | 否，人工维护源码 |
| `apps/backend/services/agent_conversation_service.py` | Agent 会话/Run 生命周期；负责本人隔离、幂等入队、可信候选引用、租约恢复、事件持久化、30 天清理、Prompt Injection 记录和敏感输入阻断 | 否，人工维护源码 |
| `apps/backend/agent_worker.py` | 独立 Agent Worker；领取持久化 Run，调用可信领域图，保存回复/事件并按可恢复错误策略重试 | 否，人工维护源码 |
| `scripts/development/start-agent-worker.ps1` | Windows Agent Worker 启动入口；定位项目虚拟环境并补充本机 `NO_PROXY` | 否，人工维护脚本 |
| `tests/integration/test_agent_conversations.py` | 会话 API、跨用户隔离、幂等/单活动 Run、SSE 重放、Worker 恢复、可信引用、注入/敏感信息及保留期清理集成测试 | 否，人工维护测试 |

既有文件同步调整：`models.py` 和 `schemas/agent.py` 增加持久化协议；`api/agent.py`/`main.py` 增加会话、Run 和 SSE 路由并保留旧同步入口；`agent/context.py` 与支付/卡片 Tool、Prompt 使用会话内不透明引用；前端 `api.ts` 和 `agent-panel.tsx` 通过认证 fetch 读取 SSE、刷新恢复 Run、管理本人会话并展示通用澄清卡；`.env.example`/`core/config.py` 登记保留期、租约、重试和 SSE 策略。`reset_demo.py` 按外键顺序清理演示用户的会话/消息/Run/事件/安全锁，新增表不会绕过 Reset 覆盖保护。`docs/api/banking-openapi.json` 是由 FastAPI 重新生成的纳管契约快照。

## 账单人工修正、分类规则与核实审计（2026-10-28）

| 路径 | 归属模块与用途 | 生成物 |
| --- | --- | --- |
| `apps/frontend/src/lib/billing-query.ts` | 前端账单缓存失效集中入口；个人分类、规则或标注变更后刷新分类、规则、标注、流水/详情、统计与异常查询 | 否，人工维护源码 |
| `apps/frontend/src/pages/insights-page.test.tsx` | 洞察页面回归：分类/规则编辑删除、优先级、引用错误、异常核实反馈和缓存刷新 | 否，人工维护测试 |
| `apps/frontend/e2e/billing-personalization.spec.ts` | 桌面1440px与390px受控浏览器：单笔标注修正/清除、分类/规则管理、异常确认及布局 | 否，人工维护测试 |
| `tests/integration/test_billing_personalization.py` | 中端账单集成：标注精确过滤/归属、规则匹配优先级、人工覆盖/恢复、审计与异常重复核实 | 否，人工维护测试 |

同步更新既有 `api/billing.py`（标注列表成对过滤参数）、`services/billing_service.py`（分类/规则/标注/异常状态审计）、前端 `api.ts`（分类/规则/标注 DTO 与 CRUD）、`format.ts`（上海日期）、`account-detail-page.tsx`（单笔标注修正/清除）、`insights-page.tsx`（分类/规则完整维护、异常操作反馈及缓存失效）和 `bill-page.tsx`（上海期间、报告错误与结果核对入口）。无数据库迁移、运行依赖或新增环境变量。

## 异常核实状态同步与 Agent 报告查看（2026-10-28）

| 路径 | 归属模块与用途 | 生成物 |
| --- | --- | --- |
| `apps/frontend/src/components/anomaly-review-controls.tsx` | 前端共享异常核实控件：确认/忽略、忙碌与失败反馈、状态切换，并同步已加载的聊天私有结果和实时异常查询缓存 | 否，人工维护源码 |
| `.runtime/report-view-anomaly-full.xml` | 本轮报告查看与异常核实改造的中端完整回归 JUnit 结果；包含测试数据元信息，仅留在忽略目录 | 是，本机验证证据，不提交 |

同步调整 `services/analysis_result_service.py`：异常候选读取增加本人当前核实状态，保留生成时快照字段；`services/bill_report_service.py`：锁用户后按本人、期间、准确账户范围复用可读报告/任务/失败记录，仅在完全缺失时入队，并以 trace 审计复用/新建；`agent/context.py`：解析查看意图、上海期间和账户选择；`agent/tools/insights.py`、洞察 Prompt/Registry/Router/Graph/API：增加 `view_bill_report` 与 `BILL_REPORT_OPENED` 确定性链路；`schemas/agent.py`：Agent 响应使用类型化事件联合。前端 `agent-panel.tsx` 提供报告状态轮询和报告/报告列表入口；`agent-panel.test.tsx`、`bill-page.test.tsx`、`test_agent_routing.py`、`test_agent_insights.py`、`test_agent_privacy.py`、`test_bill_reports.py`、`agent-chat.spec.ts` 均为既有测试文件。无数据库迁移、依赖或环境变量。
## 成员 A Agent 纵向集成（2026-10-28 统一合并）

以下文件在统一 Agent 与完整业务基座上增加账户、支付、普通借记卡、定时转账和 AA 收款能力；均为人工维护源码或测试，不是生成物。

| 路径 | 归属模块与用途 | 生成物 |
| --- | --- | --- |
| `apps/backend/agent/prompts/cards.py` | 卡片域 Prompt；限定本人卡片、掩码信息、消歧和 Action 安全流程 | 否 |
| `apps/backend/agent/prompts/payment_plans.py` | 定时转账与 AA 域 Prompt；限定草稿、授权、本人份额及不直接扣款规则 | 否 |
| `apps/backend/agent/tools/cards.py` | 卡片域 Tool；查询安全字段并通过既有 CardService 创建申请、激活、设置、状态、补卡和安全查看 Action | 否 |
| `apps/backend/agent/tools/payment_plans.py` | 计划支付域 Tool；定时计划创建/查询/暂停/恢复/取消及 AA 创建/查询/付款/取消 | 否 |
| `apps/backend/migrations/versions/0009_agent_plan_idempotency.py` | 中端持久化；接在账单报告 0007 和订阅提醒 0008 后，为计划和 AA 增加 Agent 来源的可空幂等键，并为 AA 保存请求指纹；不修改 Fineract | 否 |
| `tests/integration/test_agent_member_a.py` | 成员 A Agent 集成测试；覆盖领域注册、历史边界、联系人/转账/互转/卡片/计划/AA、HTTP 事件和写后模型失败恢复 | 否 |
| `docs/project/agent-member-a-task-breakdown.md` | 成员 A 的 A-01 至 A-45 任务、自动化状态和真实写链路验收边界 | 否 |

已有文件同步调整：`agent/context.py` 同时注入账单、订阅和成员 A 业务 Service、trace 与结构化事件；`agent/tools/accounts.py` 增加本人流水；`agent/tools/payments.py` 实现联系人和转账；`agent/registry.py`、`router.py`、`graph.py` 按可信领域装配并保持订阅独占规则；`schemas/agent.py` 合并历史、分析、报告、订阅和 Action 事件；`api/agent.py` 从 Token 注入身份并恢复已持久化写请求；计划/AA/Action Service 增加幂等与授权复核。前端 Agent 面板同时显示账单/订阅私有结果、本人流水和 Action 卡，支付页增加计划核对、草稿与多联系人 AA。

## 账单隐私与个人异常模型（2026-10-22）

| 路径 | 归属模块与用途 | 生成物 |
| --- | --- | --- |
| `apps/backend/services/analysis_result_service.py` | 中端隐私结果：24 小时精确快照、归属/有效期/当前账户重验、本人异常结果叠加当前核实状态但保留生成时快照、摘要词表、样本与范围预算、确定性文字渲染 | 否 |
| `apps/backend/services/anomaly_detection_service.py` | 账单检测：请求内日聚合与因果特征、六类候选、三个个人 Isolation Forest 配置的训练/校准/安全加载、旧规则及无交易订阅观测合并 | 否 |
| `apps/backend/migrations/versions/0006_private_analysis.py` | 中端持久化：新增 `analysis_results` 和 `anomaly_models`，独立于 `BillReport`；不修改 Fineract | 否 |
| `scripts/maintenance/train_spending_anomaly_model.py` | 账单维护：按内部用户 UUID 和截止日预训练个人模型；或清理过期分析快照；不注册为 Tool | 否 |
| `tests/integration/test_agent_privacy.py` | Agent 隐私测试：哨兵、组合查询、HTTP 私有结果、过期/撤权/跨用户、会话刷新、失败回滚、预算与安全输出、执行元数据保留及正文过滤 | 否 |
| `tests/integration/test_anomaly_detection.py` | 合成模型及六类检测测试：时间/门槛/订阅周期/跨账户付款、部分模型、候选核实合并、依赖账户撤权、保存加载和规则回退 | 否 |
| `docs/testing/billing-privacy-ml-validation.md` | 账单专项改造报告：接口契约、模型策略、自动化/合成/实际服务链路证据、复现和限制 | 否 |
| `.runtime/anomaly-models/` | 账单模型：维护 CLI 登记的 UUID `.skops` 工件，敏感本机文件，目录 700、文件 600；不提交 | 是，忽略 |
| `.runtime/bank-agent-before-privacy-20261022.dump` | 本次 `0005 → 0006` 前的中端数据库备份，权限 600，含业务敏感信息；不提交 | 是，忽略 |
| `.runtime/privacy-live-readonly-20261022.json`、`.runtime/privacy-live-payload-20261022.json` | 本次实际服务只读查询/载荷核验的最小证据；不记录密码、Token 或完整银行数据，权限 600；不提交 | 是，忽略 |
| `.runtime/privacy-desktop-20261022.png`、`.runtime/privacy-mobile-20261022.png` | 实际前端 1440px/390px 三工具查询截图，含本人演示银行数据，权限 600；不提交 | 是，忽略 |
| `.runtime/billing-privacy-tests.xml` | 本轮中端独立 PostgreSQL 全量回归 JUnit 证据；不提交 | 是，忽略 |

已有文件同时调整：三个 Tool 仅返回安全摘要，`agent/context.py` 管理请求级不透明账户引用；`api/agent.py` 增加私有分析读取，`schemas/agent.py` 增加引用事件及读取响应；`main.py` 确保该接口错误响应也禁止缓存。聊天框通过分析 ID 单独取精确结果卡；账单/洞察页显示检测可用性；两个探针不再打印精确数据。原统计/异常图测试将精确断言迁移到快照，保留权限、分页、失败及 CLI 会话清理覆盖。Reset 的用户状态清理登记新增两表，仍不在本轮执行资金重置。

六类扩展继续复用上述文件和既有前端 evidence/聊天/账单/洞察组件；新增用例并入既有测试文件。`.runtime/billing-six-tests.xml`、`.runtime/billing-six-detectors.xml`、`.runtime/six-live-20261023.json` 与 `.runtime/six-ui-20261023.json` 为本机忽略的自动化及实际只读证据，不提交。

## 月度与年度完整账单报告（2026-10-26）

| 路径 | 归属模块与用途 | 生成物 |
| --- | --- | --- |
| `apps/backend/migrations/versions/0007_bill_report_jobs.py` | 中端持久化：后台账单报告任务、领取租约及独立分页交易快照表；仅迁移中端数据库 | 否 |
| `apps/backend/migrations/versions/0008_subscription_reminders.py` | 中端持久化：提醒规则、预算规则、站内通知、本人澄清、短期 Agent 结果及幂等键；仅迁移中端数据库 | 否 |
| `apps/backend/services/bill_report_service.py` | 中端报告：固定期间/账户范围和截止日，计算收支、分类、趋势、对比、习惯、异常、周期支出及受控解读；异步恢复、幂等、依赖账户重验和分页快照；记录账户范围供历史版本重生成 | 否 |
| `tests/integration/test_bill_reports.py` | 报告集成测试：金额/比较口径、无流水与零基期、本人互转去重、幂等、私有授权及交易快照 | 否 |
| `apps/frontend/src/pages/bill-reports-page.tsx` | 前端完整报告入口、异步状态、历史筛选/分页、图表、受控解读、周期/异常及可筛选分页明细 | 否 |
| `apps/frontend/src/pages/bill-reports-page.test.tsx` | 报告页面测试：创建、空期间语义、事实与证据展示及隐藏模型元数据 | 否 |
| `apps/frontend/e2e/bill-reports.spec.ts` | 报告浏览器回归：受控 API 验证历史版本保留账户范围重生成、年报详情和 1440px/390px 无横向溢出 | 否 |
| `apps/frontend/src/pages/account-detail-page.test.tsx` | 账户详情页面测试：验证报告链接通过受认证单笔流水接口重新读取核心事实，以及个人标注保存、缓存刷新和清除恢复 | 否 |
| `.runtime/bill-report-regression.xml` | 报告及 Agent/Reset 相关 PostgreSQL 筛选回归的 JUnit 结果；本机忽略，不提交 | 是，忽略 |
| `.runtime/bill-report-targeted-regression.xml` | 最新报告任务/Agent/Reset 定向 PostgreSQL 回归 JUnit 结果；本机忽略，不提交 | 是，忽略 |
| `.runtime/bill-report-full-regression-final.xml` | 本轮最终完整中端 PostgreSQL 回归 JUnit 结果；本机忽略，不提交 | 是，忽略 |
| `.runtime/bank-agent-before-bill-report-20261026.dump` | 中端 `0006 → 0007` 前数据库备份，含业务敏感信息；本机忽略、权限 600，不提交 | 是，忽略 |

调整既有文件：`api/billing.py` 增加异步生成/状态、摘要筛选、详情和快照明细接口，并保留旧接口；`worker.py` 执行持久化任务；Agent 增加生成 Tool 和报告导航事件，账户年份识别避免把自然语言年份当成账户 ID；前端账单页、洞察页及聊天增加生成入口/导航。历史列表重生成时沿用报告保存的账户范围；`account-detail-page.tsx` 支持从查询参数打开流水，再通过核心单笔详情接口重新鉴权。部署说明记录 0007 迁移、升级前备份和 worker 要求；API 文档与 OpenAPI 同步。

## 统一 Agent 集成新增文件（2026-10-18）

以下文件为银行 Agent 模块的人工维护源码或文档，均非生成物；独立工单教程不迁入本分支。

| 路径 | 用途 |
| --- | --- |
| `apps/backend/agent/router.py` | 模型候选领域识别与中端白名单裁决 |
| `tests/integration/test_agent_insights.py` | 真实图/Tool/Service 的受控统计与异常测试，包含全账户聚合、跨账户证据、部分失败及演示 CLI 验证 |
| `tests/integration/test_agent_routing.py` | 领域权限、预算、统一入口、查询上下文（含跨年/闰年年度参照与选择器隔离）、全账户工具参数及审计测试 |
| `apps/frontend/e2e/agent-chat.spec.ts` | 桌面/移动端统一聊天受控 API 测试；验证自然语言全账户统计不继承过期月份、异常结果卡确认/忽略入口及月/年消费统计卡 |
| `scripts/testing/demo_spending_agent.py` | 隐藏密码认证、本人账户选择、统计/异常真实模型只读演示 |
| `docs/development/billing-agent-learning-guide.md` | 账单 Tool 学习链路与演示命令 |
| `docs/development/unified-agent-entry-guide.md` | 统一领域路由、查询上下文、前端使用与集成恢复说明 |

`.runtime/bank-agent-before-integration-20261018.dump` 是本机数据库升级前备份，属于忽略的敏感生成物；不提交。`.gitignore` 统一忽略各目录 `.venv/`，保留原教程的本机环境。

## 根目录治理与配置

| 路径 | 用途 |
| --- | --- |
| `README.md` | 根目录唯一部署入口；提供项目简介、日常启停、常用地址并链接从零部署指南 |
| `AGENTS.md` | Codex 长期协作规则和台账维护规则 |
| `.gitignore` | 排除凭据、工具链、缓存、日志和生成物 |
| `.gitattributes` | 统一 Windows 与 Linux 文件换行规则，避免容器脚本因 CRLF 失效 |
| `.env` | 本机真实镜像配置和数据库密码；敏感文件，不得提交 |
| `.env.example` | 无真实密码的环境变量模板，可提交 |

## 自研应用

| 路径 | 用途 | 状态 |
| --- | --- | --- |
| `apps/frontend/` | React 19 + TypeScript + Vite 8 响应式 Web App；含登录保护、统一 API Client、本人账户/流水、支付与 Action、洞察、订阅、定存、我的、借记卡、Demo 商户及 Task 契约页；Vitest/MSW 和 Playwright 测试随模块维护 | 原业务底座保留；统一聊天支持余额/流水/洞察及成员 A 写请求 Action 卡，支付页支持计划核对与多联系人 AA；Task 延后 |
| `apps/backend/` | Python 3.11+ / FastAPI 中端；当前银行业务、订阅、借记卡与 Demo 商户、安全、迁移和按领域装配的 Agent 见下方明细；账户列表/详情使用稳定 DTO，不暴露 Fineract 原始响应 | 传统业务、订阅、卡片自动化闭环、Demo 核心入账及账户/洞察/支付/卡片/计划支付 Agent 已接入；真实写链路待彩排，Task 延后 |

## 银行平台源码

| 路径 | 用途 | 保留原因 |
| --- | --- | --- |
| `platform/fineract/` | Apache Fineract 官方源码；独立浅克隆 Git 仓库，本地 `bank-agent-dev` 分支基于 `b56917e` | 用于阅读、搜索、修改、编译及源码级调试；不得作为无用文件删除 |

`platform/fineract/` 内部文件由该上游仓库自身的 README、模块结构与 Git 历史管理，本台账不逐文件复制登记。

## 基础设施

| 路径 | 用途 |
| --- | --- |
| `infrastructure/docker/compose.yaml` | 启动 PostgreSQL 18.3 和 `.env` 指定的 Fineract 镜像；默认镜像使用不可变摘要固定 |
| `infrastructure/docker/init-db.sh` | PostgreSQL 首次启动时创建 Fineract 数据库和账号 |
| `infrastructure/windows/setup.ps1` | 创建并保留根目录 `.env` 中的本地随机密码 |
| `infrastructure/windows/start.ps1` | 启动 Docker 服务，并从容器内部等待 Fineract API 健康，兼容 Windows Schannel |
| `infrastructure/windows/stop.ps1` | 停止容器但保留数据库卷 |
| `infrastructure/windows/diagnose-wsl.ps1` | 诊断 WSL 状态 |
| `infrastructure/windows/repair/` | Windows、WSL 和虚拟化修复与验证脚本 |

## 本地开发工具

| 路径 | 用途 | 状态 |
| --- | --- | --- |
| `tools/gradle/` | 可选的 Fineract 源码构建缓存；普通 Docker 部署不需要，目录被 Git 忽略 | 本机开发工具，保留 |
| `tools/jdk/` | 可选的项目专用 JDK 25，仅供 Fineract 源码编译；普通 Docker 部署不需要，目录被 Git 忽略 | 本机开发工具，保留 |
| `tools/vscode/` | 旧 Fineract VS Code 工作区、任务与启动入口，包含已失效的个人绝对路径 | “安全清理”不删除可能承载用户配置的目录；待用户单独确认后删除或重建 |
| `scripts/fineract/gradle.ps1` | 使用项目 JDK 25，缺失时使用 Docker JDK 25，并复用 `tools/gradle` 构建 Fineract | 已完成 Docker 回退配置；容器内隐藏 `.git` 避免 Build Scan 扫描，并关闭与上游 Git 插件不兼容的配置缓存 |

## 脚本、测试与数据

| 路径 | 用途 | 状态 |
| --- | --- | --- |
| `scripts/fineract/` | Fineract 构建与初始化脚本 | 构建入口已迁入；`seed_fineract.py` 以精确 externalId/稳定产品名幂等注入四名用户主账户、随机分类流水、Alice 分析副账户、5 个固定零余额卡账户、独立 Demo 商户结算账户及3个月/6个月原生 CNY Demo 定存产品；`--wealth-products-only` 只创建产品且不生成账户/流水；状态文件仅作缓存 |
| `scripts/fineract/demo_history.py` | 历史数据生成器；共享维护 8 类中文分类、演示商户与整数分金额分布，使用 Decimal、种子和截止日产生可复现消费/订阅历史，并将 Alice 消费按随机种子分配到主账户/分析副账户；跳过并统计资金不足的消费 | 否 |
| `scripts/development/` | 初始化 Python 环境、启动前后端、检查连接、Agent 探针及安全 Demo Reset 的本地开发脚本；`setup-backend.ps1` 仅接受 Python 3.11–3.13 且不依赖个人机器回退路径 | 已建立并按用途拆分入口 |
| `scripts/development/reset_demo.py` | 跨 Fineract 与中端的安全 Demo Reset；默认只读计划并显示历史种子/截止日，精确识别 Alice 分析副账户、主账户/固定卡/UUID 动态卡/商户边界后要求确认；清理本人提醒、预算、通知及Agent临时结果等用户状态，再重建联系人、分类规则、5张加密基线卡和订阅样本，保留密码哈希 | 否 |
| `scripts/development/reset-demo.ps1` | Windows 一键 Demo Reset 入口；支持转发历史种子/截止日，校验 Python 虚拟环境、补充本机 `NO_PROXY` 后调用确认式 Python 重置 | 否 |
| `scripts/development/probe_agent_balance.py` | 认证余额探针；通过私有结果通道验证，模型和终端只接收安全状态；成功/失败均清理会话 | 否 |
| `scripts/testing/` | PostgreSQL集成测试入口与隔离Fineract契约探针 | 已实现 |
| `scripts/maintenance/` | 个人异常模型预训练与过期私有分析清理；由维护人员显式执行 | 已实现 |
| `tests/api/postman/` | Postman 集合和本地环境模板 | 已建立，待补充 |
| `tests/integration/` | 跨模块、并发及迁移测试 | 三场景已实现，使用独立测试库 |

## 文档

| 路径 | 用途 |
| --- | --- |
| `docs/project/master-plan.md` | 最高优先级全局执行规划、比赛要求映射与实时进度事实来源 |
| `docs/project/project-structure.md` | 项目目录、关键文件用途、状态和保留原因的权威台账 |
| `docs/project/full-agent-implementation-plan.md` | 从原始赛题硬要求出发的完整 Agent 实施基线；覆盖统一会话、六类场景、权限、安全、生日 DAG、评估、真实验收和比赛交付，不沿用已过期技术栈作为实现指令 |
| `docs/project/team-task-breakdown.md` | 当前非 Agent 阶段三人按业务域纵向分工的最小代码单元、任务编号、依赖和验收标准；跨场景 DAG 延后到 Agent 阶段 |
| `docs/project/agent-member-a-task-breakdown.md` | 成员 A Agent 账户/支付/卡片/定时转账/AA 的 A-01 至 A-45 任务拆分、自动化证据与真实写验收边界 |
| `docs/requirements/frontend-backend-requirements.md` | 非 Agent 前端与中端产品/系统需求事实来源；盘点现有接口并定义账户、支付、账单、订阅、定存、普通借记卡的页面、兼容契约、数据模型和验收矩阵；非生成物 |
| `docs/development/agent-development-guide.md` | 团队 Agent 开发规范；规定分层、业务域文件所有权、Tool/Prompt 格式、安全边界、测试门槛和 Git 协作流程 |
| `docs/architecture/` | 系统架构文档与架构图 |
| `docs/api/` | API 协议和接口说明 |
| `docs/api/fineract-endpoint-inventory.md` | API 文档模块；本地 Fineract 源码生成的接口索引快照（生成物，纳入版本控制），记录资源、方法、路径及源码入口；不代表运行镜像全部启用 |
| `docs/api/fineract-python-api-design.md` | API 文档模块；人工维护的项目接口筛选与 Python API/Service/Client 封装设计、协议注意事项及验收清单；非生成物，初始调研历史；三场景当前实施以 banking-backend.md 为准 |
| `docs/security/` | 权限分级、安全设计和安全自评 |
| `docs/deployment/fineract-windows-local.md` | Windows/Linux、Docker、数据库与 Fineract 启动、测试、关闭及 API 使用说明 |
| `docs/deployment/local-environment-requirements.md` | Windows 新电脑从 Git clone 开始的完整部署事实来源；按顺序覆盖系统依赖、密钥、依赖还原、Fineract Seed、中端初始化、四进程启动、验证、测试、停止和排错；非生成物 |
| `docs/demo/` | 比赛演示流程、讲稿和素材说明 |
| `docs/design/` | 前端设计；包含视觉参考图及 `frontend-page-and-feature-design.md` 页面/功能/路由/接口设计，图片和规划均不等同已实现页面 |

## 运行时与归档

> 2026-11-01 安全清理已删除此前积累的历史 `.runtime` 报告、备份和截图。本文前部保留的具体文件名用于记录各轮测试产物类型，不表示这些忽略文件当前仍存在；需要时应由相应测试重新生成。

| 路径 | 用途 | 版本控制策略 |
| --- | --- | --- |
| `.runtime/` | 当前服务日志和可重新生成的测试/评估产物 | 整体忽略；安全清理只保留运行中进程正在使用的日志 |

## 项目目录外的状态

- Docker 镜像、容器和 named volumes 由 Docker Desktop 管理，存放位置由 Docker Desktop 配置决定。
- PostgreSQL 业务数据位于 Docker named volume `bank-agent_postgres_data`；整理项目文件时不得删除该卷。
- Node.js 22.12+ 作为项目目录外的本机依赖，由用户 PATH 或 `BANK_AGENT_NODE_HOME` 定位；当前工作机已验证 Node.js 22.23.3。
- 用户 Downloads 中的原始 `bank_agent_initial_plan.md` 未被移动或删除；项目内过期副本已经删除。
- 项目根目录只保留项目自己的 `AGENTS.md` 和 `README.md`；第三方源码和工具发行包自带的 Markdown、许可证与说明文件保持原位。

## 三场景传统后端文件明细（2026-10-09）

以下均为项目维护源码或文档，除标明“生成物”外不是生成物。后端要求 Python 3.11+，当前工作机使用 Python 3.13.14。业务 API 与前端认证已经接通；账户域最小 Agent API 已存在，但本轮普通银行功能不以 Agent 为前置依赖。

| 路径 | 归属模块与用途 | 生成物 |
| --- | --- | --- |
| `apps/backend/main.py` | 后端入口，业务路由、错误响应、OTP启动配置检查 | 否 |
| `apps/backend/models.py` | 持久化，用户/会话/联系人/Action/额度/计划/AA/分类/报告/风险/产品元数据/商户/订阅/提醒/预算/通知/本人Agent临时数据/卡片/卡授权/审计模型；Action 含风险、来源、过期和乐观并发版本，审计含 trace/资源索引；只映射项目独立数据库 | 否 |
| `apps/backend/alembic.ini` | 持久化，迁移目录与Python模块路径配置 | 否 |
| `apps/backend/migrations/env.py` | 持久化，读取独立数据库URL并运行在线/离线迁移；测试可注入同一数据库连接验证内存库迁移 | 否 |
| `apps/backend/migrations/script.py.mako` | 持久化，新迁移脚本模板 | 否 |
| `apps/backend/migrations/versions/0001_banking.py` | 持久化，冻结的初始schema及降级操作；由Alembic差异生成后维护 | 初始生成后冻结纳管 |
| `apps/backend/migrations/versions/0002_purchase_risk_assessment.py` | 持久化，为风险测评增加申购用途、一次性使用时间及绑定 Action；兼容迁移与降级 | 否 |
| `apps/backend/migrations/versions/0003_subscriptions.py` | 持久化，新增商户、订阅与订阅流水证据表及完整降级操作 | 否 |
| `apps/backend/migrations/versions/0004_bank_cards.py` | 持久化，新增普通借记卡与卡授权表；卡账户使用非唯一索引以保留同账户旧卡/补卡历史，另含幂等唯一约束及完整降级操作 | 否 |
| `apps/backend/migrations/versions/0005_action_audit_metadata.py` | 持久化，为 Action 增加风险级别、可信来源、过期时间、更新时间和乐观并发版本，为审计增加 trace 与业务资源索引；旧记录使用安全兼容值并支持 SQLite/PostgreSQL 完整降级 | 否 |
| `apps/backend/core/config.py` | 公共配置，Fineract/独立数据库/环境/OTP/Demo及卡片加密密钥配置 | 否 |
| `apps/backend/core/card_crypto.py` | 卡片安全，使用 AES-GCM 和卡 ID 关联数据加密/校验 Demo 完整卡号；密钥只来自环境 | 否 |
| `apps/backend/core/database.py` | 持久化，连接池与请求Session边界 | 否 |
| `apps/backend/core/errors.py` | 公共底座，领域错误与规则断言 | 否 |
| `apps/backend/core/security.py` | 安全，Argon2id、令牌摘要、HMAC OTP、参数指纹、Decimal/时区工具 | 否 |
| `apps/backend/core/deps.py` | API依赖，Bearer认证、当前用户/管理员和核心客户端 | 否 |
| `apps/backend/clients/fineract.py` | 协议适配，账户开户/审批/激活、页号流水、转账和定存正式 API，稳定命令键和错误转换 | 否 |
| `apps/backend/clients/demo_merchant.py` | 协议适配，明确限定比赛环境的 Demo 订阅取消；不连接或冒充真实第三方会员系统 | 否 |
| `apps/backend/schemas/banking.py` | API契约，请求验证模型及金额/日期/分摊约束；包含订阅扫描、预测查询、提醒提前天数和月度预算契约 | 否 |
| `apps/backend/schemas/account.py` | API契约，定义稳定的账户汇总、详情和余额 DTO，金额使用 Decimal | 否 |
| `apps/backend/api/context.py` | API公共依赖与Decimal响应编码、Service构造 | 否 |
| `apps/backend/api/auth.py` | API，登录/刷新/退出/me与开发专用本人验证码收件箱 | 否 |
| `apps/backend/api/accounts.py` | API，本人账户/余额/汇总/流水 | 否 |
| `apps/backend/api/transfers.py` | API，联系人/普通转账/本人互转/Action/计划/AA | 否 |
| `apps/backend/api/billing.py` | API，类别/规则/标注/统计/异常；兼容旧报告接口并提供异步报告生成、状态、摘要、详情和分页快照 | 否 |
| `apps/backend/api/investments.py` | API，风险/产品/推荐/定存申购/持有/赎回及管理员适配元数据 | 否 |
| `apps/backend/api/subscriptions.py` | API，手动扫描、续费和月份预测、提醒/预算规则CRUD与状态操作、本人站内通知，以及列表/详情/核实/忽略/取消 | 否 |
| `apps/backend/api/cards.py` | API，本人卡片列表/详情、申请、别名、OTP 激活、60 秒无缓存安全查看、限额/渠道、锁定/解锁、挂失与补卡 | 否 |
| `apps/backend/api/demo_cards.py` | API，development 专用 Demo 商户目录、卡消费 Action 和本人卡授权记录；非开发环境返回 404 | 否 |
| `apps/backend/services/common.py` | Service公共工具，归属校验、用户行锁、审计递归敏感字段脱敏和安全序列化；金额保持字符串，所有 datetime 统一输出带 UTC 偏移的 ISO 8601 | 否 |
| `apps/backend/services/auth_service.py` | 身份业务，Argon2、会话轮换/撤销、密码失败锁定 | 否 |
| `apps/backend/services/account_service.py` | 账户业务，归属/CNY/普通储蓄账户校验，读取核心可用余额及全账户 Decimal 汇总 | 否 |
| `apps/backend/services/recipient_service.py` | 联系人业务，本地CRUD/精确字段检索及AA参与用户引用解析 | 否 |
| `apps/backend/services/action_service.py` | 安全执行，幂等/确认/OTP/额度原子占用/执行抢占/核对及续办 | 否 |
| `apps/backend/services/transfer_service.py` | 资金业务，核心转账、事实回读、双边交易引用及响应丢失只读核对 | 否 |
| `apps/backend/services/schedule_service.py` | 调度业务，分钟级周期/预授权/月末/补执行策略和防重复发生项 | 否 |
| `apps/backend/services/aa_service.py` | AA业务，按分分摊、主动授权付款、冻结和部分付款取消 | 否 |
| `apps/backend/services/transaction_service.py` | 流水业务，规范化/完整分页/人工与规则分类/本人互转、已批准 Demo 卡授权及原生定存划转识别；卡消费以核心 transfer 引用映射为 expense/商户类别，只解析项目自有 `[Merchant]` note 前缀为订阅商户证据 | 否 |
| `apps/backend/services/billing_service.py` | 账单业务，语义CRUD、本人全部 CNY 账户或单账户汇总、跨账户异常证据及旧版同步JSON报告兼容 | 否 |
| `apps/backend/services/bill_report_service.py` | 完整账单报告：持久化任务、不可变事实/交易快照、周期比较和受控自然语言解读；自然语言打开时精确匹配本人/期间/账户范围，复用报告或任务，仅缺失时锁内入队并审计 | 否 |
| `apps/backend/services/investment_service.py` | 定存业务，原生产品适配、15分钟一次性申购测评、推荐、申购步骤、报价、赎回和恢复 | 否 |
| `apps/backend/services/subscription_service.py` | 订阅业务，800天有界完整扫描及可追溯审计、月/年周期与10%金额规则、只读续费查询/过期预测复查、状态合并和带确认快照的可恢复 Demo 取消 | 否 |
| `apps/backend/services/subscription_planning_service.py` | 订阅计划：Decimal续费预测、实际订阅账单归属与去重、预算监测、用户幂等提醒规则、30分钟澄清/私有结果、09:00站内通知worker与补发去重 | 否 |
| `apps/backend/services/card_service.py` | 卡片业务，幂等申请、Fineract 零余额自动开户、响应丢失找回、掩码/别名/OTP 激活、60 秒安全解密、限额渠道风险分级、版本保护及永久挂失补卡状态机 | 否 |
| `apps/backend/services/card_transaction_service.py` | Demo 卡消费业务，确定性卡状态/渠道/境外/单笔/日累计/余额校验、授权持久化、Fineract 双边转账、拒绝审计与响应丢失核对 | 否 |
| `apps/backend/worker.py` | 调度/账单报告/订阅提醒与预算生成入口；计划每30秒、报告任务每2秒领取并处理 | 否 |
| `apps/backend/requirements.txt` | 后端锁定依赖，包含 FastAPI、Alembic/psycopg/Argon2、卡号 AES-GCM 所需 cryptography 及最小 Agent 的 LangGraph/OpenAI 兼容客户端 | 否 |
| `apps/backend/agent/__init__.py` | Agent 模块包入口；保持轻量，不在导入时构建图或连接外部服务 | 否 |
| `apps/backend/agent/context.py` | 请求级认证用户、按领域注入的账户/账单/订阅/支付/卡片/计划/定存/生日编排 Service、查询选择、可信澄清引用、上海日期、trace 和结构化事件收集器；身份不暴露为模型参数 | 否 |
| `apps/backend/agent/state.py` | LangGraph 公共状态契约，分别维护模型消息 `messages` 与中端结构化事件 `events`；跨业务修改需团队协调 | 否 |
| `apps/backend/agent/registry.py` | Agent 领域能力注册表与动态解析器；将每个已验收领域的 Prompt 和 Tool 绑定，并只解析本次可信策略启用的领域 | 否 |
| `apps/backend/agent/graph.py` | 按获准领域绑定 Prompt/Tool，注入请求上下文，检查工具名/累计三次预算和订阅单独操作约束 | 否 |
| `apps/backend/agent/prompts/__init__.py` | 公共系统 Prompt 组合函数；不固定导入任何业务域，由领域解析器按本次任务组合 | 否 |
| `apps/backend/agent/prompts/base.py` | Agent 公共角色、权限、信任边界、工具真实性与响应规则；安全控制仍由中端代码强制执行 | 否 |
| `apps/backend/agent/prompts/accounts.py` | 账户域 Prompt；约束本人余额/流水 Tool、私有结果、空账户与不完整结果表达 | 否 |
| `apps/backend/agent/prompts/payments.py` | 支付域 Prompt；限定本人联系人消歧、付款账户末四位、普通/本人互转只创建 Action | 否 |
| `apps/backend/agent/prompts/cards.py` | 卡片域 Prompt；限定本人掩码信息、别名/末四位消歧、完整卡号隔离和 Action 流程 | 否 |
| `apps/backend/agent/prompts/payment_plans.py` | 计划支付域 Prompt；限定定时转账草稿/授权和 AA 本人份额安全流程 | 否 |
| `apps/backend/agent/prompts/insights.py` | 洞察域 Prompt；账户与日期优先级、报告/即时统计区分、消费统计事实、异常候选证据与数据边界 | 否 |
| `apps/backend/agent/prompts/subscriptions.py` | 订阅域 Prompt；限定扫描、续费/预算/提醒与 Demo 取消的独立请求、安全摘要和确认边界 | 否 |
| `apps/backend/agent/prompts/wealth.py` | 财富域 Prompt；限定原生 CNY 定存、私有精确结果、一次性风险测评、RED Action 和整笔赎回规则 | 否 |
| `apps/backend/agent/prompts/orchestration.py` | 生日编排域 Prompt；只开放固定鲜花+蛋糕白名单 DAG，要求日期、账户和两项金额均由用户明确给出，并限定 RED 授权、Hold、取消与核对边界 | 否 |
| `apps/backend/agent/tools/__init__.py` | 按业务域拆分的 Agent Tool 包入口；账户、支付、洞察和财富工具分别维护 | 否 |
| `apps/backend/agent/tools/accounts.py` | 账户域 Agent Tool；余额和流水均只查询运行时认证用户，精确结果进入私有分析快照 | 否 |
| `apps/backend/agent/tools/payments.py` | 支付域 Agent Tool；本人联系人列表/搜索、普通转账和本人互转，写操作只创建 Action | 否 |
| `apps/backend/agent/tools/cards.py` | 卡片域 Agent Tool；安全查询及申请、激活、设置、锁定/解锁、挂失、补卡和完整卡号授权请求 | 否 |
| `apps/backend/agent/tools/payment_plans.py` | 计划支付域 Agent Tool；定时计划和 AA 收款的本人查询、创建、管理及付款 Action | 否 |
| `apps/backend/agent/tools/insights.py` | 单账户/全账户统计与异常候选 Tool；账户参数必填但允许显式 null，隐藏身份并复用 BillingService；不开放写操作 | 否 |
| `apps/backend/agent/tools/wealth.py` | 财富域 Agent Tool；产品/推荐/持有写入本人私有结果，申购/赎回按稳定键只创建 RED Action，不直接移动资金 | 否 |
| `apps/backend/agent/tools/orchestration.py` | 生日编排域 Agent Tool；本人任务查询走结构化私有卡，创建前确定性复核原始消息中的事件、日期、付款账户和鲜花/蛋糕分项金额，只生成固定任务与 RED Action | 否 |
| `apps/backend/schemas/agent.py` | Agent HTTP 与结构化事件契约；定义最多 8 条用户消息历史、私有分析、账单、订阅、财富测评及转账/互转/卡片/计划/AA/财富/生日任务事件 | 否 |
| `apps/backend/api/agent.py` | 统一认证入口，可信领域裁决、按领域 Service 注入、资源归属重验、无工具事实拦截、脱敏审计及写后模型失败恢复；兼容同步入口和持久化会话 Worker 共用 | 否 |
| `scripts/development/init_banking.py` | 初始化独立数据库/角色、迁移、四 Demo 用户映射/联系人、8 类个人分类和精确商户规则、Demo 商户映射、两个原生 Demo 定存产品的低风险适配元数据、Alice 两张及其他用户各一张加密 ACTIVE 基线卡与可选管理员；`--demo-billing-fixtures` 显式登记订阅样本；幂等且不重置核心资金 | 否 |
| `scripts/testing/run_banking_tests.py` | 测试入口，创建独立bank_agent_test并运行PostgreSQL测试，屏蔽系统ROS pytest插件 | 否 |
| `scripts/testing/probe_banking.py` | 真实契约探针，隔离客户/账户/产品，正式API验证分页/转账/定存生命周期；受保护的原生成熟任务验证 | 否 |
| `tests/integration/conftest.py` | 测试夹具，独立数据库、受控核心替身及认证HTTP客户端 | 否 |
| `tests/integration/test_banking.py` | 集成测试，身份/OTP/资金/并发/调度/AA/全账户账单/订阅扫描与续费边界/取消恢复/定存恢复/卡片开户、设置、状态机、安全查看、审计脱敏及 Demo 商户入账/拒绝/核对等业务验收 | 否 |
| `tests/integration/test_migrations.py` | 迁移测试，在受控测试连接上验证升级/降级/再升级及模型一致性 | 否 |
| `tests/integration/test_wealth_seed.py` | 两个原生 CNY Demo 定存产品的幂等 Seed 契约及中端低风险适配元数据回归 | 否 |
| `tests/integration/test_agent.py` | Agent API 集成测试；验证登录保护、Token 身份注入、伪造身份拒绝、响应契约与脱敏审计 | 否 |
| `tests/integration/test_subscription_planning.py` | 订阅预测、实际与预计扣费合并、预算、动态提醒规则、幂等/隔离、worker时间与补发回归 | 否 |
| `tests/integration/test_demo_reset.py` | Demo Reset 和历史数据集成测试；验证精确副账户/主账户/固定卡/动态卡/商户边界、动态卡关闭、未知账户拒绝、种子复现、分类商户映射、TransactionService/BillingService、提醒/预算/通知及用户级表清理、基线卡幂等恢复和用户状态保留 | 否 |
| `tests/integration/test_anomaly_detection.py` | 异常检测与个人模型集成测试；除规则边界和模型安全外，使用生成分类、核心替身和临时模型目录验证特征输入、训练边界及六类检测状态/跳过原因 | 否 |
| `tests/integration/test_agent_member_a.py` | 成员 A Agent 集成测试；验证领域/Schema、联系人/转账/互转/卡片/计划/AA、结构化事件、幂等和写后恢复 | 否 |
| `tests/integration/test_agent_wealth.py` | 财富域 Agent 集成测试；验证产品/推荐/持有私有结果、结构化测评跳转、申购/赎回 RED Action、身份隔离、幂等和精确金额/利率/报价不进入模型边界 | 否 |
| `apps/backend/migrations/versions/0011_birthday_orchestration.py` | 生日跨场景固定 DAG 数据迁移；新增个人事件、任务、节点、边、事件、资金预留与 Demo 订单表 | 否 |
| `apps/backend/migrations/versions/0012_repair_bill_report_jobs.py` | 幂等修复历史 Alembic stamp 漂移；仅在缺失时补建 `0007` 所属报告任务与报告流水表，健康数据库不变，downgrade 不删除 `0007` 资产 | 否 |
| `apps/backend/services/orchestration_service.py` | 固定生日鲜花+蛋糕任务状态机；RED 授权、按月 Hold、提前两天释放并向两个 Fineract Demo 商户付款，以及暂停/恢复/取消/接管/重试/核对 | 否 |
| `apps/backend/api/tasks.py` | 本人个人事件、生日任务、任务详情与暂停/恢复/取消/接管/节点重试和核对 API | 否 |
| `tests/integration/test_orchestration.py` | 生日编排 Service/API/迁移回归；覆盖归属、幂等、RED 授权、Hold、付款、取消释放、结果不明核对和人工接管 | 否 |
| `tests/integration/test_agent_orchestration.py` | 生日编排 Agent 回归；覆盖安全 Tool Schema、显式分项输入、账户澄清、RED Action、身份隔离和确定性结构化事件 | 否 |
| `docs/api/banking-backend.md` | API文档，本机启动/首次初始化、Swagger登录与确认/OTP测试、worker、自动化测试、完整方法/路径速查、上游映射和恢复约定 | 否 |
| `docs/api/banking-openapi.json` | API契约，从FastAPI生成的版本控制快照；实时版本在/openapi.json | 是，纳管 |
| `docs/testing/banking-live-contracts.json` | 测试证据，隔离真实核心契约的脱敏结果 | 是，纳管 |
| `docs/testing/banking-backend-validation.md` | 测试说明，本轮环境、执行证据、覆盖和已知限制 | 否 |
| `docs/testing/demo-feature-validation-2026-10-31.md` | 2026-10-31 演示功能全量验收记录；汇总中端、前端、浏览器、评估集结果与统一待修问题台账 | 否 |
| `docs/testing/ai-assistant-usable-dialogue-validation-2026-11-01.md` | 用户《演示.md》真实 AI 助手对话验收报告；收录 59 条持久化 Agent HTTP 复测和 2 条真实 React/Edge 财富补测的提示词、实际回复、Run、结构化事件和安全判定，并明确未通过/未配置边界 | 否 |
| `.runtime/demo-prompt-results-*.json` | 《演示.md》逐提示词真实运行原始证据；包含未脱敏 Demo 银行事实、会话/Run/事件引用，仅本机保留，不提交 | 是，忽略 |
| `.runtime/banking-tests.xml`、`subscription-focused.xml`、`subscription-regression.xml`、`subscription-tests.xml`、`subscription-final-regression.xml`、`subscription-final-tests.xml` | 测试运行证据，PostgreSQL集成测试与订阅专项/筛选/全量回归JUnit报告；不得提交 | 是，忽略 |
| `.runtime/billing-personalization-full.xml` | 账单个人修正与规则补齐后完整中端 PostgreSQL 回归 JUnit 报告；忽略，不提交 | 是，忽略 |
| `.runtime/banking-http-smoke.log` | API运行证据，临时Uvicorn HTTP冒烟日志；不得提交 | 是，忽略 |
| `.runtime/banking-probe-state.json` | 测试运行状态，专属核心资源引用，用于探针复用；不得提交 | 是，忽略 |
| `apps/backend/.venv/`、各级`__pycache__/`、`.pytest_cache/` | 本机解释器依赖及测试/编译缓存；不得提交 | 是，忽略 |

`apps/backend/migrations/versions/`、`scripts/testing/`、`tests/integration/`、`docs/testing/` 已随本轮落地。PostgreSQL 的 `bank_agent` 保存本地业务状态，`bank_agent_test` 为可重建测试库，均在Docker数据卷中，不属于源码生成文件。Fineract源码及业务数据库不通过项目SQL脚本修改。

## 比赛前端关键文件（2026-10-11）

以下文件均为项目维护源码或测试，不是生成物；`node_modules/`、`dist/`、`test-results/` 和 `playwright-report/` 为忽略的本机生成物。

| 路径 | 归属模块与用途 |
| --- | --- |
| `apps/frontend/src/auth/auth-provider.tsx` | 认证状态、会话恢复、登录退出和认证丢失处理 |
| `apps/frontend/src/auth/auth-context.ts` | 认证上下文类型与 `useAuth` Hook；与 Provider 组件分离，支持 Fast Refresh 和跨页面复用 |
| `apps/frontend/src/auth/protected-route.tsx` | 等待会话恢复并保护全部业务路由 |
| `apps/frontend/src/lib/api.ts` | 统一 API Client、Bearer 注入、单飞刷新、超时/错误与重试策略、订阅预测/提醒/预算/通知/Agent延续引用等类型化契约 |
| `apps/frontend/src/lib/format.ts`、`format.test.ts` | 上海日期键、完整自然月/年统计卡标题、金额展示与账户号统一脱敏；账户号在首页、账户、转账、洞察和实时账单页面只显示尾号，测试覆盖普通、短值、空值和含空白输入 |
| `apps/frontend/src/lib/bill-period.ts` | 实时账单月/年期间解析与上海日期边界；与页面组件分离，供组件测试直接复用 |
| `apps/frontend/src/lib/evidence.ts`、`evidence.test.ts` | 将账单异常规则码及订阅识别证据转换为用户可读中文摘要；三处异常展示共享业务证据及空结果文案，不呈现执行来源/模型评分；测试覆盖六类异常、纯模型/合并候选及订阅未见付款观测 |
| `apps/frontend/src/components/page-state.tsx`、`page-state.test.tsx` | 加载、空数据、权限/校验/冲突/超时/不可用错误、安全重试和“服务尚未接入”统一状态及组件测试；写结果未知时不显示重试按钮 |
| `apps/frontend/src/agent/agent-provider.tsx`、`components/agent/agent-panel.tsx` | 统一 Agent 悬浮入口；发送账户/月度、最近用户消息和订阅延续引用，展示私有余额/流水/洞察、账单报告、订阅结果及成员 A 写请求 Action 卡并跳转业务页 |
| `apps/frontend/src/agent/agent-context.ts` | Agent 面板上下文类型与 `useAgent` Hook；与 Provider 组件分离，避免路由打开状态使用同步 Effect |
| `apps/frontend/src/components/agent/agent-panel.test.tsx` | Agent 对话框测试；验证认证、受限历史、自然语言月份/全账户范围、账单与订阅事件、澄清延续、缓存失效、私有流水和结构化 Action 事件展示 |
| `apps/frontend/src/pages/login-page.tsx` | 登录和锁定/认证错误展示 |
| `apps/frontend/src/pages/home-page.tsx` | 本人账户汇总、待处理 Action 和快捷入口 |
| `apps/frontend/src/pages/accounts-page.tsx`、`account-detail-page.tsx` | 本人账户、余额、分页筛选流水及单笔流水详情 |
| `apps/frontend/src/pages/payments-page.tsx`、`transfer-page.tsx` | 普通/定时/AA、转账记录和联系人管理 |
| `apps/frontend/src/pages/action-page.tsx` | 确认、OTP、执行、核对、结果和操作记录共用流程；订阅取消展示确认快照并提示过期/失败后的恢复路径；处理中每 2 秒刷新、60 秒后停止自动刷新并只保留手动刷新/核对 |
| `apps/frontend/src/pages/insights-page.tsx` | 全账户/单账户即时收支与消费分类统计、分类与三种字段规则 CRUD/优先级、中文异常证据摘要与有反馈核实、统一账单报告入口和共用服务端续费查询 |
| `apps/frontend/src/pages/bill-page.tsx`、`bill-page.test.tsx` | 独立实时月/年账单页及组件测试；解析期间、切换全账户/单账户，展示收支、分类、年度逐月收入/消费/对外转账、仅业务异常证据、截止时间、规则版本和非原子快照提示 |
| `apps/frontend/src/pages/bill-reports-page.tsx`、`bill-reports-page.test.tsx` | 按需保存的月/年完整报告、历史版本和详情；支持图表、受控解读、异步状态及明细筛选分页 |
| `apps/frontend/src/pages/account-detail-page.tsx` | 账户流水/详情；支持 `?transaction=<id>` 入口，以已认证核心详情 API 重新读取并校验交易，可维护/清除本人单笔分类、商户和备注标注 |
| `apps/frontend/src/pages/subscriptions-page.tsx` | 订阅扫描、候选核实/忽略、续费和月度预测、站内通知、提醒/预算规则管理、过期/不完整预测和 Demo取消入口 |
| `apps/frontend/src/pages/subscriptions-page.test.tsx` | 订阅预测、提醒/预算创建编辑、规则状态操作、通知已读和预算结果的页面测试 |
| `apps/frontend/e2e/subscription-reminders.spec.ts` | 桌面与390px受控浏览器验收：续费查询、提前量追问、规则管理、通知、超预算建议及Demo Action确认 |
| `apps/frontend/e2e/wealth-live.spec.ts` | 显式开启的本机真实栈验收：从 React 登录后验证两个 Fineract Demo 定存产品、比较、一次性测评、推荐和待确认 RED 申购 Action，并通过真实 Agent Worker/DeepSeek 在智能助手中验证产品目录与适配推荐卡；不确认、不输入 OTP、不移动资金 |
| `apps/frontend/src/pages/cards-page.tsx` | 普通借记卡申请、本人列表/详情、真实关联账户余额、OTP 激活、临时安全查看、别名、限额/渠道、锁定/解锁、挂失与补卡，以及批准/拒绝的 Demo 授权记录；明确 Demo 边界 |
| `apps/frontend/src/pages/demo-merchant-page.tsx` | development 专用 Demo 商城；选择本人 ACTIVE 卡、商户、金额、渠道和国家，创建幂等消费 Action，并醒目标注模拟网络与 Fineract 资金边界 |
| `apps/frontend/src/pages/wealth-page.tsx`、`risk-assessment-page.tsx` | 风险问卷、定存产品、申购、持有、赎回报价和安全确认 |
| `apps/frontend/src/pages/future-service-page.tsx`、`apps/frontend/src/pages/future-service-page.test.tsx` | 固定生日 Task 详情与组件测试；以用户可读时间线展示授权、节点、资金预留、Demo 订单和审计事件，只按服务端 `allowed_commands` 提供恢复操作，不展示内部 JSON |
| `apps/frontend/vitest.config.ts`、`src/test/`、`src/**/*.test.*` | Vitest、Testing Library 与 MSW 配置和组件/API 单元测试 |
| `apps/frontend/playwright.config.ts`、`e2e/` | Playwright 桌面和 390px 移动端浏览器测试，覆盖登录、本人互转、全账户洞察、订阅核实/取消快照确认、缓存刷新、卡片申请、锁卡确认、OTP 临时卡号查看和 Demo 消费确认；默认使用 Playwright Chromium，也可通过 `PLAYWRIGHT_BROWSER_CHANNEL` 验收本机 Chrome/Edge |
| `apps/frontend/e2e/support/durable-agent.ts` | Playwright 专用持久化 Agent 会话桥；将各场景既有同步测试响应适配为 conversation、消息入队、SSE 与 Run 状态；人工维护且不进入生产构建 |
| `apps/frontend/src/pages/cards-page.test.tsx` | 借记卡五种状态对应的可用操作与限额设置显隐矩阵组件测试 |
| `apps/frontend/src/pages/transfer-page.test.tsx` | 本人互转必填项与余额上限前端校验组件测试，确保无效输入不会进入写请求 |

## 2026-10-27 订阅扫描 Agent 文件登记

| 路径 | 用途及归属模块 | 生成物 |
| --- | --- | --- |
| apps/backend/agent/tools/subscriptions.py | 订阅域扫描/取消和预测/规则/预算 Tool；运行时注入本人和Service，结果走私有引用，取消仍复用Action | 否，人工维护源码 |
| apps/backend/agent/prompts/subscriptions.py | 订阅扫描、取消、续费查询、提醒/预算创建意图及固定范围、确认和不支持操作约束 | 否，人工维护源码 |
| tests/integration/test_agent_subscriptions.py | 订阅 Agent 身份隔离、Schema、无工具/错误不成功、调用批次、审计和隐私回归 | 否，人工维护测试 |

| tests/integration/test_agent_subscription_cancel.py | 订阅取消 Agent：Schema、身份隔离、目标匹配、Action确认、重复请求及恢复测试 | 否，人工维护测试 |

| apps/frontend/src/components/bank-header.tsx | 全局站内通知入口与未读计数 | 否，人工维护源码 |
