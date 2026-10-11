# 售后知识助手（场景包）

## 1. 解决的企业问题

客服/技术支持每天重复回答同类问题，口径不统一，新人上手慢，处理时效差。

本场景目标：

> 让客服在 10 秒内，基于官方 SOP 得到可执行步骤，并附带来源，不编造。

## 2. 不做的事（避免跑偏）

- 不做通用企业百科
- 不做自动建工单/自动退款（可二期）
- 不接全公司所有文档（只接售后权威文档）

## 3. 成功标准（可验收）

1. Top20 售后问题中，至少 16 题答案正确且可执行
2. 有效回答必须带来源片段
3. 文档未覆盖的问题，明确回复“知识库未覆盖”，不硬编
4. 仅售后相关角色可访问该库
5. 业务方连续试用 5 个工作日，有未命中问题回流机制

## 4. 本周执行顺序

1. 启动 RAGFlow（Docker）
2. 配 Chat（Agnes）+ Embedding（通义等）
3. 创建知识库「售后支持库」
4. 按文档清单导入并完成解析
5. 运行 Top20 自动验收并保存报告
6. 修文档/补条目，直到达标
7. 给 3~5 名客服试用

详细文件：
- `sales-playbook.md` **销售方案**（话术、套餐、演示、异议、报价结构）
- `sales-one-pager.md` **客户一页纸**（可发邮件/转 PDF）
- `pilot-contract-appendix.md` **试点合同附件**（范围、验收、责任、免责）
- `knowledge-structure.md` 知识库结构
- `document-checklist.md` 文档清单
- `roles-permissions.md` 权限
- `prompt-policy.md` 回答规范
- `acceptance/questions-20.md` 验收规则与运行说明
- `acceptance/questions-20.json` 自动评分数据集
- `acceptance/run_acceptance.py` 真实服务/离线响应验收 Runner
- `go-live-checklist.md` 上线清单
- `建库引导.md` 页面建库步骤
- `sample-docs/` 演示用示例 SOP

## 5. Top20 自动验收

真实服务运行：

```bash
export RAGFLOW_API_KEY='...'
export RAGFLOW_CHAT_ID='...'
python enterprise-aftersales/acceptance/run_acceptance.py
```

离线重放：

```bash
python enterprise-aftersales/acceptance/run_acceptance.py --responses /path/to/responses.jsonl
```

验收不仅要求达到 `32/40`，还强制所有应回答问题展示预期来源、所有库外问题明确安全拒答。当前样例知识库未包含物流破损、B200 冷门配件、远程协助安全、换货检测、错误码手册和政策版本记录；这些问题必须拒答，不能根据常识编造。

`acceptance/results/` 保存报告与原始回答，并默认忽略提交。正式试点需归档一份脱敏后的真实服务验收报告。

