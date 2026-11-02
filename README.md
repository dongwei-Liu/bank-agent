# Bank Agent

Bank Agent（智汇银行）是一个比赛用个人银行 Web App：React 提供页面和智能助手入口，Python/FastAPI 中端负责身份、业务规则、Action/OTP、审计与 Agent 编排，Apache Fineract 保存账户、余额、流水、转账和定存等资金事实。

公共源码仓库：[dongwei-Liu/bank-agent](https://github.com/dongwei-Liu/bank-agent)。

## 从零部署

新电脑只拉取仓库后，请直接按下面的完整文档操作：

- [Windows 从零部署指南](docs/deployment/local-environment-requirements.md)

不要跳过 `.env`、Fineract Seed 或中端初始化。最短顺序是：

1. 安装 Git、Docker Desktop、Python 3.11–3.13、Node.js 22.12+；
2. 克隆仓库并从 `.env.example` 创建 `.env`；
3. 安装 Python 与前端依赖；
4. 启动 PostgreSQL/Fineract；
5. 在隔离 Demo 环境执行 Fineract Seed，再初始化中端数据库；
6. 分别启动 FastAPI、Banking Worker、Agent Worker 和 React；
7. 打开 <http://127.0.0.1:5173>。

## 日常启动

完成首次部署后，在项目根目录启动核心银行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\start.ps1
```

再分别打开四个 PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\development\start-backend.ps1
```

```powershell
Set-Location .\apps\backend
.\.venv\Scripts\python.exe .\worker.py
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\development\start-agent-worker.ps1
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\development\start-frontend.ps1
```

常用地址：

- Web App：<http://127.0.0.1:5173>
- 中端健康检查：<http://127.0.0.1:8080/api/health>
- Swagger：<http://127.0.0.1:8080/docs>
- Fineract 健康检查：<https://localhost:8443/fineract-provider/actuator/health>

停止三个中端进程和前端时，在各自终端按 `Ctrl+C`。保留数据库数据停止 Docker 服务：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\stop.ps1
```

不要执行 `docker compose down -v`，否则会删除 PostgreSQL 数据卷。

## 主要能力

- 本人账户、余额和流水；
- 联系人、普通转账、本人互转、定时转账和 AA 收款；
- 账单统计、报告、异常候选和订阅管理；
- 普通借记卡与受控 Demo 商户交易；
- Fineract 原生 CNY 定存产品、风险测评、申购与赎回安全流程；
- 持久化 Agent 会话、结构化结果卡和固定生日任务 DAG。

模型只负责理解和调用白名单 Tool；身份、权限、幂等、确认、OTP、执行和核对由中端确定性代码控制。卡片网络、订阅商户和鲜花/蛋糕商户属于明确标注的 Demo 能力。

## 项目结构

```text
bank-agent/
├── .env.example
├── .gitattributes
├── .gitignore
├── AGENTS.md
├── README.md
├── apps/
│   ├── backend/              FastAPI 中端与 Agent
│   │   ├── agent/prompts/    领域 Prompt
│   │   ├── agent/tools/      领域 Tool
│   │   ├── api/ clients/ core/
│   │   ├── migrations/versions/
│   │   ├── schemas/ services/
│   │   ├── main.py models.py alembic.ini requirements.txt
│   │   └── worker.py agent_worker.py
│   └── frontend/             React Web App
│       ├── public/ src/
│       ├── src/agent auth components hooks lib pages test/
│       ├── e2e/support/
│       └── package.json package-lock.json
├── docs/
│   ├── api/ architecture/ demo/ deployment/ design/
│   ├── development/ project/ requirements/ security/
│   └── submission/ testing/
├── infrastructure/
│   ├── docker/
│   └── windows/repair/
├── scripts/
│   ├── development/ fineract/ maintenance/ testing/
└── tests/
    ├── api/postman/
    ├── evaluation/
    └── integration/
```

公共仓库不包含本机 VS Code 配置、`.env`/`.runtime`、依赖和构建目录，或独立的 Apache Fineract 上游源码。首次部署所需内容见 [Windows 从零部署指南](docs/deployment/local-environment-requirements.md)。

全局实时进度以 [master-plan.md](docs/project/master-plan.md) 为准，文件用途以 [project-structure.md](docs/project/project-structure.md) 为准。团队开发前请先阅读根目录 [AGENTS.md](AGENTS.md)。

## 验证

```powershell
.\apps\backend\.venv\Scripts\python.exe .\scripts\testing\run_banking_tests.py -q
Set-Location .\apps\frontend
npm run lint
npm test
npm run build
```

真实模型评估、Demo Reset、OTP 和资金写操作不会作为普通验证自动执行；这些操作必须在隔离 Demo 数据上按部署文档显式授权。
