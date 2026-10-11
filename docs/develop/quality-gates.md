# 强制质量门禁

> 生效范围：所有非 Draft PR，以及 `main` 分支 push。工作流检查名为 `enterprise-quality-gates`。

## 门禁内容

1. **测试删除策略**：默认禁止删除任何 tracked 自动化测试。确有必要时，必须在 `.github/test-deletion-allowlist.txt` 写入 `路径 | 覆盖如何被替代`，经评审后随删除一起合并；已无对应删除的陈旧条目会使 CI 失败。
2. **Python 静态检查**：只检查 PR 新增/修改的 Python 文件，固定使用 Ruff `0.12.12`，同时执行 lint 和 format check。
3. **安全回归**：无真实模型 API Key 运行租户作用域隔离、图谱召回、库外拒答、Top20 Runner 和测试配置回归。
4. **Python 单测**：运行 `test/unit_test`，生成 branch coverage JSON。
5. **Diff coverage**：`agent/`、`api/`、`common/`、`deepdoc/`、`memory/`、`rag/` 中新增的可执行 Python 行覆盖率不得低于 80%。这比低价值的全库平均覆盖率更能阻止新技术债。
6. **前端门禁**：`web/` 有变化时，必须通过锁文件安装、ESLint、TypeScript type-check 和 Jest。
7. **Go 门禁**：Go 文件变化时通过仓库规定的 `build.sh --test` 对受影响 package 执行测试；`go.mod/go.sum` 变化时执行全 Go 测试，禁止裸跑 `go test`。

## 覆盖率基线

`pyproject.toml` 的全局 `fail_under` 从 0 提升为 1，先消除“零覆盖也成功”的配置。真正约束增量质量的是 80% changed-line coverage。全库覆盖率应在恢复/替换当前删除测试后按实测结果逐步上调，不能虚构一个当前无法通过的百分比。

## 分支保护设置

仓库管理员需在 GitHub 的 `main` 分支保护规则中：

- 将 `enterprise-quality-gates` 设为 Required status check；
- 禁止管理员绕过（紧急修复走有审计记录的 break-glass 流程）；
- 要求至少一名 Code Owner/维护者批准；
- 要求分支与最新 `main` 同步后才能合并；
- 禁止 force push 和直接删除受保护分支。

代码只能提供检查，**Required status check 必须由仓库管理员在平台侧启用**。启用前 ER-013 不能视为完整闭环。

## 本地验证

```bash
python tools/ci/check_test_deletions.py --base origin/main --head HEAD \
  --allowlist .github/test-deletion-allowlist.txt

python -m pytest -q test/unit_test/tools/test_quality_gate_scripts.py
python -m pytest -q test/unit_test/enterprise_aftersales/test_acceptance_runner.py
python tools/hooks/check_files.py yaml
```

当前工作区已确认存在 45 个 tracked 测试相关文件删除。它们未获得删除确认，因此新门禁会按设计失败；不要通过批量填 allowlist 绕过 ER-002 审计结论。
