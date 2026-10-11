# 被删除测试审计（ER-002）

> 审计日期：2026-09-04  
> 审计基线：当前 `HEAD` `677960716e06c5ca191b65230adbb768e1df9393` 及未提交工作区  
> 审计方式：只读检查 `git diff --diff-filter=D`、从 `HEAD` 读取被删测试、统计测试函数，并核对对应生产路径；未恢复、移动或提交任何用户文件。

## 结论

- 当前不是“42 个删除文件”，而是 **45 个 tracked 测试相关文件被删除**：其中 **42 个测试模块**、**3 个测试支持文件**。
- 42 个测试模块共包含 **664 个测试函数**；45 个文件合计 **11,319 行**。
- 对应的 Agent、公共工具、连接器、MCP、解析、检索、同步和提交检查生产路径目前都仍存在。
- 当前没有证据表明这些删除是伴随生产功能删除的有意清理，因此 **没有任何一组可判定为安全删除**。
- 风险最高的是 `common/`（379 项）、`data_source/`（191 项）和 `rag/`（70 项）：它们覆盖元数据过滤、时间/Token 工具、企业连接器、检索分页与同步任务。
- 建议在拆分提交之前恢复这些文件；但恢复会改变用户当前工作区，因此保持 ER-002 为阻塞，等待明确确认。

## 分类统计

| 分类 | 测试模块 | 测试函数 | 风险摘要 |
|---|---:|---:|---|
| Agent | 3 | 11 | Canvas 变量、输入重置、DSL 往返契约 |
| Common | 17 | 379 | 元数据过滤、时间、Token、字符串、存储删除查询 |
| Data source | 10 | 191 | BigQuery、OneDrive、Outlook、REST、SharePoint、Slack、Teams、WebDAV |
| MCP | 2 | 7 | 数据集与文档分页 |
| RAG | 8 | 70 | DOCX、分块、排序、RAPTOR、分页、数据源同步 |
| Test infrastructure | 1 | 4 | API proxy/host 配置 |
| Developer tools | 1 | 2 | staged 文件名安全检查 |
| **合计** | **42** | **664** | 不含 3 个支持文件 |

## 逐文件核对

| 被删除测试（相对 `test/unit_test/`） | 测试数 | 对应活跃路径 | 审计判断 |
|---|---:|---|---|
| `agent/test_canvas_at_split.py` | 6 | `agent/canvas.py` | 变量表达式解析，生产路径仍存在；不可自动删除 |
| `agent/test_canvas_input_reset.py` | 4 | `agent/canvas.py` | Canvas 多轮输入重置契约，生产路径仍存在；不可自动删除 |
| `agent/test_dsl_bridge_roundtrip.py` | 1 | `web/src/pages/agent/utils/dsl-bridge.ts；internal/agent/dsl/testdata/` | 前后端 DSL 往返契约仍在使用；不可自动删除 |
| `common/test_apply_semi_auto_meta_data_filter.py` | 2 | `common/metadata_utils.py` | 元数据过滤生产路径仍存在；不可自动删除 |
| `common/test_blob_connector_fingerprint.py` | 15 | `common/data_source/blob_connector.py` | Blob 指纹与增量同步路径仍存在；不可自动删除 |
| `common/test_decorator.py` | 4 | `common/decorator.py` | singleton 工具仍存在；不可自动删除 |
| `common/test_delete_query_construction.py` | 10 | `common/doc_store/es_conn_base.py；rag/utils/es_conn.py；rag/utils/opensearch_conn.py` | 删除查询构造仍是活跃存储路径；不可自动删除 |
| `common/test_dropbox_connector.py` | 2 | `common/data_source/dropbox_connector.py` | Dropbox 连接器仍存在；不可自动删除 |
| `common/test_file_utils.py` | 9 | `common/file_utils.py` | 文件路径工具仍存在；不可自动删除 |
| `common/test_float_utils.py` | 9 | `common/float_utils.py` | 数值转换工具仍存在；不可自动删除 |
| `common/test_llm_request_context.py` | 11 | `common/llm_request_context.py` | LLM 请求上下文仍存在；不可自动删除 |
| `common/test_metadata_filter.py` | 62 | `common/metadata_es_filter.py；common/metadata_infinity_filter.py` | 检索过滤核心路径仍存在；不可自动删除 |
| `common/test_metadata_filter_operators.py` | 22 | `common/metadata_utils.py` | 过滤运算符路径仍存在；不可自动删除 |
| `common/test_misc_utils.py` | 48 | `common/misc_utils.py` | 通用工具仍被生产代码使用；不可自动删除 |
| `common/test_settings_queue.py` | 20 | `common/settings.py` | 队列配置和路由仍存在；不可自动删除 |
| `common/test_string_utils.py` | 50 | `common/string_utils.py` | 字符串处理工具仍存在；不可自动删除 |
| `common/test_tag_feature_utils.py` | 5 | `common/tag_feature_utils.py` | 标签特征路径仍存在；不可自动删除 |
| `common/test_think_stream_parser.py` | 1 | `api/db/services/dialog_service.py` | 流式思考解析路径仍存在；不可自动删除 |
| `common/test_time_utils.py` | 70 | `common/time_utils.py` | 时间工具仍广泛使用；不可自动删除 |
| `common/test_token_utils.py` | 39 | `common/token_utils.py` | Token 工具仍存在；不可自动删除 |
| `data_source/test_bigquery_connector.py` | 28 | `common/data_source/bigquery_connector.py` | BigQuery 连接器仍存在；不可自动删除 |
| `data_source/test_blob_storage_size_threshold_config.py` | 3 | `common/data_source/config.py` | 连接器大小阈值配置仍存在；不可自动删除 |
| `data_source/test_imap_connector_addr_parsing.py` | 11 | `common/data_source/imap_connector.py` | IMAP 连接器仍存在；不可自动删除 |
| `data_source/test_onedrive_connector_unit.py` | 28 | `common/data_source/onedrive_connector.py` | OneDrive 连接器仍存在；不可自动删除 |
| `data_source/test_outlook_connector_unit.py` | 32 | `common/data_source/outlook_connector.py` | Outlook 连接器仍存在；不可自动删除 |
| `data_source/test_rest_api_connector.py` | 61 | `common/data_source/rest_api_connector.py` | REST 数据源连接器仍存在；不可自动删除 |
| `data_source/test_sharepoint_connector_unit.py` | 7 | `common/data_source/sharepoint_connector.py` | SharePoint 连接器仍存在；不可自动删除 |
| `data_source/test_slack_connector_unit.py` | 5 | `common/data_source/slack_connector.py` | Slack 连接器仍存在；不可自动删除 |
| `data_source/test_teams_connector_unit.py` | 8 | `common/data_source/teams_connector.py` | Teams 连接器仍存在；不可自动删除 |
| `data_source/test_webdav_connector_unit.py` | 8 | `common/data_source/webdav_connector.py` | WebDAV 连接器仍存在；不可自动删除 |
| `mcp/test_document_metadata_pagination.py` | 4 | `mcp/server/server.py` | MCP 文档分页路径仍存在；不可自动删除 |
| `mcp/test_server_datasets.py` | 3 | `mcp/server/server.py` | MCP 数据集分页路径仍存在；不可自动删除 |
| `rag/test_docx_question_level.py` | 3 | `rag/nlp/__init__.py` | DOCX 标题层级解析仍存在；不可自动删除 |
| `rag/test_is_english.py` | 5 | `rag/nlp/__init__.py` | 语言判定仍存在；不可自动删除 |
| `rag/test_laws_docx_tables.py` | 5 | `rag/app/laws.py` | 法规 DOCX 表格解析仍存在；不可自动删除 |
| `rag/test_naive_merge.py` | 13 | `rag/nlp/__init__.py` | 基础分块合并仍是核心路径；不可自动删除 |
| `rag/test_rank_feature_scores.py` | 6 | `rag/nlp/search.py` | 检索排序特征仍存在；不可自动删除 |
| `rag/test_raptor_psi_tree_builder.py` | 18 | `rag/raptor.py；api/utils/validation_utils.py` | RAPTOR 配置与构树路径仍存在；不可自动删除 |
| `rag/test_search_pagination.py` | 4 | `rag/nlp/search.py` | 检索分页仍存在；不可自动删除 |
| `rag/test_sync_data_source.py` | 16 | `rag/svr/sync_data_source.py` | 数据源同步编排仍存在；不可自动删除 |
| `test_testcases/test_config_host_address_unit.py` | 4 | `test/testcases/configs.py；test/testcases/conftest.py` | 集成测试运行配置仍存在；不可自动删除 |
| `tools/test_check_files.py` | 2 | `tools/hooks/check_files.py` | 提交前文件检查仍存在；不可自动删除 |

## 被删除的支持文件

| 文件 | 用途 | 判断 |
|---|---|---|
| `test/unit_test/data_source/__init__.py` | data source 测试包标识 | 与整组连接器测试同时删除，不应单独判断 |
| `test/unit_test/data_source/conftest.py` | 连接器测试公共 fixture | 恢复测试模块时应一并恢复 |
| `test/unit_test/rag/conftest.py` | RAG 测试公共 fixture/stub | 恢复 RAG 测试时应一并恢复 |

## 建议处理顺序

1. 用户确认这些删除不是有意行为后，按原路径从 `HEAD` 恢复全部 45 个文件。
2. 先运行纯单元测试分组：`common`、`data_source`、`rag`、`agent`、`mcp`、`tools`。
3. 对环境依赖失败和真实回归失败分开记录；不能因为环境未就绪而再次删除测试。
4. 恢复动作单独形成一个提交，不与图谱、前端或部署配置混合。
5. 若确有功能已删除，应提交“生产代码删除 + 对应测试删除 + 文档更新”的同一原子变更，而不是只删测试。
