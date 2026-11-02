# 演示功能全量验收记录（2026-10-31）

## 1. 目的与边界

本记录按照演示功能清单完成“第一轮发现问题 → 修复 → 使用同一验收口径复测”。报告保留第一轮失败事实，同时以最终复测结果作为当前结论；每项都记录输入、执行方法、实际回复或状态以及是否成功。

本轮已在用户允许直接测试模型后调用硅基流动 `deepseek-ai/DeepSeek-V3.2` 完成在线路由评估。没有执行 Fineract Seed、Demo Reset、OTP、真实转账、真实卡消费、真实定存申购/赎回、生日任务 Hold/Release 或外部商户付款；涉及资金的自动化使用隔离数据库和受控替身，不能替代真实资金验收。

测试分支：`codex/full-agent-integration`。

## 2. 总体结果

| 检查项 | 结果 | 证据与说明 |
| --- | --- | --- |
| 中端 PostgreSQL 全量集成测试 | 通过 | 350 passed，0 failed，0 skipped；最终代码复跑耗时 266.447 秒 |
| 前端 Vitest | 通过 | 15 个测试文件，98 passed |
| Oxlint | 通过 | 0 error，0 warning |
| TypeScript/Vite 生产构建 | 通过 | 2019 modules；入口主 JS 319.03KB / gzip 101.37KB；无大包警告 |
| Playwright 浏览器测试 | 通过 | 30 passed，0 failed；桌面和 390px 全部通过 |
| DeepSeek 在线路由评估 | 通过门槛 | 最新完整评估：功能 119/120（99.17%）、安全 30/30（100%）；随后转账域定向复测 20/20 功能、5/5 安全 |
| `pip check` / Python compileall | 通过 | 无损坏依赖，后端与脚本可编译 |
| 真实资金与 OTP 场景 | 本轮未执行 | 未取得 Seed/Reset/OTP/资金写入授权，不能用自动化替身冒充真实资金验收 |

原始机器结果保存在 Git 忽略文件：`.runtime/demo-validation-backend-20261031-final.xml`、`.runtime/agent-routing-evaluation-20261031-final.json` 和 `.runtime/agent-routing-evaluation-20261031-transfers-recheck.json`，不得提交。

## 3. 具体执行方法与终端结果

### 3.1 中端全量测试

在项目根目录执行：

```powershell
.\apps\backend\.venv\Scripts\python.exe .\scripts\testing\run_banking_tests.py `
  -q --junitxml=.runtime\demo-validation-backend-20261031-final.xml
```

测试入口创建/复用隔离的 `bank_agent_test` PostgreSQL 数据库，迁移到最新 head，使用受控 Fineract/模型替身运行 Service、API、Action、Worker、权限、幂等和恢复用例，不访问现用 `bank_agent` 资金数据。终端实际结果：

```text
350 tests
350 passed
0 skipped
0 failed
time=266.447s
```

本轮同时复测了 Windows 符号链接拒绝分支。当前机器无创建符号链接权限时，测试以只针对目标路径的 `Path.is_symlink` 替身触发同一拒绝逻辑；Linux/CI 仍创建真实符号链接。因此原来的跳过项现在实际结果为：

```text
test_model_artifact_validation[symlink-invalid_model_path]
PASSED
```

Pytest 仍打印 1 条第三方 Starlette `BlockingPortal` 弃用提示；它不来自项目业务代码，不影响 350 项结果，后续应随 Starlette/TestClient 兼容升级处理，不在本轮冒险单独升级依赖。

### 3.2 前端组件、静态检查和构建

在 `apps/frontend` 执行：

```powershell
npm test -- --run
npm run lint
npm run build
```

实际终端结果：

```text
Test Files  15 passed (15)
Tests       98 passed (98)
Oxlint      0 error / 0 warning
Vite        2019 modules transformed / built in 1.07s
Main JS     319.03 kB / gzip 101.37 kB
Vitest      duration=25.62s
```

修复采用上下文/Hook 与组件分离、账期工具函数抽离、报告分页由用户操作显式重置、Action 页面使用 React Query 更新时间，以及业务页面按路由懒加载；没有通过关闭规则隐藏警告。

最终复核时，直接调用未刷新 PATH 的终端曾误用系统 Node 20.18.1：Vitest 回复 `ERR_REQUIRE_ESM`，Vite 回复“requires Node.js 20.19+ or 22.12+”。这属于错误运行时，不计为业务失败。按部署文档固定 Node 22.23.3 后，上述 98 项、lint 和 build 全部通过；`start-frontend.ps1` 也会拒绝低于 22.12 的版本。

### 3.3 浏览器测试

在 `apps/frontend` 执行：

```powershell
npx playwright test
```

Playwright 自动启动测试前端，在 1440px 桌面和 390px 移动视口运行；全部资金写流程使用网络拦截，不连接真实 Fineract。实际结果：

```text
Running 30 tests using 5 workers
30 passed
0 failed
duration=24.5s
```

Playwright 仅打印环境提示：`NO_COLOR` 因 `FORCE_COLOR` 被忽略；不影响浏览器行为或断言。

第一轮实际失败回复为 `not found`，原因是测试只模拟旧的 `/api/agent/messages`；修复后 Playwright 专用桥完整模拟 conversation、消息入队、SSE、Run 和恢复协议。复测同一输入的实际界面结果为：

```text
用户消息：我还有多少钱？
界面回复：本人储蓄可用余额为 1000 CNY。
结果：通过

私有分析用例回复：查询已完成，精确结果请查看结果卡。
私有余额卡：777.33 CNY；同时读取消费 123.45 和异常商户 Private Cafe
结果：通过；精确数据由认证分析接口读取
```

账单分析、六种异常、月/年报告、订阅扫描/取消/提醒/预算等原来同因失败的桌面与移动测试也全部收到各自结构化结果并通过断言。该桥只进入 E2E，不改变生产 Agent API。

### 3.4 Agent 在线路由评估与 Python 环境

执行：

```powershell
.\apps\backend\.venv\Scripts\python.exe .\scripts\testing\evaluate_agent.py --live --confirm-external-model-cost `
  --output .runtime\agent-routing-evaluation-20261031-final.json
.\apps\backend\.venv\Scripts\python.exe .\scripts\testing\evaluate_agent.py --live --confirm-external-model-cost `
  --scenario transfers --output .runtime\agent-routing-evaluation-20261031-transfers-recheck.json
.\apps\backend\.venv\Scripts\python.exe -m pip check
.\apps\backend\.venv\Scripts\python.exe -m compileall -q .\apps\backend .\scripts
```

实际回复：

```text
完整在线评估：functional=119/120 (99.17%), security=30/30 (100%)
门槛：functional >= 95% PASS；security = 100% PASS
唯一未命中：transfers_04 “搜索联系人别名妈妈。”，期望 payments，实际 []

补充确定性联系人路由后，转账域定向在线复测：
functional=20/20，security=5/5，failures=[]

No broken requirements found.
compileall=PASS
```

完整评估之后加入的联系人高置信路由只用于选择业务域，不授予执行权；它修复了“联系人别名/已保存收款联系人”类随机漏判。由于最终定向复测已覆盖该域，没有为了改写成绩而伪称又执行了一次完整 150 条。

## 4. 逐功能测试记录

下表中的“实际回复/结果”来自本轮 Pytest/Playwright 输出、对应断言，以及 2026-10-30 已持久化的真实只读会话；不使用推测文本。真实账户数字、账户尾号、内部引用和金额在写入 Git 前统一脱敏。

| 编号 | 功能与输入 | 具体怎么测 | 实际回复/状态 | 结果与证据 |
| --- | --- | --- | --- | --- |
| LIVE-01 | `我还有多少钱？` | Alice 登录后创建持久化会话，消息入队，由独立 Agent Worker 领取；轮询 Run 并重新读取会话详情 | Assistant：`查询已完成，精确结果请查看下方结果卡。`；Run=`SUCCEEDED`；事件包含 `ANALYSIS_READY`、`TEXT_COMPLETE`、`SUCCESS`；详情恢复 2 条消息 | 通过。精确余额只进入本人结构化卡，不写入报告；持久化会话标题 `repair verification`，2026-10-30 真实只读证据 |
| LIVE-02 | `15分钟后向Bob转账10元`（数字已脱敏） | 第一轮读取真实持久化会话；修复后用在线路由样本、短回复上下文集成测试和受控计划 Service 复测 | 第一轮最终错误创建 `TRANSFER_ACTION_CREATED`，且诚实提示“不会在15分钟后自动执行”；修复后“15分钟/明天9点”等时间词稳定路由到 `payment_plans`，`从<尾号>`只拼接最近两条服务端保存的用户消息用于路由，计划创建/授权测试通过 | 受控复测通过；未再对开发库创建真实计划或执行资金写入，因此真实持久化写链路仍待单独授权 |
| AUTH-01 | 未登录访问、登录、刷新、退出 | `test_auth_ownership_rotation_and_logout`：无 Token 请求账户；登录取得 Token；刷新令牌轮换；旧 Token/退出后 Token 再访问 | HTTP 状态依次包含 `401 → 200 → 200 → 401`；退出接口 `200` | 通过；`tests/integration/test_banking.py` |
| CONV-01 | 创建、入队、幂等、恢复会话 | 创建 conversation；同幂等键重复提交；不同消息复用键；并发提交第二条；Worker 完成两轮并从 SSE cursor 重放 | 创建=`201`；首次/同请求重放=`202` 且 Run ID 相同；键冲突=`409 IDEMPOTENCY_KEY_REUSED`；忙碌=`409 AGENT_RUN_IN_PROGRESS`；完成后消息角色=`user, assistant, user, assistant` | 通过；`tests/integration/test_agent_conversations.py` |
| PAY-01 | 搜索 Bob 并发起普通转账 | 受控 Alice/联系人/账户 Service；先搜索联系人，再调用转账 Tool，检查 Action 和核心转账调用次数 | Tool 只返回安全联系人摘要；Action=`WAITING_CONFIRMATION`；核心资金调用次数=`0` | 通过；`test_contact_search_and_transfer_create_action_without_moving_money` |
| PAY-02 | 本人两个账户互转 | 使用两个本人账户创建 internal transfer Action；再以他人账户和同账户输入测试拒绝 | 合法请求=`WAITING_CONFIRMATION`；越权/同账户返回领域错误；创建阶段核心资金调用=`0` | 通过；`test_internal_transfer_and_card_application_only_create_actions` 与 `test_account_summary_and_internal_transfer_are_user_scoped` |
| PAY-03 | 小额/大额转账、重复提交 | API 创建 Action，确认并按风险级别决定是否 OTP；复用幂等键并故意制造冲突 | 小额最终=`SUCCEEDED`；大额确认后=`WAITING_VERIFICATION`，验证后=`SUCCEEDED`；相同请求重放同 Action，变更请求冲突 | 通过；`test_transfer_boundary_replay_and_conflict` |
| PLAN-01 | 定时转账与 AA | 创建计划草稿、授权、暂停/恢复；创建 AA、按分分摊、参与人付款、取消 | 计划只生成一次 Run 且状态=`SUCCEEDED`；AA 本人份额付款 Action 最终=`SUCCEEDED`；未授权创建阶段不移动资金 | 通过受控测试；`test_schedule_pause_restart_and_unique_worker`、`test_aa_precision_freeze_participant_payment_and_cancel`。真实到期 Worker 未验收 |
| BILL-01 | 全账户统计、分类修正、异常和报告 | 对本人多个账户生成流水；调用统计、规则、异常核实与异步报告 API；Playwright 打开洞察/报告及 Agent 结果卡 | totals、分类和报告快照断言通过；“全部账户洞察”“年度报告原范围重生成”“个人规则管理”可见；Agent 月/年、六种异常及报告结果卡均显示预期内容 | 通过；桌面与 390px 均通过 |
| CARD-01 | 申请、激活、限额、渠道、锁卡、挂失、补卡 | 创建申请 Action；确认后建立零余额账户；激活/提额/解锁/挂失走 OTP；检查补卡复用账户 | 申请=`WAITING_CONFIRMATION → SUCCEEDED`；激活/提额/解锁=`WAITING_VERIFICATION → SUCCEEDED`；锁卡确认后=`SUCCEEDED`；补卡沿用原账户 | 通过受控测试；Playwright 的申请、锁卡和临时卡号查看均通过 |
| CARD-02 | Demo 商户卡消费 | 创建卡消费 Action，先检查渠道/境外/限额/余额，再确认；重复同幂等请求 | 合法交易确认后=`SUCCEEDED`，核心 transfer 只发生一次；拒绝场景不调用核心；浏览器先显示确认页，不伪造已入账 | 通过受控测试；真实 Fineract Demo 消费未执行 |
| SUB-01 | 识别订阅、核实、提醒与预算 | 800 天有界流水替身；扫描月/年周期；创建提前量规则和预算；检查通知补发、本人隔离及 Agent 对话结果 | 扫描保存可解释候选；提醒规则幂等；预算返回 actual/projected/known totals；普通页面和 Agent 扫描/续费/提醒/预算结果均出现预期卡片 | 通过；桌面与 390px 均通过 |
| SUB-02 | 取消 Demo 订阅 | 对 VERIFIED Demo 订阅创建取消 Action；确认后调用 Demo Adapter；再次模拟扣费 | 创建=`WAITING_CONFIRMATION`；确认后=`SUCCEEDED`；取消后 Demo 扣费被拒绝；快照变化时旧确认被拒绝并可重建 | 通过受控测试；不是现实第三方平台取消 |
| WEALTH-01 | 产品、推荐、持有与测评 | 调用财富只读 Tool；读取本人私有 AnalysisResult；用其他用户访问同一结果 | ToolMessage 不含精确利率/金额；本人私有结果=`200`，其他用户=`404`；风险不足时返回结构化测评入口 | 通过；`tests/integration/test_agent_wealth.py` |
| WEALTH-02 | 定存申购与整笔赎回 | 每次创建新五题测评；发起申购/赎回；检查 Action、测评消耗及核心调用 | Action=`WAITING_CONFIRMATION`，风险级别为 RED；创建阶段不移动资金；测评一次性消费；确认/OTP 后受控替身最终=`SUCCEEDED` | 通过受控测试；真实 Fineract 申购/赎回未执行 |
| DAG-01 | 固定生日鲜花+蛋糕任务 | 分别提供日期、账户、鲜花/蛋糕金额；创建任务和 RED Action；受控 Worker 执行 Hold、释放及两笔订单 | 初始任务=`WAITING_AUTHORIZATION`；Action 确认后=`WAITING_VERIFICATION`，验证后=`SUCCEEDED`；完整受控任务及两笔订单=`SUCCEEDED` | 状态机通过；真实商户 Seed、Hold 和付款未执行 |
| SEC-01 | Prompt Injection、OTP/密码/Token/完整卡号输入 | 将攻击和敏感字符串提交持久化会话；重复失败触发写 Tool 锁，再访问普通账户接口 | 敏感输入=`422 SENSITIVE_INPUT_NOT_ALLOWED`；攻击事件只保存规则号，不保存原文；达到阈值后仅 Agent 写操作锁定；账户查询仍=`200` | 通过；`tests/integration/test_agent_conversations.py` |
| UI-01 | 30 项桌面/移动浏览器流程 | Chromium，1440px/390px，使用受控 API 拦截，检查文本、结果卡、按钮、路由和横向溢出 | `30 passed / 0 failed / 24.5s`；原 16 个 `not found` 场景均通过持久化会话桥收到 SSE/Run 结果 | 通过；测试替身与当前生产协议一致，但不等同于真实 Fineract 写操作 |

### 4.1 已持久化真实对话摘录（脱敏）

```text
User: 我还有多少钱？
Assistant: 查询已完成，精确结果请查看下方结果卡。
Run: SUCCEEDED
Events: EXECUTING → TEXT_COMPLETE → ANALYSIS_READY → SUCCESS

User: 15分钟后向Bob转账10元
Assistant: 找到了一个名为“Bob”的联系人。现在我需要确认您要从哪个账户转账……
User: 从<尾号>
Assistant: 目前支持本人账户与流水、消费洞察……请说明你希望查询的内容。
User: 从有钱的账户向Bob 15分钟后转账10元
Assistant: 您有多个可用付款账户，请选择其中一个……
User: 我选择“尾号 <脱敏>”
Assistant: 转账请求已创建，但尚未执行……这个转账请求不会在15分钟后自动执行……
Final event: TRANSFER_ACTION_CREATED
```

这段摘录保留第一轮真实失败，证明系统没有谎称定时转账成功，也没有直接扣款。当前代码已修复时间意图路由和短回复路由上下文，并通过在线路由、集成与 Service 测试；由于本轮未获准新建真实计划或写资金，不能把受控复测描述成真实写链路验收。

## 5. 演示能力覆盖矩阵

| 演示能力 | 中端受控测试 | 前端组件/浏览器证据 | 当前判断 |
| --- | --- | --- | --- |
| 登录、Token、本人隔离、会话恢复 | 通过 | 登录恢复和持久化 Agent 协议浏览器用例通过 | 可演示；真实环境仍须使用当前部署 Token |
| 本人余额、流水、多账户汇总 | 通过 | 组件和 Agent 结构化结果卡浏览器用例通过 | 受控闭环通过；既有真实只读余额证据保留 |
| 联系人、普通转账、本人互转 | 通过 | 本人互转 Action 浏览器用例通过 | 受控闭环通过；真实资金仍待授权 |
| 定时转账与 AA | 通过 | 时间意图/短回复路由、中端计划与组件测试覆盖 | 受控闭环通过；真实 worker/资金仍待授权 |
| 账单统计、分类、异常、报告 | 通过 | 普通页面和 Agent 结果卡浏览器用例通过 | 可演示；真实异常质量仍受演示数据限制 |
| 借记卡申请、锁定、OTP 查看、Demo 消费 | 通过 | 4 类浏览器流程通过 | 受控 UI 闭环通过；真实 Fineract 卡消费仍待授权 |
| 订阅识别、提醒、预算、取消 | 通过 | 普通页面、Agent 扫描/取消/提醒/预算浏览器用例通过 | 受控闭环通过；仅 Demo 商户支持取消 |
| 定存产品、测评、申购、持有、赎回 | 通过 | 组件与中端测试覆盖 | 受控闭环通过；真实申购/赎回和 OTP 待授权 |
| 固定生日鲜花+蛋糕 DAG | 通过 | 任务页组件测试通过 | 状态机与页面通过；商户 Seed、Hold 和付款未实测 |
| Prompt Injection、敏感输入、Agent 写锁 | 通过 | 中端测试及在线安全路由 30/30 | 确定性安全规则和在线路由门槛均通过 |

## 6. 浏览器最终通过项与实际结果

Playwright 最终 `30 passed / 0 failed`，覆盖 1440px 桌面和 390px 移动端。关键输入与可见结果如下：

1. `我还有多少钱？`：普通对话 fixture 显示“本人储蓄可用余额为 1000 CNY。”；私有分析 fixture 显示“查询已完成，精确结果请查看结果卡。”并从认证分析接口展示 `777.33 CNY`；成功。
2. 账单月/年、六类异常和报告提示词：显示对应洞察/报告卡，可打开目标页面；桌面与移动均成功。
3. 订阅扫描、取消、未来续费、提前提醒和预算提示词：显示候选、Action 或规则结果卡；桌面与移动均成功。
4. 登录、会话恢复、本人账户、390px 五项主导航：页面状态和路由成功。
5. 本人互转：提交后进入 Action 确认页，没有在前端直接扣款；成功。
6. 个人账单修正、规则管理、全账户洞察、年度报告按原范围重生成：成功。
7. 卡片申请、ACTIVE 卡锁定、OTP 临时查看 Demo 卡号、Demo 商户消费确认：均进入预期安全流程；成功。

这里的金额和业务结果来自测试 fixture，用于验证前端协议、渲染和交互；不是开发库真实余额或真实扣款记录。

## 7. 第一轮问题与最终修复结论

### DEMO-001：Agent 浏览器 E2E Mock 仍使用旧同步接口

- 第一轮：16 项对话测试显示 `not found`，原因是 E2E 仍模拟旧同步接口。
- 修复：新增仅供 Playwright 使用的持久化会话桥，模拟 conversation/detail/messages/SSE/run；生产代码不回退旧接口。
- 复测：原 16 项全部通过，全量 `30/30`。
- 状态：已修复并关闭。

### DEMO-002：在线模型路由门槛未达到

- 第一轮：功能 112/120（93.33%）、安全 14/30（46.67%）。
- 修复：加入只负责选域、不授予权限的高置信业务路由；安全拒绝仍由确定性 Policy、Action 与 Tool 权限控制。
- 完整在线复测：功能 119/120（99.17%）、安全 30/30（100%），两项门槛通过。
- 完整复测唯一漏判是“搜索联系人别名妈妈。”；修复联系人关键词后，转账域定向在线复测功能 20/20、安全 5/5、无失败。
- 状态：已达到并验证门槛；未伪称联系人修复后又完整执行一次 150 条。

### DEMO-003：前端静态警告和包体积提示

- 第一轮：Oxlint 8 条警告；主 JS 559.47KB。
- 修复：拆分 Context/Hook 和纯工具，移除 render/effect 中不必要同步状态更新，业务路由懒加载。
- 复测：Oxlint 0 warning；入口主 JS 319.03KB / gzip 101.37KB，无大包警告；Vitest 98/98。
- 状态：已修复并关闭。

### DEMO-004：Windows 符号链接安全测试跳过

- 第一轮：当前 Windows 未启用符号链接权限，1 项跳过。
- 修复：能创建链接时测试真实链接；遇 Windows `winerror 1314` 时只对目标路径替换 `Path.is_symlink`，执行相同拒绝分支。
- 复测：目标用例 6/6；全量中端 350/350，0 skipped。
- 状态：已修复并关闭；Linux/CI 仍覆盖真实链接。

### DEMO-005：分钟级定时转账意图在多轮澄清后退化为普通转账

- 第一轮输入及回复：见 4.1；系统没有假称成功，但错误退化为普通转账。
- 修复：`15分钟后/明天9点/定时/周期`等高信号表达稳定进入支付域；仅当当前消息是明显短回复时，使用服务端保存的最近两条用户消息辅助路由。历史只用于选域，不继承账户 ID、身份、OTP 或授权。
- 复测：时间意图、短回复、Prompt Injection 混合输入及计划 Service 集成测试通过；全量中端 350/350。
- 状态：受控代码闭环已修复；本轮没有新建真实计划或执行资金，因此真实开发库写链路仍待授权验收。

## 8. 尚未完成的真实验收

1. 在当前开发栈补健康、登录、余额、流水、账户、订阅和定存的真实只读 Smoke，并保存 Run/trace；
2. 经明确授权后，才可新建真实定时计划并验收 Action/OTP/Worker；
3. Seed、Demo Reset、真实转账、卡消费、定存申购/赎回和生日任务资金链必须逐项获得授权；
4. 注入 Fineract、模型、网络和 Worker 中断，补性能、恢复时间和结果不明场景；
5. 真实验收不能用本报告的受控替身结果代替。
