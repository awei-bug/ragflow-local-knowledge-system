# Memory 多租户权限矩阵

> 最后更新：2026-09-04  
> 适用范围：Memory REST 服务、Agent Retrieval、Agent Message 写入以及长期记忆图谱检索。

## 身份定义

- **Owner**：当前认证用户 ID 与 `Memory.tenant_id` 相同。
- **有效团队成员**：存在 `UserTenant.status=VALID` 且 `UserTenant.role=normal` 的关系。
- **非有效成员**：无成员关系、待邀请（`invite`）、已撤销/失效关系，或其他未明确授权的角色。
- **API 外部 subject**：仅在请求通过 `AUTH_API` 认证时允许作为消息的业务 `user_id`；它只影响消息作用域和归属，不授予 Memory 访问权限。

当前租户模型中，团队共享只授予有效 `normal` 成员。`owner` 通过资源所属关系获得权限；尚未启用的 `admin` 关系不会被隐式提升为团队成员权限。

## 权限矩阵

| 操作 | Owner | 有效团队成员 + `team` Memory | 非成员 / invite / revoked | 有效团队成员 + private Memory |
|---|---:|---:|---:|---:|
| 查看配置与消息 | 允许 | 允许 | 拒绝 | 拒绝 |
| 搜索文本与图谱 | 允许 | 允许 | 拒绝 | 拒绝 |
| REST 追加消息 | 允许 | 允许 | 拒绝 | 拒绝 |
| Agent Retrieval | 允许 | 允许 | 拒绝并过滤 Memory ID | 拒绝并过滤 Memory ID |
| Agent Message 写入 | 允许 | 允许 | 不进入写入队列 | 不进入写入队列 |
| 修改 Memory 配置 | 允许 | 拒绝 | 拒绝 | 拒绝 |
| 删除 Memory | 允许 | 拒绝 | 拒绝 | 拒绝 |
| forget / 修改消息状态 | 允许 | 拒绝 | 拒绝 | 拒绝 |

## 后端强制规则

1. Memory ID 列表不能被调用方直接信任，统一通过 `MemoryService.get_accessible_by_ids()` 过滤。
2. 单资源读取使用与列表/Agent 相同的服务层授权规则，避免 API 与 Agent 权限漂移。
3. 修改配置、删除、forget 和消息状态变更必须通过 owner-only 检查。
4. JWT 与浏览器 Session 请求中的 `user_id` 一律替换为 `current_user.id`，防止伪造归属。
5. API Token 请求通过 `g.auth_type == AUTH_API` 识别，可保留外部 subject；Memory 权限仍使用 API Token 对应的认证租户判断。
6. Agent 写入的 `agent_id`、`session_id`、用户问题均从当前 Canvas 获取，忽略参数中的伪造值。
7. Agent Retrieval 只将授权后的 Memory ID 交给搜索，并保留 `user_id` 等消息查询作用域；图谱层继续遵守 `memory_id/user_id/agent_id/session_id` 隔离。
8. 单资源管理拒绝返回 Not Found 语义，避免通过错误差异枚举资源；批量搜索/写入在没有授权 Memory 时不调用底层搜索或队列。

## 自动化验证

```powershell
.venv\Scripts\python.exe -m pytest -q `
  test/unit_test/api/apps/services/test_memory_search_with_graph.py `
  test/unit_test/api/apps/services/test_memory_authorization.py `
  test/unit_test/api/db/services/test_memory_service_authorization.py `
  test/unit_test/api/db/joint_services/test_memory_graph_service.py `
  test/unit_test/memory/services

.venv\Scripts\python.exe -m pytest -q --noconftest `
  test/unit_test/agent/test_memory_authorization.py `
  test/testcases/test_web_api/test_message_app/test_message_routes_unit.py
```

2026-09-04 验证结果：第一组 `30 passed`，第二组 `11 passed`，共 `41 passed`。
