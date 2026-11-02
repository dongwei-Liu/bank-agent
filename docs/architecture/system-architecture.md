# Bank Agent 系统架构

## 1. 总览

```text
React Web App
  ├─ 普通银行功能页
  └─ Agent 对话 / 结构化结果卡 / Action 与 Task 跳转
             │ Bearer Token + Idempotency-Key + SSE
             ▼
FastAPI 中端
  ├─ Auth / API / DTO / Error Contract
  ├─ Conversation Service + Agent Worker
  ├─ Trusted Router + LangGraph + Domain Tools
  ├─ Deterministic Policy + Action / OTP / Security Lock
  ├─ Banking Services + Billing / Card / Subscription / Wealth
  ├─ Orchestration Service + Banking Worker
  └─ Audit / Security Events / Private Results
        │                         │
        ▼                         ▼
bank_agent PostgreSQL       Fineract REST API
（状态、语义、审计）        （账户、余额、流水、Hold、转账、定存）
                                  │
                                  ▼
                           Fineract PostgreSQL
```

中端与 Fineract 使用独立数据库。中端不保存第二套余额；账户、资金和流水以 Fineract 为事实来源。卡片介质、联系人、订阅语义、分类、Action、Agent 会话和任务状态由中端维护。

## 2. 运行进程

| 进程 | 职责 | 不负责 |
| --- | --- | --- |
| React/Vite | 页面、会话恢复、结构化卡片、导航、确认/OTP UI | 不直接访问 Fineract，不决定权限 |
| FastAPI | 认证、参数校验、同步读取、Action/任务提交、SSE | 不在 HTTP 请求中执行持久化 Agent Run 或到期任务 |
| Agent Worker | 领取 Agent Run、路由、调用模型/Tool、持久化回复与事件 | 不绕过 Service/Action，不直接执行 Fineract 命令 |
| Banking Worker | 定时转账、报告、订阅提醒/预算、生日 DAG 到期节点 | 不调用对话模型 |
| PostgreSQL | 中端事务、锁、租约、幂等、状态和审计 | 不复制 Fineract 余额 |
| Fineract | 核心客户、账户、余额、流水、Hold、转账和定存生命周期 | 不理解 Agent 会话、卡片介质或订阅语义 |

## 3. 普通业务调用

```text
页面 → FastAPI Route → Service → FineractClient → Fineract
                    └→ 中端 PostgreSQL（语义/状态/审计）
```

API 从 Token 得到当前用户；Service 在每次操作中校验资源归属。写请求先创建 Action 或受控业务请求，创建成功不等于资金成功。结果只有在回读核心事实并完成核对后才能显示为成功。

## 4. Agent 调用

```text
用户消息
  ↓ 入库前敏感信息检查 / 注入规则记录
持久化 Conversation + QUEUED Run
  ↓ Agent Worker 租约领取
可信 Router 提出领域候选
  ↓ 中端白名单、独占和权限裁决
按需组装 Domain Prompt + Tools
  ↓ LangGraph（模型 → Tool → 模型/确定性结束）
Service / Action / 私有结果
  ↓ 持久化 AgentEvent
SSE 可重放到 React
```

会话历史来自服务端本人消息，不接受客户端伪造的助手回复或 Tool 结果。SSE 只负责展示；断线后使用 `Last-Event-ID` 重放，业务状态仍由 Action、Task 或私有结果 API 重新读取。

## 5. 数据事实分层

| 数据 | 事实来源 |
| --- | --- |
| 账户、可用余额、流水、Hold、转账、定存 | Fineract |
| 用户登录、联系人、卡片状态/限制、订阅、分类 | 中端 PostgreSQL |
| Action、OTP 状态、幂等、审计、安全锁 | 中端 PostgreSQL |
| Agent 会话、Run、事件、可信候选引用 | 中端 PostgreSQL |
| 生日任务、节点、边、预留引用、Demo 订单 | 中端 PostgreSQL；真实资金引用回到 Fineract |
| 模型回复 | 非权威展示，不作为银行事实 |

## 6. 六场景与跨场景任务

- 智能转账：联系人、本人互转、定时转账、AA；
- 账单分析：统计、分类、异常候选、月/年报告；
- 财富：Fineract 原生 CNY 定存、测评、申购、持有、整笔赎回；
- 卡片：普通 Demo 借记卡介质和策略，关联 Fineract 活期账户；
- 订阅：周期证据、续费、提醒、预算和 Demo 取消；
- 跨场景：固定生日鲜花+蛋糕 DAG，RED 授权、Hold/Release、两个受控商户转账、时间线与恢复。

比赛版不提供通用 DAG 编辑器、多 Agent、任意代码执行或真实商户网络。

## 7. 部署拓扑

本地比赛环境以 Docker 提供 PostgreSQL/Fineract，前端和三个中端进程运行在开发机。所有进程读取根 `.env`；真实秘密不进入 Git。生产化需要补充受信 TLS、正式短信/MFA、秘密管理、反向代理、可观测性、备份/灾备、容量和独立安全评审。
