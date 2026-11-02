# 统一 Agent 对话入口：实现与学习指南

## 1. 当前交付

2026-10-18 接入统一聊天，2026-10-19 扩展全账户查询，2026-10-22 完成余额/统计/异常的隐私结果通道和个人 Isolation Forest；此后在同一入口接入账单报告、订阅规划，以及成员 A 的本人流水、联系人/转账、卡片、定时转账和 AA 收款。账单隐私与模型验收以 [专项报告](../testing/billing-privacy-ml-validation.md) 为准，成员 A 任务状态见 [任务拆分](../project/agent-member-a-task-breakdown.md)。没有新增领域专用聊天接口。

```text
AgentPanel -> api.sendAgentMessage(message, query_context, recent_user_history)
 -> Actor 认证 + 请求级 Db
 -> route_domains：模型提出 DomainRoute
 -> approve_domains：中端校验准入、注册表和允许集合
 -> get_agent_graph：按规范化领域 tuple 缓存图
 -> AgentContext：当前用户 + 获准领域 Service + trace + 请求级引用/日期 + 私有结果与事件收集器
 -> 普通洞察：model -> ToolNode -> Service -> AnalysisResult 精确快照
 -> 报告查看：中端解析期间/账户范围 -> view_bill_report -> BillReportService 复用或缺失时入队
 -> 写请求：model -> ToolNode -> Service -> Action/草稿/AA 请求
 -> 订阅：确定性意图 -> 私有结果/规则/取消 Action
 -> trace_id / message / 类型化分析、报告、订阅或 Action 事件 -> 原聊天框
 -> 私有结果卡，或跳转报告/订阅/Action 页面完成读取、确认、OTP、执行和核对
```

前端的账户和月份按钮生成完整自然语言问题；自由输入和按钮均发送当前 query_context。前端不判断领域，不提交用户 ID、domain 或授权结论。中端校验所选账户归属，Service 每次查询仍独立鉴权。

## 自然语言打开账单报告与异常核实状态

用户说“查看我的年度账单报告”“查看我的月度账单报告”时，`api/agent.py::send_message()` 将请求裁到 `insights` 域，`parse_bill_report_view_intent()` 按中端上海日期确定本年/本月；“看看我上个月的账单报告”及文字写明的年月优先于前端旧月份。账户范围按文字指定的全部账户、聊天选择、否则本人全部合格账户的顺序确定。`agent/graph.py::call_model()` 将已解析意图交给唯一的 `view_bill_report` Tool，模型不会重新挑范围。

`agent/tools/insights.py::view_bill_report()` 只拿运行时用户与账户引用，调用 `BillReportService.view_or_generate()`。Service 在用户行锁内精确匹配本人、期间、单账户/全账户范围，优先返回最新完整/部分报告，再返回正在生成任务，最后返回已有失败记录；仅完全没有匹配记录时才排队新报告。`BILL_REPORT_OPENED` 只带引用和状态，图不再请求模型总结；前端状态卡通过现有状态接口轮询，提供详情页或报告列表链接。失败后重新生成必须由用户主动操作，超时先去报告列表核对。

异常分析快照中的 `status` 是生成时状态。本人 GET 在不改写快照的情况下附加 `current_review_status`；普通异常 API 提供实时 `status`。`AnomalyReviewControls` 被聊天、洞察页和实时账单共用，已选择状态按钮禁用并显示“已确认/已忽略”，另一按钮保留纠正入口；提交期间禁用两项，成功更新同候选缓存并刷新异常/私有结果，失败显示原因且保留旧状态。历史报告证据保持快照。

## 全账户统计与异常查询（2026-10-19）

统计和异常沿用现有 Tool 名称。模型必须提供 `account_ref`：请求级不透明引用查询本人单账户，显式 `null` 查询本人全部合格 CNY 普通储蓄账户。省略字段、原始账户 ID、布尔值、未知引用及身份/账户列表参数均拒绝；缺失查询范围不能自动扩大为全账户。

用户明确说“全部账户/所有账户”时，文字范围优先于界面单账户选择；未说明范围时继续使用界面账户。前端新增“全部账户统计”和“全部账户异常”，生成明确问题并沿用统一接口及月份上下文。HTTP 消息请求格式保持不变；2026-10-22 增加私有读取路由、策略配置、依赖及中端迁移 0006。

- 统计 Service 精确结果继续包含 `account_id/account_ids`、`totals/categories/monthly`、截止时间和非原子快照标记；这些只写入私有快照。ToolMessage 只有 `analysis_id/kind/status/insight_codes/main_category`。
- 异常普通 API 默认单账户候选列表、全账户包装对象；可选 `include_metadata=true` 统一包装检测状态。Agent 精确结果使用带日期、`items` 和 `detection` 的私有快照，模型只接收定性结论码。跨账户交易必须用 `transactions` 内的账户/交易复合引用区分，同一交易 ID 可在不同账户出现。
- 空账户列表表示没有合格账户；账户非空但无交易/候选需分别解释。异常未命中不能保证交易安全。
- 汇总直接调用 `BillingService`，由中端枚举账户、检查归属与完整分页；模型不逐账户求和。任一账户读取失败时整体失败。
- 统一入口保留选择账户的归属校验、查询上下文注入、无 Tool 时的事实/事件拦截和脱敏 `tool_calls` 审计。

验收时在界面选择一个本人账户，发送“查询我所有账户在 2026-09 的消费分类统计”及“查询我所有账户在 2026-09 的异常消费候选”。检查对应审计中实际 Tool 的 `account_ref` 为 `null`，并与业务接口省略 `account_id`、同日期的结果核对。自动图测试和浏览器 API 替身测试不代替真实模型验收；本轮具体结果记入总规划。

## 2. 源码阅读顺序

1. `apps/backend/agent/router.py`：DomainRoute 结构化识别，目录包含 accounts/insights/payments/cards/payment_plans/subscriptions。approve_domains 拒绝重复、未知、未授权领域，并禁止订阅与其他领域混用，再规范化顺序。出现“账户编号”不等于需要余额域；只有查余额/流水才选择 accounts。
2. `apps/backend/api/agent.py`：先认证再调用路由，二次裁决返回的领域；只注入获准领域需要的 Service。Action 已提交但最终模型转述失败时返回确定性恢复消息和原事件。路由依赖和图工厂可独立替换做测试。
3. `apps/backend/agent/registry.py`：resolve_agent 将批准域的 Prompt 和 Tools 同时装配；登记领域不等于向所有请求开放该域。
4. `apps/backend/agent/graph.py`：模型基于匹配 Prompt/Tools 提取参数；执行前检查本轮累计调用不超过 3 次、工具名属于当前批准集合、无非法调用格式，整批不合格时一个也不执行。
5. `apps/backend/agent/tools/`：查询 Tool 把精确结果留在中端；支付/卡片/计划 Tool 只接受可展示引用并复用已有 Service/Action，绝不直接扣款或返回完整卡号。
6. `apps/frontend/src/components/agent/agent-panel.tsx`：加载本人账户，携带最近最多 8 条用户消息，显示私有分析卡和 Action 卡；写请求统一跳转通用操作页。

工具执行串行（max_concurrency=1），避免同一请求的数据库 Session 并发使用。图缓存不包含用户、Session 或业务 Service。默认通过认证的 Demo 用户可使用六个已注册领域；订阅扫描/取消必须单独发起，联系人、账户、卡片、计划、AA 和订阅归属仍由每次 Service 调用强制校验。

## 3. 两种模型选择与执行预算

| 阶段 | 输入 | 输出 | 边界 |
| --- | --- | --- | --- |
| 路由模型 | 问题与简短能力目录 | DomainRoute.domains | 无银行事实、无业务执行权 |
| 中端裁决 | 候选领域与允许集合 | 规范化领域 tuple | 拒绝未知、重复、未授权；无全工具兜底 |
| 执行模型 | 公共与领域 Prompt、工具契约、消息 | Tool 调用及最终回复 | 工具白名单与累计调用预算在执行前检查 |

```json
{"message":"9月份的消费情况", "query_context":{"account_id":1,"period":"2026-09"}}
```

这里的 1 是示例，实际账户应从本人账户列表选取。该问题通常批准 insights，执行统计与异常两个 Tool；若还询问余额，批准 accounts + insights，最多调用三个只读 Tool。

模型可发出一批独立查询，也可根据结果继续选择；每次 ToolNode 实际执行，精确结果留在中端，只有白名单定性摘要作为 ToolMessage 返回模型。计算、分类、权限和异常规则仍在 Service；不让模型重新求和、编造商户或将候选当成盗刷。

路由输出最多 256 tokens、执行输出最多 1024 tokens；每次网络请求超时 60 秒、零自动重试。执行递归上限 8，业务 Tool 累计上限 3；递归上限不是调用预算，两者分别约束。

前端聊天 POST 使用 300 秒等待时限；因可能保存报告或订阅候选，超时返回 WRITE_RESULT_UNKNOWN、retryable=false，提示先核对，不自动重发。普通查询 10 秒、业务写入 30 秒的底座设置保持原样；不会自动重发模型查询。真实集成中发现 30 秒的通用 POST 超时会提前取消较慢的模型答复，已通过专项测试覆盖。

## 4. 错误与事实边界

- 路由超时/解析失败明确报错，不启用所有领域。无关或未支持问题返回能力范围提示，不调用业务图。
- 没有任何工具调用时，中端不透传未经核实的银行答复或事件，明确“本次未执行查询”并提供完整提问示例，不断言一定缺少账户或日期。
- 工具异常向外传播，终止生成成功结论；失败前 rollback，再尝试写审计。审计失败不掩盖原始异常。
- 成功审计记录 trace、批准域、工具名及不透明引用/起止日期参数；失败记录错误类型，不保存用户原始问题、金额、身份密钥或完整流水。复用底座递归脱敏和 trace 索引。
- 新请求统一发送 `ANALYSIS_READY` 引用事件，余额/统计/异常精确数据都通过授权 GET 获取；`BALANCE_RESULT` 只保留旧类型兼容。默认 24 小时有效，410 时需重新查询；分析快照不等于已保存报告。
- 账单数据是逐页读取，非原子快照。异常是候选，空列表不保证安全；LARGE_V1 的历史基线是同类别，不是同商户。
- 模型只获得白名单摘要。细粒度日期、小样本及每日超过 10 个不同规范化范围只返回通用状态；精确结果本人仍可查看。最终输出由中端结论码模板渲染，模型不能补充金额或欺诈判断；不构成差分隐私。用户主动输入仍可能进入模型，账户编号在路由前占位化，执行时使用请求级引用。

## 5. 如何从前端获得结果

启动 PostgreSQL/Fineract，准备已有 Demo 用户、身份映射及硅基流动模型配置。Linux 在项目根目录启动中端：

```bash
env -u PYTHONPATH NO_PROXY=localhost,127.0.0.1,::1 no_proxy=localhost,127.0.0.1,::1 \
  apps/backend/.venv/bin/python -m uvicorn main:app --app-dir apps/backend --host 127.0.0.1 --port 8080
```

在 apps/frontend 执行 npm run dev -- --host 127.0.0.1 --port 5173，访问 http://127.0.0.1:5173，使用自己的 Demo 密码登录。

1. 打开智能助理，点击“查余额”。
2. 从“账单账户”选择本人账户，月份选 2026-09 或有流水的月份，点击“消费统计”。
3. 点击“异常候选”，核对检测证据；没有候选是合法结果。
4. 自由输入完整组合问题，例如“查询我的余额，并分析账户 1 在 2026 年 9 月的消费分类统计和异常消费候选”，账户 ID 换成自己的实际值。

月份默认上一个上海自然月。自由输入可使用所选账户和月份；明确文字中的账户、完整日期优先。只说“9月份”使用所选月份的年份，没选月份则需要补年份。“本月”“上个月”由服务端上海当前日期确定，优先于选择器月份，首尾日期均包含。日期参照按请求生成，不进入缓存图。

当前没有服务端会话持久化。前端发送最近最多 8 条用户消息，不发送旧助手回复、Tool 结果或授权状态；刷新页面或换设备后不会恢复历史。提醒提前量使用30分钟本人专属澄清引用，原月份、金额条件和订阅范围由中端持久化，不依赖不可信聊天历史。Agent 已接入报告、订阅及成员 A 的支付/卡片/计划请求；真正资金或状态执行仍需在通用 Action 页面确认、必要的 OTP 和核对。分类修改、财富和跨场景 DAG 尚未接入 Agent。

### 续费、自动提醒和预算 Agent 链路

```text
AgentPanel.send → api.sendAgentMessage → POST /api/agent/messages
 → Actor/Db认证 → parse_subscription_intent（按中端上海日期确定月份和筛选）
 → subscriptions 域裁决 → AgentContext 注入用户、SubscriptionService、SubscriptionPlanningService
 → graph.call_model 将已解析的订阅意图转成 manage_subscription_request
 → Tool 读取 VERIFIED 订阅并调用 forecast / 规则 / 预算 Service
 → 详细结果保存 SubscriptionAgentResult，只回传 result_id 和安全摘要事件
 → send_message 使用确定性回执；前端 EventCard 以 Bearer GET 读取 /api/agent/subscription-results/{id}
 → 续费卡跳转 /subscriptions；提醒规则、预算卡链接到管理区
```

无提前天数的提醒请求先查询并展示符合条件的预计项目，再创建 `SubscriptionClarification`（本人专属、30分钟）；回答“提前3天”携带 `clarification_id`，Service 才创建单条目标月动态规则。补充回答只填提前天数，范围、金额和目标月份不能被覆盖。`SubscriptionPlanningService.tick_notifications()` 由现有独立 worker 每30秒调用，上海时间09:00之后生成站内通知；错过的提醒节点只对尚未发生的预计扣费合并补发。预算评估把当月实际订阅扣费与未来预计金额去重合并，已知超额可报警；数据不完整时不能确认预算充足。点击建议的可取消项目仍创建既有 YELLOW Action，用户必须在 Action 页面明确确认。

## 6. 验证与学习练习

```bash
apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py -k agent
apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py
```

前端在 apps/frontend 中执行 npm test、npm run build 和 npm run test:e2e。浏览器测试需先执行 npx playwright install chromium。test_agent_routing.py 覆盖裁决、日期及预算；test_agent_privacy.py 和 test_agent_insights.py 覆盖私有通道、真实图/Service、组合查询、越权及 CLI；test_anomaly_detection.py 验证合成模型；agent-chat.spec.ts 用明确接口替身检查桌面及 390px 视图，不把它当成真实模型验收。

实际服务验收及最新数量以 docs/project/master-plan.md 的 2026-10-22 记录为准。受控模型测试只证明程序链路；真实模型选工具、参数与回答忠实性需要另验。历史 worker 死锁即使本轮未复现，也不代表根因已修复。

类型化私有分析和成员 A Action 事件已实现。后续可增加结构化澄清状态或服务端多轮会话；每一项须独立确认范围，不能通过受限前端历史推断已经拥有长期记忆。

参考：[LangGraph Workflows and Agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)、[结构化输出](https://docs.langchain.com/oss/python/langchain/structured-output)。

## 7. 本次集成与恢复

集成分支为 `feature/unified-agent-integration`，集成提交为 `2cc8931`，基线为 `875da8c492471acde2d064c48577c1b73ccf554e`。2026-10-18 已复用 VS Code 的 Git askpass 认证成功刷新指定远程分支，确认远端与该基线一致，无需额外合并；未自动推送。

原分支 `insight-agent` 仍指向 `7d77fc01dc36c2d17027ff5007bc6ce97063c9a4`。修改和未跟踪源码保存在 stash 对象 `44db5b94fc48ad3c7caaa81ccb97b8b4488c814b`，同时由固定引用 `refs/backups/insight-agent-before-integration-20261018` 保持可达；未删除备份。只迁入银行 Agent，独立工单教程保存在备份中，忽略的本机虚拟环境仍留在原目录。

要恢复原开发现场，先保证当前集成分支修改已提交，再执行：

```bash
git switch insight-agent
git stash apply refs/backups/insight-agent-before-integration-20261018
```

这只恢复 Git 工作区，不会回滚数据库。本机中端现已由 `0001` 经 `0005` 升级至 `0006`，原分支旧模型不应继续连接升级后的库进行开发写入。需要重现原环境时，把升级前 `.runtime/bank-agent-before-integration-20261018.dump` 恢复到独立数据库，并显式配置对应 DATABASE_URL；不要覆盖现用库。

本次统一集成不执行 Demo Reset、Seed 或真实资金操作。卡片、订阅、多账户账单、本人互转、风评和审计的源码以完整底座为准；Agent 暴露账户/洞察/报告/订阅查询以及支付、卡片、计划支付的安全请求 Tool，所有写请求仍由既有 Action 状态机控制。

## 8. 2026-10-18 历史集成验收记录（当前证据见专项报告）

最终 PostgreSQL 158 项、前端组件/API 30 项、Playwright 11 项及生产构建通过；pip check 无依赖冲突。OpenAPI 仍为 80 路径、107 操作，快照与运行源码一致。Oxlint 有 5 条既有警告，Starlette 有 1 条弃用警告。

真实前端验证余额、统计、异常、省略年份、相对月、三工具组合共六个场景；审计 `tool_calls` 的名称和账户/日期均匹配，统计与余额金额和普通业务接口一致，异常候选的交易引用、规则证据及未核实状态一致。桌面与 390px 截图无横向溢出。组合请求约 101 秒，说明聊天等待时限需要覆盖多个模型步骤；这不是供应商延迟保证。

真实证据（忽略，不提交敏感内容）：`.runtime/unified-agent-live.json`、`.runtime/integration-*.png`。完整自动回归结果为 `.runtime/unified-integration-tests.xml`。最新 trace 和已完成的远端认证核对记录在总规划中。

## 订阅识别完整链路（2026-10-27）

1. agent-panel.tsx 的 submit → send → api.ts 的 sendAgentMessage → apiRequest/fetchWithTimeout，携带 Bearer Token。
2. core/deps.py 的 get_identity/get_user → AuthService.authenticate；api/agent.py 的 send_message 生成 trace_id。
3. routing_message → router.py 的 route_domains 提出候选 → approve_domains 校验 ENABLED_DOMAINS、注册表与单独扫描限制。
4. api/context.py 的 subscription_service(db) 创建请求级 Service；AgentContext 保存可信用户、Service、trace 和事件列表。
5. get_agent_graph → build_agent_graph → resolve_agent，绑定 subscriptions Prompt 与 scan_subscriptions。
6. call_model 请求一次空参数工具；ToolNode 注入隐藏 runtime；tools/subscriptions.py 调用 SubscriptionService.scan。
7. _candidates → AccountService.list_accounts/get_account → TransactionService.all/list → FineractClient.search_transactions。完整读取后 _best_run 判断稳定周期，scan 在用户锁内合并候选及证据，写 SUBSCRIPTIONS_SCANNED 并提交。
8. Tool 将摘要写 subscription_events，只返回 completed；after_tools 直接 END。send_message 生成固定文案，序列化 SUBSCRIPTION_SCAN_COMPLETED，关联 AGENT_MESSAGE_COMPLETED 审计。
9. 前端 onSuccess 刷新 subscriptions/subscription/subscription-renewals 三组缓存并展示 EventCard。点击入口关闭面板、导航 /subscriptions；列表和详情仍走 SubscriptionService.list/detail。

matched_candidates 为本次匹配，created 为新增，found 为全部历史保存记录，三者不可混用。聊天不携带商户、金额和证据；零匹配不代表没有订阅。模型未调用 Tool 时不会生成成功卡。

扫描固定本人全部合格账户最近800天，账单账户/月选择不改变范围。用户明确限定账户/日期时由 Prompt 澄清，不默认扩大请求；当前单轮消息不携带前文，“好的”不能自动承接上次澄清。

## Demo 订阅取消 Agent

AgentPanel.send → api.sendAgentMessage → /api/agent/messages → 身份认证 → route_domains/approve_domains → subscriptions 图 → request_subscription_cancel。Tool 从可信上下文取本人和原话，只接受原话中出现的商户名称，规范化后在本人订阅中精确匹配且须唯一、Demo。常见否定表达由中端拒绝，不能覆盖所有自然语言，最终确认仍是安全边界。Tool 调 SubscriptionService.request_cancel 创建或复用 Action；图直接 END，事件只返回 Action ID 和状态，不向模型返回确认快照。前端卡片进入 ActionPage；GET /api/actions/{id} 重验归属并展示快照，用户点击确认后 ActionService.confirm/execute → SubscriptionService.execute_cancel 重新核对快照 → DemoMerchantAdapter。仅 SUCCEEDED 为成功。

取消请求使用请求级生成的幂等键；有效或处理中请求由 Service 复用，明确失败、撤回或过期后可重新申请；超时先核对，不自动换键重发。未实现批量取消或真实第三方取消；续费提醒的提前量澄清可通过本人短期引用承接一次补充。

2026-10-28：即时查询“下个月有哪些自动扣费，超过15元都告诉我”按金额严格大于15元筛选结果，不创建提醒；“下个月的扣费提前3天告诉我”创建提前3天提醒。提醒澄清的补充回答必须只给提前量，附加新月份或金额条件时按新请求解析。否定表达不会创建规则，不支持的提前天数返回明确错误；未解析出可信意图时，模型也不能直接执行订阅管理 Tool。

### 完整商户名的取消请求

对“帮我取消腾讯视频会员订阅”这类完整单一请求，中端先以登录用户的订阅列表作规范化精确匹配：整句只允许简单请求前缀、取消/退订、完整商户名及可选订阅后缀，且必须唯一命中 Demo 商户。这个确定性结果用于领域裁决；图仍先调用执行模型。如果模型未调用 Tool，或将商户名截短为完整名称的一部分，中端补全为匹配到的完整名称并调用取消请求 Tool。多个商户、否定语句、混合业务或无法唯一匹配时不走这条路径；Tool 和 Service 仍执行归属、状态、Demo、Action 和确认校验。模型不可用仍报错，不能凭空称请求已提交。
