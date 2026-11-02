# 三场景后端验收记录

基础验收日期：2026-10-09；卡片申请、激活、限额/渠道、状态机、安全查看、Demo 商户与基线 Reset 补充验收日期：2026-10-15；带时区 HTTP 序列化、并发、审计敏感字段脱敏、两次真实 Reset 与刷卡账单分类补充验收日期：2026-10-16。范围包含传统业务后端、独立数据库、初始化、调度、API 文档、最小账户域 Agent HTTP 契约，以及 Reset 的中端清理、固定/动态卡账户边界与真实 Fineract 彩排。外部模型真实调用和真实 Fineract Demo 消费仍由手工探针/确认式命令单独验收。

## 2026-11-01 Agent 多轮结果卡归属回归

- 根因：会话 SSE 从事件游标 0 重放整段会话；前端此前没有过滤事件的 `conversation_id` 和 `run_id`，于是把历史 `TEXT_COMPLETE` 与结果卡挂到当前回复。持久化消息恢复本来按完成事件所属 Run 分组，保持该行为。
- 修复：发送与恢复 Run 共用按会话/Run 过滤的 SSE 收集；游标仍越过历史事件，按 `event_id` 去重。读取断流可在短暂退避后用 `Last-Event-ID` 继续；完成事件缺失时只使用目标 Run 的持久化助手消息。结果引用不做全会话去重，允许不同 Run 合法复用同一引用。
- 前端 API 与组件回归：`npm test` **15 files / 107 passed**。覆盖三轮不同结果、相同结果引用复用、历史结果重放隔离、当前文字持久化回退、重复事件、`Last-Event-ID` 续接、连接失败重试及失败 Run 拒绝。
- 浏览器回归：`npx playwright test e2e/agent-chat.spec.ts e2e/subscription-reminders.spec.ts` **18 passed**。1440px 和 390px 下执行三轮查询、刷新恢复、继续纯文字追问；旧卡片各自保留在原回复。订阅 YELLOW 查询确认卡在后续轮次仍留在原消息，页面直查与确认后结果流程通过。
- `npm run lint`、`npm run build`、`git diff --check` 均通过。Playwright 使用受控 API/Agent 响应，不代表真实模型或生产网络验收；未改后端 API、OpenAPI、数据库或运行依赖。

## 2026-11-01 对话订阅查询 YELLOW 确认闭环

- `subscription_query` 使用现有 Action/审计接口，确定性固定 YELLOW；列表、详情、续费预测、提醒/预算规则查询在对话请求阶段只保存参数、上海日期范围、来源会话/Run 和30分钟有效期。确认前不读取订阅业务数据、不保存或返回结果；确认时重验本人归属、请求指纹、有效期和状态，结果快照与 Action 结果引用原子提交。重复确认复用同一结果，取消、失败和过期不展示成功卡片。
- 中端专项通过独立 `bank_agent_test` PostgreSQL：**31 passed**，覆盖查询类型确认前/后、筛选、请求指纹篡改、跨用户、Action 及结果过期、取消、重复确认、查询失败回滚/重试、会话事件持久化和并发重复确认。PostgreSQL 并发场景已在上述隔离数据库实际执行。
- 前端 Vitest **15 files / 102 passed**；组件覆盖查询取消、处理中防重复、刷新/重新打开后从持久会话和 Action 恢复结果，以及过期结果提示重新发起；Playwright **2 passed**，在1440px与390px验证页面订阅页直接 GET、聊天查询条件卡、点击确认、确认前没有私有结果读取及确认后结果卡。`npm run lint`、`npm run build` 通过。Playwright 使用受控 API 响应，不等同于真实模型供应商验收。
- 从当前 FastAPI `app.openapi()` 生成并核对版本控制快照：**109 paths / 143 operations**；包含新的查询请求/完成/取消/失败事件 Schema。未新增路径、数据库迁移、运行依赖或环境变量；未对开发主库执行迁移、真实订阅扫描/修改/取消或资金操作。
- 边界：真实模型供应商对中文订阅查询变体的意图泛化，以及真实开发/生产运行时端到端未在本轮验证；页面直查仍以认证和本人归属为门槛，客户端页面来源标记不参与授权。

## 2026-10-30 完整 Agent Phase 4 安全熔断与评估基座

- 版本化评估集：`tests/evaluation/agent-routing-cases.jsonl` 共 **150 条**；功能路由 **120 条**，转账、账单、财富、卡片、订阅和跨场景任务各 20 条；Prompt Injection/越权 **30 条**。离线验证器核对数量、唯一性、标签和 95% 功能/100% 安全门槛。经用户授权完整调用 `deepseek-ai/DeepSeek-V3.2`，功能 **112/120（93.33%）**、安全路由精确匹配 **14/30（46.67%）**，两个门槛均未通过；完整失败样本保存在忽略的 `.runtime/agent-routing-evaluation.json`。
- 确定性安全门：敏感输入、Prompt Injection 和受控权限失败在 10 分钟窗口内计数，达到 5 次后只锁定本人 Agent 写 Tool 15 分钟；普通登录、账户和其他认证只读接口继续可用。安全事件只保存规则/类型和脱敏元数据，不保存攻击原文。写 Tool 在调用业务 Service 前再次检查锁，旧兼容入口也不能绕过。
- 自动化：Agent 评估、会话和路由定向 **65 passed**。最终官方 PostgreSQL 完整回归收集 **333 tests**，执行结果 **332 passed、1 skipped、0 failed**；跳过项仍为 Windows 未启用符号链接权限的既有安全用例，另有 1 条 Starlette/AnyIO BlockingPortal 既有弃用警告。
- 契约与静态检查：离线评估结构验证、Python compileall、`pip check` 通过；Alembic 唯一 head 为 `0011`，OpenAPI 快照与运行代码精确一致，为 **109 paths / 143 operations**。Node 22.23.3 下前端 Vitest **15 files / 97 passed**，lint 通过并保留 8 条既有警告，生产构建通过并保留 559.43KB chunk 提示。
- 文档证据：新增 Agent 评估说明、安全设计、安全自评、系统架构、Agent/策略算法、作品简介、答辩大纲、演示脚本和彩排清单；作品简介正文按当前文件字符计数为 186，不含标题和说明。
- 真实只读栈：Docker PostgreSQL healthy，Fineract 健康接口 `UP / HTTP 200`；FastAPI 与 Vite 启动后，经前端代理完成健康、Alice 登录、本人身份、3 个本人账户、兼容同步入口 `POST /api/agent/messages` 和退出登录，全部 HTTP 200。同步入口返回 `ANALYSIS_READY`，没有在终端打印精确余额。首次探针失败来自未启动 Fineract/本机代理，启动并补最小 `NO_PROXY` 后通过。
- 开发库修复：升级前备份 `.runtime/bank-agent-before-0011-20261030.dump` 已经 `pg_restore --list` 校验，SHA-256 为 `A508036DBB36303C1CC1182B981F6246420038395143C8B4F910F8F978EEF7C5`。普通升级在 `0009` 遇到既有字段冲突后事务回滚；只读核对确认 `0009` 的字段、指纹及唯一约束已精确存在，遂应用 `0008`、协调 stamp `0009` 并继续升级至 `0011 (head)`。未执行 Seed、Reset、OTP 或资金操作。
- 真实持久化链路：FastAPI 与 Agent Worker 启动后，Alice 登录、创建会话、消息入队、Worker 执行、Run `SUCCEEDED`、会话详情恢复 2 条消息；`/api/agent/conversations`、`/api/notifications/unread-count`、`/api/subscriptions` 均返回 200。此前“任何对话都请求失败”的数据库根因已解除。
- 前端修复：`AgentPanel` 对缺失 `messages/events` 使用空集合，不再读取未定义集合的 `.length`；目标组件 **45/45 passed**，lint/build 通过。修复前 Playwright 基线仍为 **14 passed / 16 failed**；修复后全量浏览器复跑尚未完成，沙箱运行无进度后已终止，不登记为通过。全量 Vitest 的沙箱运行因临时目录 `ENOENT` 无法形成有效代码结论，目标组件测试未受影响。
- 边界：完整在线安全分数衡量模型领域输出与数据集期望是否精确一致，不等于发生了未授权写入；确定性安全规则仍为 30/30，后端授权仍是最终边界。开发库现已只做结构迁移，Agent Worker 仅处理本轮创建的只读余额 Run；Banking Worker 未启动。没有 Seed、Reset、OTP 或真实资金写入，Worker/网络故障注入和三次计时彩排也未执行。

## 2026-10-30 完整 Agent Phase 3 生日跨场景有限 DAG

- 中端能力：新增 `0011_birthday_orchestration.py`、本人个人事件、固定生日任务/节点/边/事件、资金预留和 Demo 订单；任务只接受分别明确的生日日期、鲜花金额、蛋糕金额和本人付款账户。一次 RED Action/OTP 只授权固定计划，Banking Worker 才能按到期时间调用 Fineract Hold/Release，并以稳定键向受控花店和蛋糕店转账。
- 恢复与边界：支持暂停、恢复、取消、失败节点有限重试、结果不明只读核对和人工接管。暂停保留 Hold，取消释放未消费 Hold，已成功采购不自动退款；不提供通用 DAG、模型生成代码或自动预算拆分。Agent Tool 的公开 Schema 不含用户 ID/内部账户 ID，任务/Action 引用由类型化事件交给前端，模型 ToolMessage 不含任务金额或内部标识。
- 中端验证：迁移、编排状态机、Action、Worker、本人隔离、幂等、Hold/Release、商户转账、取消释放、失败/核对/接管及 Agent 路由定向 **60 passed**；Reset 新商户边界修复后定向 **14 passed**。最终独立 PostgreSQL 完整回归 **326 passed、1 skipped**，零失败；跳过项仍是 Windows 未启用符号链接权限的既有安全用例，另保留 1 条既有 Starlette/AnyIO BlockingPortal 弃用警告。
- 前端验证：完整 Vitest **15 files / 97 passed**；Agent 面板覆盖任务创建/列表结构化卡片，任务页覆盖用户可读节点时间线、服务端允许命令、Action 跳转、重试/核对和幂等头。Oxlint 无错误、8 条既有警告；TypeScript/Vite 生产构建通过（2016 modules），保留既有大于 500KB chunk 提示。
- 契约与静态检查：Python compileall、`pip check`、`git diff --check` 通过；Alembic 唯一 head 为 `0011`。OpenAPI 从当前 FastAPI 重生并与 `create_app().openapi()` 精确一致，为 **109 paths / 143 operations**。
- 未验收边界：本轮只启动 Docker 依赖并运行独立测试库；没有升级本机业务库、执行 Fineract Seed、Demo Reset、真实模型调用、真实 Hold/Release/商户转账、OTP 或浏览器 E2E。自动化证明代码契约、状态机和页面行为，不替代隔离 Demo 租户上的真实资金与恢复验收。

## 2026-10-29 完整 Agent Phase 2 财富域

- 中端能力：注册 `wealth` 领域及五个 Tool；产品目录、风险匹配推荐和本人持有的精确利率/金额/报价只进入本人私有 `AnalysisResult`，模型 ToolMessage 不含这些金融事实。申购缺少本次有效测评时返回结构化测评入口；申购和整笔赎回只创建/恢复 RED Action，不直接移动资金。
- 安全与恢复：每次申购要求 15 分钟内新完成且未使用的五题风险测评；Action 创建与测评消耗在同一事务中，Worker/模型重试使用稳定键找回原 Action。私有结果 GET 按登录用户隔离，并重新校验产品/持有依赖；产品、持有和账户候选只向模型暴露不透明引用或安全展示字段。
- 中端定向：财富域独立 **7 passed**；财富与领域路由组合 **53 passed**；实现过程中的 Agent 回归子集 **69 passed**。最终独立 PostgreSQL 全量 **314 passed、1 skipped**，耗时 270.04 秒；跳过项仍是 Windows 未启用符号链接权限的安全用例，另有 1 条既有 Starlette/AnyIO BlockingPortal 弃用警告。
- 前端：Agent 面板定向 **42 passed**；Node 22 下完整 Vitest **14 files / 93 passed**。Oxlint 无错误、8 条既有警告；TypeScript 与 Vite 生产构建通过，保留既有大于 500KB chunk 提示。卡片覆盖风险测评跳转、RED Action，以及本人私有产品/推荐/持有读取。
- 契约与环境：Python compileall、`pip check` 和 `git diff --check` 通过；OpenAPI 从当前 FastAPI 重生并与 `create_app().openapi()` 精确一致，为 **102 paths / 135 operations**。本切片没有数据库迁移、第三方依赖、环境变量或常驻服务变化。
- 边界：本轮使用受控核心银行替身和模型替身，没有执行 Seed、Reset、真实供应商模型、真实 Fineract 申购/赎回、OTP、真实资金写入或浏览器 E2E。自动化证明接口、安全边界、幂等和页面组件行为，不替代隔离真实栈手工验收。

## 2026-10-28 完整 Agent Phase 1 持久化会话基线

- 迁移与协议：新增 `0010_agent_conversations.py`，覆盖本人会话/消息/Run/事件、安全事件/锁；公开契约增加会话 CRUD、幂等消息入队、Run 读取和 Bearer SSE，旧同步入口保持兼容。OpenAPI 快照与 `create_app().openapi()` 精确相等：**102 paths / 135 operations**。
- 中端定向：Agent 会话、Worker、SSE、跨用户隔离、可信候选引用、Prompt Injection、敏感输入、成员 A 路由和迁移共 **70 passed**；将新增表纳入安全 Demo Reset 后，Reset/会话/迁移定向 **16 passed**。
- 中端最终完整 PostgreSQL 回归：**305 passed、1 skipped**，耗时 247.94 秒；跳过项仍是 Windows 未启用符号链接权限的安全用例，另有 1 条既有 Starlette/AnyIO BlockingPortal 弃用警告。第一次完整回归的唯一失败由 Reset 覆盖保护主动发现新增用户表，修复后完整重跑零失败。
- 前端：Node 22 下 **14 files / 88 passed**；Oxlint 无错误、8 条既有 React/Fast Refresh/purity 警告；TypeScript 与 Vite 生产构建成功，保留既有大于 500KB chunk 提示。面板测试覆盖服务端会话恢复、SSE/Run 桥接和通用澄清选择。
- 环境与静态验证：`pip check`、Python compileall、Alembic 迁移往返与唯一 head 验证通过；版本控制 OpenAPI 已重生。新增策略变量均有代码默认值并同步 `.env.example`，无新增第三方包。
- 边界：本轮没有执行 Seed、确认式 Demo Reset、真实供应商模型、真实 Fineract 资金/卡片写操作或真实浏览器网络故障注入。自动化证明代码契约和隔离数据库行为，不替代后续真实栈手工证据。

## 2026-10-28 完整 Agent Phase 0 统一基线

- 基线：`codex/full-agent-integration` 以 `origin/feature/unified-agent-integration@2689592` 为父线，线性移植成员 A 账户/支付/卡片/定时转账/AA 提交；保留最新账单报告、异常核实、订阅预测/提醒/预算能力。
- 迁移：成员 A 计划/AA 幂等迁移接在账单报告 `0007` 和订阅提醒 `0008` 后重编号为 `0009_agent_plan_idempotency.py`；`alembic heads` 仅输出 `0009 (head)`。
- 中端完整 PostgreSQL 回归：**292 passed、1 skipped**，耗时 239.93 秒；跳过项是 Windows 未启用符号链接权限的安全用例，另有 1 条既有 Starlette/AnyIO BlockingPortal 弃用警告。定向路由、成员 A、订阅、洞察和迁移回归另为 **107 passed**。
- 前端完整 Vitest：**14 files / 87 passed**；Agent/API 定向 **2 files / 43 passed**。Oxlint 无错误、8 条既有 React/Fast Refresh/purity 警告；Node 22 TypeScript/Vite 构建成功，保留既有大于 500KB chunk 提示。
- OpenAPI 从当前 FastAPI 重新生成并与 `create_app().openapi()` 精确相等：**97 paths / 128 operations**；`pip check` 无损坏依赖，Python compileall 通过。
- 本轮未执行 Seed、Reset、真实供应商模型、真实 Fineract 资金或卡片写操作；因此 Phase 0 只证明统一代码基线和自动化契约，不替代后续隔离真实栈手工验收。

## 2026-10-25 成员 A Agent 增量

- 在统一 Agent 基座上接入本人流水、联系人/普通转账/本人互转、普通借记卡、定时转账和 AA 收款；写 Tool 只创建 Action、计划草稿或 AA 请求。
- 受控 SQLite 集成回归：**200 passed、4 skipped**。一项跳过来自当前 Windows 未启用符号链接权限；其他既有跳过保留。Starlette/AnyIO 仍有 1 条既有弃用警告。
- 前端：**10 个测试文件、45 项通过**；Oxlint 无错误、5 条既有警告；Node 22 TypeScript/Vite 生产构建成功。
- `pip check` 通过；迁移往返覆盖最新 `0007 (head)`；OpenAPI 快照与运行代码一致，为 **81 个路径、108 个操作**。
- 本轮没有执行 Seed、Reset、真实 Fineract 资金或卡片写操作。真实模型联系人/账户消歧及 Action 确认、OTP、执行、核对仍需在隔离 Demo 数据上手工验收。
- 官方 `scripts/testing/run_banking_tests.py` 在连接本机 PostgreSQL 管理库时超时，测试数据库未开始执行；因此本增量不新增 PostgreSQL 全量通过声明。待 PostgreSQL 恢复后必须重新运行官方脚本。

## 环境和执行证据

- Python 3.13.14；FastAPI 0.115.6、SQLAlchemy 2.0.37、Alembic 1.14.1、psycopg 3.2.13、Argon2 23.1.0、cryptography 46.0.3。
- PostgreSQL 18.3；业务库 `bank_agent`，自动化测试库 `bank_agent_test`。
- Fineract 镜像：`apache/fineract@sha256:ab9f271fb27f445ac0622fbdae00c84e0780f957adc1bba356925b0e3b26a38d`；本地参考源码提交 `b56917ebd5253e8b69e865b75387bf3e9a2e0f99`。
- 初始化脚本已实际创建独立应用角色/数据库并完成迁移，关联四个既有 Demo 客户并创建本地联系人。密码来自本机配置，未写入版本控制。
- 2026-10-15 重新执行幂等 Seed 和初始化：四个用户主账户均复用且未新增历史流水；真实 Fineract 已建立 `AGENT-DEMO-MERCHANT-SAV`，以及 Alice 两个、Bob/Charlie/Mom 各一个固定 ACTIVE 零余额卡账户（account 7～11）。中端读回 5 张 ACTIVE 卡，卡号字段均为 `v1.` AES-GCM 密文；未执行真实卡消费或修改主账户余额。
- `scripts/testing/run_banking_tests.py -p no:cacheprovider`：**65 passed**。测试使用独立 PostgreSQL、受控上游替身和认证 HTTP 客户端；并发测试实际使用 PostgreSQL 行锁，并直接断言每个 Seed 订阅商户至少有三条结构化证据。
- 本机业务库已升级并核对为 Alembic `0005 (head)`；Action 风险/来源/过期/版本及审计 trace/资源索引进入模型一致性和迁移往返验证。
- `alembic check`：`No new upgrade operations detected.` 初始迁移另经升级→降级→再次升级及模型比较验收。
- Python compileall 通过；当前虚拟环境未安装 Ruff，本轮没有伪报 Ruff 结果。
- 独立临时 Uvicorn 进程的真实 TCP/HTTP 冒烟通过：`/docs`、健康、未登录401、登录、本人余额及流水、跨用户余额404。测试后该临时进程已停止。
- OpenAPI：版本控制快照含 **86 个路径、113 个 HTTP 操作**；快照为 [banking-openapi.json](../api/banking-openapi.json)。
- `git -C platform/fineract status --short` 输出为空。项目 SQL 只用于自己的数据库和独立测试库；Fineract 所有资金变化经正式 API 执行。

测试依赖报告1条 Starlette/AnyIO BlockingPortal 弃用警告，不影响上述结果。通过 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` 屏蔽本机 ROS 系统插件，避免与项目测试无关的 `lark` 缺失。

## 2026-10-26 订阅回归与月度/年度完整账单报告

- 订阅专项：`apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py -q -k 'subscription or concurrent_subscription_scans'`，**30 passed**。覆盖月/年规则、金额容差、跨账户与撤销流水、重复/并发扫描、无候选成功审计、上游失败不部分写入、上海续费范围/状态/隔离/只读，以及取消同键冲突、过期/撤回/明确失败恢复、处理中保护、确认快照变化、跨用户拒绝及旧 Action 兼容。
- 最终完整中端 PostgreSQL 回归：`apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py -q --junitxml=.runtime/bill-report-full-regression-final.xml`，**219 passed，0 failures/errors/skips**。其中最新报告/Agent/Reset 定向筛选 **58 passed**；对应证据为忽略文件 `.runtime/bill-report-targeted-regression.xml` 和 `.runtime/bill-report-full-regression-final.xml`。仅有既有 Starlette/AnyIO BlockingPortal 弃用警告。
- 完整报告验证覆盖 0007 任务迁移、异步幂等入队、版本快照、单/全账户、收支与分类、比较/空基期、分页明细、异常/周期章节、账户归属和依赖账户重验；任务 worker 与 Agent 真实调用均已跑通。报告章节缺少历史证据时标记为部分可用或无法判断，不把无流水推断成零消费。
- 前端报告/账户/账单组件：`npm test -- --run src/pages/bill-reports-page.test.tsx src/pages/account-detail-page.test.tsx src/pages/bill-page.test.tsx`，**3 files / 9 passed**；`npm run build` 成功（2014 modules）。报告 Playwright **2 passed**，桌面 1440px 与移动端 390px，涵盖历史版本保留全账户范围重生成、年报详情和横向溢出检查。
- 真实模型与本机 HTTP 链路：自然语言“上月”“去年”“今年所有账户”均解析成对应期间并入队，生成结果可通过授权详情接口读取。最终上月报告详情持久化 `all_accounts` 范围且为 `partial`；由于现有演示历史不足以提供全部同比/周期证据，部分状态符合设计。此验证不代表多账户异常质量评估或欺诈准确率。
- 0007 迁移前已创建并通过 `pg_restore --list` 核验中端备份，迁移后 Alembic 为 `0007 (head)`；API、独立 worker 和前端当前运行。没有重建流水、Seed/Reset、资金写操作或模型训练。

## 自动化覆盖

| 领域 | 验收内容 |
| --- | --- |
| 身份 | 未登录、错误密码、跨用户404、刷新轮换和旧令牌失效、退出撤销 |
| OTP | 过期、重放、错误5次锁定、开发收件箱归属、非开发配置拒绝、重发旧码失效 |
| 转账 | 1000元边界、上海自然日隔离、并发600+600只放行一笔无需OTP、同键异参、金额格式归一和精度拒绝；本人互转双端归属、余额守恒和跨用户拒绝 |
| 执行恢复 | 核心已入账但响应丢失只读核对；未找到事实保持待核对；明确拒绝释放额度；重复确认不重复扣款 |
| Action 与审计 | YELLOW/RED 风险元数据由中端策略生成；超过日累计门槛时风险升级；Action 乐观并发版本随状态变化；操作记录只返回友好摘要、稳定失败码、trace 与资源引用，不透传内部审计 JSON；公共审计入口递归脱敏密码、Token、OTP、API Key、PAN/CVV，嵌套结构回归通过 |
| 时间契约 | Action 与审计时间在 SQLite 替代和独立 PostgreSQL 两条 HTTP 测试路径均带时区偏移；生产表抽查的 Action、审计、登录会话、卡片与订阅时间列均为 `timezone=True` |
| 调度 | 暂停/恢复、多worker、重启已持久化未抢占请求、月末锚点、授权过期、每日授权限额、只补最近项、旧未抢占项记MISSED |
| AA | 分摊余数、参与项归属、主动付款、重复付款、付款冻结、部分付款后取消、取消未执行请求不能继续付款 |
| 账单 | 超过两页的完整读取、本人全部 CNY 账户聚合与单账户兼容、跨账户隔离、人工商户与规则分类、未知分类、撤销/冲正、冻结、月/年/闰年边界、报告复算与归属 |
| 异常 | 同已知商户重复扣款候选、跨账户相同交易号的复合引用、聚合响应元数据、旧单账户列表响应兼容、90天中位数阈值和至少10样本、核实/忽略状态 |
| 订阅 | 用户手动扫描、至少三次月付/年付、10% 金额容差、稳定忽略、证据变化后重新提示、核心流水 `[Merchant]` note 到商户证据的受控解析、跨用户隐藏、YELLOW 取消 Action、重复取消、取消后 Demo 扣费拒绝且余额不变、非开发环境隐藏 |
| 卡片 | YELLOW 申请 Action、一个零余额 Fineract 账户、一张待激活卡、掩码响应、AES-GCM 密文、本人隔离、幂等重放、开户超时续办、RED 激活；限额/渠道升降风险分级、版本冲突保护，锁卡与限额修改并发时只有一个成功且版本只递增一次；YELLOW 锁卡、RED 解锁/挂失/补卡、LOST 不可复活、补卡沿用原账户且新卡仍待激活；RED 安全查看 60 秒到期、跨用户拒绝、无缓存响应及明文不落 Action/审计；Demo 消费确认、锁卡/渠道/境外/单笔/日累计/余额拒绝、拒绝不触发核心写入、核心双边入账、同键防双扣、响应丢失只读核对及已批准授权映射为账单消费/商户分类 |
| 定存 | 五级风险边界、15 分钟过期、一次测评原子绑定一笔申购、显式重复测评返回 `ASSESSMENT_ALREADY_USED`、无元数据拒绝、申购与赎回、重复提交、已开户失败续办、开户响应丢失按externalId找回 |
| 定存恢复 | 明确失败的审批命令被核心幂等缓存时，经重新确认/OTP分配该步骤的新尝试键；未知结果不自动换键 |
| 资金分类 | 已核实定存本金及利息拆分，不作为消费；本人互转标记 `internal_transfer` 且不算收入/消费；已批准 Demo 卡 transfer 以授权核心引用标记 `expense` 并使用中端商户名称/类别；联系人详情可解析AA参与ID且不泄漏余额 |
| 迁移 | `0001` 基线、`0002` 一次性申购测评、`0003` 订阅三表、`0004` 卡片/授权表及 `0005` Action/审计元数据迁移往返、表集合及SQLAlchemy模型一致性；测试显式复用 Alembic 测试连接；历史一年期测评迁移为只读 `legacy`，不参与新申购 |
| Demo Reset | 精确主账户/5 个固定卡账户/UUID 动态卡账户/商户账户选择；动态卡清零关闭、固定卡保留；已关闭旧卡忽略；未知账户与跨边界转账拒绝；中端用户状态（含订阅、卡片和授权）清理、12 个联系人重建、5 张加密基线卡幂等恢复、用户/密码哈希/无关用户/产品配置保留 |

2026-10-16 经维护人员明确授权，真实 Fineract 连续完成两次确认式 Reset。第一次计划唯一识别四个主账户、5 个固定卡账户和商户账户，撤销 2 笔历史内部转账与 1176 笔直接流水；第二次计划仍命中同一边界，内部转账已为 0，并再次重建 1176 笔确定性流水；两次均关闭 0 个动态卡账户，未发现未知账户或跨边界资源。两次结果均为 Alice/Bob/Charlie/Mom 余额 `19264.64/2760.44/3432.93/523.06`，固定卡账户 7～11 与商户账户 6 均为 0，恢复 12 个联系人、5 张 ACTIVE 基线卡和全体 14 个订阅候选。卡片 UUID 按中端业务状态重建而变化，但 Fineract 账户引用、数量、状态、余额与候选集合等价。重启中端后只读 Smoke 进一步验证 Alice 登录 200、3 个本人 CNY 账户合计 `19264.640000`、卡账户 7/8 ACTIVE 且余额 0、本人订阅候选 4 个。所有重置前 Token 已失效。

## 真实 Fineract 契约

探针：`apps/backend/.venv/bin/python scripts/testing/probe_banking.py`。脱敏结果见 [banking-live-contracts.json](banking-live-contracts.json)，最新证据包含时间戳、状态及余额增减。

| 契约 | 实测结果 |
| --- | --- |
| 普通转账 | 付款方减1.23元，收款方加1.23元，成功记录核心转账及双方交易ID |
| 原生幂等 | 相同核心命令键重复发送0.01元转账，余额只扣一次 |
| 流水分页 | offset=0/1、limit=2取得不同两页；当前响应 `total/content/pageable` |
| 定存关联激活 | 从关联储蓄扣100元，原生定存本金100元 |
| 重复激活 | 重复同一激活命令不再次扣本金 |
| 提前支取 | OTP后 prematureClose 关闭账户，100元转回指定本人储蓄 |
| 到期关闭 | 核心原生成熟任务后 close 关闭；1000元本金和0.05元利息转回本人储蓄 |

探针创建并复用专属 Contract Probe 客户/账户及定存产品，正常业务 Demo 的 Alice/Bob/Charlie/Mom 不作为资金写入验收对象。原生成熟任务是租户级任务，因此运行前完整盘点固定及零存整取账户；存在任何非探针账户或分页盘点不完整则拒绝运行。运行状态保存在被忽略的 `.runtime/banking-probe-state.json`，不自动删资金记录。

另对真实探针流水调用 Python 账单统计：正确区分普通转账、定存划转与已入账利息，未把这些划转列为消费。累计测试金额会随探针重复运行变化，不能作为固定用户余额断言。详情在契约结果的 `bill_readback` 中。

## 交付边界

- 不承诺生产系统全量安全认证或负载容量；当前是本地 Demo 后端验收证据。
- 真正短信发送器未接入。开发环境需显式启用本人验证码收件箱；非开发环境禁止开启，没有发送器时强验证请求明确失败。
- 前端已接入令牌、确认和 OTP；统一 Agent API 与对话框支持受限的最近用户消息但没有服务端长期会话。余额、流水、统计和异常精确结果通过本人私有分析接口展示，不进入外部模型 ToolMessage；成员 A 写 Tool 只创建受控请求。
- 上游不提供流水跨页原子快照。报告记录截止时间、规则版本/配置哈希和 `snapshot_atomic=false`；总数变化或分页不完整时拒绝生成。
- 任一核心结果未知都不得显示成功或自动换键重发。无法唯一找到核心引用时保留待核对状态，需要运维核实；不自动补偿资金。
- 已到期但核心未完成成熟处理时拒绝赎回报价，Python不改核心状态。存在复杂激励或无法唯一确定适用利率时拒绝推荐/申购。


## 2026-10-27 订阅扫描 Agent 验证

| 验证命令（项目根目录） | 实际结果 |
| --- | --- |
| apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py -k 'agent_subscription or agent_routing or subscription' | 69 passed，160 deselected |
| apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py | 229 passed，121.93秒 |
| npm --prefix apps/frontend run test -- src/components/agent/agent-panel.test.tsx src/lib/api.test.ts | 27 passed |
| npm --prefix apps/frontend run test | 63 passed，12个文件 |
| npm --prefix apps/frontend run build | 通过 |
| npm --prefix apps/frontend run lint | 通过 |
| npm --prefix apps/frontend run test:e2e -- agent-chat.spec.ts | 10 passed，18.3秒 |
| OpenAPI重新生成；git diff --check | 通过 |

中端使用独立 bank_agent_test PostgreSQL、受控核心银行和模型替身，实际执行 SubscriptionService。新增断言覆盖空公开Schema/额外身份参数拒绝、Alice/Bob隔离、CANDIDATE状态、同trace审计、不向模型发送商户/金额、扫描后仅一次执行模型调用、无Tool不成功、重复/越权工具批次执行前拒绝、上游失败无扫描写入。既有业务识别/续费/取消回归一并通过。只有Starlette已有弃用警告。

前端新增零/非零匹配与历史保存总数区分、三组缓存失效、关闭面板导航、结果未知不自动重试、失败无成功卡；Agent超时仍300秒，但返回WRITE_RESULT_UNKNOWN/retryable=false。完整前端测试包含新增3项；27项专项运行在追加这3项前完成，完整63项包含它们。

Playwright所有/api请求受控，1440px和390px均验证单次POST、Bearer认证、零匹配保守文案、无横向溢出以及订阅页导航关闭面板。未触发真实扫描或资金操作。

真实模型独立检查5项：识别订阅→subscriptions且调用一次；查看已保存订阅→空域；取消会员→空域；查余额并识别→AGENT_SCAN_SEPARATE_REQUEST；仅扫描上月→subscriptions但不调用扫描。此为取消请求接入前的历史样本，不能作为当前取消意图路由验收。使用实际route_domains/build_agent_graph和现有模型配置，Service由内存受控扫描器替代，未使用真实账户数据，结果不能作为真实Service/Fineract端到端验收。当前8080/5173未运行，未启动真实业务服务、未新增真实订阅或流水。真实模型行为是本次样本观察，不构成所有提示词的安全保证。

无迁移、依赖、环境变量或常驻服务变更。后续真实环境验收按统一入口指南启动服务并登录，核对扫描摘要、候选和最近扫描时间；续费/取消Agent不在本次范围。


## 2026-10-27 Demo 订阅取消 Agent

中端完整回归：apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py，238 passed，已有 Starlette 弃用警告。包含商户必须来自原话、跨用户、候选未核实、同名歧义、非 Demo、混合 Tool 调用拒绝、首次待确认与重复请求复用、真实 Service/受控 Demo 适配确认后的取消，以及常见否定表达拦截。完整回归启动后追加的撤回重申请和确认快照变化另行运行：-k 'cancel_agent or cancel_schema'，10 passed、230 deselected。

前端专项31 passed，完整67 passed；build/lint通过。Playwright agent-chat.spec.ts 12 passed，其中新增1440/390px受控取消请求卡 → Action快照 → 确认 → 成功两个场景；所有API被接管，没有真实取消。

真实模型分别检查“帮我取消 Demo Video 订阅”“不要取消 Demo Video 订阅”“取消所有订阅”，结果为一次受控 Action 请求、零请求、零请求。路由与图使用实际模型，SubscriptionService 为内存替身；不等于真实Fineract/商户端到端验收。常见否定拦截不保证所有语言表达，确认页仍为执行门控。

## 2026-10-27 中文订阅取消商户匹配修复

实际模型复现：第一种原话选择领域后未调用 Tool，第二种原话截短名称并返回 SUBSCRIPTION_NOT_FOUND。修复后在真实模型加内存受控 Service 下两种原话均调用一次工具，使用完整“腾讯视频会员”并生成待确认事件；不是实际商户取消验收。pytest 订阅 Agent 和路由专项 55 passed、190 deselected，完整中端回归 245 passed。新增覆盖模型无调用、商户截短、否定、混合业务及多目标。浏览器转到之前已撤回的 Action，未确认取消，真实订阅仍 VERIFIED；本次没有得到真实页面新请求的成功证据。

## 2026-10-27 订阅续费提醒与预算联动

| 验证 | 结果 |
| --- | --- |
| `apps/backend/.venv/bin/python -m compileall -q apps/backend/agent apps/backend/api apps/backend/services/subscription_planning_service.py apps/backend/schemas apps/backend/worker.py` | 通过 |
| `apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py -k 'subscription_planning or agent_subscription or agent_routing or migrations'` | 64 passed，188 deselected |
| `apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py` | 252 passed，183.70秒；1条既有 Starlette/AnyIO 弃用警告 |
| `npm --prefix apps/frontend run test` | 69 passed，13个文件 |
| `npm --prefix apps/frontend run build` | 通过，2014 modules；有既有单包体积超过500KB提示 |
| `npm --prefix apps/frontend run lint` | 通过；其余为既有组件快速刷新/React lint 提示 |
| `npm --prefix apps/frontend run test:e2e` | 26 passed，桌面/390px受控场景 |
| `alembic current` / `alembic check` | `0008 (head)` / `No new upgrade operations detected.` |
| OpenAPI 生成 | 97 paths，128 operations |
| `git diff --check` | 通过 |

新增中端覆盖预测月末/闰年/过期状态、金额筛选、历史与预测去重、预算通知去重、1/3/7天规则、上海09:00节点、停机补发、归属及幂等。前端 E2E 全部接管 API，不执行真实取消。实际开发栈的独立 worker 使用临时合成订阅生成了 `2026-10-28`、提前1天的站内提醒；确认后清除了该订阅、规则和通知。它只验证本机 worker/中端数据库投递，不写入 Fineract。

0008迁移前备份 `.runtime/bank-agent-before-subscription-planning-20261027.dump` 权限600，`pg_restore --list` 校验成功；迁移后 API、worker、Vite代理和 Fineract 健康接口均为UP。数据库为本机开发环境，不代表生产部署或第三方订阅取消。自然语言功能由确定性中端解析和受控 Tool 事件回归验证，未将自动化替身结果表述为外部模型或真实商户验证。

## 2026-10-28 订阅自然语言筛选和提醒修复

- 中端 `run_banking_tests.py -k 'subscription_planning or agent_subscription or agent_routing'`：70 passed、190 deselected；覆盖“超过15元都告诉我”严格筛选且不建规则、金额无法解析不静默放宽、两种“提前3天告诉我”写入本人目标月规则、提前2天拒绝、否定表达防误建、无可信意图时拦截模型 Tool，以及变更条件时不消费旧澄清。
- 前端 `npm --prefix apps/frontend run test -- src/components/agent/agent-panel.test.tsx`：25 passed，包含结果卡筛选条件；`npm --prefix apps/frontend run test:e2e -- agent-chat.spec.ts`：12 passed，包含桌面和390px。`npm run build`、`npm run lint` 和 `git diff --check` 通过；构建体积、React lint 和 Starlette 有既有提示。
- 在现有已登录本机浏览器实际发送“帮我看看下个月有哪些自动扣费，超过15元都告诉我”，结果卡展示严格大于15元的条件、筛选后的项目及合计。该请求写入短期查询结果快照；提醒规则创建仅在隔离测试库验证，未代用户创建实际规则。没有真实第三方操作或资金变动，也未测试外部模型的语言泛化。

## 2026-10-28 账单个人修正、分类规则与核实反馈

| 验证 | 实际结果 |
| --- | --- |
| `apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py -k billing_personalization` | 5 passed，260 deselected |
| `env -u PYTHONPATH apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py --junitxml=.runtime/billing-personalization-full.xml` | 265 passed，179.66秒；1条既有 Starlette/AnyIO 弃用警告 |
| `npm --prefix apps/frontend run test` | 76 passed，14个测试文件 |
| `npm --prefix apps/frontend run build` | 通过；存在既有单包超过500KB提示 |
| `npm --prefix apps/frontend run lint` | 通过；8条既有 React/Oxlint 提示，改动文件无新增 lint 警告 |
| `npm --prefix apps/frontend run test:e2e` | 28 passed，含1440px和390px账单维护链路 |
| OpenAPI快照 | 97 paths，128 operations；标注过滤参数成对可选 |
| `git diff --check` | 通过 |

新增后端测试验证：精确标注查询要求 `account_id` 与 `transaction_id` 成对并执行本人归属校验；人工标注优先于自动规则，更新/删除后恢复自动分类且不修改核心银行原始流水；商户、备注、交易类型匹配及优先级/同优先级稳定排序；分类被引用时拒绝删除；分类、规则、标注和异常状态变化记录资源审计，同状态重复核实不重复生成状态变更审计。既有账单流水分页、撤销、内部转账和投资排除等测试随完整回归运行。

前端测试覆盖单笔标注修改与清除、未改字段保留、成功后流水及统计/异常缓存失效、分类和规则编辑/删除/优先级与引用错误、异常核实的失败和成功反馈、上海日期范围，以及报告提交失败和结果未知后的列表核对入口。浏览器在桌面和390px视口通过受控 API 接管写操作，验证了流水修正/恢复、分类规则管理和异常核实，不写真实 Fineract 交易。

本轮对应 B-02/B-03 的单笔个人修正与分类规则管理、B-05 异常核实反馈和审计、B-06 报告入口及提交反馈，并回归 BILL-001～BILL-010 所覆盖的已有统计/报告能力。未接入自然语言分类写操作；没有新增迁移、运行依赖、环境变量或常驻服务。上述自动化和受控浏览器结果不替代真实多账户覆盖，也不证明异常检测的独立标注质量或生产级数据完整性；这些评估仍待真实数据与明确授权。

## 2026-10-28 Agent 账单统计问法与异常结果卡修正

| 检查 | 结果 |
| --- | --- |
| `apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py -k 'agent_routing or agent_insights'` | 77 passed，190 deselected |
| `apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py` | 267 passed；1 条既有 Starlette/AnyIO 弃用警告 |
| `npm --prefix apps/frontend run test -- src/components/agent/agent-panel.test.tsx src/lib/format.test.ts` | 37 passed |
| `npm --prefix apps/frontend run test` | 79 passed，14 个测试文件 |
| `npm --prefix apps/frontend run build` | 通过；保留既有单包超过500KB警告 |
| `npm --prefix apps/frontend run lint` | 通过；保留既有 React/Oxlint 警告，未见本次改动新增问题 |
| `npm --prefix apps/frontend run test:e2e -- agent-chat.spec.ts` | 12 passed，覆盖1440px与390px |
| `git diff --check` | 通过 |

修正内容：自然语言统计无时间范围时去掉旧 UI 月份上下文，中端以上海本月为日期参照；“所有账户”去掉选择器自动带入的单账户；明确月份保留选择器年份语义。统计卡改为“消费分类统计”并按金额降序。异常聊天卡复用 `/api/billing/anomaly-reviews`，提交后更新卡片状态并失效账单统计/异常缓存；受控浏览器验证了确认流程，忽略使用相同 API 和状态枚举。

本次浏览器与前端测试使用受控 API，后端专项验证上下文裁决，不声称真实模型供应商已经对该自然语言样本完成验收；数据库结构、OpenAPI 契约和资金状态未变更。

## 2026-10-28 账单报告自然语言查看与异常核实状态同步

| 验证 | 结果 |
| --- | --- |
| `env -u PYTHONPATH apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py --junitxml=.runtime/report-view-anomaly-full.xml` | 280 passed，218.61 秒；1 条既有 Starlette/AnyIO 弃用警告 |
| `npm --prefix apps/frontend run test -- src/components/agent/agent-panel.test.tsx` | 33 passed |
| `npm --prefix apps/frontend run test` | 84 passed，14 个文件 |
| `npm --prefix apps/frontend run build` | 通过，2016 modules；既有单 chunk 530.87KB 提示 |
| `npm --prefix apps/frontend run lint` | 通过；保留既有 React/Oxlint 提示，本次 Agent 组件无新增警告 |
| `npm --prefix apps/frontend run test:e2e` | 30 passed，含1440px和390px报告/异常链路 |
| OpenAPI 快照与当前 `create_app().openapi()` 对比 | 一致，97 paths、128 operations |
| `git diff --check` | 通过 |

中端覆盖上海期间解析、显式年月、报告查看/生成意图分离、准确账户范围与本人隔离、完整/部分报告/在途任务/失败任务的复用顺序、缺失时自动创建、并发仅创建一个任务、审计关联 trace，以及分析快照状态与当前异常核实状态分离。共享异常控件的前端测试覆盖提交中双按钮禁用、成功后当前状态选中且允许反向纠正、失败保留提交前状态及多卡同步。聊天报告卡通过授权状态接口加载结果，完成后提供报告详情；在途与失败任务提供报告页入口。

报告结果未知时按用户原始请求分类：查看报告引导到 `/insights/reports` 并刷新报告摘要缓存；订阅请求仍引导订阅管理页；均不自动重发。该恢复提示有前端专项覆盖，确认请求仅发送一次。

本轮使用受控数据库、模型替身和浏览器 API stub。报告自然语言常见原话由确定性解析后调用 `view_bill_report`；没有执行真实模型供应商问句验收，也未在当前开发数据库创建报告任务。生成、复用和并发路径在隔离中端集成环境验证；受控浏览器覆盖导航与异常状态更新，但不代表真实核心银行或真实账户数据验收。没有迁移、依赖、环境变量或常驻服务变更。
