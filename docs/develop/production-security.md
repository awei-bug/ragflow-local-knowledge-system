# 生产部署安全基线

本文定义 RAGFlow 源码部署在企业生产环境中的最低密钥、初始化账号和网络暴露要求。开发模式继续兼容仓库现有本地默认值；生产模式必须显式启用并通过 fail-fast 校验。

## 1. 部署模式

唯一支持的值：

```text
RAGFLOW_DEPLOYMENT_MODE=development
RAGFLOW_DEPLOYMENT_MODE=production
```

变量未设置时使用 `development`。任何拼写错误都会直接终止启动，不会静默降级到开发模式。API、worker 和其他调用 `common.settings.init_settings()` 的进程均执行同一校验。

## 2. 生产密钥要求

生产模式必须从 Secret 管理系统注入下列活动配置，禁止提交到 `.env`、Helm values、镜像或仓库：

| 条件 | 必需变量 | 最低长度 |
| --- | --- | ---: |
| 始终 | `RAGFLOW_SECRET_KEY` | 32 |
| 始终 | `REDIS_PASSWORD` | 16 |
| `DB_TYPE=mysql` | `MYSQL_PASSWORD` | 16 |
| `DB_TYPE=postgresql` | `POSTGRES_PASSWORD` | 16 |
| `STORAGE_IMPL=MINIO` | `MINIO_PASSWORD` | 16 |
| `DOC_ENGINE=elasticsearch` | `ELASTIC_PASSWORD` | 16 |
| `DOC_ENGINE=opensearch` | `OPENSEARCH_PASSWORD` | 16 |
| `DOC_ENGINE=oceanbase` | `OCEANBASE_PASSWORD` | 16 |
| `DOC_ENGINE=seekdb` | `SEEKDB_PASSWORD` | 16 |
| `RAGFLOW_CRYPTO_ENABLED=true` | `RAGFLOW_CRYPTO_KEY` | 32 |

校验会拒绝空值、仓库历史默认值、明显占位符、长度不足和字符多样性不足的值。异常只包含变量名和失败原因，不包含密钥原文。

可使用企业密码生成器；临时生成示例：

```bash
openssl rand -base64 48
```

## 3. 超级管理员初始化

开发模式仍可沿用原有本地流程。生产环境执行 `--init-superuser` 时，`DEFAULT_SUPERUSER_PASSWORD` 必须显式注入且满足 16 字符最低要求；`admin`、`password`、占位符和历史默认值会在写数据库之前被拒绝。

初始化完成后仍应通过身份平台或管理流程轮换一次密码，并记录审计事件。自动初始化不应长期保留在启动参数中。

## 4. Docker Compose 生产路径

生产覆盖层位于：

```text
docker/docker-compose.production.yml
```

它执行两项强制策略：

1. 向 RAGFlow 容器注入 `RAGFLOW_DEPLOYMENT_MODE=production` 和由宿主 Secret 环境提供的凭据；
2. 删除 Elasticsearch/OpenSearch/Infinity/OceanBase/SeekDB、MySQL、MinIO、Redis、NATS、TEI、Jaeger、Kibana、ClickHouse 和 sandbox manager 的宿主机端口，只保留 RAGFlow Web 的 80/443 映射。

覆盖层使用 Compose `!reset` / `!override` 标签。部署机必须使用支持这些标签的现代 Docker Compose；本地已用 Docker Compose v5.3.0 解析验证。

Linux/WSL2 部署示例：

```bash
cd /path/to/ragflow
export RAGFLOW_SECRET_KEY="$(openssl rand -base64 48)"
export MYSQL_PASSWORD="$(openssl rand -base64 36)"
export REDIS_PASSWORD="$(openssl rand -base64 36)"
export MINIO_PASSWORD="$(openssl rand -base64 36)"
export ELASTIC_PASSWORD="$(openssl rand -base64 36)"

python tools/ops/validate_production_config.py
docker compose \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.production.yml \
  up -d
```

`validate_production_config.py` 检查 Docker 实际解析后的 JSON，而不是只扫描 YAML 文本。它会拒绝内部服务端口发布、缺少生产模式和弱密钥。不要保存或打印 `docker compose config --format json` 的输出，因为其中包含解析后的凭据。

如确有堡垒机调试或受控运维入口，可用 `--allow-published-service SERVICE` 显式豁免；豁免必须进入变更记录并在维护结束后撤销。

## 5. Helm / Kubernetes

Helm 默认 values 已移除内置密码。生产推荐由 External Secrets、Vault 或平台密钥服务创建 Kubernetes Secret，并设置：

```yaml
secrets:
  existingSecret: ragflow-production-secrets
```

Chart 将普通运行配置写入 ConfigMap，将凭据从外部 Secret 加载。未配置 `existingSecret` 时，Chart 可以生成 Secret，但所有 `env.*PASSWORD` 和 `env.RAGFLOW_SECRET_KEY` 必须通过受保护且不入库的 values 文件提供。

Kubernetes Secret 至少需要：

- `RAGFLOW_SECRET_KEY`
- `MYSQL_PASSWORD`、`MYSQL_ROOT_PASSWORD`
- `MINIO_PASSWORD`、`MINIO_ROOT_PASSWORD`
- `REDIS_PASSWORD`
- 活动检索引擎的密码；Infinity 无此项

## 6. 验证与轮换

每次发布前：

```bash
python -m pytest -q \
  test/unit_test/common/test_production_security.py \
  test/unit_test/tools/test_validate_production_config.py \
  test/unit_test/tools/test_helm_security_contract.py
python tools/ops/validate_production_config.py
```

轮换顺序：先在依赖服务和 Secret 管理系统创建新凭据，再滚动更新应用，验证健康检查与业务抽检，最后撤销旧凭据。`RAGFLOW_SECRET_KEY` 轮换会使现有会话失效，应安排维护窗口并提前通知。

## 7. 当前边界

- Compose 覆盖层已完成静态解析和自动预检，但尚未在当前机器执行真实容器启动；Docker Linux Engine 仍不可用。
- 当前机器没有 Helm CLI，因此 Helm 模板已做静态契约测试，仍需在 CI 或 Linux 发布环境执行 `helm lint` 与 `helm template`。
- Secret 自动轮换、双密钥过渡和审计事件属于后续密钥生命周期治理，ER-008 在完成真实部署验证前保持进行中。
