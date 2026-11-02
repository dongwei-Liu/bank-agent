# Bank Agent 非 Agent 前端与中端需求规格

> 文档状态：需求基线 V1，待按本文逐阶段实现与验收。
> 最近更新：2026-10-16。
> 适用范围：`apps/frontend` React Web App、`apps/backend` Python/FastAPI 中端及其 `bank_agent` PostgreSQL 数据库、通过中端访问的 Apache Fineract。
> 明确排除：LangGraph、LLM、Prompt、Tool、对话协议、Agent 事件及 Agent 验收。现有 Agent 入口可以保留，但不得成为本文任何业务功能的前置依赖。

## 1. 文档目的与优先级

本文定义比赛版普通银行 Web App 的用户需求、页面、业务规则、中端接口、数据归属、失败行为和验收标准。开发人员不得用页面 Mock、前端常量或模型回答替代本文指定的事实来源。

文档优先级如下：

1. `AGENTS.md` 规定协作、文档和部署治理；
2. `docs/project/master-plan.md` 规定项目全局目标、阶段与实时状态；
3. 本文是非 Agent 前端与中端业务需求的事实来源；
4. `docs/design/frontend-page-and-feature-design.md` 负责页面设计；
5. `docs/api/banking-backend.md` 和 `docs/api/banking-openapi.json` 只描述当前已经实现的接口事实。

本文的目标状态不得提前写入 OpenAPI 或“已实现”API 文档。只有代码、迁移和验证完成后，才能同步这些事实文档。

## 2. 范围、参与者与术语

### 2.1 本阶段范围

| 场景 | 本阶段要求 | 状态定义 |
| --- | --- | --- |
| 账户基础 | 登录、本人账户、余额、流水、多账户汇总、本人账户互转 | 已实现并兼容 |
| 智能转账 | 联系人、普通转账、定时转账、AA、确认、OTP、恢复 | 已实现并兼容 |
| 账单分析 | 跨账户统计、分类、异常核实、实时月报和年报 | 已实现并兼容；真实栈页面读回待手工彩排 |
| 订阅/代扣 | 周期扣费识别、核实、三天提醒、Demo 取消 | 已实现并兼容 |
| 理财操作 | 原生定存、比较、每次申购重新测评、申购、持有、整笔赎回 | 已实现并兼容 |
| 卡片管理 | 多张普通借记卡、开户、激活、额度、渠道、锁卡、挂失、补卡、Demo 商户消费 | 已实现并回归；5 张预置卡及核心零余额账户已在本机建立，真实消费彩排待完成 |
| 跨场景联动 | 生日资金预留、购物 DAG、任务接管 | 本阶段不做，留待 Agent 阶段 |

### 2.2 使用者

- 普通个人客户：唯一正式用户角色，可操作本人资源；
- 内部初始化/维护人员：通过脚本或已有管理员 API 准备演示数据，不建设管理后台；
- Demo 商户：仅用于可控地验证卡片交易和订阅取消，不是真实外部机构；
- 系统 worker：执行到期计划、恢复任务和后台识别，不拥有超出用户授权的权限。

### 2.3 统一术语

- 前端：`apps/frontend` 中的 React Web App；
- 中端：`apps/backend` 中的 FastAPI Banking Service 及其自有 PostgreSQL 数据库；
- 核心银行后端：Apache Fineract 及其独立数据库；
- Action：中端对写操作的持久化安全状态机，不作为用户菜单名称；
- Demo 卡/商户：业务流程为自研模拟，但成功资金入账必须进入 Fineract；
- 账户：Fineract 中的真实演示账户；中端不得维护第二套账户余额。

### 2.4 状态标签

本文使用以下标签：

- `已实现并兼容`：现有路径和语义继续作为基线；
- `需要兼容调整`：保留路径和已有字段，以可选字段或新增端点扩展；
- `需要新增`：当前中端没有对应实现；
- `本阶段不做`：不进入当前开发和验收。

## 3. 当前系统基线

### 3.1 现有接口盘点

以版本控制中的 `docs/api/banking-openapi.json` 为准，排除 Agent 消息与私有分析读取接口后，现有非 Agent 契约共有 **84 个路径、111 个 HTTP 操作**。

| 接口组 | 路径数 | 操作数 | 主要路径 | 当前结论 |
| --- | ---: | ---: | --- | --- |
| 健康与认证 | 5 | 5 | `/api/health`、`/api/auth/*`、`/api/me` | 已实现并兼容 |
| 账户与流水 | 6 | 6 | `/api/accounts*` | 已实现并兼容 |
| 联系人 | 2 | 5 | `/api/recipients*` | 已实现并兼容 |
| 转账 | 3 | 4 | `/api/transfers*`、`/api/internal-transfers` | 普通转账与本人互转均已实现 |
| Action | 9 | 9 | `/api/actions*` | 已实现；风险/来源/过期/并发版本和审计资源索引已补齐 |
| 定时转账 | 6 | 9 | `/api/transfer-schedules*` | 已实现并兼容 |
| AA 收款 | 3 | 6 | `/api/aa-collections*` | 已实现并兼容 |
| 账单与语义 | 15 | 26 | categories、rules、annotations、billing、bill-reports | 全账户与单账户汇总、独立实时月/年页面及后台报告 API 已接入 |
| 风险与定存 | 15 | 18 | risk-assessments、investments | 已实现；新申购使用 15 分钟一次性测评 |
| 订阅与 Demo 取消 | 8 | 8 | subscriptions、demo/subscriptions | 已实现；仅手动扫描，统一上海日期续费查询，取消明确限定 Demo 商户 |
| 普通借记卡与 Demo 商户 | 12 | 15 | cards、activate、reveal、limits、状态操作、card transactions、demo merchants | 已实现；Demo 端点仅 development 开放 |

现有接口的完整参数和响应继续以 OpenAPI 快照及 `docs/api/banking-backend.md` 为准。本文不复制所有 schema，而是定义兼容边界和目标增量。

### 3.2 现有数据表

当前中端数据库已有：`users`、`login_sessions`、`recipients`、`actions`、`daily_usage`、`transfer_schedules`、`schedule_runs`、`aa_collections`、`aa_shares`、`categories`、`classification_rules`、`transaction_annotations`、`bill_reports`、`anomaly_reviews`、`risk_assessments`、`product_metadata`、`merchants`、`subscriptions`、`subscription_occurrences`、`bank_cards`、`card_authorizations`、`audit_events`。`risk_assessments` 已由 Alembic `0002` 增加申购用途、使用时间和绑定 Action；订阅三表由 `0003` 建立；卡片与授权表由 `0004` 建立；Action 与审计查询字段由 `0005` 兼容补齐。

卡片和卡授权已有正式数据表；Demo 消费会持久化 `PENDING/EXECUTING/APPROVED/DECLINED` 授权、拒绝原因及核心转账/双方流水引用。商户、订阅和订阅扣费证据已持久化，不使用前端数组作为事实来源。

### 3.3 已知缺口

- 计划任务双 worker 的既有 PostgreSQL 死锁已修复并通过完整集成回归；后续新增写操作仍必须复用用户锁与 Action 行刷新约定；
- Demo Reset 已扩展到固定卡账户、UUID 动态卡账户、Demo 商户、卡授权和订阅状态：固定账户清零复用、动态账户清零关闭，随后恢复 5 张加密基线卡并重新扫描带结构化商户证据的确定性流水；自动化与本机只读计划已通过，仍需维护人员确认式真实写入并重复执行验证等价性；
- 账单统计与异常接口已允许省略 `account_id` 并严格聚合当前用户全部 CNY 储蓄账户；显式单账户调用保持旧响应兼容；
- `bill-reports` 生成持久快照，但新前端主流程应实时查看；
- 卡片中端已实现申请、本人列表/详情、别名、Fineract 零余额自动开户、OTP 激活、限额/渠道风险分级、锁定/解锁、永久挂失与沿用原账户补卡、OTP 后 60 秒无缓存安全查看，以及受控 Demo 商户确认、拒绝、真实核心入账与响应丢失核对；
- `/api/tasks` 只有前端预留契约，本阶段不交付。

## 4. 全局产品与交互需求

### 4.1 信息架构

| ID | 需求 | 页面/组件 | 状态 |
| --- | --- | --- | --- |
| NAV-001 | 一级导航固定为首页、账户、支付、洞察、我的 | 全局底栏 | 已实现并兼容 |
| NAV-002 | 卡片作为账户页的二级页签，并提供首页快捷入口 | `/accounts`、`/cards` | 已实现并回归 |
| NAV-003 | 财富从首页快捷入口进入独立页面，不新增一级导航 | `/wealth` | 已实现并兼容 |
| NAV-004 | 订阅从洞察页摘要进入独立页面 | `/insights`、`/subscriptions` | 已实现并兼容 |
| NAV-005 | Demo 商户为独立且醒目标注的演示页面，不进入银行一级导航 | `/demo/merchant` | 已实现并回归 |
| NAV-006 | 现有 Agent 悬浮入口可以保留，但不纳入本文验收 | 全局 Agent Drawer | 本阶段不做 |

### 4.2 页面通用状态

| ID | 需求 | 状态 |
| --- | --- | --- |
| UI-001 | 所有业务页面提供加载中、空数据、无权限、请求校验失败、服务不可用、可重试错误、不可重试错误和手动刷新状态 | 主要读取页面已统一；本轮补齐空流水、支付依赖、空联系人和操作记录重试，剩余复杂写表单逐页验收后再标完整完成 |
| UI-002 | HTTP 401 显示为登录失效，不得显示为“后端离线” | 已实现并兼容 |
| UI-003 | Fineract 失败时不得回退到固定余额、固定账户或固定成功结果 | 已实现并兼容 |
| UI-004 | 处理中页面统一每 2 秒短轮询一次，连续自动轮询最长 60 秒；离开页面或进入终态后停止，不在各业务页散落独立参数 | 已在通用 Action 页实现并通过组件/构建回归 |
| UI-005 | 60 秒后仍未终态时显示“仍在处理中”，只保留手动刷新和结果核对，不自动创建新请求 | 已在通用 Action 页实现并通过组件/构建回归 |

### 4.3 金额、时间和隐私

| ID | 需求 | 状态 |
| --- | --- | --- |
| DAT-001 | API 金额使用十进制字符串，中端内部使用 `Decimal`，禁止 float | 已实现并兼容 |
| DAT-002 | 币种首版固定 CNY，但金额响应仍携带币种 | 已实现并兼容 |
| DAT-003 | 时间使用带时区的 ISO 8601，中端统一保存带时区时间 | 已实现并兼容：PostgreSQL 使用带时区列；统一 JSON 序列化会为驱动返回的无时区时间补 UTC 偏移，并有 SQLite/PostgreSQL HTTP 回归断言 |
| DAT-004 | 页面默认掩码账户号和卡号 | 已实现并兼容：账户号统一经 `formatAccountNo` 只展示尾号，卡号接口及页面只默认展示掩码值；请求仍使用内部账户/卡片 ID |
| DAT-005 | 密码、Token、OTP、完整卡号、加密密钥不得进入日志、审计 data、URL 或 Git | 需要兼容调整 |
| DAT-006 | Fineract 原始大对象不得直接透传给前端 | 已实现并兼容 |

## 5. 身份、会话与“我的”

| ID | 需求 | 对应接口 | 状态 | 验收 |
| --- | --- | --- | --- | --- |
| AUTH-001 | 用户由初始化脚本预置，不提供注册和找回密码 | init 脚本、`POST /api/auth/login` | 已实现并兼容 | 页面没有不可用的注册/找回入口 |
| AUTH-002 | 登录成功签发 access/refresh token，前端使用 `sessionStorage` 保存 | auth login/refresh | 已实现并兼容 | 刷新页面可恢复；关闭标签页后清理 |
| AUTH-003 | 并发 401 只触发一次刷新；刷新失败清理会话并回登录页 | 统一 API Client | 已实现并兼容 | 并发请求不产生刷新风暴 |
| AUTH-004 | 连续密码失败进入现有登录锁定逻辑 | login | 已实现并兼容 | 返回明确 429/锁定提示 |
| AUTH-005 | `/me` 只返回当前 Token 用户，不能由客户端指定用户 ID | `GET /api/me` | 已实现并兼容 | Alice 不能读取 Bob 身份 |
| AUTH-006 | “我的”展示身份、开发环境标记、退出和本人操作记录 | `/me`、logout、actions | 已实现并兼容 | 不展示其他用户资源 |
| AUTH-007 | 操作记录只展示业务摘要、状态、时间、失败原因和 traceId | actions/audit | 已实现并回归 | 不泄露内部 payload、凭据或上游错误正文 |

## 6. 账户、流水与本人互转

### 6.1 用户需求

| ID | 需求 | 页面 | 接口/数据 | 状态 |
| --- | --- | --- | --- | --- |
| ACC-001 | 账户中心只展示当前用户的 CNY 储蓄账户 | `/accounts` | `GET /api/accounts` | 已实现并兼容 |
| ACC-002 | 首页显示所有 CNY 储蓄账户可用余额合计及账户数量 | `/` | `GET /api/accounts/summary` | 已实现并兼容 |
| ACC-003 | 首页和账户页列出每个账户，不设置隐含“第一账户即主账户”规则 | `/`、`/accounts` | accounts | 已实现并兼容 |
| ACC-004 | 账户详情显示状态、余额、产品、脱敏账号和开户日期 | `/accounts/:accountId` | account/detail/balance | 已实现并兼容 |
| ACC-005 | 流水支持分页、日期、金额和收支方向筛选及单笔详情 | 账户详情 | transactions | 已实现并兼容 |
| ACC-006 | 账户页不提供独立开户或销户；新账户只能由办卡流程创建 | 账户页 | CardService/Fineract | 已实现并兼容 |
| ACC-007 | 用户可以在本人两个不同储蓄账户之间转账 | `/payments/internal` | `POST /api/internal-transfers` | 已实现并兼容 |
| ACC-008 | 本人互转两边流水均保留，并标记 `internal_transfer` | 流水 | Fineract 事实 + 中端语义 | 已实现并兼容 |
| ACC-009 | 内部转账不得计入收入、支出、消费分类或异常大额消费 | 洞察 | Transaction/Billing Service | 已实现并兼容 |

### 6.2 本人互转规则

| ID | 需求 | 状态 |
| --- | --- | --- |
| ACC-010 | 转出和转入账户必须属于当前用户、为 ACTIVE CNY 储蓄账户且不能相同 | 已实现并兼容 |
| ACC-011 | 请求包含 `from_account_id`、`to_account_id`、`amount` 和可选 `remark` | 已实现并兼容 |
| ACC-012 | 沿用日累计 1000 元门槛、Action、幂等、确认、OTP、执行抢占和核对规则 | 已实现并兼容 |
| ACC-013 | 核心转账成功后记录双方 transaction ID 和 transfer ID | 已实现并兼容 |
| ACC-014 | 超时或结果不明只读核对，不更换幂等键自动重发 | 已实现并兼容 |

## 7. 联系人与支付

| ID | 需求 | 页面 | 接口 | 状态 |
| --- | --- | --- | --- | --- |
| PAY-001 | 联系人支持姓名、手机号和别名检索及 CRUD | 支付中心抽屉 | recipients | 已实现并兼容 |
| PAY-002 | 普通转账只能转入当前 Fineract 演示租户中的有效账户 | `/payments/new` | transfers | 已实现并兼容 |
| PAY-003 | 日累计不超过 1000 元为 YELLOW，需结构化确认 | Action 页 | transfers/actions | 已实现并兼容 |
| PAY-004 | 日累计超过 1000 元为 RED，确认后必须 OTP | Action 页 | actions/otp/verify | 已实现并兼容 |
| PAY-005 | 定时转账支持 once/daily/weekly/monthly、暂停、恢复和运行记录 | 支付中心计划页签 | transfer-schedules | 已实现并兼容 |
| PAY-006 | 计划创建或修改后必须重新授权，worker 才可执行 | 计划详情 | schedules/actions | 已实现并兼容 |
| PAY-007 | AA 支持等额和指定金额分摊，参与人不得重复 | 支付中心 AA 页签 | aa-collections | 已实现并兼容 |
| PAY-008 | AA 参与人必须是系统内用户，并由本人登录后主动支付 | AA 详情 | shares/pay | 已实现并兼容 |
| PAY-009 | 本阶段不发送短信或邮件邀请 | AA 详情 | 无外部通知 | 本阶段不做 |

## 8. Action、安全验证与审计

### 8.1 状态机

公开状态继续使用：`WAITING_CONFIRMATION`、`WAITING_VERIFICATION`、`AUTHORIZED`、`EXECUTING`、`RECONCILING`、`SUCCEEDED`、`FAILED`、`CANCELLED`。

| ID | 需求 | 状态 |
| --- | --- | --- |
| ACT-001 | 创建 Action 只表示请求已持久化，不表示业务已成功 | 已实现并兼容 |
| ACT-002 | 前端按钮完全由中端状态决定，不得在前端提升风险等级或跳过步骤 | 已实现并兼容 |
| ACT-003 | 用户确认必须提交服务端 `request_hash`，参数改变后原确认失效 | 已实现并兼容 |
| ACT-004 | OTP 为随机六位、五分钟有效、最多五次错误、重发间隔三十秒，沿用现有锁定规则 | 已实现并兼容 |
| ACT-005 | 所有写接口使用 1–160 字符 `Idempotency-Key`；同键同参返回原结果，同键异参返回 409 | 已实现并兼容 |
| ACT-006 | `RECONCILING` 只能读取上游事实，不得用新幂等键重新执行未知结果 | 已实现并兼容 |
| ACT-007 | Action 增补 `risk_level`、`source`、`expires_at`、`updated_at`、`version`，现有字段保持不变 | 已实现并通过迁移/业务回归 |
| ACT-008 | 审计增补 `trace_id`、`resource_type`、`resource_id`，敏感字段继续脱敏 | 已实现并通过迁移/业务回归 |
| ACT-009 | 开发验证码仅当前登录用户可读取本人 Action，非 development 环境路由不可用 | 已实现并兼容 |

### 8.2 用户展示

| ID | 需求 | 状态 |
| --- | --- | --- |
| ACT-010 | `/actions/:actionId` 继续作为内部通用路由，页面标题使用“确认转账”“激活银行卡”“安全验证”“处理结果”等业务名称 | 已实现并兼容 |
| ACT-011 | `reconcile` 对用户显示为“核对处理结果”，审计显示为“操作记录”，不暴露内部状态机术语 | 已实现并通过前端回归 |

## 9. 账单、分类与异常

| ID | 需求 | 接口/数据 | 状态 |
| --- | --- | --- | --- |
| BILL-001 | 洞察默认汇总本人全部 CNY 储蓄账户 | billing statistics | 已实现并兼容 |
| BILL-002 | 用户可切换到一个账户查看同样的统计 | billing statistics + account_id | 已实现并兼容 |
| BILL-003 | 分类仅使用确定性规则：merchant、note、type | rules/annotations | 已实现并兼容 |
| BILL-004 | 人工单笔标注优先于自动规则；用户可在流水详情维护/清除标注，并编辑、删除分类和商户/备注/交易类型规则及优先级 | categories/rules/annotations | 已实现并经中端、页面与桌面/390px浏览器回归 |
| BILL-005 | 内部转账、反向交易和投资本金划转按现有语义单独处理，不算消费 | TransactionService | 已实现并兼容 |
| BILL-006 | 异常至少保留 LARGE_V1 和 DUPLICATE_V1，并展示样本、基线和金额证据 | billing anomalies | 已实现并兼容；前端将规则码和证据对象转换为中文摘要，不展示内部 JSON |
| BILL-007 | 异常仅是候选，用户可标记 verified 或 ignored；当前状态明确显示，已选状态按钮禁用并保留反向纠正入口；成功/失败有反馈并审计实际状态变化，不自动冻结资金 | anomaly-reviews | 已实现并经中端、页面与桌面/390px浏览器回归 |
| BILL-008 | 月报、年报实时计算并显示上海时间 `data_cutoff`、规则版本和非原子快照提示；未来期间拒绝；报告写入失败和结果未知提供核对入口 | `/insights/bills/:period` | 已实现并经上海日期、组件及报告结果未知回归 |
| BILL-009 | `bill-reports` 路径继续兼容，但不作为新前端的主入口 | bill-reports | 已实现并兼容 |
| BILL-010 | `account_id` 缺省时，统计和异常接口枚举当前用户全部符合条件的账户，返回 `account_ids`、统一币种、完整性标志和聚合结果；任一账户分页不完整时整体失败或标记不完整，不得静默漏算 | billing statistics/anomalies | 已实现并兼容；显式单账户异常响应继续为旧列表格式 |
| BILL-011 | 自然语言查看月/年报告默认使用上海本月/本年，显式期间和“所有账户”优先；按本人、期间和准确账户范围复用报告/在途任务/失败记录，只有完全缺失时自动排队；事件只携带引用与状态，结果未知引导报告列表且不自动重发 | `/api/agent/messages`、授权报告状态/详情 | 已实现并经隔离中端、前端及桌面/390px受控回归；真实模型供应商验收待进行 |

## 10. 订阅与代扣

### 10.1 识别规则

| ID | 需求 | 状态 |
| --- | --- | --- |
| SUB-001 | 同一规范化商户至少出现三次相似扣款才生成候选 | 已实现并兼容 |
| SUB-002 | 第一版只识别月付和年付；月付间隔使用 25–35 天，年付使用 350–380 天 | 已实现并兼容 |
| SUB-003 | 金额相对候选中位数允许上下 10% 浮动 | 已实现并兼容 |
| SUB-004 | 候选必须保存关联账户、交易 ID、日期、金额、周期和判定证据 | 已实现并兼容 |
| SUB-005 | 用户可以核实或忽略候选；被忽略候选在规则版本和证据未显著变化时不重复打扰 | 已实现并兼容 |
| SUB-006 | 已核实订阅显示预计金额、周期、下次扣费日及识别置信信息 | 已实现并兼容 |
| SUB-007 | 洞察页突出提示未来三天内预计续费，点击进入 `/subscriptions` | 已实现并兼容 |
| SUB-015 | 扫描仅在本人全部合格账户的 800 天流水分页完整时成功；返回实际扫描日期、时间、本次匹配候选数，`found` 保持为已保存订阅总数；零候选成功也记扫描审计 | 已实现并回归 |
| SUB-016 | 统一续费查询按上海日期返回已核实订阅；默认 `days=3`，严格整数 1–90，范围包含今天与截止日，并按预计日期和 ID 稳定排序 | 已实现并回归 |
| SUB-017 | 预计日期已过只进入待复查列表，不推断实际漏扣；续费 GET 只读，不扫描或修改业务状态 | 已实现并回归 |

### 10.2 取消闭环

| ID | 需求 | 状态 |
| --- | --- | --- |
| SUB-008 | 取消为 YELLOW Action，展示商户、预计金额、周期和下次扣费日后确认 | 已实现并兼容 |
| SUB-009 | 成功后调用明确标注的 Demo 商户 Adapter，订阅状态改为 `CANCELLED` 并清空下次扣费日 | 已实现并兼容 |
| SUB-010 | 重复取消返回相同终态，不重复调用商户 | 已实现并兼容 |
| SUB-011 | Demo 商户再次发起已取消订阅的扣费时拒绝，并记录拒绝原因和审计 | 已实现并兼容 |
| SUB-012 | 不删除历史订阅、扣费证据或取消记录 | 已实现并兼容 |
| SUB-013 | 页面不得宣称取消了任何真实第三方会员 | 已实现并兼容 |
| SUB-014 | 首版仅由用户点击“重新扫描”触发识别，Demo Reset 可以预置候选；本阶段不增加自动订阅扫描 worker | 已实现并兼容；页面仍为手动扫描，Reset 重建结构化商户流水后主动预置候选，不增加常驻 worker |
| SUB-018 | 同键取消重放保持原 Action；有效待确认/处理中请求不并行；过期、用户撤回和明确失败可由新幂等键恢复；确认快照变化以 `SUBSCRIPTION_CHANGED` 阻止执行，未知结果只允许查看/核对 | 已实现并回归；仍只允许 Demo Adapter |

### 10.3 目标接口

| 方法与路径 | 作用 | 状态 |
| --- | --- | --- |
| `POST /api/subscriptions/scan` | 重新读取本人流水并幂等更新候选 | 已实现并兼容 |
| `GET /api/subscriptions/renewals?days=3` | 上海时区续费范围、已核实近期项目、过期预测待复查列表和最近成功扫描时间 | 已实现并回归；只读，不隐式扫描 |
| `GET /api/subscriptions` | 查询候选、已核实、已忽略和已取消订阅 | 已实现并兼容 |
| `GET /api/subscriptions/{id}` | 查询证据、周期、扣费和状态详情 | 已实现并兼容 |
| `POST /api/subscriptions/{id}/verify` | 核实候选，幂等 | 已实现并兼容 |
| `POST /api/subscriptions/{id}/ignore` | 忽略候选，幂等 | 已实现并兼容 |
| `POST /api/subscriptions/{id}/cancel` | 创建取消 Action，需要幂等键 | 已实现并兼容 |
| `POST /api/demo/subscriptions/{id}/charge` | development 环境验证取消后拒绝扣费 | 已实现并兼容；只验证策略且不移动资金 |

## 11. 定存与财富

| ID | 需求 | 状态 |
| --- | --- | --- |
| WLT-001 | 产品、利率、期限、本金和持有状态只来自 Fineract 原生定期存款 | 已实现并兼容 |
| WLT-002 | 本地 `product_metadata` 只保存风险和推荐适配信息，不伪造收益 | 已实现并兼容 |
| WLT-003 | 产品比较和推荐使用确定性字段，推荐结果不构成收益承诺 | 已实现并兼容 |
| WLT-004 | 每次点击申购后都必须完成一份新的五题风险测评 | 已实现并兼容 |
| WLT-005 | 测评仅可被一个申购 Action 原子消费，重复使用必须拒绝 | 已实现并兼容 |
| WLT-006 | 产品风险高于测评等级时禁止申购，不能通过免责声明绕过 | 已实现并兼容 |
| WLT-007 | 申购和赎回均为 RED，必须 OTP | 已实现并兼容 |
| WLT-008 | 支持整笔提前关闭和到期关闭，不支持部分赎回 | 已实现并兼容 |
| WLT-009 | 赎回必须先报价，执行前条件变化返回 `QUOTE_CHANGED` | 已实现并兼容 |
| WLT-010 | `POST /api/risk-assessments` 响应兼容增加 `purpose`、`used_at`、`used_action_id`；申购请求兼容增加可选 `assessment_id`，新前端必须显式传入 | 已实现并兼容（实际字段名为 `action_id`） |
| WLT-011 | 旧请求未传 `assessment_id` 时，只能使用当前用户最新、未使用、申购用途且在 15 分钟内创建的测评，否则返回 `RISK_ASSESSMENT_REQUIRED`；创建 Action 时原子占用测评 | 已实现并兼容 |

## 12. 普通借记卡管理

### 12.1 模型和边界

本项目采用银行式简化模型：借记卡是账户的使用介质，每张卡对应一个 Fineract CNY 活期主账户。中端不实现信用卡额度、账单日、最低还款、利息、实体制卡或物流，也不宣称实现完整的Ⅰ/Ⅱ/Ⅲ类账户监管体系。

业务边界参考[中国工商银行借记卡章程页面](https://big5.icbc.com.cn/column/678756826291666944.html)和[中国银行长城借记卡章程](https://www.boc.cn/bcservice/bc3/bc31/202111/t20211115_20301745.html)中“借记卡关联存款账户、先存后用”的基本关系，只用于比赛版领域建模，不宣称覆盖章程全部条款或现实监管要求。

### 12.2 生命周期

```text
申请 Action
  → 用户确认
  → 中端规则自动审批
  → Fineract 创建/审批/激活零余额储蓄账户
  → 创建 PENDING_ACTIVATION 卡
  → OTP 激活
  → ACTIVE
  → LOCKED（可 OTP 解锁）
  → LOST（永久失效）
  → OTP 补卡
  → 新卡 PENDING_ACTIVATION，沿用原账户
  → 旧卡 REPLACED
```

| ID | 需求 | 状态 |
| --- | --- | --- |
| CARD-015 | Fineract 开户任一步骤超时或结果不明时，按外部引用只读核对，禁止重复开户 | 已实现并回归 |
| CARD-016 | 账户已创建但卡记录失败时从持久化步骤恢复，不得生成第二个账户 | 已实现并回归 |

### 12.3 功能需求

| ID | 需求 | 状态 |
| --- | --- | --- |
| CARD-001 | 用户可持有多张本行普通借记卡；Alice 初始化两张，其他演示用户各一张 | 已实现并在本机建立 5 张基线卡 |
| CARD-002 | 办卡不从账户页发起开户，只能通过卡申请流程自动创建零余额账户 | 已实现并回归 |
| CARD-003 | 卡片显示产品名、自定义别名、状态、账户余额和掩码卡号 | 已实现并回归 |
| CARD-004 | 默认单笔限额 5000 元、日累计限额 20000 元 | 已实现并回归；不确定交易计入日累计防止绕过 |
| CARD-005 | 默认启用线上、POS、ATM，默认关闭境外交易 | 已实现并回归；Demo 消费执行前重新校验 |
| CARD-006 | 支持调整单笔/日累计限额和四类渠道开关 | 已实现并回归 |
| CARD-007 | 申请、降低限额、关闭任一渠道和锁卡为 YELLOW，需要确认 | 已实现并回归 |
| CARD-008 | 激活、提高限额、开启线上/POS/ATM/境外渠道、解锁、挂失和补卡为 RED，需要 OTP | 已实现并回归 |
| CARD-009 | LOST 卡永久不可解锁；补卡生成新卡并保留账户、余额和历史流水 | 已实现并回归 |
| CARD-010 | 卡片别名可以直接修改，但仍需审计；别名不参与资金身份判断 | 已实现并兼容 |
| CARD-011 | 默认只显示卡号后四位；OTP 后完整 Demo 卡号最多显示 60 秒，刷新或离开页面立即失效 | 已实现并回归 |
| CARD-012 | 不生成或展示真实 CVV、磁道、芯片或支付网络凭据 | 已实现并兼容 |
| CARD-013 | 完整 Demo 卡号使用认证加密保存；密钥来自环境变量且不得入库、日志或 Git | 已实现并回归 |
| CARD-014 | 卡片锁定、未激活、挂失、渠道关闭或超过额度时，交易必须在调用 Fineract 前拒绝 | 已实现并回归 |
| CARD-017 | 补卡生成的新卡必须再次 OTP 激活，补卡 Action 本身不得直接使新卡可交易 | 已实现并回归 |
| CARD-018 | Demo 卡限额上限为单笔 50000 元、日累计 100000 元，超过上限的提额请求直接拒绝 | 已实现并回归 |
| CARD-019 | Alice 最终保留原有储蓄账户并新增两张卡各自绑定的账户，因此完整 Demo 基线下共有三个 CNY 储蓄账户；其他演示用户各新增一张卡及其账户 | 已实现；本机核心账户与中端卡记录已建立 |

### 12.4 目标接口

| 方法与路径 | 作用 | 状态 |
| --- | --- | --- |
| `GET /api/cards`、`GET /api/cards/{id}` | 本人卡片列表和详情 | 已实现并回归 |
| `POST /api/cards` | 创建办卡 Action，使用幂等键 | 已实现并回归 |
| `PATCH /api/cards/{id}` | 修改本人卡片别名 | 已实现并兼容 |
| `POST /api/cards/{id}/activate` | 创建激活 RED Action | 已实现并回归 |
| `POST /api/cards/{id}/limits` | 创建额度/渠道变更 Action | 已实现并回归 |
| `POST /api/cards/{id}/lock` | 创建锁卡 YELLOW Action | 已实现并回归 |
| `POST /api/cards/{id}/unlock` | 创建解锁 RED Action | 已实现并回归 |
| `POST /api/cards/{id}/report-lost` | 创建挂失 RED Action | 已实现并回归 |
| `POST /api/cards/{id}/replace` | 创建补卡 RED Action | 已实现并回归 |
| `POST /api/cards/{id}/reveal` | 创建安全查看 RED Action | 已实现并回归 |
| `GET /api/cards/{id}/reveal?action_id=...` | 在本人 RED Action 的 60 秒窗口内无缓存返回完整 Demo 卡号 | 已实现并回归 |
| `GET /api/cards/{id}/transactions` | 查询卡片授权和对应核心交易引用 | 已实现并回归；仅 development 开放 |

### 12.5 Demo 商户交易

| ID | 需求 | 状态 |
| --- | --- | --- |
| DEMO-001 | `/demo/merchant` 持续显示“比赛演示商户，不是真实支付网络” | 已实现并回归 |
| DEMO-002 | 页面要求用户登录，只能选择本人的 ACTIVE 卡 | 已实现并回归 |
| DEMO-003 | 用户输入商户、金额、渠道和境内/境外标志，提交时携带幂等键 | 已实现并回归 |
| DEMO-004 | 中端先检查卡状态、渠道、单笔限额、日累计限额和账户归属 | 已实现并回归 |
| DEMO-005 | 拒绝交易记录明确原因，不调用 Fineract、不改变余额 | 已实现并回归 |
| DEMO-006 | 放行交易通过 Fineract `accounttransfers` 将钱转入对应 Demo 商户账户 | 已实现并回归（受控核心替身）；真实栈待彩排 |
| DEMO-007 | 结果保存 transfer ID、双方 transaction ID，并可从账户流水和账单核对 | 已实现并回归 |
| DEMO-008 | 同幂等键重放不能重复扣款；超时进入核对状态，禁止换键重试 | 已实现并回归 |

目标接口为 `GET /api/demo/merchants` 和 `POST /api/demo/card-transactions`，仅 development/demo 环境开放。

## 13. 页面规格

| 路由 | 页面 | 核心内容 | 状态 |
| --- | --- | --- | --- |
| `/login` | 登录 | 登录、锁定提示、会话恢复 | 已实现并兼容 |
| `/` | 首页 | 总余额、账户列表、待处理操作、卡片/财富/账单快捷入口 | 已实现并回归 |
| `/accounts` | 账户与银行卡 | “账户/银行卡”二级页签，多账户、多卡 | 已实现并回归 |
| `/accounts/:accountId` | 账户详情 | 余额、信息、分页筛选流水、单笔详情 | 已实现并兼容 |
| `/cards/:cardId` | 卡片详情 | 状态、限额、渠道、授权记录、锁定/挂失/补卡 | 已实现并回归 |
| `/payments` | 支付中心 | 普通、本人互转、记录、定时、AA、联系人 | 已实现并兼容 |
| `/payments/new` | 普通转账 | 账户、联系人、金额、备注 | 已实现并兼容 |
| `/payments/internal` | 本人互转 | 本人转出/转入账户、金额、备注 | 已实现并兼容 |
| `/actions/:actionId` | 业务确认与结果 | 参数、确认、OTP、执行、核对、操作记录 | 已实现并兼容 |
| `/insights` | 洞察 | 全账户收支、分类、异常、实时账单、订阅提醒 | 全账户统计、异常和三天订阅提醒已实现 |
| `/insights/bills/:period` | 实时月/年账单 | 汇总、趋势、分类、异常、截止时间 | 已实现并通过组件/构建回归 |
| `/subscriptions` | 订阅管理 | 候选、核实、忽略、三天提醒、取消 | 已实现并兼容；另有 `/subscriptions/:subscriptionId` 证据详情，周期、间隔、容差和历史扣款均以用户可读内容展示，不透传 JSON |
| `/wealth` | 定存财富 | 产品、比较、推荐、持有、申购、赎回 | 已实现并兼容；真实栈写操作待手工彩排 |
| `/wealth/risk-assessment` | 本次申购风险测评 | 五题、结果、返回申购 | 已实现并兼容 |
| `/me` | 我的 | 身份、退出、本人操作记录、环境标记 | 已实现并兼容 |
| `/demo/merchant` | Demo 商户 | 卡片渠道/额度验证和测试消费 | 已实现并回归 |
| `/tasks/:taskId` | 跨场景任务 | 仅保留未来契约，不进入导航和验收 | 本阶段不做 |

## 14. 数据模型需求

### 14.1 现有表增补

| ID | 表 | 新字段 | 目的 | 状态 |
| --- | --- | --- | --- | --- |
| DB-001 | `actions` | `risk_level`、`source`、`expires_at`、`updated_at`、`version` | 查询策略结论、来源、过期和乐观并发 | 已实现并通过 `0005` 迁移回归 |
| DB-002 | `audit_events` | `trace_id`、`resource_type`、`resource_id` | 建立跨 Action 和业务资源的可检索审计链 | 已实现并通过 `0005` 迁移回归 |
| DB-003 | `risk_assessments` | `purpose`、`used_at`、`used_action_id` | 保证一次测评只用于一次申购 | 已通过 `0002` 实现；实际关联字段名为 `action_id` |
| DB-010 | 以上现有表 | 新增字段必须可空或提供安全默认值 | 兼容已有记录和迁移 | 已在 `0002`～`0005` 迁移往返中验证 |

### 14.2 新表

| ID | 表 | 核心字段 | 约束 | 状态 |
| --- | --- | --- | --- | --- |
| DB-004 | `merchants` | id、name、category、adapter_type、fineract_account_id、active | Demo 商户外部标识唯一；不存余额 | 已实现；初始化映射独立 Fineract Demo 商户账户 |
| DB-005 | `bank_cards` | id、user_id、fineract_account_id、product_name、alias、pan_ciphertext、last4、status、single_limit、daily_limit、online_enabled、pos_enabled、atm_enabled、international_enabled、replaces_card_id、version、timestamps | 卡号不可明文；本人账户归属；旧卡关系可追溯 | 已实现并兼容 |
| DB-006 | `card_authorizations` | id、user_id、card_id、merchant_id、idempotency_key、amount、currency、channel、country_code、status、decline_code、action_id、fineract_transfer_id、from_transaction_id、to_transaction_id、timestamps | 用户+幂等键唯一；金额 Decimal；未知结果可核对 | 已实现并回归 |
| DB-007 | `subscriptions` | id、user_id、merchant_id、status、cadence、expected_amount、amount_tolerance、next_charge_at、evidence、rule_version、verified_at、cancelled_at、action_id、timestamps | 用户+商户+周期候选稳定唯一；保留历史 | 已实现并兼容 |
| DB-008 | `subscription_occurrences` | id、subscription_id、account_id、transaction_id、occurred_on、amount | 订阅+账户+流水唯一，支持证据回溯 | 已实现并兼容 |
| DB-009 | 资金事实边界 | 不新增余额表 | 中端不建立本地账户余额、卡片余额或订阅资金余额表；资金事实始终来自 Fineract | 已实现并兼容 |

## 15. API 兼容、错误与迁移规则

### 15.1 兼容原则

| ID | 需求 | 状态 |
| --- | --- | --- |
| API-001 | 现有 URL、HTTP 方法和响应字段不删除、不改名 | 已实现并兼容 |
| API-002 | 新响应字段必须是可选字段或具有稳定默认值 | 需要兼容调整 |
| API-003 | 新请求约束先更新同仓库前端，再在中端启用强制校验 | 需要兼容调整 |
| API-004 | 已有 `bill-reports` 和一年期历史风险测评记录继续可读取，但新前端不依赖其旧语义 | 需要兼容调整 |
| API-005 | 数据迁移前后旧 Action、报告和测评仍可查看 | 需要兼容调整 |
| API-006 | 新功能不得要求前端读取 Fineract 原始 JSON | 已实现并兼容 |

### 15.2 错误

| ID | 需求 | 状态 |
| --- | --- | --- |
| ERR-001 | 所有接口错误继续使用下列统一结构 | 已实现并兼容 |
| ERR-002 | 状态语义保持：401 未认证，403 无权限，404 隐藏不存在或跨用户资源，409 幂等/状态/报价冲突，422 输入或业务规则不满足，429 锁定/限频，502 上游数据或契约错误，503 上游不可用或必要外部组件缺失 | 已实现并兼容 |

```json
{
  "error": {
    "code": "STABLE_CODE",
    "message": "用户可理解的说明",
    "retryable": false
  }
}
```

### 15.3 新增稳定错误码

| ID | 需求 | 状态 |
| --- | --- | --- |
| ERR-003 | 稳定错误码：沿用 `RISK_ASSESSMENT_REQUIRED` 和 `REVEAL_EXPIRED`；新增 `ASSESSMENT_ALREADY_USED`；卡片使用 `CARD_NOT_ACTIVE`、`CARD_LOCKED`、`CARD_LOST`、`CARD_CHANNEL_BLOCKED`、`CARD_SINGLE_LIMIT_EXCEEDED`、`CARD_DAILY_LIMIT_EXCEEDED`；订阅使用 `SUBSCRIPTION_NOT_VERIFIED`、`SUBSCRIPTION_CHARGE_BLOCKED` | 已实现并兼容；重复取消订阅按幂等规则返回原 Action，不制造 `SUBSCRIPTION_ALREADY_CANCELLED` 错误 |

## 16. 非功能与安全要求

| ID | 要求 | 状态 |
| --- | --- | --- |
| NFR-001 | 本阶段以本机 Docker 演示为部署目标，不承诺公网生产 SLA | 已实现并兼容 |
| NFR-002 | Chrome、Edge 当前稳定版及 390px 移动视口完成自动化或手工验收 | 已实现并兼容：2026-10-16 在默认 Playwright Chromium、本机 Chrome 和 Edge 分别 9/9 通过，每轮均包含 390px 导航可用性用例 |
| NFR-003 | 普通本地查询使用统一超时配置；超过时限必须呈现可恢复状态 | 已实现并兼容：查询 10 秒、写操作 30 秒；查询超时可重试，写超时返回 `WRITE_RESULT_UNKNOWN` 且页面禁止直接重发 |
| NFR-004 | 任何跨用户资源请求返回 404 或统一无权限错误，不泄露资源是否存在 | 已实现并兼容 |
| NFR-005 | 所有资金写操作、卡状态操作和订阅取消均可审计、可幂等、可恢复 | 已覆盖订阅取消、卡状态和 Demo 卡消费；真实栈仍需彩排 |
| NFR-006 | 完整卡号使用认证加密；密钥通过环境变量配置并进入部署文档和 `.env.example`，真实值不得提交 | 已实现并回归 |
| NFR-007 | Demo 专用 API 由环境开关控制，非 development/demo 环境不注册或返回 404 | 已实现并回归 |
| NFR-008 | 日志和测试证据不得包含密码、Token、OTP、完整卡号或真实密钥 | 已实现并兼容：公共审计入口递归脱敏凭据、Token、OTP、API Key、PAN/CVV；卡号明文不落 Action/审计，安全测试固定该约束 |
| NFR-009 | Demo Reset 仅允许本地显式命令执行，打印目标环境并要求确认，禁止作用于未知数据库 | 已实现并兼容 |

## 17. Demo Reset 要求

| ID | 需求 | 状态 |
| --- | --- | --- |
| RST-001 | Reset 运行前验证当前环境为 development/demo | 已实现并兼容 |
| RST-002 | 明确显示将重置的 Fineract 租户、中端数据库和 Demo 资源 | 已实现并兼容 |
| RST-003 | 不删除 Docker named volume 或数据库本身 | 已实现并兼容 |
| RST-004 | 幂等恢复 Alice 两张卡、其他用户各一张卡、Demo 商户、订阅证据、账户和确定性流水 | 已实现并通过自动化与两次真实 Reset：两次均恢复 5 张 ACTIVE 基线卡、12 个联系人、14 个订阅候选和相同账户余额 |
| RST-005 | 清理本项目 Action、授权、计划运行、卡片授权和订阅状态，但不触碰非 Demo 外部资源 | 已实现并回归 |
| RST-006 | 重置后自动运行只读 Smoke，并输出账户、卡片、订阅和商户引用 | 已实现并完成真实验收；重启中端后 Alice 登录、3 账户汇总、两张 ACTIVE 卡和 4 个本人订阅候选读回通过 |
| RST-007 | 重复执行得到等价业务状态，不重复创建核心对象 | 已实现并完成两次真实 Reset；核心账户 ID 2～11 与商户账户 6 稳定复用，余额、卡数量/状态、联系人和候选集合等价 |
| RST-008 | Fineract 只匹配并重置带本项目固定 externalId 的 Demo 资源；不得清空整个租户或触碰未知资源 | 已实现并兼容 |
| RST-009 | 中端 Reset 保留预置用户及其密码哈希，清理登录会话并重建业务演示状态 | 已实现并兼容 |

当前 Reset 精确支持四名用户主账户、5 个固定 `AGENT-*-CARD-*` 卡账户、由本项目生成的 UUID 形态 `BANK-CARD-*` 动态账户及 `AGENT-DEMO-MERCHANT-SAV`。固定卡和商户账户清零后复用，动态卡账户清零后关闭；已关闭旧动态卡不再重复处理。发现未知账户、跨出演示边界的转账、非终态的异常卡账户或不支持安全撤销的流水类型时仍会拒绝执行，而不是部分清理。2026-10-16 已由维护人员授权连续完成两次真实写入 Reset：第一次清理 2 笔历史内部转账和 1176 笔直接流水，第二次清理 0 笔内部转账和重新生成的 1176 笔直接流水；两次均恢复相同业务基线。

## 18. 需求追踪与验收矩阵

| 验收 ID | 覆盖需求 | 用户场景 | 页面 | API | Service | 数据表/事实 | 关键断言 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AT-001 | NAV-001～003、AUTH-001～006、ACC-001～005、UI-001～003、DAT-001～006 | Alice 登录查看资产 | 登录、首页、账户 | auth、me、accounts | AuthService、AccountService | users、sessions、Fineract | 只见本人账户，总额等于逐账户求和 |
| AT-002 | AUTH-005、ACC-001、NFR-004 | Bob 访问 Alice 账户 | 账户详情 | accounts/{id} | AccountService | Fineract 账户归属 | 返回 404/无权限，不泄露余额 |
| AT-003 | ACC-007～014、ACT-001～008、BILL-005、BILL-010、DB-001～002 | 本人账户互转 | 支付、Action | internal-transfers、actions | InternalTransferService、ActionService | actions、audit、Fineract | 双边余额正确，账单不算收支，重放不重复扣款 |
| AT-004 | PAY-001～003、ACT-001～006 | 普通小额转账 | 支付、Action | recipients、transfers、actions | TransferService、PolicyService | actions、daily_usage、Fineract | 需要确认，不需要 OTP，双方事实可核对 |
| AT-005 | PAY-004、ACT-001～006、NFR-005 | 日累计大额转账 | 支付、Action | transfers、actions/otp/verify | TransferService、PolicyService、OtpService | actions、daily_usage、audit | 必须 OTP，错误和重放受控 |
| AT-006 | PAY-005～009、ACT-001～006 | 定时与 AA | 支付 | transfer-schedules、aa-collections | ScheduleService、AAService、Worker | schedules、runs、aa、Fineract | 授权、暂停、恢复、付款和运行记录正确 |
| AT-007 | BILL-001～010、DAT-001～003 | 全账户实时账单 | 洞察、实时账单 | billing、categories、rules、annotations | BillingService、TransactionService | 分类、规则、标注、Fineract | 汇总完整，内部转账排除，显示截止时间 |
| AT-008 | BILL-006～007 | 异常核实 | 洞察 | billing/anomalies、anomaly-reviews | BillingService | anomaly_reviews、Fineract | 展示证据，仅核实或忽略，不冻结账户 |
| AT-009 | NAV-004、SUB-001～007、SUB-014、DB-004、DB-007～008 | 识别订阅 | 洞察、订阅 | subscriptions/scan、subscriptions | SubscriptionService | merchants、subscriptions、occurrences、Fineract | 三次、周期和 10% 容差证据可解释，扫描只由用户触发 |
| AT-010 | SUB-008～013、ACT-001～008、ERR-003 | 取消订阅 | 订阅、Action | subscriptions/{id}/cancel、demo charge | SubscriptionService、DemoSubscriptionAdapter | subscriptions、audit、Fineract | 确认后取消，后续 Demo 扣费被拒绝 |
| AT-011 | WLT-001～007、WLT-010～011、DB-003 | 定存申购 | 财富、测评、Action | risk-assessments、investments/subscriptions | RiskService、InvestmentService | risk_assessments、actions、Fineract | 每次新测评、越级阻止、OTP 后才执行 |
| AT-012 | WLT-008～009、ACT-001～006 | 整笔赎回 | 财富、Action | redemption-quotes、redemptions | InvestmentService | actions、Fineract 定存/储蓄 | 报价变化拒绝，资金回本人储蓄账户 |
| AT-013 | NAV-002、ACC-006、CARD-001～003、CARD-007～008、CARD-015～017、CARD-019、DB-005 | 申请并激活借记卡 | 账户、卡片、Action | cards、cards/{id}/activate、actions | CardService、AccountService | bank_cards、actions、Fineract | 只创建一个零余额账户，OTP 后 ACTIVE；Alice 完整基线为原账户加两张卡账户 |
| AT-014 | CARD-004～006、CARD-014、CARD-018、DEMO-002～005、DB-006 | 卡片限制 | 卡片、Demo 商户 | cards/{id}/limits、demo/card-transactions | CardPolicyService | bank_cards、card_authorizations | 渠道、额度或系统上限不符时不调用 Fineract |
| AT-015 | NAV-005、DEMO-001～008、NFR-007 | 卡片真实 Demo 消费 | Demo 商户、流水 | demo/merchants、demo/card-transactions | CardService、TransferService | Fineract、card_authorizations | 商户双边入账、余额和账单一致、重放不双扣 |
| AT-016 | CARD-007～010、CARD-015～017、ACT-001～008 | 锁卡、解锁、挂失、补卡 | 卡片、Action | cards lock/unlock/report-lost/replace | CardService、ActionService | bank_cards、audit、Fineract | 风险级别正确，挂失永久，补卡保留账户且新卡重新激活 |
| AT-017 | UI-001～005、ACT-006、ERR-001～003、NFR-003、NFR-005 | Fineract 停止、网络中断或超时 | 所有业务页 | 相关读取/写入/reconcile | adapters、各域 Service | audit、Fineract | 不显示假数据；结果不明只核对不重发 |
| AT-018 | RST-001～009、NFR-009 | Demo Reset | 命令行、Smoke | reset/seed 内部入口 | DemoResetService | 中端数据库、Fineract Demo 数据 | 只处理固定 externalId，保留用户密码，重复执行不重复资源 |
| AT-019 | CARD-011～013、DAT-004～005、NFR-006、NFR-008 | 安全查看 Demo 卡号 | 卡片详情、Action | cards/{id}/reveal、actions/otp/verify | CardService、OtpService | bank_cards、audit | OTP 后限时显示；存储和日志无明文卡号，不存在 CVV |
| AT-020 | AUTH-007、ACT-009～011 | 查看操作记录和开发 OTP | 我的、Action | actions、actions/{id}/audit、dev otp inbox | ActionService、AuditService | actions、audit_events | 仅本人可见；用户文案无内部 JSON，生产环境无 OTP 路由 |
| AT-021 | API-001～006、DB-009～010 | 旧客户端与历史数据兼容 | 所有现有页面 | 现有 84 条非 Agent 路径/111 个操作 | 各域 Service、Migration | 现有表、Fineract | 旧字段不删除，迁移后旧记录可读，不新增余额事实表 |
| AT-022 | NFR-001～009、TST-001～007 | 全量质量门槛 | 全部目标页面 | 全部非 Agent API | 全部非 Agent Service | 中端数据库、Fineract | 本地 Demo、安全、性能、浏览器、移动视口和分层测试证据齐全 |

每个场景还必须覆盖空数据、越权、参数非法、重复提交、网络断开、Fineract 503、请求超时和刷新恢复。

`NAV-006` 和 `OOS-001～009` 明确处于“本阶段不做”，因此不映射到可执行验收；一旦范围改变，必须先修改本文状态并新增对应验收 ID。

## 19. 测试要求

| ID | 需求 | 状态 |
| --- | --- | --- |
| TST-001 | 中端单元测试覆盖分类、订阅周期、金额容差、卡片额度、渠道、风险分级和状态迁移 | 卡片额度、渠道、风险、状态迁移和消费拒绝矩阵已覆盖；其余矩阵持续补齐 |
| TST-002 | PostgreSQL 集成测试覆盖幂等、并发、额度原子累计、测评单次消费、锁卡/挂失竞态和 worker 死锁回归 | 已实现并兼容；卡片锁定与限额修改竞态连续 3 次通过，只有一个 Action 成功且版本只递增一次 |
| TST-003 | Fineract 隔离契约测试覆盖开户、本人互转、Demo 商户转账、响应丢失核对和补卡账户复用 | 受控核心替身已全部覆盖；真实 Fineract 卡片/商户契约待补 |
| TST-004 | 前端组件测试覆盖路由保护、全账户总额、表单校验、Action 按钮、订阅证据、卡片状态和错误映射 | 已实现并兼容：当前 12 个测试文件 60 项通过，覆盖续费错误态、Action 过期/失败恢复提示及订阅确认快照 |
| TST-005 | Playwright 使用 Chrome/Edge 等价 Chromium 验收桌面与 390px；自动写操作默认网络拦截，真实本地栈只运行可重置的隔离 Smoke | 已实现并兼容：9 个场景在 Chromium、Chrome、Edge 各通过一轮，写操作均由路由拦截，未触发真实资金变更；真实栈资金 Smoke 仍归 TST-003/TST-007 |
| TST-006 | 安全测试覆盖跨用户访问、幂等冲突、OTP 失败锁定、Demo API 环境隔离和日志敏感信息扫描 | 已实现并兼容：上述场景均由 PostgreSQL 集成测试覆盖，公共审计脱敏额外验证嵌套字典/列表不会持久化秘密值 |
| TST-007 | 测试结果必须区分“受控替身通过”和“真实 Fineract 契约通过” | 已实现并兼容：测试记录独立列明 65 项受控替身/PostgreSQL 结果、既有真实 Fineract 探针结果和仍未执行的真实 Reset/卡消费 |

## 20. 实施顺序

1. 评审本文并冻结需求编号与兼容策略；
2. 修复现有计划 worker 并发死锁，完成 Demo Reset；
3. 增加全账户账单汇总、本人互转和一次性申购测评（已完成并通过回归）；
4. 实现订阅识别、核实、三天提醒和 Demo 取消（已完成并通过回归）；
5. 实现普通借记卡、自动开户、卡状态机、加密卡号和 Demo 商户交易（自动化范围已完成）；
6. 完成前端页面、真实栈 Smoke、组件测试、集成测试和 E2E；
7. 在 Agent 阶段单独设计跨场景任务，不在本阶段提前实现 `/api/tasks`。

## 21. 明确不做

| ID | 范围 | 状态 |
| --- | --- | --- |
| OOS-001 | 用户注册、找回密码、完整个人资料维护和管理员后台 | 本阶段不做 |
| OOS-002 | 多币种、信用卡、透支、信用账单、还款和利息 | 本阶段不做 |
| OOS-003 | 实体制卡、邮寄、物流、真实银行卡组织或真实商户接入 | 本阶段不做 |
| OOS-004 | 自动冻结异常交易或账户 | 本阶段不做 |
| OOS-005 | 短信、邮件和推送通知 | 本阶段不做 |
| OOS-006 | PDF 账单导出 | 本阶段不做 |
| OOS-007 | 部分定存赎回、基金、证券或虚构理财产品 | 本阶段不做 |
| OOS-008 | 公网生产部署承诺 | 本阶段不做 |
| OOS-009 | 跨场景 DAG、任务中心实现和任何 Agent 能力 | 本阶段不做 |
