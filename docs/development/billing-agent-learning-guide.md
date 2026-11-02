# 账单 Agent 配对学习指南

> 2026-10-22 更新：三个 Tool 已采用私有结果通道。当前模型参数是 `account_ref/from_date/to_date`，精确结果写入 `AnalysisResult`，ToolMessage 仅白名单摘要，聊天按引用独立 GET 精确卡片。当前实现与维护见 [专项报告](../testing/billing-privacy-ml-validation.md) 和 [统一入口指南](unified-agent-entry-guide.md)。下方旧练习、第 8 节独立接口和历史验收仅供理解演进，不应照搬旧的精确 Tool 结果或新增领域专用接口。

## 1. 本轮分工与完成边界

示例实现 `get_spending_statistics`，用户已完成异常查询练习，实际命名为 `get_spending_anomalies`。两个工具共用账户、开始日期、结束日期，以及可信的用户和账单 Service 上下文。

统计和异常均可通过脚本运行洞察图，异常模式通过 `--query anomalies` 选择。2026-10-18 已完成统一前端与 `/api/agent/messages` 的账户/洞察域接入，含真实模型三工具组合验收；最新实现按 [统一入口指南](unified-agent-entry-guide.md) 阅读。下文第 8 节保留为历史备选教学，不代表应再新增领域专用入口。保存月报/年报、分类修改仍未接入。

## 2. 沿着一次调用阅读代码

```text
demo_spending_agent.py: 登录、选择本人账户、创建请求级 Session/Service
  -> build_agent_graph(("insights",)): 组合 Prompt 和工具
  -> model: 用户消息 + 系统规则 -> AIMessage.tool_calls
  -> tools_condition: 有 tool_calls 才进入 tools
  -> ToolNode: 参数校验 + ToolRuntime 注入
  -> get_spending_statistics: runtime.context 中读取 user 和 billing_service
  -> BillingService.statistics: 调用 TransactionService.all
  -> Fineract 逐页流水 + 中端标注/分类规则
  -> 确定性分类、Decimal 求和 -> AnalysisResult 精确快照
  -> 白名单摘要 -> ToolMessage -> model: 选择结论码 -> 中端模板 -> END
  -> ANALYSIS_READY 引用 -> 前端 GET 精确结果卡
```

按顺序阅读：

1. [演示入口](../../scripts/testing/demo_spending_agent.py)：通过 `AuthService.login/authenticate` 确定身份，校验租户；密码通过 `getpass` 输入，退出时撤销演示会话。
2. [上下文](../../apps/backend/agent/context.py)：`billing_service` 可选以兼容原有余额调用；洞察调用必须注入它。用户身份不是模型参数。
3. [注册表](../../apps/backend/agent/registry.py)：`insights` 绑定统计、异常 Tool 与洞察 Prompt；注册领域不会自动改变现有 HTTP 接口启用的领域。
4. [公共图](../../apps/backend/agent/graph.py)：`bind_tools` 给模型工具契约；模型选择调用后，真正执行函数的是 `ToolNode`。正常示例是两次模型返回、一次 Tool 调用。
5. [统计 Tool](../../apps/backend/agent/tools/insights.py)：`SpendingStatisticsInput` 使用 Pydantic 定义三个参数、禁止额外字段并检查日期顺序；函数只将可信用户及参数交给 Service。
6. [账单 Service](../../apps/backend/services/billing_service.py)：`statistics` 汇总非撤销交易；只有 `expense` 纳入消费分类，转账、定存划转等独立列出。
7. [流水 Service](../../apps/backend/services/transaction_service.py)：先校验账户归属，再完整读取分页、规范化交易，并优先采用人工类别，其次匹配规则，否则保留“未分类”。
8. [洞察 Prompt](../../apps/backend/agent/prompts/insights.py)：约束调用时机、账户/时间澄清、结果表达和真实性；权限仍由 Service 强制执行。

`AgentState.messages` 保存模型可见的消息链，`AgentContext` 保存执行依赖。HTTP `events` 仅携带 `ANALYSIS_READY` 引用；模型只收到白名单摘要，精确结果由授权 GET 返回。真实演示应使用项目测试身份，勿在自定义日志/回调打印完整状态。

工具内部使用 `_SpendingToolInput` 扩展业务参数模型：ToolNode 在参数校验前注入 `runtime`，所以内部 Schema 需接受它，再用 `InjectedToolArg` 将它从模型可见 Schema 中移除。这样既能禁止伪造 `user_id` 等额外字段，又不会误拒绝框架注入的上下文。测试直接检查模型只能看到三个业务参数。

一个请求使用一个数据库 Session。演示调用配置 `max_concurrency=1`，避免多个 Tool 同时使用这个 Session；不要将带 Session 的 BillingService 全局缓存或跨用户共享。

## 3. 第一次：自动化测试，不调用真实模型

在项目根目录执行。先按 [环境要求](../deployment/local-environment-requirements.md) 安装依赖并启动 PostgreSQL。

```bash
apps/backend/.venv/bin/python -m pip install -r apps/backend/requirements.txt
apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py -k agent_insights
```

使用 `-k agent_insights` 是因为现有 runner 已固定收集整个 `tests/integration`；再传文件路径不会可靠地限制为单个文件。runner 使用独立 `bank_agent_test`，测试会重建该库的表。

不具备 PostgreSQL 时，可以先跑 SQLite 快速练习；它不能替代完整 PostgreSQL 回归：

```bash
BANK_TEST_DATABASE_URL=sqlite:// PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  apps/backend/.venv/bin/python -m pytest tests/integration/test_agent_insights.py -q
```

Windows PowerShell 的 PostgreSQL 测试命令：

```powershell
.\apps\backend\.venv\Scripts\python.exe scripts/testing/run_banking_tests.py -k agent_insights
```

测试中的 `ScriptedModel` 固定生成工具调用，**不是在检验模型理解能力**。图、ToolNode、Tool、BillingService 和数据库都实际运行，Fineract 使用受控替身。

主要成功用例准备 205 笔各 10 元消费、一笔撤销消费及一笔 500 元转账。预期消费 2050、转账 500、餐饮 10、未分类 2040；验证完整分页、撤销排除和转账口径。输出应为测试通过，无外部模型请求。

其余用例覆盖无数据、非法参数、伪造身份字段、越权账户、上游失败、分页不完整、上下文缺失和手工脚本的结果检查。失败图必须在第一次模型返回之后中断，不再生成成功回答。对抗用例证明确定性边界，不证明真实模型能抵抗所有提示注入。

## 4. 第二次：真实模型 + 本人真实账单

需要已有中端用户及 Fineract 身份映射、运行中的中端 PostgreSQL/Fineract、有效模型配置。脚本直接调用图和 Service，不需要启动 FastAPI 或 React。

```bash
apps/backend/.venv/bin/python scripts/testing/demo_spending_agent.py \
  --username alice --period 2026-09
```

按提示输入自己的 Demo 密码；脚本不会打印账户清单，未传 `--account-id` 时选取本人第一个合格账户。不要把密码写进命令行，不要假设 Alice 的账户一定是 1。

已知本人账户 ID 后可以追加 `--account-id`，例如把下面的 `123` 替换成刚查到的 ID：

```bash
apps/backend/.venv/bin/python scripts/testing/demo_spending_agent.py \
  --username alice --account-id 123 --period 2026-09
```

演示脚本每次模型请求默认等待 60 秒，可添加 `--model-timeout 120`（范围 1–300 秒）。正常流程请求模型两次，该设置是每次请求的网络超时，不是整个流程的总时限；无自动重试。公共图默认 20 秒，统一 HTTP 入口明确配置为 60 秒。若出现 `DEMO_MODEL_TIMEOUT`，完整查询与回答未验收，脚本仍会清理登录会话。

PowerShell 使用 `.\apps\backend\.venv\Scripts\python.exe`，参数相同。月份必须明确为 `YYYY-MM`，脚本根据日历处理月末及闰年，不接受“上个月”。查询区间含起止日期。

脚本默认只打印 Tool 名称、安全摘要、确定性结论与技术调用耗时，不打印金额、商户、原始账户/交易引用、模型自由回复或完整参数。检查实际调用、请求级不透明引用/日期和白名单摘要；无调用、参数错误、失败或没有最终回答均非零退出，失败仍回滚并撤销演示会话。精确数值在前端结果卡与普通业务接口核对，不能用自然语言回复代替事实核验。

真实结果不应断言固定金额。无流水是合法结果；有交易但没有 `expense` 不等于账户没有交易。`transaction_count` 是非撤销交易总笔数，不是消费笔数。统计查询不创建账单报告；登录/退出仍会写中端会话与审计记录。

## 5. 失败时从哪里排查

| 现象 | 检查点 |
| --- | --- |
| 缺少 langchain_core/langgraph | 当前虚拟环境是否按 requirements.txt 安装完整，运行 pip check |
| PostgreSQL 连接失败 | `.env` 数据库配置、Docker 状态；测试库使用专用 runner |
| 登录失败或锁定 | 使用已有用户的真实 Demo 密码；修改 `.env` 不会自动更新已建账号 |
| 没有本人账户 | 初始化身份映射与 Fineract 数据，不能改用其他用户账户 |
| AGENT_CONTEXT_MISSING | 构造 AgentContext 时是否传了请求级 BillingService |
| TRANSACTIONS_CHANGED | 分页期间数据变化或不完整；不要使用部分结果冒充完整账单 |
| 模型没调用工具 | 脚本输出实际次数及模型诊断；若回复重复确认已提供的账户/日期，属于过度澄清，不能当成查询成功 |
| finish_reason 为 length | 模型输出触及 Token 上限，可能未生成完整调用/回答；与正常 stop 后澄清不同，按诊断分别处理 |
| 模型/网络错误 | 模型配置、网络和服务可用性；不要输出 API Key 排查 |
| 回答遗漏或不忠实 | 这是模型验收失败，记录样本；执行模型预算为 1024 tokens；最终文字由中端白名单模板渲染 |

## 6. 历史异常查询练习（2026-10-22 前的契约，勿直接复用精确返回）

不复制统计业务实现，只复制它的调用方式：

1. 在 `tools/insights.py` 新增 `get_spending_anomalies`，采用相同的三个参数与运行时身份。可复用现有输入模型；若重命名共享模型，同步测试及说明。
2. 使用 `runtime.context.billing_service.anomalies(user, account_id, from_date, to_date)`，不直接查询数据库或 Fineract。
3. 结果保留 `rule`、`transaction_ids`、`evidence`、`status`、`candidate_only`，不把候选称为已确认盗刷。
4. 为洞察 Prompt 增加异常查询触发和结果解释。没有命中规则不能保证所有交易安全。
5. 写成功、无候选、越权、失败测试；大额规则需至少 10 个历史样本，同日相同已知商户/金额才能产生重复候选。
6. 测试通过后，把异常 Tool 加入 `insights` 注册项。不要提前登记空函数。

用户已通过 `AnomalyModel` 驱动公共图，覆盖空结果、重复消费候选和上游失败时不再调用模型。演示脚本新增 `--query anomalies`，检查真实调用 `get_spending_anomalies`、账户/日期参数、候选列表及必要字段；默认统计模式保持兼容。ToolMessage 的空列表可能直接是 Python 列表，不能总是调用 json.loads。

真实模型手工命令（项目根目录）：

```bash
apps/backend/.venv/bin/python scripts/testing/demo_spending_agent.py \
  --username alice --period 2026-09 --query anomalies --model-timeout 120
```

密码交互输入，账户从本人列表选择。自动校验不代表模型回答忠实：人工比对交易引用、证据和候选语义；空列表只能表述为未命中当前规则。本轮不自动调用付费模型或读取真实用户账单。

图测试使用替身决定调用哪个 Tool；它验证图、工具与 Service 的连接，不证明真实模型的意图识别和回答忠实性。

## 8. 固定洞察域接口备选教程（非当前统一入口目标）

本节是此前固定洞察域接口的备选教学步骤，不代表接口已经存在。用户已明确改为统一前端入口、模型候选路由及中端裁决，当前实施应优先阅读 [统一对话入口教学](unified-agent-entry-guide.md)，继续复用 `/api/agent/messages`。下述独立接口方案不作为当前目标，也不应让前端用关键词选择领域。

```text
React 对话提交 message
  -> 统一 apiRequest 注入 Bearer Token
  -> 洞察路由：Actor 认证、Db 提供请求级 Session
  -> 构造 AgentContext：当前用户 + AccountService + BillingService(db)
  -> 仅启用 insights 的公共图
  -> 模型选择统计或异常 Tool -> 同一 Service
  -> 最终回答 + trace_id + events
  -> React 展示回复或错误
```

### 8.1 复用现有执行与审计逻辑

修改 `apps/backend/api/agent.py`：把 `send_message` 从 `trace_id = str(uuid4())` 到末尾的 try/except 提取为普通函数 `_run_agent_message(body, user, db, graph, context)`。

- 原有 `graph.invoke` 的 context 改用传入的 `context`。
- config 同时设置 `recursion_limit=4` 和 `max_concurrency=1`，同一请求的 Session 不并发使用。
- 保留 `_final_answer`、响应模型、成功与失败审计、上游错误映射，不把原始 ToolMessage、账单、用户问题、Token 写入审计。
- 对数据库错误应先 rollback 后再处理失败审计，避免失败事务导致审计再次报错。
- 旧 `send_message` 调用这个 helper，并传入原有账户上下文；旧路由、认证和响应保持兼容。

不要复用脚本 `inspect_result` 作为 HTTP 判定规则。脚本针对一个明确任务要求一次指定调用；HTTP 对话允许因缺账户/日期而不调用工具、先返回澄清问题。该区别不意味着可以跳过业务权限或捏造结果。

### 8.2 新增固定洞察域依赖与路由

在相同 API 模块增加 `from api.context import billing_service`，然后添加：

```python
@lru_cache
def get_insights_agent_graph():
    return build_agent_graph(("insights",))


@router.post("/insights/messages", response_model=AgentMessageResponse)
def send_insights_message(
    body: AgentMessageRequest,
    user: Actor,
    db: Db,
    graph: Any = Depends(get_insights_agent_graph),
):
    context = AgentContext(
        user=user,
        account_service=get_account_service(),
        billing_service=billing_service(db),
    )
    return _run_agent_message(body, user, db, graph, context)
```

`@lru_cache` 只缓存图；BillingService、Session 和用户不能缓存。这个 router 已被 main.py 注册，路由前缀 `/api/agent` 会自动拼接完整路径，无需创建第二个 FastAPI 应用。

### 8.3 前端调用与请求协议

请求：`POST /api/agent/insights/messages`，请求头沿用登录后的 Bearer Token；JSON 只接受 `message`，例如：

```json
{"message": "查询账户 1 在 2026 年 9 月的异常消费候选"}
```

这里的账户 1 只是协议例子，实际使用本人账户列表中的 ID。中端通过 Token 确定身份，前端不提交用户 ID、密码或领域配置。

成功响应沿用 `AgentMessageResponse`：`trace_id`、自然语言 `message`、`events`。本轮 Tool 没有写入结构化事件，events 通常为空；不能把 Tool 的候选列表直接塞入仅支持 BALANCE_RESULT 的事件契约。

在 `apps/frontend/src/lib/api.ts` 的 api 对象增加：

```typescript
sendInsightsAgentMessage: (message: string) =>
  apiRequest<AgentMessageResponse>('/agent/insights/messages', {
    method: 'POST',
    body: JSON.stringify({ message }),
  }),
```

`apiRequest` 已包含 `/api` 前缀、Bearer 注入、401 刷新和错误映射，不再手动重复添加。账单对话组件的 `useMutation` 使用 `api.sendInsightsAgentMessage`，并沿用现有 AgentPanel 的发送中、错误和回复展示模式。

当前全局 AgentPanel 的 mutationFn 是 `api.sendAgentMessage`。不要直接全局替换后误以为余额也继续支持：洞察域没有余额 Tool。先让账单专用对话调用新接口；统一入口的任务路由需另外设计。当前请求仍是单轮，不传完整对话历史，不能声称支持“再查上个月”一类跨请求上下文。

### 8.4 接口封装后需要验证什么

- 未登录返回 401；空消息、伪造 user_id 或 enabled_domains 返回 422。
- 用 FakeGraph 验证 Token 对应用户被注入，context.billing_service.db 是当前请求 Session，配置限制串行执行。
- 用受控模型和真实图验证本人统计/异常请求成功、越权拒绝、上游失败正确映射且没有成功回复。
- 余额旧路由回归、成功/失败审计、响应事件类型保持兼容；审计不含金额、完整流水或访问令牌。
- 前端通过已有 API Client 发送 Bearer 与 message，展示加载/错误/回复，401 刷新机制正常。
- 实施新增接口后同步 OpenAPI 快照、API 文档和总规划。前端改动按项目约定执行构建与组件测试。

## 9. 异常模式脚本验证记录（2026-10-17）

账单 Agent 专项 48 项全部通过，包含新增的 20 项异常模式校验与脚本认证清理用例。完整 PostgreSQL 回归为 84 通过、1 失败，失败是已记录的双 worker 调度死锁，不将全量标记为通过。本轮未执行真实模型查询。

新覆盖：空列表/合法候选的 JSON 和原生列表形式，错误工具/账户/日期、无调用/重复调用、失败/缺失/错关联 ToolMessage、错误结构、候选标记错误、没有最终回答，以及统计/异常模式成功、上游失败和模型超时后的退出。实际 ToolNode 返回的原生空列表曾触发 json.loads TypeError，现已修正。

第 8 节仍是待实现接口教程，本次不修改 API 或前端。

后续统一入口教学与验证更新：恢复脚本依赖的 `model_timeout_seconds` 构图参数，新增非空重复候选经认证脚本与真实 ToolNode/Service 的闭环测试。Agent 定向 51 项、最新完整 PostgreSQL 回归 86 项通过；历史调度死锁本轮未复现，未修复其根因。真实模型未执行。统一入口按 [新指南](unified-agent-entry-guide.md) 实施，本节旧测试记录保留为历史证据。

## 7. 本次验证记录（2026-10-14）

- 新增账单 Agent 测试 15 项，随完整 PostgreSQL 中端回归共 52 项通过；保留 1 条现有 Starlette/AnyIO 弃用警告。
- 原有空消息测试补充图依赖替身，确保不要求真实模型密钥；未修改现有 Agent HTTP 接口。
- 脚本帮助入口、受控认证/查询/会话撤销测试通过。真实模型查询未执行，需要按第 4 节由用户交互验收。
- 历史 worker 死锁本次未复现，但未修改相关代码，不能视为已修复。
- 本机系统 ROS 的 PYTHONPATH 会干扰 pip check；`env -u PYTHONPATH apps/backend/.venv/bin/python -m pip check` 通过。

### 手工测试反馈修正

用户登录并选定账户后曾出现“必须实际调用统计工具且仅调用一次”。使用相同问题单独请求模型复现：模型以 `finish_reason=stop` 返回账户与日期确认问题，`tool_calls=[]`，属于过度澄清。提示词现明确：已给出账户编号和绝对日期时直接查询，权限由 Service 校验；脚本使用明确 `account_id` 表述。

失败诊断现在显示实际调用次数、模型可见回复、工具参数、结束原因和 Token 用量，不输出认证信息、完整模型元数据或内部推理。新增测试区分 0 次/2 次调用以及 length 截断；不通过强制调用或忽略验收来隐藏问题。

修正后真实 DeepSeek 选工具探针返回一次 `get_spending_statistics`，账户 ID 与 2026-09-01 至 2026-09-30 日期正确；探针没有执行账单工具。16 项统计专项测试通过，完整真实统计结果及回答仍需按第 4 节重跑核验。
