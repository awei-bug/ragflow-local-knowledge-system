# 可复现开发环境（ER-014）

> 适用日期：2026-09-04。本文定义本项目唯一受支持的源码开发路径，避免 Windows 原生 Python、临时跳包脚本和手工修改配置形成多套实现。

## 支持基线

- 操作系统：Linux，或 Windows 11 + WSL2（Ubuntu）。
- Python：3.13.x，由 `uv` 根据 `pyproject.toml` 和 `uv.lock` 管理。
- Node.js：至少 18.20.4；前端必须使用 `web/package-lock.json` 和 `npm ci`。
- Docker：Docker Engine 或 Docker Desktop，并提供 Compose v2。
- Go：使用仓库 `build.sh`；禁止用裸 `go test`/`go build` 代替原生依赖编排。

Windows 原生 Python 不是受支持基线。当前已验证它可能在 `datrie` 编译阶段依赖本机 MSVC，并且容易与 Go 原生静态库、Linux 容器路径产生偏差。Windows 用户应在 WSL2 内执行下列命令。

## 一条命令安装

```bash
bash tools/dev/bootstrap.sh
```

脚本只走项目当前官方路径：

1. 使用锁文件同步 Python 3.13 和 test dependency group；
2. 以 editable 方式安装仓库内 Python SDK；
3. 调用 `ragflow_deps/download_deps.py` 下载解析器和 Go 原生构建依赖；
4. 使用 `npm ci` 安装前端锁定依赖；
5. 启动 `docker/docker-compose-base.yml` 的基础服务。

中国大陆网络可使用镜像：

```bash
RAGFLOW_USE_CHINA_MIRRORS=1 bash tools/dev/bootstrap.sh
```

只准备代码依赖、不启动基础服务：

```bash
RAGFLOW_BOOTSTRAP_START_SERVICES=0 bash tools/dev/bootstrap.sh
```

## 一条命令验证

```bash
bash tools/dev/verify.sh
```

验证内容包括：

- `uv.lock` 未漂移；
- base Compose 配置可渲染；
- 在明确移除模型 API Key 的环境中运行企业级 smoke tests；
- 对本轮安全/图谱代码执行 Ruff；
- 前端 TypeScript type-check 和 ESLint。

该 smoke suite 不访问真实模型，不要求 `ZHIPU_AI_API_KEY` 或 `SILICONFLOW_API_KEY`。需要真实模型和完整服务的 E2E 仍属于独立验收层，不能混入普通单元测试收集阶段。

## WSL2 首次准备

在 WSL2 中先确认：

```bash
python3 --version
uv --version
node --version
npm --version
docker version
docker compose version
```

若 `docker` 不存在，必须在 Docker Desktop 设置中启用当前 Ubuntu 发行版的 WSL integration。若 Node.js 低于 18.20.4，应通过团队统一的 Node 版本管理方式升级；不要从 Windows PATH 混用 `node.exe` 与 WSL 文件系统依赖。

## 禁止的替代路径

- 不使用 `tools/run_uv_sync*.py` 或硬编码本机 `uv.exe` 路径作为团队安装方案。
- 不通过跳过 `datrie`、`graspologic` 等依赖制造“看似可用”的第二套环境。
- 不把真实模型密钥写入测试配置、仓库 `.env` 或测试夹具。
- 不在 Go 代码上直接运行裸 `go test`/`go build`。

## 故障定位

- Python 依赖失败：先确认运行位置是 Linux/WSL2，然后执行 `uv sync --python 3.13 --group test --frozen`。
- Go 原生依赖失败：先检查 `ragflow_deps/` 下载结果、`build.sh` 和 `internal/development.md`。
- 前端缺少 `tsc`/`eslint`：删除不完整的 `web/node_modules` 后重新执行 `npm ci`，不要逐个全局安装工具。
- API Key 报错发生在单元测试收集阶段：视为测试隔离回归；普通单元测试必须可在无密钥环境收集和运行。
