# Banking Backend 与 Agent API 使用约定

传统业务与 Agent 必须通过 `Python API → Service → FineractClient → Fineract` 调用；不得直接使用核心系统凭据或绕过 Action 授权。理财限定 Fineract 原生定期存款。当前 Agent 开放本人余额/流水、单/全账户账单洞察与报告、订阅识别/提醒/预算、联系人转账、普通借记卡、定时转账、AA 收款和固定生日跨场景任务；所有写 Tool 只创建 Action、草稿、请求或受控任务，不直接完成资金、卡片状态或生日采购。

## 启动后端并进行测试

以下命令适用于 Linux/bash。请从克隆后的项目根目录执行根路径命令；需要进入中端目录时，使用 `cd apps/backend`。要求 Python 3.11+、Docker 和 Docker Compose。

**本机已有 `.env`、虚拟环境和初始化数据时，直接按 1 → 3 → 4 操作。新环境先完成第 2 步，再继续。** 每个长期运行的进程单独占用一个终端。

### 1. 启动 PostgreSQL 和 Fineract

在终端执行：

```bash
docker compose --env-file .env -f infrastructure/docker/compose.yaml up -d
docker compose --env-file .env -f infrastructure/docker/compose.yaml ps
curl -k https://localhost:8443/fineract-provider/actuator/health
```

首次启动需等待核心系统完成迁移；健康检查返回 `status: UP` 后再进行核心账户查询或初始化。若尚未就绪，稍后重试；查看日志：

```bash
docker compose --env-file .env -f infrastructure/docker/compose.yaml logs --tail 100 fineract
```

新环境还没有 `.env` 时，先按第 2 步准备配置，再执行本步骤。

### 2. 首次初始化（本机已完成，可跳过）

从项目根目录执行，已有 `.env` 时保留原文件；新环境先复制 `.env.example` 为 `.env`，填写真实配置后再启动容器。

```bash
python3 -m venv apps/backend/.venv
apps/backend/.venv/bin/python -m pip install -r apps/backend/requirements.txt
```

根 `.env` 的关键配置如下（占位值必须自行替换）：

| 配置 | 用途与要求 |
| --- | --- |
| `FINERACT_IMAGE` | 保留模板中已验证的镜像摘要 |
| `POSTGRES_ADMIN_PASSWORD` | PostgreSQL 管理密码；初始化和测试建库使用 |
| `FINERACT_DB_PASSWORD`、`FINERACT_MASTER_PASSWORD` | Fineract 初始化配置；已有数据库沿用原值 |
| `DATABASE_URL` | `postgresql+psycopg://bank_agent:<独立密码>@127.0.0.1:5432/bank_agent`；密码中特殊字符需 URL 编码 |
| `OTP_SECRET` | 至少 32 字符随机秘密 |
| `CARD_ENCRYPTION_KEY` | 32 个随机字节的 URL-safe Base64；用于 Demo 卡号 AES-GCM 加密，不得提交 |
| `DEMO_PASSWORD` | 至少 12 字符的 Demo 初始登录密码 |
| `ADMIN_PASSWORD` | 可选，至少 12 字符；设置后初始化管理员 `admin` |
| `ENVIRONMENT`、`DEV_OTP_INBOX` | 本地测试设为 `development` 和 `true` |

启动第 1 步的依赖并确认健康后，依次执行：

```bash
# 仅新环境需要：创建核心 Demo 用户、储蓄账户、历史流水和独立商户结算账户
apps/backend/.venv/bin/python scripts/fineract/seed_fineract.py
# 创建独立业务库、执行迁移、关联用户/商户并初始化登录用户、联系人和基线卡
apps/backend/.venv/bin/python scripts/development/init_banking.py
```

本地账号为 `alice/bob/charlie/mom`，初始密码来自 `DEMO_PASSWORD`；通过核心 externalId `AGENT-ALICE/BOB/CHARLIE/MOM` 关联客户。Seed 另创建 5 个固定 `AGENT-*-CARD-*` 零余额账户、卡片商户 `AGENT-DEMO-MERCHANT-SAV`，以及生日任务专用的 `AGENT-DEMO-FLOWER-SAV` 和 `AGENT-DEMO-CAKE-SAV`；初始化脚本将三类商户分别映射为 development 专用卡片或编排商户，并为 Alice 建立两张、其他用户各一张 ACTIVE 加密基线卡。重复运行 Seed 与业务初始化会复用账户、密码、映射和已有卡，不重置账户余额、不重复资金流水；修改 `.env` 的密码不会自动修改已有账号。`init_banking.py --migrate-only` 仅建库和迁移。

本机随机凭据保存在被 Git 忽略的根 `.env`，不要提交或复制到文档。非开发环境禁止启用验证码收件箱；短信发送器未接入时 OTP 返回 `OTP_DELIVERY_UNAVAILABLE`。

### 3. 启动 API

```bash
cd apps/backend
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8080 --reload
```

出现 `Application startup complete` 后保持终端运行。`--reload` 用于开发时自动重载；按 `Ctrl+C` 停止 API。

| 地址 | 用途 |
| --- | --- |
| <http://127.0.0.1:8080/docs> | Swagger，交互填写参数并调用接口 |
| <http://127.0.0.1:8080/openapi.json> | 实时 OpenAPI 契约 |
| <http://127.0.0.1:8080/api/health> | API 进程健康检查；不代表数据库和核心业务全部可用 |

### 4. 在 Swagger 登录并验证查询

1. 打开 `/docs`，展开 `POST /api/auth/login`，点击 **Try it out**，填写后执行：

   ```json
   {"username":"alice","password":"<根 .env 中的 DEMO_PASSWORD>"}
   ```

2. 复制响应的 `access_token`，点击页面右上角 **Authorize**，粘贴 token 即可，不手动添加 `Bearer`。
3. 执行 `GET /api/me`，确认当前用户名与客户映射；再执行 `GET /api/accounts`，取得本人账户 ID。
4. 用返回的 ID 调用 `GET /api/accounts/{account_id}/balance` 和 `GET /api/accounts/{account_id}/transactions`，核对真实余额和流水。不要把其他用户账户 ID 用作本人账户。
5. 访问令牌有效期 15 分钟。过期后重新登录，或调用 `POST /api/auth/refresh`，请求体 `{"refresh_token":"<登录返回值>"}`；将新 `access_token` 重新填入 Authorize，并保存轮换后的刷新令牌。退出使用 `POST /api/auth/logout`。

### 5. 验证一笔转账及确认/OTP

通过 Swagger 调用会改变 Demo 账户的真实核心余额。需要隔离账户的完整资金契约验收使用下方真实契约探针。

1. `GET /api/recipients` 获取收款联系人 ID，`GET /api/accounts` 获取付款账户 ID。
2. `POST /api/transfers` 的 `Idempotency-Key` 填入本次请求的唯一值（例如自行生成的 UUID），请求体如下，替换账户及联系人 ID：

   ```json
   {"from_account_id":1,"recipient_id":"<联系人ID>","amount":"1.00","currency":"CNY","remark":"接口测试"}
   ```

3. 保存响应的 `id` 和 `request_hash`，调用 `POST /api/actions/{action_id}/confirm`，请求体为 `{"request_hash":"<原 request_hash>"}`。金额用十进制字符串；相同请求重试保持幂等键和参数不变。
4. 若状态为 `WAITING_VERIFICATION`，调用 `POST /api/actions/{action_id}/otp`。开发验证码接口未展示在 Swagger，可在浏览器开发者控制台执行以下代码，替换 token 和 Action ID：

   ```javascript
   fetch('http://127.0.0.1:8080/api/dev/otp-inbox/<action_id>', {
     headers: { Authorization: 'Bearer <access_token>' }
   }).then(response => response.json()).then(console.log)
   ```

   在 Swagger 调用 `POST /api/actions/{action_id}/verify`，提交 `{"code":"<六位验证码>"}`。收件箱仅允许读取本人 Action 的有效验证码。
5. 查询 `GET /api/actions/{action_id}`，仅 `SUCCEEDED` 代表已核实成功；再查询余额和流水核对。`EXECUTING/RECONCILING` 时按下文恢复约定处理，不创建新键重复付款。

普通转账按上海自然日累计，累计不超过 1000 元要求确认，超过要求 OTP；定存申购、赎回和计划预授权均要求 OTP。

### 6. 测试定时转账时启动 worker

在另一个终端执行：

```bash
cd apps/backend
.venv/bin/python worker.py
```

每 30 秒扫描一次到期计划，并领取已授权生日任务的到期节点。创建转账计划后须调用 `authorize` 并完成 Action 确认和 OTP；生日任务也必须先完成 RED Action/OTP 授权。仅启动 API 不执行任何到期节点。API 和 worker 共用根 `.env` 与业务库。按 `Ctrl+C` 停止 worker，计划和任务仍保留，重启后恢复扫描；多个 worker 通过数据库行锁、节点状态、稳定幂等键和唯一发生键防重。

### 6.1 使用持久化 Agent 对话时启动 Agent Worker

新会话 API 只负责把消息持久化为 `QUEUED` Run；必须另开终端启动 Agent Worker，模型和 Tool 才会实际运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\development\start-agent-worker.ps1
```

Linux/macOS 可在 `apps/backend` 执行 `.venv/bin/python agent_worker.py`。Agent Worker 与上面的 Banking Worker 职责不同：前者处理对话 Run，后者执行定时转账、报告、订阅后台任务和已授权生日 DAG 节点；完整本地栈需要两个进程都启动。停止 Agent Worker 不会丢失已入队消息，重启后按租约继续；仅启动 API 时前端会显示处理中，而不会在 HTTP 请求内直接调用模型。

### 7. 运行自动化测试

另开终端，从项目根目录执行：

```bash
apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py
```

入口创建并使用独立 `bank_agent_test` 数据库，要求 PostgreSQL、业务数据库角色和 `POSTGRES_ADMIN_PASSWORD` 已就绪；不需要先启动 API 或 worker。集成测试使用受控 Fineract 替身验证业务与并发，不代表真实核心契约验收。2026-10-15 最新完整回归为 63 项通过，当前结果仍以本次测试输出为准。

需要验证真实 Fineract 时执行：

```bash
apps/backend/.venv/bin/python scripts/testing/probe_banking.py
```

探针要求 PostgreSQL/Fineract 就绪、已配置 `ADMIN_PASSWORD`、开发环境及验证码收件箱，使用隔离 Contract Probe 客户并产生真实核心资金流水。成熟任务的租户级保护与证据位置见本文末尾；不应以普通业务测试替代这一步。验收记录见 [banking-backend-validation.md](../testing/banking-backend-validation.md)。

### 8. 迁移、停止与常见问题

代码升级后手动迁移和检查（首次初始化已自动迁移）：

```bash
cd apps/backend
.venv/bin/python -m alembic -c alembic.ini upgrade head
.venv/bin/python -m alembic -c alembic.ini check
```

API 和 worker 各自用 `Ctrl+C` 停止。需要同时停止依赖且保留数据时，在根目录执行：

```bash
docker compose --env-file .env -f infrastructure/docker/compose.yaml stop
```

| 现象 | 处理 |
| --- | --- |
| 找不到 `.venv/bin/python` 或缺少依赖 | 按首次初始化步骤创建虚拟环境并安装 requirements |
| 启动提示 `OTP_SECRET` 不足 32 字符 | 补充根 `.env`，重启 API/worker |
| 连接数据库失败或业务表不存在 | 确认容器已运行、DATABASE_URL 与现有角色密码一致，执行业务初始化/迁移 |
| 401 | 登录后在 Authorize 填入有效 access_token；过期则刷新或重新登录 |
| 账户 404 | 从本人 `/api/accounts` 取 ID；跨用户资源也返回 404 |
| 核心 502/503 | 检查 Fineract 健康、日志和配置；不要换键重发结果不明的资金请求 |
| 端口 8080 被占用 | 停止旧 API，或将命令的 `--port` 改为其他端口并同步调整访问 URL |
| 定时计划未执行 | 确认 worker 正在运行、计划已 OTP 授权且未过期，查看 `runs` 和计划状态 |

Windows 将根目录解释器替换为 `apps/backend/.venv/Scripts/python.exe`，后端目录内替换为 `.venv/Scripts/python.exe`，项目路径换为实际路径。已有 PowerShell 启动脚本仍可使用。生产环境需由进程管理器负责进程重启和日志收集。

## 登录、确认与执行

1. `POST /api/auth/login` 提交 `{"username":"alice","password":"<配置的初始密码>"}`。
2. 请求携带 `Authorization: Bearer <access_token>`。访问令牌15分钟，刷新7天。`POST /api/auth/refresh` 轮换令牌；`POST /api/auth/logout` 撤销当前会话。令牌为随机不透明值，服务端仅保存摘要。
3. 资金请求和计划授权携带 `Idempotency-Key`（1–160字符，按用户和业务类型隔离）。相同参数重放原 Action，异参409。
4. 展示返回的 `payload` 和 `amount`，用户确认后 `POST /api/actions/{id}/confirm` 提交原 `request_hash`。
5. 状态为 `WAITING_VERIFICATION` 时，先 `POST /api/actions/{id}/otp`，再 `POST /api/actions/{id}/verify` 提交 `{"code":"六位验证码"}`。仅开发环境可认证读取 `GET /api/dev/otp-inbox/{id}` 本人验证码，此端点不出现在公开 OpenAPI 中。
6. 只把 `SUCCEEDED` 显示为成功。`EXECUTING/RECONCILING` 表示尚未完成核对，不得换键重发。

Action 字段包括 `id/kind/status/request_hash/payload/amount/result/steps/error_code`，并兼容增加由中端可信策略生成的 `risk_level/source/expires_at/updated_at/version`。`version` 由 SQLAlchemy 乐观并发控制维护，调用方不得自行提交或覆盖；验证码摘要、内部验证期限和额度占用标记不对外暴露。金额一律十进制字符串；datetime 一律输出带 UTC 偏移的 ISO 8601，即使测试数据库驱动返回无时区值也会在统一序列化层补为 UTC。公共查询与管理端点见下表，完整请求约束以 `/openapi.json`、Swagger `/docs` 为准；版本控制快照见 [banking-openapi.json](banking-openapi.json)。

| 状态 | 调用方处理 |
| --- | --- |
| `WAITING_CONFIRMATION` | 展示当前参数并请求用户确认 |
| `WAITING_VERIFICATION` | 发送并验证 OTP |
| `AUTHORIZED` | 已授权但尚未持久化执行抢占；重复确认由服务继续执行 |
| `EXECUTING` | 已持久化抢占；等待结果或只读核对 |
| `RECONCILING` | 核心结果不确定；调用 reconcile，未核实前禁止重发 |
| `SUCCEEDED` | 核心事实已读取并核实；返回上游引用 |
| `FAILED` | 核心明确拒绝且没有转账执行引用；额度占用已释放 |
| `CANCELLED` | 未执行请求已取消 |

每日累计按上海自然日、按用户序列化计算，普通转账累计≤1000元仅确认，超过要求 OTP。已成功和结果不明的转账均占用累计额度。计划的 OTP 预授权允许在指定参数、每日限额和有效期内自动执行，不借用普通转账的短期 OTP。

OTP 随机六位、5分钟、最多5次错误后用户锁定15分钟，重新发送间隔30秒，旧码立即作废且不重置错误次数。请求确认有效期一天；OTP 授权有效期5分钟且只能由本 Action 使用。更改资金参数必须重新创建或重新授权。

## 已实现接口速查

当前版本控制的公开契约包含 **109 个路径、143 个 HTTP 操作**。下表列出公开业务接口；同一行多个方法分别对应查询、新建、修改或删除。除健康、登录和刷新外均要求 Bearer 登录，产品元数据维护还要求管理员身份。参数、请求体与响应以 [Swagger](http://127.0.0.1:8080/docs) 和 [OpenAPI 快照](banking-openapi.json) 为准。

### 认证与健康

| 方法 | 完整路径 | 功能 |
| --- | --- | --- |
| GET | `/api/health` | API 进程健康检查（无需登录） |
| POST | `/api/auth/login` | 账号密码登录（无需登录） |
| POST | `/api/auth/refresh` | 刷新并轮换令牌（使用刷新令牌） |
| POST | `/api/auth/logout` | 撤销当前登录会话 |
| GET | `/api/me` | 当前登录用户和客户映射 |

### 账户与流水

| 方法 | 完整路径 | 功能 |
| --- | --- | --- |
| GET | `/api/accounts` | 本人储蓄账户列表 |
| GET | `/api/accounts/summary` | 本人账户汇总 |
| GET | `/api/accounts/{account_id}/balance` | 账户余额 |
| GET | `/api/accounts/{account_id}` | 账户详情 |
| GET | `/api/accounts/{account_id}/transactions` | 流水分页与日期、金额、方向筛选 |
| GET | `/api/accounts/{account_id}/transactions/{transaction_id}` | 单笔流水详情 |

### 普通 Demo 借记卡

| 方法 | 完整路径 | 功能 |
| --- | --- | --- |
| GET、POST | `/api/cards` | 本人卡片列表；创建 YELLOW 办卡 Action |
| GET、PATCH | `/api/cards/{card_id}` | 本人卡片详情；修改别名并审计 |
| POST | `/api/cards/{card_id}/activate` | 创建必须 OTP 的 RED 激活 Action |
| POST、GET | `/api/cards/{card_id}/reveal` | 创建必须 OTP 的 RED 安全查看 Action；凭本人成功 Action 在 60 秒内无缓存读取完整 Demo 卡号 |
| POST | `/api/cards/{card_id}/limits` | 创建限额/渠道 Action；降额/关闭为 YELLOW，提额/开启为 RED |
| POST | `/api/cards/{card_id}/lock` | 创建 YELLOW 锁卡 Action |
| POST | `/api/cards/{card_id}/unlock` | 创建必须 OTP 的 RED 解锁 Action |
| POST | `/api/cards/{card_id}/report-lost` | 创建必须 OTP 的 RED 永久挂失 Action |
| POST | `/api/cards/{card_id}/replace` | 创建必须 OTP 的 RED 补卡 Action，新卡沿用原账户 |
| GET | `/api/cards/{card_id}/transactions` | 查询本人卡片的 Demo 授权、拒绝原因和核心转账/双方流水引用；仅 development 开放 |
| GET | `/api/demo/merchants` | 查询已映射核心结算账户的受控 Demo 商户；仅 development 开放 |
| POST | `/api/demo/card-transactions` | 创建 YELLOW Demo 消费 Action；需要幂等键且仅 development 开放 |

办卡 Action 确认后按稳定 `BANK-CARD-{action_id}` externalId 在 Fineract 创建、审批并激活一个零余额 CNY 储蓄账户，再在中端生成 `PENDING_ACTIVATION` 卡。响应丢失时先按 externalId 找回原账户，禁止重复开户；完整 Demo 卡号只以 AES-GCM 密文保存，列表和详情仅返回后四位。状态与设置操作执行前校验卡片版本，LOST 卡不能解锁；补卡生成新的待激活卡、旧卡永久为 `REPLACED`，二者关联同一个 Fineract 账户。安全查看要求 RED Action 和 OTP，授权只保留 60 秒，读取响应禁止缓存，明文不进入 Action、审计、URL 或数据库。

Demo 消费先创建 `card_transaction` Action，确认后在用户锁内重查卡版本、ACTIVE 状态、渠道、境外开关、单笔/日累计限额、账户归属和核心可用余额。拒绝时只保存明确 `decline_code` 和审计，不调用 Fineract；放行时使用稳定幂等键将卡关联账户转入 `AGENT-DEMO-MERCHANT-SAV`，回读核心 transfer 与双方 transaction ID 后才显示成功。核心响应丢失时进入 `RECONCILING` 并按 `[Card:{authorization_id}]` 标记只读核对；禁止换键重发。不确定交易也计入日累计，避免并发或超时绕过限额。账单读取再以当前用户已批准的 `card_authorizations.fineract_transfer_id` 匹配核心流水，将卡侧扣款确定性标为 `expense` 并带入中端商户名称与类别；不依赖金额或自由文本猜测。

### Agent 对话

| 方法 | 完整路径 | 功能 |
| --- | --- | --- |
| POST | `/api/agent/messages` | 旧客户端同步兼容入口；身份仍只取自 Bearer Token，敏感输入在模型调用前拒绝 |
| POST、GET | `/api/agent/conversations` | 新建本人服务端会话；按最近更新时间查询本人有效会话 |
| GET、DELETE | `/api/agent/conversations/{conversation_id}` | 恢复本人消息、结构化事件和当前 Run；删除本人会话内容 |
| POST | `/api/agent/conversations/{conversation_id}/messages` | 使用 `Idempotency-Key` 持久化一条本人消息并创建 `QUEUED` Agent Run；同一会话只允许一个活动 Run |
| GET | `/api/agent/conversations/{conversation_id}/events` | Bearer 认证 SSE；使用 `Last-Event-ID` 重放断线后的持久化事件 |
| GET | `/api/agent/runs/{run_id}` | SSE 超时或断线后的本人只读 Run 状态恢复 |
| GET | `/api/agent/analyses/{analysis_id}` | 本人的精确分析快照；覆盖余额/流水/统计/异常以及定存产品/推荐/持有，每次重验账户、产品或持有依赖，全部响应 `Cache-Control: no-store`，跨用户 404，已过期但未清理的本人结果 410 |
| GET | `/api/agent/subscription-results/{result_id}` | 本人已确认的订阅列表、详情、续费预测、预算/提醒规则精确结果；30分钟有效，禁止缓存，跨用户404，过期410 |

新前端使用会话 API，不再让浏览器提交聊天历史。会话默认保留 30 天，独立 `agent_worker.py` 领取 Run、执行现有领域图并持久化助手消息和事件；API 进程只负责认证、入队和读取。Worker 使用租约与最多三次恢复，重启后可继续领取未完成 Run；资金结果不明仍遵循 Action 的核对规则，不能因 Run 重试换幂等键重复扣款。SSE 只是展示通道，所有 Action、分析结果和业务页面仍按当前用户重新鉴权。

`POST /api/agent/messages` 的 `events` 是类型化事件联合；订阅只读意图返回 `SUBSCRIPTION_QUERY_REQUESTED`，事件只包含 Action 引用、查询类型、不可变条件、YELLOW 等级与有效期。聊天按钮通过公共 `POST /api/actions/{action_id}/confirm` 提交 Action 返回的 `request_hash`；确认后 Action 只保存本人私有结果引用，聊天卡通过 `/api/agent/subscription-results/{result_id}` 读取精确结果。`SUBSCRIPTION_QUERY_COMPLETED`、`SUBSCRIPTION_QUERY_CANCELLED` 与 `SUBSCRIPTION_QUERY_FAILED` 持久化用于刷新/断线恢复；重复确认复用同一结果，超时读取原 Action 状态，不自动创建新请求。查询 Action 默认30分钟有效，不要求 OTP，确认前不读取订阅业务结果。聊天中的“确认”等自然语言不触发确认。页面 `/api/subscriptions`、`/api/subscriptions/{id}`、`/api/subscriptions/forecast`、续费和规则 GET 仍为登录认证、本人校验后的直接只读查询，不接受客户端“页面来源”作为权限凭据。取消订阅仍在操作页按现有 YELLOW 流程确认。

账单查看事件 `BILL_REPORT_OPENED` 只包含报告 ID、期间、状态和 `generated`，旧生成事件 `BILL_REPORT_READY` 保留兼容。报告状态由现有授权状态 GET 轮询，报告金额/明细仍由报告详情接口读取。新会话入口还支持通用 `CLARIFICATION_REQUIRED`，候选只携带会话内 `option_ref`；中端解析真实联系人、账户、卡片或生日任务付款账户后再次校验本人归属和当前状态。

身份只从登录 Token 获取，客户端不能提交 `user_id`、`client_id` 或租户。余额、统计、异常及定存产品/推荐/持有的精确结果写入中端 `AnalysisResult`；订阅预测/规则/预算详情写入独立 `SubscriptionAgentResult`。ToolMessage 只含安全状态或摘要，前端用本人授权 GET 读取精确卡片。分析结果默认24小时有效，订阅结果30分钟有效，不增加“已保存报告”数量。`BALANCE_RESULT` 只为旧客户端保留，新请求不发出。验证码、密码、Bearer/API Token 和完整卡号禁止进入聊天；拒绝请求只保存脱敏的秘密类型安全事件，不保存原文。

`query_context` 可含正整数 `account_id` 和 `YYYY-MM` 的 `period`，二者均可省略；拒绝其他字段，旧的仅 `message` 请求兼容。前端自由输入和快捷按钮均传选择条件，涉及账单时中端先校验所选账户归属。用户文字中的明确账户/完整日期优先；月份缺年时使用所选月份的年份，未选则需澄清；本月/上个月由中端上海日期确定，覆盖所选月份。上下文不是授权，最终账户仍由 Service 校验。

账单洞察域提供独立的 `view_bill_report` 与 `generate_bill_report`。用户明确查看月/年报告时，`view_bill_report` 依据上海日期、本人、期间及准确账户范围查找最新 complete/partial 报告、在途任务或已有失败记录，结果通过 `BILL_REPORT_OPENED` 返回报告引用、期间、状态和是否新建。缺少完全匹配的报告才在用户锁内排队生成，并提示“未找到对应报告，已开始生成”；已有失败记录不会因重复查看自动创建新任务。月报/年报未指定期间时分别默认为上海本月/本年，文字期间优先；未指定账户时优先沿用聊天选择，未选则查询本人全部合格账户，明确“所有账户”覆盖单账户选择。聊天卡只展示状态并跳转授权报告页，精确金额、商户和明细不进入模型。
兼容端点 `/api/agent/messages` 仍可携带最近最多 8 条用户消息，每条不超过 2000 字、合计不超过 6000 字；这部分客户端历史只作为不可信上下文。新会话入口由中端从持久化消息中选择最近 8 条用户消息，不接受客户端伪造助手回复、Tool 结果、授权状态、身份、租户或获准领域。

余额、流水、统计、异常、定存产品、定存推荐和本人定存持有的精确结果均写入中端 `AnalysisResult`；ToolMessage 只有白名单摘要，`ANALYSIS_READY` 只含 `analysis_id/kind`。前端单独读取 `{analysis_id, kind, created_at, expires_at, data}`，文字与精确卡片对应同一快照。读取财富结果时还会重验引用产品或持有是否仍可由当前用户访问。默认有效 24 小时，不增加“已保存报告”数量；失败回滚，不发布半份结果。`BALANCE_RESULT` 类型仅为旧客户端保留，新请求不发出该事件。

`query_context` 可含正整数 `account_id` 和 `YYYY-MM` 的 `period`，二者均可省略；拒绝其他字段，旧的仅 `message` 请求兼容。前端自由输入和快捷按钮均传选择条件，涉及账单时中端先校验所选账户归属。用户文字中的明确账户/完整日期优先；月份缺年时使用所选月份的年份，未选则需澄清；本月/上个月由中端上海日期确定，覆盖所选月份。上下文不是授权，最终账户仍由 Service 校验。

模型候选领域经中端白名单裁决后只装配本次需要的 `accounts/insights/payments/cards/payment_plans/subscriptions/wealth/orchestration`；最多三个 Tool 调用、串行执行、递归上限 8。`orchestration` 为独占领域，一次请求只能列出本人生日任务或创建一个固定任务，不能与其他领域工具混批。没有 Tool 时返回“本次未执行查询/操作”及重试示例，不能输出未经验证的银行事实。模型侧引用是请求级或会话级不透明值，写工具只接受联系人名称/别名、账户末四位、卡片别名/末四位以及产品/持有不透明引用；生日任务还要求用户原文或可信会话历史明确给出事件名称、完整日期、鲜花金额、蛋糕金额和本人账户末四位，模型不得拆分总预算。真实归属和内部 ID 由 Service 再校验。审计包含 trace、域、工具和脱敏参数，不存密码、Token、OTP、完整卡号或完整流水。详见 [统一入口指南](../development/unified-agent-entry-guide.md)。

财富域提供 `list_fixed_deposit_products`、`recommend_fixed_deposits`、`list_my_fixed_deposits`、`request_fixed_deposit_subscription` 和 `request_fixed_deposit_redemption` 五个 Tool。前三个只把产品利率、推荐收益、持有本金/到期值等精确事实写入本人私有分析快照，模型只看到安全状态、数量和不透明引用。每次申购都要求 15 分钟内新完成且未使用的五题风险测评；缺失时返回 `WEALTH_RISK_ASSESSMENT_REQUIRED` 并跳转 `/wealth/risk-assessment`。申购和整笔赎回只创建/恢复 `WEALTH_ACTION_CREATED` RED Action，必须在 Action 页面完成 OTP；创建 Action 不表示资金已移动，重试使用稳定键回放原 Action，报价和金额仍从授权页面重新读取。

写请求事件如下；`status=WAITING_CONFIRMATION` 表示尚未执行：

| 事件 | 用途 |
| --- | --- |
| `TRANSFER_ACTION_CREATED` | 普通联系人转账 Action |
| `INTERNAL_TRANSFER_ACTION_CREATED` | 本人账户互转 Action |
| `CARD_ACTION_CREATED` | 办卡、激活、设置、状态、补卡或安全查看 Action |
| `SCHEDULE_AUTHORIZATION_CREATED` | 已保存计划的授权 Action；计划完成确认和 OTP 后才生效 |
| `AA_PAYMENT_ACTION_CREATED` | 当前用户本人 AA 份额付款 Action |
| `WEALTH_RISK_ASSESSMENT_REQUIRED` | 申购前缺少本次可用的五题风险测评，跳转结构化测评页 |
| `WEALTH_ACTION_CREATED` | 定存申购或整笔赎回 RED Action；必须在 Action 页完成 OTP |
| `ORCHESTRATION_TASK_CREATED` | 固定生日任务及 RED 授权 Action 的引用；任务创建不代表资金已预留或商户已收款 |
| `ORCHESTRATION_TASKS_READY` | 本人生日任务的安全摘要列表；精确节点、金额和执行日志由任务详情 API 重新鉴权读取 |

如果 Action 已持久化后最终模型转述超时/失败，中端返回 200、确定性“请求已创建但资金/状态尚未变更”消息和原 Action 事件，避免客户端因 5xx 盲目换键重试。前端必须跳转 `/actions/{action_id}` 重新读取状态，不能以模型文字作为执行结论。

用户明确要求生成/保存报告时，`generate_bill_report` 仍提交后台任务并返回旧 `BILL_REPORT_READY`（报告 ID、排队状态和期间）；“消费分类/金额/异常统计”仍使用即时统计或异常 Tool，不会自动保存为报告。报告查看/生成可能改变中端任务状态；Agent 请求超时或断网属于结果未确认，前端不自动重发，先通过报告列表核对。

模型候选领域经中端白名单裁决后只装配获准的 `accounts/insights/payments/cards/payment_plans/subscriptions`；最多三个 Tool 调用、串行执行、递归上限8。订阅与其他领域不能混用，扫描和取消仍须单独发起。取消 Tool 只接收商户名称，按本人 Demo 订阅唯一匹配并创建/复用 YELLOW Action，事件只返 `action_id/status`，用户必须在 Action 页面确认。对已识别的订阅列表、商户详情、续费预测及提醒/预算规则读取意图，中端解析并冻结上海日期/金额/商户等查询条件、创建30分钟 `subscription_query` YELLOW Action；Tool 不读取订阅数据，聊天确认按钮确认后才由 Service 查询并写本人私有结果。规则创建和预算设置仍沿用原 Tool 流程，缺少提醒提前量时返回30分钟本人澄清引用，精确查询结果通过本人私有 GET 获取。规则编辑/暂停/恢复/删除仍通过管理页完成。详见 [统一入口指南](../development/unified-agent-entry-guide.md)。

洞察摘要不含精确金额、数量、占比、商户、备注或原始账户/交易 ID；固定通用类别需满足消费/类别各至少5笔，非完整自然月及每日超过10个不同规范化查询范围只给通用状态，精确接口不受此摘要限制。用户原话仍可能发送给领域路由模型，不构成差分隐私保证。洞察模型只选择结论码，中端用确定性模板渲染；订阅查询/设置由确定性中端意图解析和 Service 生成结果，不让模型编造金额或预算结论。银行链路在局部禁用外部全量 tracing，不修改全局环境。

`/api/billing/anomalies` 的默认单账户列表/全账户对象保持兼容；`include_metadata=true` 统一返回带 `items`、账户范围和 `detection` 的对象，说明 `hybrid/rules_only` 及原因。无模型/不足/过期/损坏/推理失败均保留规则结果，不代表机器学习检测完成。统计和报告 API 继续返回精确数据。维护和验证见 [专项报告](../testing/billing-privacy-ml-validation.md)。

虽然使用 POST，该接口中的查询不写核心银行资金；订阅扫描、报告入队以及成员 A 写 Tool 可能在中端持久化结果、Action、计划草稿或 AA 请求，但不会直接执行核心转账。前端等待最多 300 秒；超时或断网后不自动重发，应分别到订阅页、报告列表或 Action 页面核对，真正资金执行仍沿用既有确认、OTP、幂等和只读核对规则。

### 个人事件与固定生日任务

| 方法 | 完整路径 | 功能 |
| --- | --- | --- |
| GET、POST | `/api/personal-events` | 查询本人个人事件；幂等保存生日事件 |
| GET | `/api/tasks` | 查询本人任务安全摘要列表 |
| POST | `/api/tasks/birthday` | 幂等创建固定生日 DAG 和 RED 授权 Action；不直接预留或付款 |
| GET | `/api/tasks/{task_id}` | 查询本人任务、节点、边、预留、Demo 订单和事件时间线 |
| POST | `/api/tasks/{task_id}/{command}` | 按服务端 `allowed_commands` 执行 `pause`、`resume`、`cancel` 或 `takeover` |
| POST | `/api/tasks/{task_id}/nodes/{node_id}/retry` | 对明确失败且允许重试的本人节点进行有限重试 |
| POST | `/api/tasks/{task_id}/nodes/{node_id}/reconcile` | 对结果不明节点只读核对 Fineract 事实，禁止换幂等键重付 |

生日任务不是通用工作流编辑器。请求必须分别提供生日日期、鲜花金额、蛋糕金额和本人 ACTIVE CNY 储蓄账户；服务端生成固定白名单节点/边和不可变指纹，创建 `orchestration_authorization` RED Action。只有 Action 完成确认和 OTP 后任务才进入可执行状态。生日当月的资金预留使用 Fineract Hold，采购节点先释放对应 Hold，再以稳定键转入受控花店/蛋糕店核心账户；核心响应不明进入 `RECONCILING`，不能自动重发。暂停保留未消费 Hold，取消释放未消费 Hold，已完成采购不自动退款；部分成功可由用户选择失败节点重试、取消剩余任务或人工接管。页面只显示服务端允许的命令，所有接口按当前登录用户重新校验归属。

### 联系人与转账

| 方法 | 完整路径 | 功能 |
| --- | --- | --- |
| GET / POST | `/api/recipients` | 联系人列表/按字段检索；新增联系人 |
| GET / PUT / DELETE | `/api/recipients/{recipient_id}` | 联系人详情、修改、删除 |
| GET / POST | `/api/transfers` | 创建转账 Action；转账请求列表 |
| GET | `/api/transfers/{transfer_id}` | 转账请求详情 |
| POST | `/api/internal-transfers` | 本人两个 ACTIVE CNY 储蓄账户互转；复用 Action、日累计门槛、OTP、幂等和核对 |

### 公共 Action 授权与恢复

| 方法 | 完整路径 | 功能 |
| --- | --- | --- |
| GET | `/api/actions/{action_id}` | Action 状态、结果与步骤 |
| POST | `/api/actions/{action_id}/confirm` | 提交参数指纹并确认，按策略执行或进入 OTP |
| POST | `/api/actions/{action_id}/otp` | 发送验证码 |
| POST | `/api/actions/{action_id}/verify` | 验证 OTP 并继续执行 |
| POST | `/api/actions/{action_id}/cancel` | 取消未执行请求 |
| POST | `/api/actions/{action_id}/reconcile` | 只读核对上游事实和本地状态 |
| POST | `/api/actions/{action_id}/resume` | 已知但未激活的定存申请续办，重新确认/OTP |
| GET | `/api/actions/{action_id}/audit` | 本人可见的友好操作记录；只返回摘要、状态、失败码、时间、trace 与资源引用，不透传内部审计 JSON |
| GET | `/api/actions` | 本人 Action 列表 |

### 定时转账与 AA 收款

| 方法 | 完整路径 | 功能 |
| --- | --- | --- |
| GET / POST | `/api/transfer-schedules` | 计划列表、新建草稿 |
| GET / PUT / DELETE | `/api/transfer-schedules/{schedule_id}` | 计划详情、修改、取消（DELETE） |
| POST | `/api/transfer-schedules/{schedule_id}/authorize` | 创建计划预授权 Action，需确认/OTP |
| POST | `/api/transfer-schedules/{schedule_id}/pause` | 暂停未来执行 |
| POST | `/api/transfer-schedules/{schedule_id}/resume` | 校验已有授权后恢复 |
| GET | `/api/transfer-schedules/{schedule_id}/runs` | 计划发生项与执行历史 |
| GET / POST | `/api/aa-collections` | 收款单列表、创建均分或指定份额收款单 |
| GET / PUT / DELETE | `/api/aa-collections/{collection_id}` | 收款单详情、草稿修改、取消（DELETE，不退款） |
| POST | `/api/aa-collections/{collection_id}/shares/{share_id}/pay` | 参与人创建本人份额的付款 Action |

### 账单、分类与报告

| 方法 | 完整路径 | 功能 |
| --- | --- | --- |
| GET / POST | `/api/categories` | 分类列表、新增 |
| GET / PUT / DELETE | `/api/categories/{id}` | 分类详情、修改、删除 |
| GET / POST | `/api/classification-rules` | 分类规则列表、新增 |
| GET / PUT / DELETE | `/api/classification-rules/{id}` | 分类规则详情、修改、删除 |
| GET / POST | `/api/transaction-annotations` | 人工标注列表、新增；GET 可同时传 `account_id` 与 `transaction_id` 精确筛选，缺一返回 `INVALID_FILTER`，并校验本人账户/交易；无过滤参数继续返回本人全部标注 |
| GET / PUT / DELETE | `/api/transaction-annotations/{id}` | 人工标注详情、修改、删除 |
| GET | `/api/billing/statistics` | 区间分类及收支汇总；`account_id` 可选，缺省时聚合本人全部 CNY 储蓄账户并返回 `account_ids/complete` |
| GET | `/api/billing/anomalies` | 异常交易候选及证据；`account_id` 可选，缺省时返回带账户范围、完整性和 `items` 的聚合结果；显式单账户仍返回兼容列表 |
| POST | `/api/billing/anomaly-reviews` | 标记异常已核实或忽略 |
| GET / POST | `/api/bill-reports` | 兼容旧版报告列表与同步报告创建；新页面使用异步入口 |
| POST | `/api/bill-report-generations` | 幂等提交后台月度/年度报告生成任务，返回 `202` |
| GET | `/api/bill-report-generations/{id}/status` | 查询本人报告生成状态，响应禁止缓存 |
| GET | `/api/bill-report-summaries` | 按期间范围、状态、账户筛选并分页查询报告摘要，不返回交易载荷 |
| GET | `/api/bill-reports/{id}/transactions` | 对已保存流水快照按日期、方向、分类筛选并分页 |
| GET / DELETE | `/api/bill-reports/{id}` | 报告快照详情、删除（不删除流水） |

### 订阅识别与 Demo 取消

| 方法 | 完整路径 | 功能 |
| --- | --- | --- |
| POST | `/api/subscriptions/scan` | 用户主动扫描本人全部合格账户近 800 天流水；分页必须完整才保存候选。保留 `found` 为已保存订阅数，并增加 `matched_candidates`、`from_date`、`to_date`、`scanned_at` |
| GET | `/api/subscriptions/renewals?days=3` | 按上海日期查询已核实且即将续费的订阅、日期已过的待复查订阅及最近成功扫描时间；`days` 为整数 1–90，默认 3 |
| GET | `/api/subscriptions/forecast?month=2026-11` | 订阅预测；可用 `month` 或成对的 `from_date/to_date`，不能混用，范围最多366天；无参数默认上海今天至三天后 |
| GET | `/api/subscriptions/reminder-rules[/{rule_id}]` | 本人提醒规则列表/详情，禁止缓存 |
| POST / PUT | `/api/subscriptions/reminder-rules[/{rule_id}]` | 创建/编辑提醒规则，要求 `Idempotency-Key`、明确订阅范围及提前天数（1、3、7及组合）；有效状态相同规则可复用 |
| POST | `/api/subscriptions/reminder-rules/{rule_id}/{pause\|resume\|delete}` | 暂停、恢复或软删除提醒规则；操作要求 `Idempotency-Key` |
| GET | `/api/subscriptions/budget-rules[/{rule_id}]` | 本人月度预算规则列表/详情，禁止缓存 |
| POST / PUT | `/api/subscriptions/budget-rules[/{rule_id}]` | 创建或更新目标月唯一预算，要求 `Idempotency-Key`；写入后立即评估 |
| POST | `/api/subscriptions/budget-rules/{rule_id}/{pause\|resume\|delete}` | 暂停、恢复或软删除预算监测；恢复后立即评估 |
| GET | `/api/notifications`、`/api/notifications/unread-count` | 本人站内通知与未读数；列表可用 `unread_only=true`，禁止缓存 |
| POST | `/api/notifications/{notification_id}/read` | 将本人通知标为已读 |
| GET | `/api/subscriptions` | 本人候选、已核实、已忽略和已取消订阅列表 |
| GET | `/api/subscriptions/{subscription_id}` | 订阅判定证据及关联账户/流水详情 |
| POST | `/api/subscriptions/{subscription_id}/verify` | 核实候选；要求 `Idempotency-Key`，同状态重放不重复审计 |
| POST | `/api/subscriptions/{subscription_id}/ignore` | 忽略候选；证据未变化时重新扫描不再次提醒 |
| POST | `/api/subscriptions/{subscription_id}/cancel` | 创建 YELLOW `subscription_cancel` Action；只需参数确认，不要求 OTP |
| POST | `/api/demo/subscriptions/{subscription_id}/charge` | 仅 development 环境验证取消后拒绝扣费；不移动真实资金 |

扫描沿用三笔稳定扣款、月付 25–35 天/年付 350–380 天以及中位金额上下 10% 规则；实际日期区间和本次匹配数随扫描结果返回。成功扫描审计在零候选时也会记录，续费查询读取该时间。上游读取失败或分页不完整时整体失败，不保存部分识别结果。并发扫描在用户锁内重新读取当前订阅状态后合并扣费证据；没有新的稳定证据时不顺延预计日期。

续费查询范围是上海时区“今天至今天加 `days` 天”，两端均包含；列表按预计日期和订阅 ID 排序。`needs_review` 只表示预测日期已过，建议重新扫描核对，不代表实际漏扣、欠费或扣费成功。GET 不会触发扫描或更新订阅状态。洞察页和订阅页共用该查询并显示服务端日期范围、最近扫描时间；查询失败显示错误，不显示为空。

预测只纳入本人 `VERIFIED` 订阅。月付/年付按已保存下一预计日期和历史锚定日扩展，月末和闰年按当月最后一天截断；已过期或缺日期的预测进入 `needs_review` 并从合计排除，`complete=false` 表示金额可能偏低。预测始终标注为“预计”，不会触发扫描或更改预计日期。预算把目标月实际匹配的订阅扣费与本月尚未发生的预计金额合并，同一订阅当月已有实际扣费时不重复计入；历史读取按本人账户完整分页，撤销流水排除、同一账户交易去重，商户无法唯一归属时报告不完整。已知金额超过预算仍告警；只有完整评估且总额不超预算时才确认预算内。

提醒规则仅适用于已核实订阅，支持全部、单订阅或 `expected_amount > amount_gt`，并可固定目标月或持续生效。中端 worker 每30秒检查一次，上海时间09:00前不生成提醒；同一订阅、预计发生日和提前节点按用户合并去重。停机后仅对尚未发生的预计扣费补发，并将错过的节点合并成一条、展示原计划时间。目标月份规则在该月结束后过期；订阅取消、状态变化、规则停用或金额不再满足条件时停止后续投递，历史通知保留并标记失效。预算通知按用户/月份复用一条记录，不每日重复创建；页面提供建议项，只有用户点击后才进入既有 Demo YELLOW Action 确认流程。

Agent 查询和写入通过 `/api/agent/messages` 的类型化事件返回不透明 `result_id`；精确项目仅能由本人通过 `/api/agent/subscription-results/{result_id}` 读取，快照有效30分钟且响应禁止缓存。缺少提前量时，中端保存本人专属30分钟待补充记录，下一条“提前3天”等回答必须携带原引用；不能用新消息覆盖原月份、金额门槛或订阅范围。没有月份的规则持续有效，页面支持编辑、暂停、恢复和软删除；Agent 当前只支持查询、创建规则和设预算，不支持用自然语言暂停/修改/删除。

“下个月有哪些自动扣费，超过15元都告诉我”是带严格大于金额条件的即时查询，只返回匹配结果并展示筛选条件，不创建提醒；“下个月的扣费提前3天告诉我”表达了提前通知意图，会创建目标月提前3天的提醒规则。提前量仅支持1、3、7及组合，不支持的天数返回422。澄清引用仅在补充回答只包含提前量及可选提醒措辞时使用；若同时改变月份、金额或范围，按新请求处理，不能悄悄沿用原条件。模型在中端无法确定订阅意图时不能执行订阅管理 Tool。

订阅取消只调用本项目明确标注的 `demo_subscription` 适配器，不代表已经取消任何真实第三方会员。Action 记录用户确认时看到的商户、金额、周期和预计扣费日；执行时重新校验本人归属、订阅状态、Action 关联和快照。快照变化返回 `SUBSCRIPTION_CHANGED`，需重新确认。相同幂等键始终返回原 Action，跨订阅复用返回冲突；有效待确认或处理中 Action 不会并行创建。已过期、用户取消或明确失败的请求允许使用新键重申请；执行结果未知时只可查看或核对，不自动换键重发。历史 Action 无快照时兼容使用其原确认字段。取消成功后状态持久化为 `CANCELLED`、清空预计续费日并保留订阅、扣费证据和 Action；重复取消返回成功记录。Demo 扣费验证发现已取消状态时返回 `SUBSCRIPTION_CHARGE_BLOCKED` 并写审计，非开发环境对该入口返回 404。确定性 Seed 将商户写入 Fineract 交易 `note` 的 `[Merchant] ` 项目标记；中端只解析这一前缀作为商户证据，普通备注不会被自动当成商户。旧环境需经确认式 Demo Reset 重建历史后才能获得这部分候选证据。

### 风险评估与定期存款

| 方法 | 完整路径 | 功能 |
| --- | --- | --- |
| GET | `/api/risk-assessments/questionnaire` | 版本化五题风险问卷 |
| GET / POST | `/api/risk-assessments` | 提交评估、评估记录列表 |
| GET | `/api/risk-assessments/{id}` | 评估详情 |
| GET | `/api/investments/products` | 定存产品目录 |
| GET | `/api/investments/products/compare` | 产品对比；查询参数重复传入 ids |
| GET | `/api/investments/products/{id}` | 产品详情与适用条件 |
| PUT | `/api/investments/products/{id}/metadata` | 维护产品风险/推荐适配元数据（仅管理员） |
| GET | `/api/investments/recommendations` | 按金额、期限和流动性需求推荐 |
| GET / POST | `/api/investments/subscriptions` | 创建申购 Action；申购请求列表 |
| GET | `/api/investments/subscriptions/{id}` | 申购请求详情 |
| GET | `/api/investments/holdings` | 本人定存持有账户 |
| GET | `/api/investments/holdings/{id}` | 定存账户本金、利息、期限及状态 |
| GET | `/api/investments/redemption-quotes` | 获取赎回报价和 quote_hash |
| GET / POST | `/api/investments/redemptions` | 创建赎回 Action；赎回请求列表 |
| GET | `/api/investments/redemptions/{id}` | 赎回请求详情 |

### 开发专用接口与文档入口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/dev/otp-inbox/{action_id}` | 仅开发环境、显式开启、本人有效验证码；不计入上面的公开契约 |
| GET | `/docs`、`/redoc`、`/openapi.json` | Swagger、ReDoc 和实时契约；无需登录，调用业务接口仍需认证 |

资金 POST 返回业务请求/Action，创建成功不等同入账成功。已成功转账、申购和赎回没有删除接口；AA 与计划的 DELETE 关闭后续业务。分钟级 worker 为进程入口，没有额外“执行扣款”HTTP 接口。

## 业务入口与上游映射

| Python API | Service | Fineract 依赖 / 本地职责 |
| --- | --- | --- |
| `/api/accounts`、`/summary`、`/{id}`、`/{id}/balance` | AccountService | `clients/{id}/accounts`、`savingsaccounts/{id}`；仅本人普通 CNY 储蓄账户 |
| `/api/recipients`、`/{id}` CRUD | RecipientService | 本地联系人；创建/变更验证核心收款账户，返回信息不含收款方余额 |
| `/api/transfers` POST/GET、`/{id}` GET，`/api/internal-transfers` POST | TransferService + ActionService | `POST accounttransfers`，随后读取转账事实和双方流水 ID；本人互转两端必须均归属当前用户并标记为 `internal_transfer` |
| `/api/actions`、`/{id}` GET，`confirm/otp/verify/cancel/reconcile/resume` POST，`audit` GET | ActionService | 授权、额度、执行抢占、恢复与审计；resume仅用于未激活的已知定存申请 |
| `/api/personal-events`、`/api/tasks`、`/api/tasks/birthday`、任务命令与节点恢复 POST | OrchestrationService + ActionService + Banking Worker | 固定生日 DAG、RED 授权、Fineract Hold/Release、两个受控 Demo 商户转账、暂停/取消/有限重试/只读核对/人工接管；不提供任意 DAG |
| `/api/transfer-schedules`、`/{id}` CRUD，`authorize/pause/resume` POST，`runs` GET | ScheduleService | 本地分钟级计划，复用 TransferService；不调用 standinginstructions |
| `/api/aa-collections`、`/{id}` CRUD，`/{id}/shares/{share_id}/pay` POST | AAService | 本地分摊，参与人主动创建付款 Action；实际资金经统一转账 |
| `/api/accounts/{id}/transactions`、`/{transaction_id}` GET | TransactionService | `savingsaccounts/{id}/transactions/search` 和单笔接口 |
| `/api/categories`、`/classification-rules`、`/transaction-annotations` 及各自 `/{id}` CRUD | BillingService | 本地类别、确定性规则和人工语义元数据；不改原始金额 |
| `/api/billing/statistics`、`/anomalies` GET，`/anomaly-reviews` POST | BillingService | 完整区间分页、分类汇总、异常证据和核实状态 |
| `/api/bill-reports` POST/GET、`/api/bill-report-generations`、`/api/bill-report-summaries`、`/{id}` GET/DELETE、`/{id}/transactions` GET | BillingService + BillReportService + 独立 worker | 兼容旧版报告；异步生成有版本的月/年度事实和分页交易快照 |
| `/api/risk-assessments/questionnaire` GET，`/api/risk-assessments` POST/GET、`/{id}` GET | InvestmentService | 本地版本化五题风险问卷；新测评 15 分钟有效，并原子绑定且只用于一笔申购 |
| `/api/investments/products`、`/api/investments/products/{id}`、`/api/investments/products/compare?ids=…&ids=…` GET | InvestmentService | `fixeddepositproducts`、产品详情和账户模板；原生利率表 `interestRateCharts` |
| `/api/investments/products/{id}/metadata` PUT | InvestmentService / 管理员 | 仅补充风险等级、推荐开关和提前支取适配开关；不编辑核心产品本金/利率 |
| `/api/investments/recommendations` GET | InvestmentService | amount、term_months、needs_liquidity确定性过滤排序，收益标注估算 |
| `/api/investments/subscriptions` POST/GET、`/{id}` GET | InvestmentService + ActionService | `fixeddepositaccounts` create→approve→activate，`linkAccountId`关联本人账户扣款 |
| `/api/investments/holdings`、`/{id}` GET | InvestmentService | 客户固定存款账户和 `fixeddepositaccounts/{id}` |
| `/api/investments/redemption-quotes` GET，`/redemptions` POST/GET、`/{id}` GET | InvestmentService + ActionService | 提前金额计算、关闭模板、`close/prematureClose`，`onAccountClosureId=200`转回本人储蓄 |

### 转账、计划与 AA

联系人检索支持 `field=name|phone|alias&query=…`，多个匹配全部返回，API 不自动选人。普通转账输入示例：

```json
{"from_account_id":1,"recipient_id":"<联系人ID>","amount":"100.00","currency":"CNY","remark":"午餐"}
```

为只读恢复转账响应丢失的情况，核心备注写入唯一 `[Bank:<Action UUID>]` 标记及前50字符说明；完整备注保存在本地请求。核心命令幂等键稳定为 `bank:<Action UUID>:transfer`，长度不超过当前镜像的50字符限制。正常成功后 `steps` 记录 `transfer_id/from_transaction_id/to_transaction_id`。

计划创建在上述字段外增加 `execute_at`（含时区、精确到分钟）、`recurrence=once|daily|weekly|monthly`、`daily_limit`、`valid_until`。创建/修改为 DRAFT，通过 `/{id}/authorize` 创建 OTP Action 后激活。月末日期按原始日期锚点裁剪；重启对一次性补执行，对周期计划只执行最近一次到期项，其余记 MISSED。暂停不撤销已发送核心的资金操作。修改参数撤销旧授权。到期限额/授权失效时为 WAITING_AUTHORIZATION。

AA 输入包含 `account_id/title/amount/mode/participants`。参与项使用本地登录用户ID（各用户 `/api/me` 的 `id`，或本人联系人详情的 `participant_user_id`），不使用 Fineract clientId。equal模式按分均分，余数按输入顺序分配；custom模式每项必须有金额且总和相等。发起人参与的份额为SELF_PAID；他人不能代为授权。付款请求创建后即禁止修改分摊，首笔成功后冻结。取消只关闭未付款项，已经付款不自动退款。

### 账单与报告

流水输入使用 `page/page_size/from_date/to_date/min_amount/max_amount/direction`；本镜像原生 `offset` 是页号。报表完整读取全部页，分页总数变化或去重后不完整时明确拒绝生成。上游不提供跨页原子快照，返回 `snapshot_atomic=false`。

分类优先级为人工指定类别→按 priority 确定性规则→已批准 Demo 卡授权的商户类别→未分类。规则匹配 merchant/note/type，priority 为 0–1000、数值越大越优先；禁止从金额猜商户或类别。分类、规则、人工标注的新增/变更/删除写资源审计；异常核实只在状态发生变化时写审计。前端修改个人语义数据后刷新流水、统计和异常查询，保存的报告与聊天私有结果仍保留各自快照。撤销和冲正不计入统计；普通转账、本人互转、Demo 卡消费、定存本金、冻结和费用分别计量，`direction_totals`区分流入与流出，`totals`是各类正金额合计而非净收支。定存整笔赎回通过核心转账、已关闭账户本金及总支取事实核验后拆出利息；无法严格核验的归入 fixed_transfer，不猜测利息。

异常仅返回候选：`LARGE_V1` 要求≥1000元、此前90天同类至少10条、超过中位数三倍；`DUPLICATE_V1` 要求同账户、同日、同已知商户、同金额的不同交易。返回规则编号、样本数/中位数/交易ID等证据；可标记 verified/ignored。个人 Agent 分析读取保留候选生成时的 `status`，并按当前用户核实表补充 `current_review_status`，不改写快照。聊天、洞察和实时账单复用同一核实控件；确认/忽略后同步已加载的同候选卡、失效异常与私有分析查询，成功状态可反向纠正。

即时消费分类统计使用 `/api/billing/statistics`，不保存报告。完整报告通过 `POST /api/bill-report-generations` 按需保存，JSON 示例：

```json
{"account_id":null,"period":"2026"}
```

`account_id` 必须显式提供；`null` 表示本人全部合格账户，具体 ID 表示单账户。`period` 使用 `YYYY-MM` 或 `YYYY`；当前月/年可生成阶段报告，截止日固定为任务提交时的上海本地日期。未来期间拒绝生成。`Idempotency-Key` 按用户作用域；相同键和请求体重试返回原任务，换新键会创建新版本。接口只入队，独立 worker 负责报告生成。

摘要列表支持 `period_from/period_to`、`account_id`、`status` 和 `page/page_size`；每条摘要包含原始 `account_scope/scope_account_id`，用于重生成时沿用全部账户或单账户范围。交易快照支持 `from_date/to_date/direction/category` 和分页。旧 `/api/bill-reports` GET/POST 保留同步报告契约，新页面和 Agent 使用新生成入口。历史列表可打开、按原范围重新生成新版本或删除版本。

报告固定账户依赖、期间和截止时间，包含收入、消费、费用、对外转账、本人互转、本金流动、净现金流、分类占比、趋势、可比期间、消费习惯、异常及周期支出。金额和分类由中端确定性计算，消费分类占比以本期消费为分母；本人互转不计入收入/消费，跨账户两端按交易引用去重。没有有效流水时收支金额显示为不可确认，不将空数据伪装为零。分类/计算/解读版本与分类配置指纹保存在报告中。核心账本后续变化不改写已生成版本；上游跨页非原子状态会显式标记，读取不完整或账户授权失效时拒绝发布/读取。异常、周期或解读单独失败时可发布部分报告并标出缺失模块。

自然语言解读模型只收到允许的结论代码，不接收原始流水、商户、备注、精确金额、账户标识或报告载荷；模型只能排序白名单结论，中端用保存事实渲染模板。超时或非法输出回退到模板，不阻断事实报告。报告、状态、摘要和交易接口均禁止缓存，并逐次校验归属和依赖账户。删除报告不会删除核心流水。

### 定存与恢复

申购输入 `product_id/from_account_id/amount/term_months`，可显式传入 `assessment_id`；兼容旧客户端未传时，仅选取当前用户最新、未使用且仍在 15 分钟有效期内的申购测评。创建 Action 与占用测评在同一数据库事务中完成，同一测评不能用于第二笔申购。`0002` 以前的一年期历史记录迁移为只读 `legacy` 用途，仍可查询但不会被新申购选中。没有管理员补充元数据的产品可查但不能自动推荐或申购。五题总分5–9/10–14/15–19/20–24/25对应五级。超过承受等级、金额/期限不满足、测评失效或已使用、激励利率无法确定时拒绝，不使用虚构收益。

申购每步独立稳定键；创建后立即保存 holding_id。已开户但审批/激活失败时先 reconcile 读取核心状态，再 resume 进入重新确认及 OTP，不重复开户。已明确返回400/403并核实未完成的审批/激活步骤，可在显式resume及重新确认/OTP后分配该步骤的新稳定尝试键，以避开核心缓存的失败响应；超时或未知结果保持原键，不自动换键。仍在执行的请求不立即续办，需等执行租约过期并核对状态。创建响应丢失时按 `BANK-<Action UUID>` externalId 在本人账户列表唯一核对。找不到唯一引用保持待核对，禁止自动重新开户或补偿资金。

赎回先获取报价，创建请求携带 quote_hash；执行前再次核对日期、金额、利率和收款账户。条件改变返回 QUOTE_CHANGED，取消未执行请求后重新报价和授权。已到期但核心还未更新至MATURED时返回 MATURITY_PROCESSING_REQUIRED，由核心自身到期任务处理，Python业务不代改状态。已成功请求只读，不提供删除入账记录。

## 错误、测试与开发边界

业务错误形状 `{"error":{"code":"…","message":"…","retryable":false}}`。401未登录/令牌无效，404包含跨用户资源隐藏，409用于幂等冲突/状态或报价变化，422请求校验或不兼容产品规则，429锁定/限频，502核心契约/数据错误，503核心不可用/验证码发送器缺失。核心失败不返回假余额或假成功。定存申购沿用 `RISK_ASSESSMENT_REQUIRED` 表示缺失/过期测评，显式重复使用同一测评返回 `ASSESSMENT_ALREADY_USED`；旧客户端未传 `assessment_id` 时仍只自动选择最新未使用测评。

Agent 写 Tool 另有确定性 `AGENT_WRITE` 熔断门。10 分钟内累计 5 次敏感输入、Prompt Injection 或被中端识别的权限/伪造引用/幂等滥用后，后续 Agent 写 Tool 在实际 Service 调用前返回 423 `SECURITY_LOCKED`，锁定 15 分钟；模型输出不能取消、缩短或绕过。熔断只限制 Agent 写入，普通认证只读页面与 API 保持可用。安全事件只保存规则编号、错误码和脱敏计数，不保存原始秘密、完整提示词、Token、OTP 或卡号。

```bash
# 首选：独立 bank_agent_test 数据库，包含并发测试
apps/backend/.venv/bin/python scripts/testing/run_banking_tests.py
# 不依赖 PostgreSQL 的快速测试（并发测试会跳过）
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 apps/backend/.venv/bin/python -m pytest tests/integration -q
# 显式真实契约验证，会创建和使用隔离 Demo 账户并产生真实核心资金流水
apps/backend/.venv/bin/python scripts/testing/probe_banking.py
```

真实探针要求已配置 ADMIN_PASSWORD、development 环境及开发验证码收件箱。仅使用专属 Contract Probe 客户与账户。到期契约涉及原生租户级成熟任务，脚本先检查整个租户定存及零存整取账户均属于隔离探针客户；存在其他定存或无法完整盘点时拒绝运行该任务。证据输出为 [banking-live-contracts.json](../testing/banking-live-contracts.json)，测试资源引用保存在被忽略的 `.runtime/banking-probe-state.json`，不自动删除资金记录。业务测试使用 bank_agent_test，绝不 truncate bank_agent 或 Fineract 数据库。

当前仍没有生产短信通道、真实支付网络或通用投资产品。普通借记卡的申请、激活、安全查看、限额/渠道、状态机和受控 Demo 商户消费已经接入；后者会真实移动 Fineract Demo 资金，但卡号和商户网络本身仍是比赛模拟。订阅识别和 Demo 取消也已接入，但不会连接或冒充真实第三方会员系统。前端已经接入登录、确认/OTP、六类业务功能页、统一 Agent 面板和固定生日任务时间线；花店/蛋糕店及下单网络同样是明确标注的受控 Demo Adapter，只有资金预留和成功转账以 Fineract 为事实来源。分页可能并发变动、核心拒绝未来业务日期等情况会报错；客户端按明确状态处理，不绕过授权或伪造结果。


## 六类异常检测补充契约（2026-10-23）

`GET /api/billing/anomalies` 参数不变，默认单账户列表/全账户对象兼容；`include_metadata=true` 统一返回精确对象。新增 `expense_count` 为范围内消费数、`dependency_account_ids` 为个人特征和订阅付款检查实际读取账户集合；后者用于私有快照权限重验，不扩展卡片交易展示范围。

新增类型为 `SPENDING_SURGE_V1`、`DAILY_CONCENTRATION_V1`、`MERCHANT_DEVIATION_V1`、`CATEGORY_MIX_SHIFT_V1`、`SUBSCRIPTION_DEVIATION_V1`、`ACCOUNT_HABIT_SHIFT_V1`。候选可带 `anomaly_types` 和 `findings`，每项 finding 含 `type/sources/window/provisional/evidence`；来源为 `rule/model`，窗口含 `from_date/to_date`。精确交易集合一致时合并，保留已有规则键与核实状态；仅重叠不合并。

年度历史上限经确认采用1200天，月度180天，基线仍需此前至少3笔稳定扣费。

未见订阅扣费使用 `observation_kind=expected_charge_not_observed`，`transactions/transaction_ids` 为空，证据只有预期日/截止日/商户等观测事实，不伪造零元交易。稳定键按订阅、预期周期、账户范围生成。

`detection.capabilities` 以六个类型码为键，值含 `status=completed|partial|skipped`、实际 `sources`、固定 `skip_reasons` 和 `cutoff_date`。`detection.profiles` 逐项显示模型推理可用性；`partial/provisional` 标识覆盖限制及当日提示。顶层模型 ready 仅表示至少一个配置实际完成推理，不能理解为六类全部由机器学习完成。

Agent Tool 参数与事件不变。白名单新增 `PARTIAL_DETECTION/PROVISIONAL_FINDINGS`；小样本和非整月仍仅提供受限摘要，所有新证据仅授权私有GET可见。订阅观测也不得进入模型输入、状态或日志。

## 2026-10-27：订阅扫描 Agent 协议

POST /api/agent/messages 接受自然语言“帮我识别订阅扣费”，沿用认证和请求字段。新增响应事件 SUBSCRIPTION_SCAN_COMPLETED，data 必含非负整数 created、updated、found、matched_candidates，ISO 日期 from_date/to_date、带时区 scanned_at，以及固定 timezone=Asia/Shanghai。事件不含 items 或私有商户/金额。

扫描固定全部本人合格账户最近800天，保存候选与审计，不自动核实。found 保留全部已保存订阅数量语义；matched_candidates 是本次规则匹配数。普通订阅 API 兼容，Service.scan 仅增加可选 trace_id 关键字参数。

订阅请求与其他领域组合返回 422 `AGENT_SUBSCRIPTION_SEPARATE_REQUEST`；扫描或取消与其他工具同批调用会被拒绝，返回 `AGENT_SUBSCRIPTION_SEPARATE_REQUEST`。未获准工具返回 `AGENT_TOOL_NOT_ALLOWED`。模型不调用工具时返回无成功事件的确定性提示。列表、续费、核实和忽略意图不隐式触发扫描。

扫描成功直接结束图，中端生成成功文字和摘要。同 trace_id 关联业务及 Agent 审计。扫描内部已提交，后续失败不能推断未执行；前端超时为 WRITE_RESULT_UNKNOWN、retryable=false，不自动重发，先核对订阅页最近扫描时间。此为恢复提示，不是新增跨请求恰好一次保证。

取消意图路由至 subscriptions 域。商户名称按大小写和空白规范化后，必须唯一匹配当前用户的 Demo 订阅；无匹配或有多个匹配时拒绝创建 Action。Tool 使用随机幂等键调用现有取消 Service，Service 会复用仍有效的关联 Action 或创建新 Action。事件不携带商户、金额、周期或订阅 ID；前端链接到授权 Action 页面重新读取并展示详情。WAITING_CONFIRMATION 状态仅表示待核对，只有用户在页面点击确认后才会执行取消。本轮未执行新增 Agent 取消流程测试或真实模型验收。

## 2026-10-27：Demo 订阅取消 Agent

POST /api/agent/messages 可发起单个 Demo 订阅取消请求，响应事件 SUBSCRIPTION_CANCEL_REQUESTED 包含 action_id 和 Action status。Tool 的模型可见参数仅 merchant；中端检查商户出现在用户原话、本人订阅商户唯一精确匹配并为 Demo，Service 检查状态及复用 Action。常见否定表达会被拒绝；复杂意图仍依赖模型，最终确认由用户在 Action 页面完成。

首次请求为 WAITING_CONFIRMATION，不表示取消成功。GET /api/actions/{id} 按本人重新读取快照；POST /api/actions/{id}/confirm 校验 request_hash 后进入确定性状态机，执行前重验快照。仅 SUCCEEDED 代表确认成功；失败、过期、撤回及未知结果使用既有 Action 恢复规则。请求超时不得自动重发；Agent 生成的幂等键不提供跨请求同键重放保证，当前有效请求由 Service 复用。

完整商户名的单一取消请求增加确定性匹配：在当前用户订阅中唯一匹配的 Demo 商户可纠正模型无工具调用或截短商户名称的问题；匹配限定整句的简单取消/退订表达，不处理否定、混合业务或多目标。原有 Action 确认、幂等及结果未知恢复规则不变。
