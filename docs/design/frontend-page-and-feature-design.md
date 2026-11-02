# Bank Agent 前端页面与功能设计

> 状态：非 Agent 页面设计基线，尚未代表页面均已实现。
> 依据：`docs/requirements/frontend-backend-requirements.md`、当前 FastAPI OpenAPI 和比赛六类场景。
> 原则：页面按用户任务组织，不按后端接口数量堆菜单；查询可以直接展示，写操作统一进入 Action 安全流程。

## 1. 设计结论

现有视觉外壳可以保留，不需要推倒重做。需要重构的是认证、数据源和业务页面：

- 现有 AI 助手入口可以保留，但不作为本设计中任何页面或业务功能的前置依赖；
- 底部一级导航控制在 5 个：`首页 / 账户 / 支付 / 洞察 / 我的`；
- 卡片作为账户页二级页签并保留首页快捷入口；定存从首页进入，订阅从洞察进入；
- 跨场景任务延后到 Agent 阶段，本阶段不进入导航或验收；
- 所有业务数据来自中端，前端不硬编码用户、账户 ID、余额、联系人或授权状态；
- 所有写操作复用通用 Action 页面完成确认、OTP、结果和恢复，不在每个功能中重复实现一套安全流程。

## 2. 页面地图

### 2.1 公共页面与全局组件

| 路由/组件 | 页面或功能 | 优先级 | 主要能力 | 当前接口 |
| --- | --- | --- | --- | --- |
| `/login` | 登录页 | P0 | 用户名密码登录、错误/锁定提示、会话恢复 | `POST /api/auth/login`、`POST /api/auth/refresh` |
| `ProtectedRoute` | 登录保护 | P0 | 未登录跳转、Token 过期只刷新一次、失败清空会话 | 统一 API Client |
| 全局 Agent Drawer | AI 助手悬浮层 | 独立范围 | 保留现状，但不参与本文页面验收 | Agent 文档与接口 |
| 全局错误与连接状态 | 状态提示 | P0 | 区分未登录、业务拒绝、Fineract 不可用和网络断开 | `/api/health` 与统一错误结构 |

### 2.2 已有中端接口可支撑的页面

| 路由 | 页面 | 优先级 | 主要功能 | 对应接口 |
| --- | --- | --- | --- | --- |
| `/` | 首页 | P0 | 全部 CNY 储蓄账户余额合计、账户列表、近期 Action、卡片/财富/账单快捷入口 | `/api/me`、`/api/accounts/summary`、`/api/accounts`、`/api/actions` |
| `/accounts` | 账户与银行卡 | P0 | “账户/银行卡”二级入口；本人真实账户和多张普通借记卡 | `/api/accounts`、`/api/accounts/summary`、`/api/cards` |
| `/accounts/:accountId` | 账户详情与流水 | P0 | 余额、账户信息、分页流水、日期/金额/方向筛选、单笔详情 | `/api/accounts/{id}`、`/balance`、`/transactions`、`/transactions/{transactionId}` |
| `/payments` | 支付中心 | P1 | 普通转账、本人互转、转账记录、定时转账、AA 收款 | transfers、internal-transfers、transfer-schedules、aa-collections |
| `/payments/new` | 新建转账 | P1 | 选本人付款账户、搜索联系人、金额/备注、创建 Action | `/api/accounts`、`/api/recipients`、`POST /api/transfers` |
| `/payments/internal` | 本人账户互转 | P1 | 选择两个不同本人账户、金额/备注、创建通用 Action | `/api/accounts`、`POST /api/internal-transfers` |
| `/actions/:actionId` | 操作确认/验证/结果（内部通用页） | P0 | 根据业务类型显示“确认转账”“安全验证”“处理结果”等用户名称；参数复核、OTP、取消、执行进度和失败恢复 | `/api/actions/{id}` 及 confirm/otp/verify/cancel/reconcile/resume/audit |
| `/insights` | 财务洞察首页 | P1 | 全账户收支、分类、异常提醒、实时月/年账单和三天内订阅提醒 | billing statistics/anomalies；订阅摘要已接入 |
| `/insights/bills/:period` | 实时账单分析 | P1 | 月/年切换、分类图表、收支趋势、异常证据、人工核实、数据截止时间 | billing、categories、classification-rules、annotations；bill-reports 仅兼容保留 |
| `/wealth` | 定存与财富 | P1 | 产品目录/比较/推荐、每次申购重新测评、申购、持有、整笔赎回 | risk-assessments、investments 全组接口 |
| `/wealth/risk-assessment` | 本次申购风险评估 | P1 | 五题问卷、一次性测评结果、返回申购流程 | risk-assessments |
| `/me` | 我的 | P0 | 当前用户、退出登录、操作记录、开发环境入口提示 | `/api/me`、logout、actions |

普通 CRUD 不单独占页面：联系人编辑、分类规则、交易标注、风险问卷、OTP 和单笔流水优先使用抽屉、对话框或页内步骤，减少路由碎片。

`Action` 是后端状态机术语，不作为用户菜单或页面标题。用户看到的是具体业务流程，例如“确认转账 → 安全验证 → 处理结果”；`/actions/:actionId` 只是这些流程共用的内部实现和可恢复深链。审计默认收纳在结果页的“操作记录”折叠区，`reconcile` 对用户显示为“核对处理结果”，不暴露工程术语。

### 2.3 比赛场景的新增/未来页面

| 路由 | 页面 | 优先级 | 计划功能 | 假设后端能力 |
| --- | --- | --- | --- | --- |
| `/cards`、`/cards/:cardId` | 普通借记卡管理 | P1 | 申请、自动审批开户、本人列表/详情、OTP 激活、60 秒安全查看、额度/渠道、锁定解锁、挂失和补卡已接入 | CardService、Fineract 账户与卡片 Action API |
| `/subscriptions`、`/subscriptions/:subscriptionId` | 订阅管理与证据 | P1 | 三次周期扣费识别、核实/忽略、三天提醒、证据详情、Demo 取消 | 已接入 SubscriptionService 和取消 Action API |
| `/demo/merchant` | Demo 商户 | P2 | 验证卡状态、渠道和额度；成功后真实转入 Fineract 商户账户 | development/demo 专用商户和卡交易 API |
| `/tasks/:taskId` | 跨场景任务 | 后续 | 仅保留未来契约，本阶段不进入导航或验收 | Agent 阶段重新设计 |

## 3. 五个一级导航的职责

### 首页

- 当前用户问候、全部本人 CNY 储蓄账户余额合计和账户列表；
- 最近待确认/待验证/失败的 Action；
- 余额查询、转账、账单、借记卡和定存等快捷入口；
- 不在首页堆完整图表或所有账户详情。

### 账户

- 只显示当前登录人的账户；
- Bob、Charlie、Mom 是联系人或其他用户，不是 Alice 的“我的账户”；
- 账户详情承载流水，不再单独增加“流水”一级页面。
- 使用“账户 / 银行卡”二级页签：账户保持只读，银行卡管理普通借记卡及其绑定的 Fineract 主账户；
- 不把账户列表第一条当作“主账户”，需要付款账户时必须由用户选择或由后端返回明确关系。

### 支付

- 普通转账、本人账户互转、计划转账、AA 收款和历史记录共用一个支付中心；
- 联系人作为转账表单的辅助管理，不单独占一级导航；
- 创建操作后统一跳转 `/actions/:actionId`。

### 洞察

- 账单统计、异常、实时月/年视图和订阅管理；
- 图表只展示后端统计结果，前端不重新推导金融事实；
- 异常必须显示规则、样本和证据，不能只显示“AI 判断异常”。
- 默认聚合本人全部 CNY 储蓄账户，也允许切换单账户；
- 洞察首页提示未来三天内预计续费，详情进入 `/subscriptions`。

### 我的

- 用户身份、退出、Action 历史、开发环境标记；
- 后续再增加安全设置和会话管理，不把业务功能塞入此页。

## 4. 必须统一的交互流程

### 4.1 登录与令牌

```text
打开应用 → 恢复会话/刷新 → GET /api/me
                     ↓失败
                   登录页
                     ↓成功
            加载本人账户与首页数据
```

比赛 Demo 阶段可使用 `sessionStorage` 保存访问令牌和刷新令牌，关闭标签页即清理；API Client 负责自动添加 Bearer、单飞刷新以及 401 清理。生产银行方案应改为服务端 HttpOnly Cookie，不把当前 Demo 存储方案描述为生产最佳实践。

### 4.2 写操作与 Action

```text
业务表单 → 创建业务请求/Action → 展示结构化参数
       → 用户确认 → GREEN/YELLOW 直接执行，或 RED 发送 OTP
       → 验证 → 执行/核对 → SUCCESS / ERROR / UNKNOWN
```

- “创建成功”不等于资金已执行；
- Action 页面根据后端状态决定可用按钮，前端不得自行提升授权等级；
- 开发验证码收件箱只在明确 development 环境显示；
- 处理中状态每 2 秒轮询一次，最多自动轮询 60 秒，之后保留手动刷新；
- UNKNOWN/超时只允许调用 reconcile，不自动换幂等键重发。

### 4.3 独立 Agent 边界

- 现有 Agent Drawer 可以继续存在，但本文中的普通银行页面不能依赖 Agent 才能完成操作；
- 本文不规定 LangGraph、Prompt、Tool、对话协议、`taskId` 或结果回写；
- Agent 阶段未来可以通过稳定业务路由进入页面，但页面仍需从中端重新读取并校验资源归属与状态；
- 跨场景 DAG 等到 Agent 阶段另行设计，不作为本轮前端实现或验收内容。

## 5. 当前前端的保留与改造

| 现有内容 | 决策 |
| --- | --- |
| `AppShell`、品牌色、响应式布局 | 保留，并继续兼容桌面与 390px 移动视口 |
| 悬浮 Agent 入口 | 可以保留现状，但独立于本文需求和验收 |
| 首页账户卡片和快捷入口 | 使用认证后的真实总余额、账户列表和卡片/财富/账单入口 |
| `accounts-page` | 保持本人动态账户；增加普通借记卡二级页签，不恢复演示账户硬编码 |
| `transfer-page` | 保留真实转账流程；增加本人账户互转入口 |
| `insights-page` | 改为全账户实时聚合，并增加订阅摘要入口 |
| `wealth-page` | 使用 Fineract 原生定存；每次申购重新进入五题测评 |
| `profile-page` | 保留身份、退出、Action 历史和开发环境标识 |
| `demo-accounts.ts` 等硬编码数据 | 不得作为用户、账户、余额、卡片、订阅或授权状态的事实来源 |

## 6. 后端接口缺口与假设

### 6.1 兼容扩展与公共前置

1. **账户 DTO 已完成，继续保持稳定**：`/api/accounts` 和 `/api/accounts/{id}` 已使用 `AccountSummary/AccountDetail`；后续只能兼容增加可选字段，不得把 Fineract 原始结构重新暴露给 React。
2. **多账户语义（已实现）**：`/api/accounts/summary` 汇总本人全部 CNY 储蓄账户；账单统计与异常的 `account_id` 可选，洞察页缺省展示全部账户并可切换单账户。
3. **本人账户互转（已实现）**：`/api/internal-transfers` 复用现有幂等、风险分级、Action 和 Fineract 资金执行逻辑，并为统计提供明确的 `internal_transfer` 语义。
4. **一次性风险测评（已实现）**：测评响应包含用途和使用状态，定存申购可显式传 `assessment_id`；每份测评 15 分钟有效且只能绑定一次申购 Action。
5. **错误与结果恢复**：继续使用 `error.code/message/retryable`，前端必须区分未登录、拒绝、状态冲突、Fineract 不可用、超时和结果不明。
6. **公共写操作可靠性**：修复计划任务并发死锁，并提供可重复的一键 Demo Reset，之后才扩展新的写操作场景。

### 6.2 新增场景接口

- **普通借记卡**：卡片列表/详情、申请、激活、别名、限额、渠道、锁定/解锁、挂失、补卡、安全查看和交易记录；卡片绑定中端受控创建的 Fineract 零余额 CNY 储蓄账户。
- **Demo 商户**：仅 development/demo 环境开放；先由中端校验卡片状态、渠道和限额，通过后才向 Fineract 提交真实商户转账。
- **订阅（已实现）**：手动扫描、候选证据、核实/忽略、续费提醒和 Demo 取消 Action；取消后的 Demo 扣费被拒绝并审计，页面明确不代表真实第三方取消。
- **通知**：待确认、待 OTP、计划失败和三天内续费提醒可以先由页面短轮询加手动刷新实现，通知中心不是硬前置。
- **跨场景任务**：`/api/tasks` 仅保留未来契约说明，当前非 Agent 阶段不实现、不接页面、不验收。

## 7. 推荐实施顺序

### F0：评审并冻结需求基线

- 评审 `docs/requirements/frontend-backend-requirements.md`；
- 核对现有 79 条非 Agent 路径、106 个操作与兼容策略；
- 任何新业务字段、状态或路由先回写需求编号与追踪矩阵。

### F1：公共写操作可靠性

- 修复计划任务双 Worker 并发死锁；
- 建立一键 Demo Reset；
- 验证幂等、Action 恢复、开发 OTP 收件箱和审计追踪。

### F2：现有能力兼容增强（已完成并回归）

- 多账户首页汇总和全账户账单聚合；
- 本人账户互转；
- 每次定存申购重新测评并一次性占用结果。

### F3：订阅闭环（已完成并回归）

- 候选识别、证据、核实/忽略和三天提醒；
- YELLOW 取消与 Demo 扣费拒绝验证。

### F4：普通借记卡闭环（开户、设置与状态机已完成）

- 自动开户、待激活卡、别名、掩码、AES-GCM 密文和 OTP 激活已完成；
- 限额/渠道风险分级、锁定/OTP 解锁、永久挂失和沿用原账户补卡已完成；
- OTP 后 60 秒无缓存安全查看已完成，刷新或离开页面清除；
- Demo 商户交易验证卡片策略、Fineract 双边资金和账单分类。

### F5：页面与测试收口

- 完成五个一级导航下的全部目标页面；
- 覆盖空数据、越权、重复提交、网络中断、Fineract 不可用、超时和结果不明；
- 完成 Chrome、Edge、桌面和 390px 移动视口验收。

跨场景 DAG 与 Agent 能力不在以上顺序中，进入 Agent 阶段后另行编制需求和验收。

## 8. 当前最近一步

普通借记卡的开户、设置、状态机、安全查看和独立 Demo 商户页已完成自动化回归；卡策略拒绝、确认后 Fineract 双边入账及授权记录均已接入。下一步在可重置隔离环境彩排真实核心写入和账单读回。
