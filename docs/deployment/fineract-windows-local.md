# Fineract 本地开发环境（Windows / Linux）

当前状态（2026-10-08）：Windows 与 Linux 均使用 Docker Compose 启动 PostgreSQL 和 Fineract。Windows 已实测健康接口返回 `UP`，默认账号查询客户返回 HTTP 200，默认业务库已完成初始化。

普通部署使用固定 Fineract 镜像，不需要源码。公开项目仓库不包含 Apache Fineract 上游源码；如需源码级调试，可在项目根目录把 <https://github.com/apache/fineract.git> 单独克隆到 `platform/fineract`，再检出已验证提交 `b56917ebd5253e8b69e865b75387bf3e9a2e0f99`。默认运行镜像固定为 `apache/fineract@sha256:ab9f271fb27f445ac0622fbdae00c84e0780f957adc1bba356925b0e3b26a38d`，避免 `latest` 漂移。

## 环境与运行

Windows 使用 Docker Desktop 的 Linux 容器与 WSL2 后端；Linux 使用 Docker Engine 与 Docker Compose 插件。PostgreSQL 在容器内运行；仅从源码重建 Fineract 镜像时需要 Java 25。没有项目 JDK 时，仓库脚本会复用 `gradle:9.7.1-jdk25` 容器，不修改系统 Java。数据库镜像固定为 `postgres:18.3`。

修改 `platform/fineract` 源码不会自动更新容器。需要先执行 `:fineract-provider:jibDockerBuild` 生成本地 `fineract:latest`，再把本机 `.env` 的 `FINERACT_IMAGE` 改为该标签并重建 Fineract 服务；未改源码时继续使用固定摘要镜像。

### Windows 启动与停止

1. 完成 Docker Desktop 首次启动设置，启用 WSL2 / Linux containers。如 Windows 提示重启，先重启。
2. 在 PowerShell 执行：

```powershell
$ProjectRoot = Join-Path $env:USERPROFILE "bank_agent"
Set-Location $ProjectRoot
powershell -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\start.ps1
```

脚本保留已有密码，启动容器，并在 Fineract 容器内部检查健康接口。首次启动需下载镜像及执行数据库迁移，可能耗时数分钟。使用容器内检查是为了避开部分 Windows Schannel 对 Fineract 过期自签名开发证书的兼容问题。

停止（保留数据）：`powershell -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\stop.ps1`。

### Linux 启动、测试与关闭

以下命令均在项目根目录执行。需要 Docker Engine、Docker Compose 插件以及根目录 `.env`。`.env` 中至少应配置固定摘要的 `FINERACT_IMAGE`、`POSTGRES_ADMIN_PASSWORD`、`FINERACT_DB_PASSWORD` 和 `FINERACT_MASTER_PASSWORD`，三个密码应使用各自独立的随机值，不得提交该文件。

如果本机还没有 `fineract:latest`，先从迁入项目的源码构建：

```bash
cd platform/fineract
./gradlew :fineract-provider:jibDockerBuild --no-daemon
cd ../..
```

启动 PostgreSQL 与 Fineract：

```bash
docker compose --env-file .env -f infrastructure/docker/compose.yaml up -d
docker compose --env-file .env -f infrastructure/docker/compose.yaml ps
```

首次启动需要初始化数据库和执行迁移，通常比后续启动慢。可查看 Fineract 日志：

```bash
docker compose --env-file .env -f infrastructure/docker/compose.yaml logs -f fineract
```

健康检查：

```bash
curl -k --retry 60 --retry-delay 5 --retry-connrefused \
  https://localhost:8443/fineract-provider/actuator/health
```

该命令会在首次迁移尚未完成时每 5 秒重试。预期结果包含 `"status":"UP"`。测试默认租户的 Clients API：

```bash
curl -k \
  -u mifos:password \
  -H "Fineract-Platform-TenantId: default" \
  https://localhost:8443/fineract-provider/api/v1/clients
```

空数据库的预期结果为：

```json
{"totalFilteredRecords":0,"pageItems":[]}
```

正常关闭并保留数据库和附件卷：

```bash
docker compose --env-file .env -f infrastructure/docker/compose.yaml stop
```

再次启动仍使用前述 `up -d` 命令。不要执行 `docker compose down -v`；`-v` 会永久删除 `bank-agent_postgres_data` 和附件卷。

## 数据库配置

| 设置 | 值 |
| --- | --- |
| 宿主机客户端地址 | `127.0.0.1:5432` |
| 容器内数据库地址 | `db:5432` |
| 应用用户名 | `fineract` |
| 应用密码 | `.env` 中 `FINERACT_DB_PASSWORD` |
| 租户目录库 | `fineract_tenants` |
| 默认租户业务库 | `fineract_default` |
| 数据库管理员 | `postgres`，密码为 `.env` 中 `POSTGRES_ADMIN_PASSWORD` |
| 租户标识 | `default` |
| 租户时区 | `Asia/Shanghai` |

初始化脚本仅在空数据卷第一次启动时执行；应用账号拥有两个库，不使用数据库超级用户。表结构由 Fineract 启动迁移创建。

数据在 Docker named volume `bank-agent_postgres_data` 中，不在源码目录。附件存放在独立持久化卷。不要运行 `docker compose down -v`，该命令会删除持久化卷。已有数据库初始化后，仅修改 `.env` 不会更改数据库内的密码；需要同步执行数据库密码变更。

## API 与检查

- 后端：`https://localhost:8443/fineract-provider`
- 健康接口：`https://localhost:8443/fineract-provider/actuator/health`
- 初始演示账号：`mifos` / `password`
- 请求头：`Fineract-Platform-TenantId: default`
- 开发环境使用自签名 HTTPS 证书。

Windows PowerShell：

```powershell
docker compose --env-file .env -f infrastructure/docker/compose.yaml ps
docker compose --env-file .env -f infrastructure/docker/compose.yaml logs --tail 100 fineract
docker compose --env-file .env -f infrastructure/docker/compose.yaml exec -T fineract wget --no-check-certificate -qO- https://127.0.0.1:8443/fineract-provider/actuator/health
docker compose --env-file .env -f infrastructure/docker/compose.yaml exec -T fineract wget --no-check-certificate -qO- --header="Fineract-Platform-TenantId: default" --header="Authorization: Basic bWlmb3M6cGFzc3dvcmQ=" https://127.0.0.1:8443/fineract-provider/api/v1/clients
```

端口仅绑定本机，当前配置用于本地开发。正式共享前需要更改默认应用密码和配置可信证书。

## Windows 依赖排查

Docker Desktop 已通过 winget 安装。如 Docker 提示 WSL 缺失或版本过低，在管理员 PowerShell 执行 `wsl --install --no-distribution` 和 `wsl --update`，按系统提示重启。BIOS/UEFI 需要启用硬件虚拟化。

官方当前开发文档建议至少 16GB RAM 和 8 核 CPU。本配置 Java 堆上限为 2GB；这只是堆限制，不是整个系统的内存需求。

Windows 组件修复及更新已完成，Docker/WSL 已通过实际容器运行验证。此前的临时诊断日志已在 2026-11-01 工作区安全清理中删除；后续故障应重新采集当前日志，避免使用过期环境证据。
