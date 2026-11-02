# Windows 从零部署指南

本文是 Bank Agent 本地部署的统一事实来源。假设电脑上没有项目文件、依赖、Docker 数据或本地配置，从 Git clone 开始完成可运行的前端、中端、Agent Worker 和 Fineract Demo 环境。

本文主路径在 Windows 10/11 + PowerShell 上验证。真实密码、API Key、Token 和完整卡号不得提交到 Git、日志、截图或聊天。

## 1. 部署后会运行什么

```text
浏览器 http://127.0.0.1:5173
        ↓
React / Vite
        ↓ /api
FastAPI 中端 http://127.0.0.1:8080
        ├─ Banking Worker
        ├─ Agent Worker → SiliconFlow / DeepSeek
        ├─ bank_agent PostgreSQL
        └─ Apache Fineract https://localhost:8443
                         └─ Fineract PostgreSQL
```

中端数据库与 Fineract 数据库相互独立。`DATABASE_URL` 只能指向 `bank_agent`，不能指向 `fineract_default` 或 `fineract_tenants`。

## 2. Git 能提供与不能提供的内容

Git clone 后已经具备：

- React、FastAPI、LangGraph 源码；
- `requirements.txt`、`package-lock.json`；
- Docker Compose、数据库迁移、Seed 和启动脚本；
- `.env.example` 配置模板；
- 自动化测试和文档。

每台电脑仍需自行获得：

- Git for Windows；
- Docker Desktop 与 WSL2 Linux 容器引擎；
- Python 3.11–3.13；
- Node.js 22.12 或更高的 22.x；
- Python 包、npm 包、Docker 镜像和本地数据库卷；
- 根目录 `.env` 及其中的本机密钥；
- SiliconFlow API Key（只有 Agent 对话需要）；
- Playwright 浏览器（只有运行 E2E 时需要）。

普通 Docker 部署不需要 Java、Gradle 或 `platform/fineract` 源码。只有修改或编译 Fineract 本身时才单独准备这些内容。

## 3. 安装系统依赖

### 3.1 必需软件

安装并重新打开 PowerShell：

1. Git for Windows；
2. Docker Desktop，启用 WSL2 engine 和 Linux containers；
3. Python 3.11、3.12 或 3.13，安装时勾选加入 PATH；
4. Node.js 22 LTS（最低 22.12）。

验证：

```powershell
git --version
docker version
docker compose version
python --version
node --version
npm --version
```

Docker 命令必须同时显示 Client 和 Server。若只有 Client，先启动 Docker Desktop并等待引擎就绪。

### 3.2 网络与磁盘

首次部署需要访问 GitHub、Docker Registry、PyPI、npm Registry 和 SiliconFlow。建议预留至少 8GB 可用空间。公司代理环境必须允许本机 `localhost`、`127.0.0.1` 和 `::1` 直连。

## 4. 克隆仓库

```powershell
Set-Location $env:USERPROFILE
git clone https://github.com/dongwei-Liu/bank-agent.git bank_agent
$ProjectRoot = Join-Path $env:USERPROFILE "bank_agent"
Set-Location $ProjectRoot
git status --short
```

源码仓库为公开仓库，克隆不需要 GitHub 登录。以上示例将项目克隆到当前用户目录下的 `bank_agent`；后续命令均从项目根目录执行。提交或推送个人分支时，请在 VS Code 或 Git 中使用自己的 GitHub 认证。

## 5. 创建并填写 `.env`

复制模板：

```powershell
Copy-Item .env.example .env
notepad .env
```

至少替换所有 `replace_with_...` 占位符。可以用本机 Python 生成安全值，输出只粘贴到 `.env`：

```powershell
python -c "import base64,secrets; print('POSTGRES_ADMIN_PASSWORD='+secrets.token_hex(24)); print('FINERACT_DB_PASSWORD='+secrets.token_hex(24)); print('FINERACT_MASTER_PASSWORD='+secrets.token_hex(24)); print('BANK_AGENT_DB_PASSWORD='+secrets.token_hex(24)); print('OTP_SECRET='+secrets.token_hex(32)); print('DEMO_PASSWORD='+secrets.token_urlsafe(18)); print('ADMIN_PASSWORD='+secrets.token_urlsafe(18)); print('CARD_ENCRYPTION_KEY='+base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

`BANK_AGENT_DB_PASSWORD` 不是单独的环境变量；把它替换到 `DATABASE_URL` 中：

```dotenv
DATABASE_URL=postgresql+psycopg://bank_agent:<BANK_AGENT_DB_PASSWORD>@127.0.0.1:5432/bank_agent
```

关键变量：

| 变量 | 用途 | 要求 |
| --- | --- | --- |
| `POSTGRES_ADMIN_PASSWORD` | 本机 PostgreSQL 管理账号 | 随机、仅本机 |
| `FINERACT_DB_PASSWORD` | Fineract 数据库账号 | 与管理密码不同 |
| `FINERACT_MASTER_PASSWORD` | Fineract 租户主库 | 随机、仅本机 |
| `DATABASE_URL` | 中端独立数据库 | 必须是 `bank_agent` 用户和库，必须含密码 |
| `OTP_SECRET` | Demo OTP HMAC | 至少 32 字符 |
| `DEMO_PASSWORD` | alice/bob/charlie/mom 登录密码 | 至少 12 字符 |
| `ADMIN_PASSWORD` | 可选管理员登录密码 | 设置时至少 12 字符 |
| `CARD_ENCRYPTION_KEY` | Demo 卡号 AES-GCM 密钥 | URL-safe Base64 编码的 32 字节 |
| `SILICONFLOW_API_KEY` | Agent 模型认证 | 每位开发者使用自己的 Key |
| `SILICONFLOW_BASE_URL` | OpenAI 兼容入口 | 默认 `https://api.siliconflow.cn/v1` |
| `SILICONFLOW_MODEL` | 模型 ID | 当前默认 `deepseek-ai/DeepSeek-V3.2` |

`DEV_OTP_INBOX=true` 只允许 `ENVIRONMENT=development`。没有 SiliconFlow Key 时普通页面和 REST API 仍可使用，但智能助手不能完成模型调用。

`.env` 已被 Git 忽略。不要执行 `git add -f .env`。

## 6. 安装项目依赖

### 6.1 Python 中端

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\development\setup-backend.ps1
```

脚本在 `apps/backend/.venv` 创建虚拟环境并严格按 `requirements.txt` 安装依赖。验证：

```powershell
.\apps\backend\.venv\Scripts\python.exe --version
.\apps\backend\.venv\Scripts\python.exe -m pip check
```

### 6.2 React 前端

```powershell
Set-Location .\apps\frontend
npm ci
Set-Location ..\..
```

必须使用 `npm ci`，不要用一次性的手工安装代替锁文件。

### 6.3 PowerShell 执行策略

本文所有脚本都使用单次 `-ExecutionPolicy Bypass`，不要求永久修改系统策略。若在当前终端直接运行脚本，可临时执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

关闭终端后自动失效。

## 7. 启动 PostgreSQL 与 Fineract

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\start.ps1
```

首次拉取镜像和迁移可能需要数分钟。脚本最多等待 15 分钟并在成功后输出 Fineract 地址。验证：

```powershell
curl.exe -k https://localhost:8443/fineract-provider/actuator/health
```

必须看到 `"status":"UP"`。查看容器：

```powershell
docker compose --env-file .env -f .\infrastructure\docker\compose.yaml ps
```

## 8. 首次创建 Demo 银行数据

以下步骤会写入本机隔离 Demo 租户。不要对生产租户或未经授权的共享租户执行。

先预览：

```powershell
.\apps\backend\.venv\Scripts\python.exe .\scripts\fineract\seed_fineract.py --dry-run --history-seed 20261024 --as-of 2026-10-23
```

确认地址、租户和计划后执行幂等 Seed：

```powershell
.\apps\backend\.venv\Scripts\python.exe .\scripts\fineract\seed_fineract.py --history-seed 20261024 --as-of 2026-10-23
```

Seed 创建或复用：

- Alice、Bob、Charlie、Mom 及其 CNY 储蓄账户；
- 可复现的分类交易历史与 Alice 分析副账户；
- 借记卡关联账户和受控 Demo 商户账户；
- 鲜花/蛋糕任务商户；
- 3 个月和 6 个月的 Fineract 原生 CNY Demo 定存产品。

Seed 不会把真实银行数据写入仓库。再次运行会按稳定 externalId 和产品名复用资源。

## 9. 初始化中端数据库

```powershell
.\apps\backend\.venv\Scripts\python.exe .\scripts\development\init_banking.py
```

该脚本会：

1. 创建独立 `bank_agent` 数据库账号和数据库；
2. 执行 Alembic 到最新 `head`；
3. 创建四个 Demo 登录用户并映射 Fineract 客户；
4. 初始化联系人、分类规则、商户、卡片和定存适配元数据。

已有密码哈希会保留。验证迁移：

```powershell
Set-Location .\apps\backend
.\.venv\Scripts\python.exe -m alembic current
Set-Location ..\..
```

当前仓库应显示 `0012 (head)`。

需要订阅演示样本时再显式执行：

```powershell
.\apps\backend\.venv\Scripts\python.exe .\scripts\development\init_banking.py --demo-billing-fixtures
```

## 10. 启动完整应用

保持 Docker 运行，分别打开四个 PowerShell，均从项目根目录开始。

终端 1：FastAPI 中端：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\development\start-backend.ps1
```

终端 2：银行异步 Worker：

```powershell
Set-Location .\apps\backend
.\.venv\Scripts\python.exe .\worker.py
```

终端 3：持久化 Agent Worker：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\development\start-agent-worker.ps1
```

终端 4：React 前端：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\development\start-frontend.ps1
```

进程职责：

- FastAPI 提供认证和业务 API；
- Banking Worker 执行计划、报告、提醒和已授权任务；
- Agent Worker 领取对话 Run 并调用模型/Tool；
- Vite 提供前端并把 `/api` 代理到 FastAPI。

## 11. 验证部署

连接检查：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\development\test-connection.ps1
curl.exe -k https://localhost:8443/fineract-provider/actuator/health
```

浏览器：

- <http://127.0.0.1:5173>
- <http://127.0.0.1:8080/docs>

使用以下用户名之一登录，密码为本机 `.env` 中的 `DEMO_PASSWORD`：

- `alice`
- `bob`
- `charlie`
- `mom`

模型配置只读检查：

```powershell
Set-Location .\apps\backend
.\.venv\Scripts\python.exe -c "from core.config import get_settings; s=get_settings(); print('base_url=',s.siliconflow_base_url); print('model=',s.siliconflow_model); print('key_configured=',bool(s.siliconflow_api_key))"
Set-Location ..\..
```

不要打印 API Key 本身。

## 12. 运行自动化测试

中端集成测试使用独立的 `bank_agent_test`，不会把普通测试写入演示业务库：

```powershell
.\apps\backend\.venv\Scripts\python.exe .\scripts\testing\run_banking_tests.py -q
```

前端：

```powershell
Set-Location .\apps\frontend
npm run lint
npm test
npm run build
Set-Location ..\..
```

需要浏览器 E2E 时额外安装 Playwright 浏览器：

```powershell
Set-Location .\apps\frontend
npx playwright install chromium
npm run test:e2e
Set-Location ..\..
```

真实模型评估、财富真实栈 E2E、Demo Reset、确认、OTP 和资金写操作均不是普通测试的一部分，必须单独显式启用。财富真实栈 E2E 会调用外部模型并创建待确认 RED Action，但不会自动确认或扣款。

## 13. 日常停止与再次启动

在四个应用终端分别按 `Ctrl+C`。停止 Docker 服务并保留数据：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\stop.ps1
```

下次启动只需执行第 7 节和第 10 节，不要重复 Seed 或初始化。拉取到新迁移后执行：

```powershell
Set-Location .\apps\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
Set-Location ..\..
```

不要执行带 `-v` 的 `docker compose down`；这会删除 PostgreSQL 数据卷。

## 14. 常见故障

### `git` 无法识别

重新安装 Git for Windows，关闭并重新打开 PowerShell，再运行 `git --version`。不要依赖某个编辑器内置的临时 Git 路径。

### PowerShell 禁止运行脚本

使用本文提供的 `powershell -NoProfile -ExecutionPolicy Bypass -File ...`，不要永久降低整机策略。

### `No module named core`

需要导入 `core` 的短命令应先进入 `apps/backend`；项目脚本则从仓库根目录按本文给出的完整路径运行。

### Fineract 出现 `SSL: UNEXPECTED_EOF_WHILE_READING`

若回溯同时含 `http_proxy`，在当前 PowerShell 临时补充本机直连：

```powershell
$env:NO_PROXY = "localhost,127.0.0.1,::1"
$env:no_proxy = $env:NO_PROXY
```

不要关闭 TLS 校验来掩盖代理错误，也不要长期使用 `NO_PROXY=*`。

### 前端显示 401

先在 `/login` 登录。确认 FastAPI 和 Vite 都运行，并用 `test-connection.ps1` 检查代理。清理浏览器 sessionStorage 后重新登录可排除旧 Token。

### Agent 一直处于 `QUEUED` 或请求失败

确认 Agent Worker 正在运行，`.env` 中模型、Base URL 和 Key 已配置，并查看 Agent Worker 终端。普通页面正常不代表模型配置正确。

### 修改 `.env` 密码后无法连接

修改文件不会自动轮换已存在数据库角色或 Demo 用户密码。全新环境可删除本机 Docker 数据卷后重新部署；已有数据必须使用明确的轮换或受控 Reset 流程，不能盲目覆盖。

## 15. 安全边界

- `.env`、`.runtime`、`.venv`、`node_modules`、Docker 数据卷均不进入 Git；
- Fineract 是资金事实来源，中端数据库不保存第二套余额；
- Agent 写 Tool 只能创建受控 Action，不能绕过确认或 OTP；
- `seed_fineract.py` 和 Reset 只能用于明确授权的隔离 Demo 环境；
- Demo Reset 会撤销并重建受控演示数据，默认只预览，执行前必须输入精确确认短语；
- 完整卡号、OTP、密码、Token 和 API Key 不得进入模型消息。

## 16. 可选：Fineract 源码开发

普通运行使用固定 Docker 镜像，不需要 Fineract 源码、JDK 或 Gradle。只有需要阅读、修改或自行编译 Fineract 时，才在 `platform/fineract` 放置独立上游 Git 仓库，并在项目目录外或被忽略的 `tools/` 中准备 JDK/Gradle。该源码单元保持独立 Git 历史，不与 Bank Agent 根仓库混合提交。
