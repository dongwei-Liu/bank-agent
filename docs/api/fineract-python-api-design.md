# Fineract 接口盘点与 Python 封装设计

> 日期：2026-10-09。本文保留初始六场景接口调研；三场景实施已获批准并落地。当前接口、原生定存范围与安全约定以 [banking-backend.md](banking-backend.md) 为准。
> 下文“拟实现/现有实现/未运行验收”均描述初始调研时点，不能作为当前实时状态。模拟理财建议已被用户批准的原生定存方案替代。
> 总规划：[master-plan.md](../project/master-plan.md)；逐项源码索引：[fineract-endpoint-inventory.md](fineract-endpoint-inventory.md)。

## 1. 证据范围与结论

本次扫描本地 Apache Fineract 源码提交 `b56917ebd5253e8b69e865b75387bf3e9a2e0f99`：169 个 JAX-RS 资源类、967 个 HTTP 方法声明，包括管理及内部接口。该数字是源码声明数，不是业务功能数；同一 POST 上的多个 `command` 不单独计数，external-id 变体则单独列出。Spring 登录页、Actuator 自动端点与测试模块不计入。

源码接口索引包含方法、路径、operationId、源码摘要及资源文件链接。它不等于实际容器的 OpenAPI：项目使用固定摘要镜像，源码与镜像版本不保证相同。本轮只做静态核对，没有调用写接口，也没有重新执行运行时验收。

证据分级：

- **现有实现**：`apps/backend` 当前仅封装健康检查和余额查询；历史进度记录有余额联调证据。
- **初始化已有使用**：Seed 脚本已有客户、产品、开户、审批、激活、存取款调用；不等于 Python Banking Service 已封装。
- **源码确认**：本文其余 Fineract 路径来自本地资源定义，运行镜像兼容性待契约测试。
- **拟实现**：本文所有新增 `/api/...` 路由、Service 方法及 DTO 都是设计建议。

在线辅助参考为 [Apache Fineract 官方 API 旧版文档](https://fineract.apache.org/docs/legacy/)；旧文档不能覆盖当前源码的全部搜索接口、分页语义和命令。冲突时先以本地源码解释设计，再以目标镜像验证上线契约。

建议保留三层：`Python API → Business Service → FineractClient`。API 和业务层共同封装项目能力，只有客户端层理解 Fineract HTTP 协议。不要把近千条 Fineract 路由全部原样代理给前端或 Agent。

## 2. Fineract 有哪些接口

以下按业务领域归类；路径默认省略 `/fineract-provider/api/v1`，完整逐项清单见源码索引。

| 接口领域 | 代表资源 | 主要功能 | 本项目取舍 |
| --- | --- | --- | --- |
| 客户 | `/clients`、`/clients/{id}/accounts`、identifiers、familymembers、地址 | 客户资料、账户归属、身份标识、家庭信息与生命周期 | 客户及关联账户必需；复杂 KYC 后续再评估 |
| 储蓄账户 | `/savingsaccounts`、transactions、charges | 开户、审批、激活、余额、流水、存取款、计息、费用、账户限制 | 核心；管理写操作与用户入口分开 |
| 储蓄产品 | `/savingsproducts` | 产品目录、币种、利率、开户规则 | 产品读取、初始化所需 |
| 账户间转账 | `/accounttransfers` | 转账创建、查询、撤销、贷款退款转账 | 储蓄到储蓄转账必需；撤销仅受控维护 |
| 周期转账 | `/standinginstructions`、`/standinginstructionrunhistory` | 建立/修改/删除周期指令、执行历史 | 候选；首版不直接接为定时转账执行器 |
| 冻结及限制 | savings `holdAmount`、`releaseAmount`、`blockDebit` 等；onholdtransactions | 冻结/解冻金额、限制账户收支、查询担保冻结记录 | 候选；不能与虚拟卡状态混为一谈 |
| 定期存款 | `/fixeddepositproducts`、`/fixeddepositaccounts` | 产品、账户、交易及存款生命周期 | 可选；不等同基金或模拟理财 |
| 周期存款 | `/recurringdepositproducts`、`/recurringdepositaccounts` | 定期缴存产品、账户及交易 | 非首批 |
| 股金 | `/products/{type}`、`/accounts/{type}`、`/shareproduct/{productId}/dividend` | 股金产品、股金账户与分红 | 不直接当作本项目理财产品模型 |
| 贷款 | `/loanproducts`、`/loans`、charges、schedule、rescheduleloans | 申请、审批、放款、还款、费用、重排计划 | 不在当前六场景核心范围 |
| 扩展信贷 | working-capital、delinquency、collateral、guarantors、loan-originators、external-asset-owners | 营运资金贷款、逾期、抵押、担保、资产转移 | 不封装到本项目用户 API |
| 机构与人员 | `/offices`、`/staff`、`/tellers`、officetransactions | 网点、职员、柜员、机构交易 | 网点用于内部参数；其他排除 |
| 团体业务 | `/groups`、`/centers`、meetings、calendars、collectionsheet | 团体/中心、会议及批量收款 | 不是 AA 收款现成实现，当前排除 |
| 会计 | `/glaccounts`、`/journalentries`、`/glclosures`、accountingrules、provisioningentries | 总账、分录、结账、会计规则和拨备 | 由 Fineract 内部承载；不手工写分录模拟转账 |
| 基础字典 | `/currencies`、`/paymenttypes`、`/codes`、`/charges`、taxes、interestratecharts | 币种、支付方式、字典、费用、税及利率表 | 读取按需；币种启用限初始化 |
| 管理身份 | `/authentication`、`/users`、`/roles`、`/permissions`、twofactor、OIDC 配置 | 后台身份、权限及双因素 | 不替代 Bank Agent 的客户身份和交易确认 |
| 审批与审计 | `/makercheckers`、`/audits`、`/v2/audits` | 核心系统命令审批与审计 | 运维辅助；不能替代 Agent Action/Trace |
| 报表与扩展数据 | `/reports`、`/runreports`、`/datatables`、`/adhocquery`、`/search` | 报表、扩展表、搜索、管理查询 | 首版账单走流水，不开放任意查询/SQL |
| 文档及备注 | documents、images、notes、templates | 附件、图片、备注和模板 | 备注可选；不作为交易分类唯一存储 |
| 通知与集成 | notifications、sms、email、hooks、externalevents、interoperation | 通知、通信、事件和互操作 | 后续按需，不代表真实商户支付已接通 |
| 运维与批处理 | `/jobs`、`/scheduler`、businessdate、configurations、batches、imports、internal | 批处理、业务日期、系统配置及内部服务 | 管理用途，禁止通过通用代理暴露 |
| 调查与评分 | survey、surveys、scorecards、povertyLine、likelihood | 问卷、社会绩效和评分 | 不是理财适当性现成实现 |

当前源码没有本项目所需的虚拟卡发卡/挂失、外部会员取消、商户购物、LLM 对话与 DAG 原生业务闭环。客户自助插件属于独立项目，不应从旧文档中的 `/self/...` 推断本地已提供这些接口。

## 3. 分层封装边界

```text
React / Agent Tool
        ↓ 同一业务服务与相同授权规则
API：用户身份、Pydantic 请求/响应、HTTP 错误、幂等键入口
        ↓
Service：账户归属、业务约束、金额规则、Action/Policy、统计、审计
        ↓
FineractClient：租户与认证、URL/command、日期与金额编码、上游错误
        ↓
Apache Fineract：账户余额、交易记录、核心转账事实
```

- API 不直接调用 FineractClient，不接受用户提交的 `clientId/officeId` 作为授权事实。
- Service 接收可信 `ActorContext(user_id, client_id, tenant_id)`；客户与 Fineract client 的映射由后端维护。
- Agent Tool 只能调用与 REST 入口相同的服务方法；不能调用 `create_transfer` 客户端方法直接执行。
- Adapter 不决定风险等级，不执行客户权限判断；Service 不依赖 LLM。
- Demo 初始化使用独立维护服务/脚本，不在公开用户 API 上提供充值、任意开户审批或撤销交易。
- 每个公共能力定义具体 DTO；不建设 `POST /api/fineract/{path}` 这类任意代理。

## 4. 核心 Fineract 接口与 Python 映射

Fineract 表中路径相对 `/api/v1`；`id`、`tid` 分别代表储蓄账户与交易 ID。P0 为只读底座，P1 为安全写链路，P2 为扩展候选。除余额外，新增 Python 方法均待实现。

| 优先级 / 能力 | Fineract 调用 | Client 拟封装方法 | Service 拟方法 | 对外 Python API（建议） |
| --- | --- | --- | --- | --- |
| P0 当前客户 | `GET /clients/{clientId}` | `get_client(client_id)` | `CustomerService.get_current_customer(actor)` | `GET /api/me` |
| P0 本人账户 | `GET /clients/{clientId}/accounts` | `list_client_accounts(client_id)` | `AccountService.list_accounts(actor)` | `GET /api/accounts` |
| P0 账户详情 | `GET /savingsaccounts/{id}` | `get_savings_account(id)`（已有） | `AccountService.get_account(actor, id)` | `GET /api/accounts/{id}` |
| P0 可用余额 | 同上，读取 `summary.availableBalance` | 复用账户详情 | `get_balance(actor, id)`（已有方法待补身份） | `GET /api/accounts/{id}/balance`（已有） |
| P0 本人资产汇总 | 客户关联账户 + 各储蓄账户详情 | 组合已有读取 | `AccountService.get_summary(actor)` | `GET /api/accounts/summary` |
| P0 流水列表 | `GET /savingsaccounts/{id}/transactions/search` | `search_savings_transactions(id, filter)` | `TransactionService.list_transactions(actor, id, filter)` | `GET /api/accounts/{id}/transactions` |
| P0 流水详情 | `GET /savingsaccounts/{id}/transactions/{tid}` | `get_savings_transaction(id, tid)` | `TransactionService.get_transaction(actor, id, tid)` | `GET /api/accounts/{id}/transactions/{tid}` |
| P0 收款人解析 | 自研联系人 + `GET /clients/{clientId}` + 关联账户/储蓄详情 | 复用客户和账户读取 | `RecipientService.resolve(actor, query)` | `GET /api/recipients?query=...` |
| P1 请求转账 | 创建阶段不写 Fineract；读取相关账户 | 复用读取 | `TransferService.request_transfer(actor, request, key)` | `POST /api/transfers`，只创建 Action |
| P1 执行转账 | `POST /accounttransfers` | `create_account_transfer(payload, key)` | `TransferService.execute_authorized_action(action_id)`（内部） | 经 Action 确认/验证触发，不提供无条件执行接口 |
| P1 转账结果 | `GET /accounttransfers/{transferId}` | `get_account_transfer(transfer_id)` | `TransferService.get_transfer(actor, local_id)` | `GET /api/transfers/{transferId}`，使用本地资源引用 |
| P1 转账历史/核对 | `GET /accounttransfers` | `list_account_transfers(filter)` | `TransferService.reconcile(...)`（内部） | 用户列表优先查本地已授权记录；不透出全租户列表 |
| P0/P2 储蓄产品 | `GET /savingsproducts`、`GET /savingsproducts/{id}` | `list_savings_products()`、`get_savings_product(id)` | `DepositProductService.list/get(...)` | `GET /api/deposit-products`、`GET /api/deposit-products/{id}` |
| P0 字典（按需） | `GET /currencies`、`GET /paymenttypes`、`GET /offices/{id}` | `get_currencies()`、`list_payment_types()`、`get_office(id)` | 内部参考数据读取 | 初期不单独暴露；由必要 DTO 带出 |

本人账户必须通过可信客户映射限定范围，不能继续把 Alice、Bob、Charlie、Mom 都当作本人资产。关联账户响应包含不同账户类型；首版只选择支持的储蓄账户，保留状态筛选并逐个核验归属。收款人列表应是已授权的本地联系人，不开放全租户客户搜索作为个人通讯录。

## 5. 初始化与维护接口

以下接口确实有用，但用途是 Demo 引导、环境管理或专门维护。封装可供 Seed 复用，不默认增加公开 REST 入口。

| 用途 | Fineract 调用 | 拟 Client 方法 | 调用方 |
| --- | --- | --- | --- |
| 查找/创建演示客户 | `GET /clients?externalId=...`、`POST /clients` | `find_clients`、`create_client` | `DemoProvisioningService` / Seed |
| 激活客户 | `POST /clients/{id}?command=activate` | `activate_client` | 初始化（创建时可指定激活） |
| 产品初始化 | `GET /savingsproducts/template`、`POST /savingsproducts` | `get_savings_product_template`、`create_savings_product` | Seed；先查再建 |
| 储蓄开户 | `GET /savingsaccounts/template`、`POST /savingsaccounts` | `get_savings_account_template`、`create_savings_account` | Seed / 后续明确开户场景 |
| 审批、激活账户 | `POST /savingsaccounts/{id}?command=approve` / `activate` | `approve_savings_account`、`activate_savings_account` | Seed；状态感知、重复执行不重复开户 |
| 初始资金及历史交易 | `POST /savingsaccounts/{id}/transactions?command=deposit` / `withdrawal` | `deposit`、`withdraw` | Seed；不作为账户间转账替代 |
| 支付参数模板 | `GET /savingsaccounts/{id}/transactions/template` | `get_transaction_template` | 初始化或支付方式选择 |
| 启用演示币种 | `PUT /currencies` | `configure_currencies` | 管理；合并现有配置，不能误覆盖 |
| 撤销普通交易 | `POST /savingsaccounts/{id}/transactions/{tid}?command=undo` | `undo_savings_transaction` | 人工维护；不开放给通用 Agent |
| 撤销账户间转账 | `POST /accounttransfers/{id}?command=undo` | `undo_account_transfer` | 人工维护；需独立业务审核 |
| 核心审计 | `GET /audits`、`GET /audits/{id}` | 需要时再封装 | 排障/对账，不替代项目审计 |
| 业务日期 | `GET /businessdate` | `get_business_date` | 读取租户日期，验证交易日期策略 |
| 健康状态 | `GET /fineract-provider/actuator/health` | `check_health`（不走 `/api/v1` base） | 深度就绪检查；已有 `/api/health` 保持应用存活语义 |

## 6. 六场景如何复用这些封装

| 项目场景 | Python API 候选 | 业务层职责 | Fineract 依赖 / 自研边界 |
| --- | --- | --- | --- |
| 智能转账 | `/api/recipients`、`/api/transfers`、`/api/actions/{id}` | 消歧、草稿、日累计、确认、验证、执行及对账 | 客户/储蓄读取 + accounttransfers；联系人与 Action 自研 |
| 账单分析 | `GET /api/bills?period=...` | 分类、月/年度汇总、趋势、最大消费、异常规则 | 流水搜索/详情；merchant/category/语义与统计自研 |
| 订阅管理 | `GET /api/subscriptions`；`POST /api/subscriptions/{id}/cancellation-requests` | 周期识别、续费预测、创建取消 Action | 流水是证据；订阅状态和取消 Adapter 自研，不能把撤销旧扣款当取消订阅 |
| 卡片管理 | `GET /api/cards`；`POST /api/cards/requests`；`POST /api/cards/{id}/change-requests` | 模拟卡发卡、限额、线上限制、锁定/挂失状态机 | 关联储蓄账户；不把储蓄账户 block 当作单卡挂失 |
| 理财操作 | `GET /api/investments/products`；`POST /api/investments/order-requests` | 模拟产品、风险问卷、适当性、申购/赎回、订单与收益 | 产品/收益模型自研；资金可复用受控转账，结算账户和会计语义待确认；不是直接存取款造余额 |
| 跨场景联动 | `POST /api/tasks`；`GET /api/tasks/{id}`；暂停/恢复请求 | DAG、资金预留、条件、到期重验、Mock 商户及通知 | 余额/流水/转账共享；计划及外部商户自研 |

写场景通用建议：`GET /api/actions/{id}`、`POST /api/actions/{id}/confirm`、`POST /api/actions/{id}/verify`、`POST /api/actions/{id}/cancel`。确认与验证的挑战签发、有效期、尝试次数需在安全专项实现时补齐；自然语言“确认”不能直接执行。所有路由共享 ActionService / PolicyService / VerificationService / AuditService。

### 可选原生能力，不直接纳入首批实现

| 能力 | 已确认的 Fineract 接口 | 采用前需解决 |
| --- | --- | --- |
| 周期转账 | `GET/POST /standinginstructions`；`GET /standinginstructions/{id}`；`PUT /standinginstructions/{id}?command=update|delete`；`GET /standinginstructionrunhistory` | 周期任务若在 Fineract 内直接执行，可能绕过每次执行时的项目 Policy/Action 校验；建议首版由项目调度器调用统一转账服务 |
| 金额冻结 | `POST /savingsaccounts/{id}/transactions?command=holdAmount` | 金额冻结、账户设置、lien 语义及余额影响需目标镜像测试；与当前自研资金预留方案不自动替换 |
| 释放冻结 | `POST /savingsaccounts/{id}/transactions/{tid}?command=releaseAmount` | 关联原冻结交易、重复释放与并发验证；不能重复扣减本地预留与上游冻结 |
| 担保冻结记录 | `GET /savingsaccounts/{id}/onholdtransactions` | 存在 `guarantorFundingId` 等参数；不要假设它就是所有 holdAmount 交易的通用列表 |
| 账户收支限制 | `POST /savingsaccounts/{id}?command=block|unblock|blockDebit|unblockDebit|blockCredit|unblockCredit` | 作用范围是储蓄账户，不能直接映射到单张虚拟卡 |
| 定期/周期存款 | fixeddepositproducts/accounts、recurringdepositproducts/accounts 及交易资源 | 与“模拟理财”的产品边界需先确认；避免多建一套未要求的真实存款业务 |

## 7. 关键协议与转换规则

### 7.1 流水搜索：不能照搬旧 API 假设

本地源码首选 `GET /savingsaccounts/{id}/transactions/search`，支持：

- `fromDate/toDate`：交易日期，包含边界；`fromSubmittedDate/toSubmittedDate`：提交日期。
- `fromAmount/toAmount`、`types`、`credit/debit`。
- `offset/limit`、`orderBy/sortOrder`、`locale/dateFormat`。

**注意：当前源码 `TransactionSearchRequest.pageable()` 使用 `PageRequest.of(offset, limit)`，这里的 offset 实际作为从 0 开始的页号，不是跳过的记录数。** 同名参数在其他接口不一定相同。Python 建议公开 `page=0&page_size=20`，由 Adapter 针对此端点映射；禁止全局统一把 offset 当记录偏移量。

此搜索接口返回 Spring Data `Page`；客户列表等使用 Fineract 自有 `Page(totalFilteredRecords, pageItems)`。两者不能共用未经验证的 JSON 解析。搜索响应最终字段受运行配置影响，目标镜像需保存脱敏 fixture 后明确映射到统一 `items/total/page/page_size`。

拟定筛选契约：`from_date/to_date` ISO 日期、`direction=credit|debit`、`min_amount/max_amount` 十进制字符串、`page>=0`、`1<=page_size<=100`；只允许白名单排序，默认 `transactionDate,id` 同向倒序并显式传 `sortOrder=DESC`。账单服务逐页读全区间，不能只统计第一页。新流水插入时页号分页可能漂移，演示统计需固定时间上界并去重，必要时声明非原子快照。

若目标镜像不支持 search，可评估 `GET /savingsaccounts/{id}?associations=transactions` 作为受限 Demo 回退；先验证响应确实包含所需完整数据。不得把普通账户 404 当接口不兼容，也不得静默截断后宣称完整月账单。

交易方向根据类型/entryType 契约映射，不按金额正负猜测；显式处理撤销、冲正、费用、利息、转账和冻结交易。冻结不等于消费，内部互转不应重复统计成外部支出。未知类型保留原始类型并标记待分类。分类元数据按租户 + 账户 + Fineract transactionId 关联，缺失则归“未分类”。

### 7.2 余额与金额

保留已有响应 `balance: string`，明确等于 Fineract `summary.availableBalance`，可增补 `ledger_balance`、`currency`、`as_of`。账户顶层/summary 币种来源按 fixture 校验一致性；核心字段缺失或币种不一致时返回上游数据错误，不能默认 `0` 或默认 CNY 掩盖缺失。

HTTP JSON 数字读取时用 `json.loads(response.text, parse_float=Decimal)` 等精确解析方式，再建 Pydantic 模型；仅 `Decimal(str(float))` 不能追回 JSON 解码阶段已经丢失的精度。写请求显式将金额编码为上游接受的十进制字符串或精确 JSON 数字；禁用 `float(amount)`。

DTO 对外金额统一字符串，当前 CNY 最多两位小数；非法精度应拒绝而不是静默四舍五入。资产合计按币种分组；部分账户失败时明确返回不完整状态或整个请求失败，不将部分合计伪装为总资产。

### 7.3 转账协议与完整性

使用 `POST /accounttransfers`，不要在 Python 内用 `withdrawal + deposit` 拼接：两次远程调用无法保证同时成功。储蓄账户类型使用上游枚举 `2`，首版仅支持同币种储蓄到账户转账；这不是跨行支付网络接口。

Fineract 请求字段示意（需契约测试，不是本轮执行请求）：

```json
{
  "fromOfficeId": "1", "fromClientId": "1", "fromAccountType": "2", "fromAccountId": "1",
  "toOfficeId": "1", "toClientId": "2", "toAccountType": "2", "toAccountId": "2",
  "transferDate": "2026-10-08", "transferAmount": "200.00",
  "transferDescription": "生活费", "dateFormat": "yyyy-MM-dd", "locale": "en"
}
```

office/client/type 必须从后端可信账户读取并补全，不由前端授权；`transferDate` 按业务日期策略生成，不允许用户任意回溯记账。公开请求只需付款账户、已确认收款人引用、金额、币种和备注。返回 Action 后冻结业务参数，改金额或收款人应重新确认。

执行过程：校验身份/账户/币种/余额 → 创建持久化 Action → 确认或强验证 → 原子抢占执行权与额度 → 再查最新事实 → 调用转账 → 保存上游 transfer/transaction 引用 → 查询核对 → 写审计与对话结果。

命令响应可能受 maker-checker 配置影响；HTTP 200、`commandId` 或仅接受命令不等于资金已转成功。以实际命令结果及可核对的交易事实判定成功；不要拿任意 `resourceId` 猜转账 ID，应在响应 fixture 中确认字段含义。

源码有 `Idempotency-Key` 可配置请求头及命令幂等处理。Adapter 应透传稳定的业务执行键，但仍需验证目标镜像的作用范围、同键异参、处理中、失败重试语义。本地存储 `(tenant, actor, operation, key, request_hash)` 和 Action 状态，不能只依赖 header，也不能把 externalId 当已验证的转账幂等键（当前 AccountTransferRequest 没有 externalId 字段）。

写请求超时可能已入账；必须进入待核对状态，不立即换 key 重发或自动退款。建议 Action 增加 `RECONCILING`（待确认设计），重试复用原键，核对仍不确定时人工接管。日累计需覆盖并发执行和在途额度；查询余额本身不能解决并发超支。完整资金一致性测试通过前不开放用户执行。

### 7.4 错误、连接与审计

- GET 可设置有界重试；不对所有 POST 自动重试。
- 400/422 仅对可解释业务校验翻译；账户不存在映射 404；本项目授权拒绝 403；冲突/重复异参映射 409；上游网络不可用 503；上游无效响应 502。上游服务账号 401/403 是集成错误，不冒充用户登录失效。
- 提议统一错误 `{code,message,trace_id,retryable}`；不将原始上游异常体、凭据或租户信息直接展示给用户。
- 复用 HTTP 连接池，FastAPI lifespan 关闭客户端；配置超时、租户、证书与 base URL；用户请求不能选择任意租户。
- 原始上游 DTO 只在 Adapter 内部流转；脱敏审计保存必要命令引用与状态，不记录凭据或 OTP。
- Fineract 日期可能是数组，也可能为配置后的字符串；由 Adapter 归一化 ISO 日期，并用 fixture 锁定实际格式。

## 8. Python 模块与 DTO 建议

以下是待确认的逻辑归属，不在本轮创建空文件：

| 模块 | 职责与主要类型 |
| --- | --- |
| `api/accounts.py` | 账户列表、详情、余额、汇总；`AccountSummary`、`AccountDetail`、现有 `BalanceResponse` |
| `api/transactions.py` | 流水查询与详情；`TransactionFilter`、`TransactionPage`、`TransactionDetail` |
| `api/recipients.py` | 已授权联系人检索与消歧；`RecipientCandidate`，只显示必要脱敏信息 |
| `api/transfers.py` | 请求转账、查看转账；`TransferRequest`、`TransferStatus` |
| `api/actions.py` | 确认/验证/取消与状态；`ActionResponse`、`ConfirmationRequest`、`VerificationRequest` |
| `api/deposit_products.py` | 存款产品读取；`DepositProductSummary/Detail` |
| `services/account_service.py` | 扩展当前服务，增加 actor、归属校验及按币种汇总 |
| `services/transaction_service.py` | 方向/日期/撤销归一化、查询、语义关联；账单统计另属 BillingService |
| `services/recipient_service.py` | 联系人解析与收款账户有效性检查 |
| `services/transfer_service.py` | 创建请求、内部授权执行、结果核对；不导入 LLM |
| `services/action_service.py` 等 | 公共 Policy、Confirmation、Verification、Audit 与执行状态协作 |
| `clients/fineract.py` | 当前文件扩展只读方法和私有 HTTP 处理，后续按体量拆成 savings/client/transfer 模块 |
| `schemas/` | 公共业务 DTO；与上游响应结构分离 |
| 自研持久化层 | 用户-client 映射、联系人、Action、执行幂等、审计、语义、预留和计划任务；独立于 Fineract 事实表 |

统一流水 DTO 至少含：`transaction_id/account_id/date/submitted_date/amount/currency/direction/type/reversed/transfer_reference/category/merchant`；未知值允许空并说明来源。余额 DTO 保持兼容已有前端。公共 ID 的本地/上游映射必须在 schema 中明确，不混用 actionId、transferId、transactionId。

固定路由 `/accounts/summary` 应在 `/accounts/{id}` 前注册，避免被动态路由截获。新增接口与已有前端接口字段保持兼容；替换硬编码账户列表属于后续前端接入任务。

## 9. 实施顺序与验收清单（待确认）

1. **契约探测**：核对运行镜像/OpenAPI、只读客户与账户响应、流水分页/字段、交易类型和日期；保存脱敏样本，记录版本。写契约在隔离 Demo 账户测试，不操作真实资金。
2. **只读封装**：完善余额精确解析/缺字段失败/授权；实现本人账户、流水、收款人和必要产品查询。
3. **安全公共层**：持久化身份、Action、Policy、日累计、幂等与审计，定义确认/验证事件。
4. **转账切片**：Adapter accounttransfers → 内部执行服务 → 请求/确认 API → 前端结果回写。
5. **消费切片**：账单统计与订阅识别复用流水服务；取消订阅走模拟业务 Action。
6. **扩展切片**：卡片、理财、任务按同一安全模板推进；原生冻结/周期指令是否采用另做验证决策。

验收证据必须覆盖：

- 账户只返回本人资源；跨客户读取拒绝；收款人查询不泄露对方余额。
- Decimal 精度、日期与币种转换、缺失余额拒绝、404/上游超时/非法 JSON。
- 流水第 0/1 页无错误跳页、日期边界、稳定排序、空页、撤销/冲正/冻结分类；账单总额可复算。
- 小额确认、大额强验证、累计跨阈值、并发额度占用、同键重复和异参拒绝。
- 转账双方真实交易关联与余额变化；超时后重试不双扣；maker-checker 未执行时不能报成功。
- 原生冻结与周期转账若采用，另测影响范围、取消、恢复、到期重新授权和服务重启。

本次待确认的主要建议：首批封装账户/流水/收款人与转账所需上游接口；用户转账 API 只创建 Action；定时任务首版走自研调度；继续使用规划中的模拟卡、模拟理财、模拟订阅域。确认前不把这些建议视为已决策或已实现。

## 10. 关键源码导航

以下路径相对于项目根目录；完整资源索引含其余全部资源链接。

- [客户与关联账户](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/ClientsApiResource.java)
- [储蓄账户及生命周期命令](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/SavingsAccountsApiResource.java)
- [流水搜索、详情、存取款及冻结命令](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/SavingsAccountTransactionsApiResource.java)
- [流水分页参数实现](../../platform/fineract/fineract-core/src/main/java/org/apache/fineract/portfolio/search/data/TransactionSearchRequest.java)
- [账户间转账资源](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/account/api/AccountTransfersApiResource.java)
- [转账请求字段](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/account/data/request/AccountTransferRequest.java)
- [周期转账资源](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/account/api/StandingInstructionApiResource.java)
- [担保冻结记录](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/DepositAccountOnHoldFundTransactionsApiResource.java)
- [冻结/限制命令常量](../../platform/fineract/fineract-core/src/main/java/org/apache/fineract/portfolio/savings/SavingsApiConstants.java)
- [幂等处理](../../platform/fineract/fineract-core/src/main/java/org/apache/fineract/commands/service/SynchronousCommandProcessingService.java)
- [本地源码安全边界：后台用户、自助插件及下游责任](../../platform/fineract/SECURITY.md)
