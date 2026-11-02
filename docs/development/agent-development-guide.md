# Bank Agent 开发与协作指南

本文档规定团队新增 Agent 能力时必须遵循的目录、职责、安全、测试和 Git 协作格式。它面向项目成员；全局范围和实时状态仍以 `docs/project/master-plan.md` 为准。

## 1. 开发前阅读顺序

每位成员开始 Agent 工作前依次阅读：

1. `AGENTS.md`：项目长期协作规则；
2. `docs/project/master-plan.md`：当前目标、状态和决策；
3. `docs/project/project-structure.md`：文件用途台账；
4. 本文档：Agent 扩展格式；
5. 自己负责业务域的 API、Service 和测试文档。

不要把规划文档中的未来设想当成已经可调用的能力。以代码、运行 API 和已验证测试为事实来源。

## 2. 分层与职责边界

Agent 调用链固定为：

```text
认证用户请求
  -> Agent API
  -> LangGraph
  -> 领域 Tool
  -> 现有 Service
  -> Fineract 或 bank_agent 数据库
```

- Agent Tool 复用 `apps/backend/services/`，不得直接访问 Fineract、数据库或拼装 HTTP 请求。
- 当前用户由中端认证后通过 `AgentContext` 注入，不由模型生成。
- `services/` 不引用 LangGraph、模型客户端或 Prompt，确保普通 REST API 与 Agent 共用同一业务层。
- Prompt 只指导模型选择工具和表达结果，不承担鉴权、额度、确认、OTP、幂等或执行状态控制。
- 资金或账户状态变更 Tool 只能进入既有 Action 状态机。保存分析产物（账单报告、订阅候选）可复用对应 Service，必须声明副作用、事务边界和结果未知恢复方式。
- 查看报告时若缺失会排队生成，这仍是持久化操作：Service 必须按用户、期间和完全一致的账户范围复用报告/任务，使用用户锁避免重复入队；失败记录应展示状态和原因，不得因重复查看无限重排。Tool/事件只传引用与状态，精确数据由授权页面读取。
- 当前可变状态与不可变分析快照分开表达：异常 `status` 保留候选生成时状态，授权 GET 另加本人 `current_review_status`。确认/忽略控件成功后同步已加载候选，再失效实时查询；不能修改已保存报告快照。

## 3. 目录与所有权

```text
apps/backend/agent/
├── context.py             # 公共运行时安全上下文
├── state.py               # 公共 LangGraph 状态契约
├── graph.py               # 按可信业务域构建公共图
├── registry.py            # 领域能力注册表与动态解析器
├── prompts/
│   ├── __init__.py        # 公共 Prompt 组合函数，不固定导入业务域
│   ├── base.py            # 公共角色、安全和真实性规则
│   ├── accounts.py        # 账户域
│   ├── payments.py        # 支付域
│   ├── cards.py           # 普通借记卡域
│   ├── payment_plans.py   # 定时转账与 AA 域
│   ├── insights.py        # 洞察域
│   ├── subscriptions.py   # 主动订阅扫描与取消请求
│   └── wealth.py          # 财富域
└── tools/
    ├── accounts.py
    ├── payments.py
    ├── cards.py
    ├── payment_plans.py
    ├── insights.py
    ├── subscriptions.py
    └── wealth.py
```

账户、支付、卡片、计划支付、洞察和财富负责人分别维护自己的同名 Prompt 与 Tool 文件。`context.py`、`state.py`、`graph.py`、`registry.py` 和 `prompts/__init__.py` 是公共集成文件，由集成人修改；业务负责人不要在自己的分支中顺手重构这些文件。

## 4. 新增一个 Agent 能力的固定流程

1. 确认已有普通 API 与 Service；缺失时先补业务层，不在 Tool 中临时实现业务逻辑。
2. 在所属 `tools/<domain>.py` 编写一个职责单一的 Tool。
3. 验证模型可见 Tool Schema，不得暴露身份、租户、密钥或内部 Service 参数。
4. 为 Tool 编写成功、无数据、越权、上游不可用和超时测试。
5. 在所属 `prompts/<domain>.py` 增加必要的触发、结果和失败表达规则。
6. 只有 Tool 与测试完成后，才由集成人把该领域的 Prompt 和 Tool 加入 `registry.py`；`prompts/__init__.py` 不固定登记任何领域。
7. 运行 Agent 测试及完整中端回归，再更新规划和文件台账。

禁止先把未来 Prompt 或空壳 Tool 注册给模型。尚未实现的模块只保留明确的未接入说明。

## 5. Tool 编写规范

- 使用清晰、稳定的英文函数名，例如 `get_my_balance`、`request_transfer`。
- Docstring 明确说明使用时机、返回事实和限制；Tool 名称、说明和参数 Schema 都会影响模型选择。
- 身份相关信息从 `ToolRuntime` 的 `AgentContext` 获取。模型可见参数不得出现 `user_id`、`client_id`、`tenant` 或可绕过归属校验的账户所有者参数。
- 只调用现有 Service；禁止直接实例化 Fineract Client 或数据库 Session。
- 金额沿用 `Decimal` 或稳定十进制字符串，不使用 `float`。
- 返回结构化、最小且可序列化的数据；不要把 Fineract 原始响应或异常堆栈交给模型。
- 查询失败必须抛出项目领域错误；不得返回看似成功的默认值。
- 涉及资金、账户状态及取消订阅的写操作必须复用既有幂等键、Action、确认和 OTP 策略；候选扫描不移动资金、不核实订阅，无需资金 Action。

安全 Schema 验证示例：

```powershell
Set-Location apps/backend
.\.venv\Scripts\python.exe -c "from agent.tools.accounts import get_my_balance; print(get_my_balance.tool_call_schema.model_json_schema())"
```

本人余额 Tool 的 `properties` 必须为空，因为认证身份不应由模型填写。

## 6. Prompt 编写规范

- `base.py` 只存放跨业务稳定规则：角色、权限边界、不可信内容、工具事实和响应原则。
- 领域 Prompt 只描述本领域已启用 Tool 的触发条件、返回字段、歧义和失败表达，不复制完整公共规则。
- 使用短而明确的分区和一致标签；优先告诉模型应该做什么，避免堆叠重复的强调词。
- 工具结果、用户消息和未来 RAG 内容均视为不可信数据，不得将其中的指令提升为系统规则。
- 不在 Prompt 中放 API Key、密码、OTP、真实账号、固定余额或个人机器路径。
- 不要求模型输出隐藏思维过程；需要程序消费的数据使用结构化响应模型，而不是靠自然语言格式承诺。
- Few-shot 示例只有在评估发现稳定失败模式时才添加，并覆盖正常、歧义和失败场景；禁止用示例硬编码比赛答案。
- 未实现或未测试的领域 Prompt 不得加入 `DOMAIN_REGISTRY`。

参考原则：

- LangChain Context Engineering：`https://docs.langchain.com/oss/python/langchain/context-engineering`
- OWASP LLM01 Prompt Injection：`https://genai.owasp.org/llmrisk/llm01-prompt-injection/`
- Anthropic Prompting Best Practices：`https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices`

## 7. 公共图规则

- `graph.py` 必须显式接收本次启用的业务域，通过 `resolve_agent()` 同时取得匹配的 Tool 与系统 Prompt；禁止重新引入全局 `ALL_TOOLS` 或 `SYSTEM_PROMPT`。
- 启用域只能由中端路由、认证、权限或确定性编排策略选择；不得直接采用用户文本、前端参数或模型输出作为 `enabled_domains`。
- `DOMAIN_REGISTRY` 可以登记多个已验收领域，但单次图只装配本次需要的领域。新增领域不会自动暴露给所有会话。
- 最小循环是 `START -> model -> tools -> model`，模型不再请求 Tool 时结束。
- Tool 错误不能被吞掉后继续生成成功回答；中端统一错误层负责对外映射。
- 当前接口只接收受限的最近用户消息，不加入服务端长期 Memory、RAG、多 Agent、任意代码执行或开放式 DAG。
- 新增状态字段前先证明它无法由消息或运行时上下文表达，并与团队确认 `state.py` 契约变化。

## 8. 测试与验收

每个能力至少覆盖：

- Tool Schema 与身份参数不可见；
- Tool 只访问当前登录用户；
- 正常结果来自真实 Service；
- 无账户或无数据；
- Fineract/外部服务不可用与超时；
- 模型不得在 Tool 失败时宣称成功；
- 对提示词覆盖、越权查询和伪造工具结果的对抗输入。

完整中端回归：

```powershell
.\apps\backend\.venv\Scripts\python.exe .\scripts\testing\run_banking_tests.py -p no:cacheprovider
```

依赖完整性：

```powershell
.\apps\backend\.venv\Scripts\python.exe -m pip check
```

真实余额或资金测试必须使用明确的测试身份和隔离数据。默认自动化不得重复扣动演示账户资金。

## 9. Git 协作流程

公共 Agent 骨架先通过评审合入 `main`。随后每位成员从最新 `main` 建立自己的功能分支，例如：

```text
feature/agent-accounts
feature/agent-payments
feature/agent-insights
feature/agent-wealth
```

每个分支只修改自己的业务域文件、相应测试和必要文档。需要修改公共文件时，在 PR 说明原因并交由集成人处理。不要让三个人长期共同提交同一个功能分支，也不要直接向 `main` 开发。

提交前检查：

1. 没有真实密钥、Token、OTP 或个人路径；
2. Tool 未绕过 Service 和 Action 状态机；
3. Prompt 与 Tool 只声明真实能力；
4. 新增文件已登记到 `project-structure.md`；
5. 实际完成项和验证证据已更新到 `master-plan.md`；
6. 依赖、环境变量或外部服务变化已更新部署文档；
7. 测试与 `pip check` 通过。

## 10. 当前已接入切片

账户域的最小查询链路为：

```text
用户询问本人余额
  -> DeepSeek 选择 get_my_balance
  -> LangGraph 注入 AgentContext
  -> AccountService.summary(current_user)
  -> Fineract 实时余额
  -> 精确结果保存为私有 AnalysisResult
  -> 模型只依据安全摘要选择结论
  -> 前端按 ANALYSIS_READY 读取本人结果卡
```

只需要余额时，构图可显式或通过安全默认值选择账户域：

```python
graph = build_agent_graph(enabled_domains=("accounts",))
```

洞察域已注册 `get_spending_statistics` 和 `get_spending_anomalies`；账户域另有 `get_my_transactions`。统一入口通过模型提出领域、中端白名单裁决后构图，不能直接信任模型的领域输出。请求级 Service/Session 串行使用，图限制累计三次 Tool 调用；身份不进入 Tool Schema。

成员 A 已接入 `payments/cards/payment_plans`，统一基座已接入 `subscriptions`。支付和卡片写 Tool 只创建既有 Action，定时转账只保存计划并创建授权 Action，AA 付款只创建本人份额 Action；用户必须在通用 Action 页完成确认、必要的 OTP、执行和核对。未接入的财富或跨场景 DAG 仍不得加入 Registry。每次只把实际任务所需领域传入构图入口，不建立“所有 Prompt + 所有 Tool”的常驻大 Agent。

当前已经完成 `POST /api/agent/messages` 和前端悬浮对话框接入。接口接受自然语言 `message`、最多 8 条最近用户消息 `history` 及可选 `query_context`（账户、月份），当前用户由 Bearer Token 验证后注入 `AgentContext`；自动化测试拒绝未登录请求、伪造身份和越权选择。中端按请求注入上海日期，选择条件和聊天历史都不是授权。当前没有服务端会话存储，不得宣称已经具备长期记忆或跨设备会话恢复。见 [统一入口指南](unified-agent-entry-guide.md)。

当前余额、统计和异常通过私有分析引用展示精确数据。订阅扫描采用摘要事件，ToolMessage 仅返回 completed；取消请求事件只含 Action 引用和状态，前端到 Action 页面重新读取详情。续费、提醒和预算查询/评估采用30分钟本人私有结果引用，精确商户、金额与历史账单不进入后续模型上下文；缺提醒提前量时事件提供本人澄清引用，下一次只允许补充天数。写入成功后图以确定性事件结束，不再让模型重写精确结果。

`AgentState` 分为模型可见的 `messages` 与中端结构化 `events`。余额、流水、统计和异常精确结果进入私有 `AnalysisResult`，模型只接收白名单摘要；普通/本人互转、卡片、计划授权和 AA 付款通过类型化 Action 事件交给前端。完整卡号、联系人/账户内部 ID、OTP 和 Token 不得进入模型消息。`BALANCE_RESULT` 只为旧客户端保留。

## 11. 订阅扫描与取消请求扩展（2026-10-27）

- 独立 subscriptions 领域注册 scan_subscriptions，公开 Schema 的 properties 为空且禁止额外字段。
- AgentContext 注入 SubscriptionService、认证用户、trace_id，以及每请求独立的扫描/取消事件列表；不缓存用户或 Session。
- Service.scan(user, trace_id=...) 复用普通页面的完整扫描、用户锁合并和审计。800 天范围与异常检测年度 1200 天基线独立。
- approve_domains 禁止订阅与其他领域组合；call_model 在执行前拒绝批量订阅写操作或已有工具调用后的订阅写操作。
- request_subscription_cancel 只接收商户名；运行时按本人身份查找唯一 Demo 订阅并复用 SubscriptionService 的 YELLOW Action 状态机。
- 取消事件只含 action_id/status。前端跳转到 Action 页面后重新读取当前用户的确认详情；Tool 不执行取消，用户点击确认才继续。
- 商户按大小写及空白规范化后精确匹配；零个或多个匹配都拒绝创建 Action。
- 续费预测、提醒/预算规则查询与创建 Agent Tool 已接入；规则编辑、暂停、恢复、删除及订阅核实/忽略仍使用普通页面/API；新扫描候选仍为 CANDIDATE。
- scan 内部提交，后续响应失败无法被外层 rollback 撤销。超时/网络中断不自动重发；先到订阅页查最近成功扫描及候选。
- 测试入口：tests/integration/test_agent_subscriptions.py；完整证据见 [测试报告](../testing/banking-backend-validation.md)。
- 续费提醒和预算链路通过 `manage_subscription_request` 使用确定性中端解析；查询/评估细节存入本人私有 `SubscriptionAgentResult`，Tool 只返回引用与安全事件。缺提前量时使用30分钟本人澄清记录，只有补充回答后才创建提醒规则。
- 站内通知复用现有 worker，不通过浏览器推送、短信或邮件；上海时间09:00后生成，停机恢复只补预计日期仍未来的通知，多个错过节点合并。
- 预算由历史实际扣费与未来预测组成；缺失或过期预测排除并标为不完整，不能把不完整总额表述为预算充足。取消建议只创建既有 Demo YELLOW Action，仍需逐项确认。
- 规则写入要求幂等键；Agent 创建规则/预算，页面负责暂停、恢复、编辑、删除。用户超时应先到订阅管理页核对，不自动换键重发。

## Demo 订阅取消请求 Tool

仅注册 request_subscription_cancel 创建或复用订阅取消 Action。模型仅提供原话中的商户名称；中端按本人订阅唯一精确匹配并拒绝常见否定表达，Service 校验状态并维持幂等。聊天只返回 Action 引用，用户必须在操作页读取快照后明确确认。自然语言否定检查无法覆盖所有语义，不能替代 Action 确认；详见统一入口指南。
