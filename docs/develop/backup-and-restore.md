# RAGFlow 备份与恢复闭环

> 适用基线：当前生产配置 `DOC_ENGINE=elasticsearch`、Docker Compose 命名卷、Linux/WSL2。其他检索后端会被工具明确拒绝，未完成对应恢复演练前不得宣称可恢复。

## 目标与责任

| 指标 | 当前目标 | 负责人/证据 |
|---|---:|---|
| RPO | 24 小时 | 每日加密备份及 timer 日志 |
| RTO | 4 小时 | 季度隔离恢复演练报告 |
| 在线保留 | 14 天 | 备份工具只清理自身命名的过期归档 |
| 异地副本 | 至少 1 份 | 对象存储/离线介质，由运维确认复制成功 |
| 恢复演练 | 每季度及重大升级前 | `drill` 输出、卷检查、业务抽检记录 |

企业恢复的事实源是 MySQL、MinIO、Redis 与 Elasticsearch 命名卷。工具复用仓库现有 `docker/migration.sh` 完成一致的卷归档，并在其外增加强制加密、双层 SHA-256 校验、路径穿越防护、保留策略和隔离恢复演练。备份不保存 `.env` 或私钥；部署配置与密钥必须从独立 Secret 管理系统恢复。

## 安全模型

- 备份必须使用 `age` 公钥加密；没有 recipient 时直接失败，不提供明文降级路径。
- 生产机只保存公钥 recipient。私钥 identity 保存在独立恢复机/离线密钥介质，不能提交仓库或放入生产备份目录。
- 加密归档旁的 `.sha256` 先检测传输损坏；`age` 身份认证和归档内每个卷文件的 SHA-256 再检测篡改/损坏。
- 恢复前拒绝绝对路径、`..`、符号链接、硬链接和设备文件，避免恶意归档写出临时目录。
- `drill` 只允许 `ragflow-drill-*` 项目名，并拒绝覆盖任何已存在的演练卷；演练卷带本次运行唯一标签，只有确认归属后才会清理。

## 首次配置

在离线恢复环境生成密钥：

```bash
age-keygen -o /secure/offline/ragflow-backup.agekey
age-keygen -y /secure/offline/ragflow-backup.agekey
```

第二条输出公钥 recipient。只把公钥配置在生产机：

```bash
sudo install -d -m 0700 /etc/ragflow /var/backups/ragflow
sudo install -m 0600 tools/ops/systemd/backup.env.example /etc/ragflow/backup.env
sudo editor /etc/ragflow/backup.env
```

安装 timer（示例假设仓库部署到 `/opt/ragflow`，服务账号已加入 `docker` 组）：

```bash
sudo install -m 0644 tools/ops/systemd/ragflow-backup.service /etc/systemd/system/
sudo install -m 0644 tools/ops/systemd/ragflow-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ragflow-backup.timer
systemctl list-timers ragflow-backup.timer
```

每日 02:30（带最多 15 分钟随机延迟）执行。`--manage-compose` 会记录执行前正在运行的服务，只停止这些服务形成一致快照，并在结束或失败后只恢复同一组服务且等待健康；原本停止的服务不会被意外启动。这会造成计划内停机，应放在维护窗口；如果业务不能接受，应先实施数据库/对象存储原生在线快照方案，再调整 RPO。

## 手动备份与验证

```bash
export RAGFLOW_BACKUP_AGE_RECIPIENT='age1...'
.venv/bin/python tools/ops/ragflow_backup.py backup \
  --output-dir /var/backups/ragflow \
  --project docker \
  --manage-compose \
  --retention-days 14
```

把新归档和同名 `.sha256` 一起复制到异地存储。随后在持有私钥的隔离恢复机验证：

```bash
.venv/bin/python tools/ops/ragflow_backup.py verify \
  --archive /restore/ragflow-backup-YYYYMMDDTHHMMSSZ.tar.gz.age \
  --identity /secure/offline/ragflow-backup.agekey
```

## 生产恢复

1. 宣布维护窗口，冻结写入并记录事故/变更单。
2. 确认目标主机的 RAGFlow 版本、Compose 项目名、容量和 Secret 配置。
3. 先对现状做一次保全备份，不得直接覆盖唯一副本。
4. 执行恢复；现有卷存在时，底层迁移脚本还会要求人工二次确认。

```bash
.venv/bin/python tools/ops/ragflow_backup.py restore \
  --archive /restore/ragflow-backup-YYYYMMDDTHHMMSSZ.tar.gz.age \
  --identity /secure/offline/ragflow-backup.agekey \
  --target-project docker \
  --manage-compose \
  --confirm-restore
```

5. 验证 `docker compose -p docker -f docker/docker-compose.yml ps` 全部健康。
6. 登录系统抽检：用户/租户、知识库数量、随机文档下载、随机检索、来源引用、长期记忆作用域。
7. 记录实际恢复耗时、数据时间点、缺失项和是否达到 RPO/RTO；不达标必须开整改项。

## 隔离恢复演练

在没有同名端口冲突的隔离主机执行（演练只恢复卷，不启动第二套 Compose 服务）：

```bash
.venv/bin/python tools/ops/ragflow_backup.py drill \
  --archive /restore/ragflow-backup-YYYYMMDDTHHMMSSZ.tar.gz.age \
  --identity /secure/offline/ragflow-backup.agekey \
  --target-project ragflow-drill-2026q3
```

工具先预留并标记四个演练卷，验证恢复后卷均非空，再只删除带本次运行归属标签的卷；恢复中途失败也执行归属清理。卷级演练通过后，还必须用隔离端口启动演练项目并完成上述业务抽检，才算完整恢复演练。

演练记录至少包含：

```text
演练日期：
归档时间点：
归档 SHA-256：
Git commit / 产品版本：
恢复主机：
开始/结束时间：
实际 RPO：
实际 RTO：
卷级验证：
业务抽检：
问题与整改 owner/截止日期：
审批人：
```

## 告警与日常检查

```bash
systemctl status ragflow-backup.timer
journalctl -u ragflow-backup.service --since '2 days ago'
find /var/backups/ragflow -maxdepth 1 -name 'ragflow-backup-*.tar.gz.age' -mtime -2 -print
```

监控系统应在 26 小时内没有成功归档、归档尺寸异常下降、异地复制失败或季度演练逾期时告警。systemd timer 只负责调度，不替代集中告警。

## 当前限制

- 截至 2026-09-04，已重新验证：Windows Docker 客户端可用但 Linux Engine 管道不存在，Ubuntu WSL2 也未启用 Docker integration；因此代码、单测和静态验证可以完成，但真实备份/恢复演练尚未执行。
- 当前工具只接受 Elasticsearch 配置。Infinity、OpenSearch、OceanBase、SeekDB、外部 S3/OSS 等部署必须分别实现并演练其原生备份恢复路径后再扩展白名单。
- `docker/migration.sh` 要求卷不被运行容器占用，所以一致备份会产生维护窗口。
