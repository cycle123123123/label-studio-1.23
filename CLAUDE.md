# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中编写代码时提供指导。

## 项目概述

Label Studio 1.23.0，开源数据标注工具。本检出为官方 1.23.0 发行版 **加上自定义中文汉化和从内部 "text" 分支迁移的功能**（任务分配、分配管理 API、工作流审计、统计看板、Data Manager 扩展、S3/MinIO 兼容修复）。

迁移功能、本地数据库和服务端部署历史的权威记录请读仓库根目录的 `AGENTS.md`。本文件是通用架构/命令参考。

## 构建与验证命令

### 后端（Python/Django）

Python 环境是 conda 环境，不是默认解释器。使用：

```bash
export PYTHONPATH=D:/work/label-studio-1.23.0/label_studio
export DJANGO_SETTINGS_MODULE=core.settings.label_studio
export DJANGO_DB=sqlite
PYTHON=C:/Users/CYCLE/anaconda3/envs/ls123/python.exe
```

`manage.py` 位于 `label_studio/`。`Makefile` 封装了大部分任务：

| 任务 | 命令 |
|------|---------|
| 开发服务器 | `make run-dev`（SQLite, DEBUG） |
| 迁移 | `make migrate-dev` |
| 生成迁移 | `make makemigrations-dev` |
| Shell | `make shell-dev` |
| 运行测试 | `make test`（= `cd label_studio && DJANGO_DB=sqlite pytest -v -m "not integration_tests"`） |
| 重新生成 URL 注册表 | `make update-urls` → 写入 `label_studio/core/all_urls.json` |
| 生成 swagger | `make generate-swagger` |
| 格式化 / lint 检查 | `make fmt` / `make fmt-check`（pre-commit；python 用 ruff、black、isort） |

**运行单个后端测试**（cwd = `label_studio/`）：

```bash
DJANGO_DB=sqlite python -m pytest tests/test_annotations.py::TestClass::test_name -x
```

注意：`.tavern.yml` API 测试要求 `DJANGO_DB` 指向真实 Postgres，本地 SQLite 环境下会跳过。迁移健康检查（`manage.py migrate --check` 和 `makemigrations --check`）都必须返回 0。

### 前端（web/ — NX workspace）

所有命令在 `web/` 下运行。先执行一次 `yarn install --frozen-lockfile`。

| 任务 | 命令 |
|------|---------|
| Lint/format | `yarn biome check [files]` / `yarn biome check --write [files]` |
| 生产构建（主应用） | `yarn ls:build` → 输出到 `web/dist/` |
| Editor 开发构建 | `yarn nx run editor:build:development` |
| 带 HMR 开发 | `yarn dev`（HMR 服务器在 :8010）或 `make frontend-dev` |
| Editor 单元测试 | `yarn lsf:unit` |
| Datamanager 单元测试 | `yarn dm:unit` |
| Labelstudio 应用单元测试 | `yarn ls:unit` |
| 应用 e2e（Cypress） | `yarn ls:e2e` |
| Editor 集成测试（Cypress） | `yarn lsf:integration` |
| Storybook | `yarn ui:serve`（端口 4400） |

单个前端测试：通过 NX 传 `--testPathPattern`，例如 `yarn nx run editor:unit --testPathPattern=name-of-suite`。

## 架构

### 后端 — `label_studio/`

Django 5.1 + Django REST Framework 3.15 单体应用。入口：`label_studio/server.py`（CLI `label-studio` 控制台脚本）和 `label_studio/manage.py`。设置位于 `core/settings/base.py`（全部由环境变量驱动）+ `core/settings/label_studio.py`（社区版；`DJANGO_DB` 环境变量从 `DATABASES_ALL` 中选择 sqlite/postgresql/mysql）。

Django 应用（每个拥有 models + `api.py` + `serializers.py` + `urls.py` + `migrations/`）：

- `tasks` — `Task`/`Annotation`/`AnnotationDraft` 模型、标注 API、任务分配（`tasks/assignment.py`）。**自定义迁移工作集中在这里。**
- `projects` — `Project` 模型 + API、项目下一任务（`projects/functions/next_task.py`）、signals。
- `data_manager` — Data Manager：任务列表/筛选（`data_manager/managers.py`）、列（`functions.py`）、批量操作（`data_manager/actions/`）。
- `data_import` / `data_export` — 任务导入流水线和标注导出。
- `io_storages` — 云存储提供商（S3, GCS, Azure, local, ...）。每个提供商是子包（`s3/`、`gcs/`、...），含 `models.py`/`serializers.py`/`api.py`。提供商模型必须声明 `app_label = 'io_storages'`。
- `ml`、`ml_models`、`ml_model_providers` — ML 后端（训练/预测 webhook）。
- `organizations`、`users`、`webhooks`、`labels_manager`、`jwt_auth`、`session_policy`、`fsm`（标注工作流状态机）。

`core/` 中的共享基础设施：
- `core/redis.py` — `start_job_async_or_sync(...)`：在 RQ workers（django-rq）上入队后台任务的标准方式。
- `core/current_request.py` — 线程本地 `CurrentContext`（测试后必须清理；见 `conftest.py`）。
- `core/utils/iterators.py` — 大型 queryset 用 `iterate_queryset()`，不要用 `.iterator()`（顺序不保证）。
- `core/all_urls.json` — 生成的 URL 注册表（通过 `make update-urls`）；路由变更时提交它。
- 仓库根目录 `feature_flags.json` — 社区版中 feature flags 始终开启。
- `core/static_build` — 收集的 Django 静态文件，包括构建后的前端。

### 前端 — `web/`

NX workspace，三大组件，各有独立构建目标：

- `apps/labelstudio` — 主应用：路由、设置页、项目页。React 18，状态用 **Jotai** atoms（`src/atoms`），API 客户端在 `src/services`。i18n 用 `react-i18next`，locale JSON 在 `src/locales`。
- `libs/editor`（即 LSF）— 标注编辑器库。React + **mobx-state-tree** stores；标注语言在 `src/tags`（object/control tags），canvas 渲染用 Konva（`src/components`），regions 在 `src/regions`，工具在 `src/tools`。
- `libs/datamanager` — 数据浏览列表视图（筛选、列、批量操作），由后端 `/api/dm/` 端点驱动。
- `libs/ui` — `@humansignal/ui` 设计系统：共享组件（`src/lib/`）、**语义设计 token**（`src/tokens/tokens.scss`）。始终复用这些而不是手写 UI。
- `libs/core` — `@humansignal/core` 共享工具（debounce、字符串工具、lodash 替代）。
- `libs/app-common` — 跨应用共享的组件。
- `libs/frontend-test` — Cypress/Jest 辅助库（`@humansignal/frontend-test/helpers/LSF`）。

包/导入规则（由 lint 强制）：
- 导入别名：`@humansignal/ui`、`@humansignal/icons`、`@humansignal/core`、`@humansignal/app-common`、`@humansignal/frontend-test`。
- `web/apps/*` 可以导入 `web/libs/*`；`web/libs/*` 不能导入 `web/apps/*`。`libs/app-common` 可以导入 apps；其他都不能导入它。
- 不用 lodash — 用 `@humansignal/core/lib/utils/*` 的 es-toolkit 再导出（见 `.cursor/rules/no-lodash.mdc`）；`cloneDeep` → 原生 `structuredClone`。
- 用语义 token（`p-tight`、`text-body-medium`、`bg-primary-surface`），绝不用数字 token（`p-200`、`text-16`、`bg-grape-600`）。见 `DESIGN.md` 和 `.cursor/rules/design.mdc`。

### 前端 ↔ 后端集成

Django 提供构建后的前端服务：生产构建落在 `web/dist/`，被收集进 Django 静态目录，由 Django/nginx 服务。labelstudio 应用通过 `/api/...` 与 REST API 通信（Data Manager 在 `/api/dm`）。`FRONTEND_HMR=true` 时，Django 改从 :8010 的 NX dev 服务器提供 dev bundles。自定义部署将根目录 `dist/` 和 `label_studio/` 覆盖到官方 Docker 镜像上（见 `AGENTS.md`）。

## 约定与坑（实战经验）

- **前端静态 chunk 名固定。** 修改经 Django 服务的前端代码后要硬刷新浏览器（否则旧 bundle 会一直缓存）。
- **i18next 键路径必须与 `t()` 调用完全一致** — 不一致会静默回退英文。Locale 文件在 `web/apps/labelstudio/src/locales/`（3 个命名空间）。
- **`pytest.ini` 设置了 `fflag_feat_fit_568_finite_state_management=1`** — 测试中 FSM 生效；线程本地 `CurrentContext` 每个测试自动清理。
- 手动分配模式与共享多标注者任务池不兼容 — 官方 `test_next_task` 相关用例已在测试文件中 `@skip` 并注明原因。
- 迁移记录名必须与文件名完全一致（重命名迁移但不同步 `name=` 字符串会破坏 Django）。
- `AnnotationSerializer.create` 和几个自定义视图依赖 `transaction.atomic()` — 不要移除；SQLite 无法从损坏事务中的 IntegrityError 恢复。
- Django 启动日志里的 pypi 超时是噪音 — 忽略。
- 本地数据库：`C:\Users\CYCLE\AppData\Local\label-studio\label-studio\label_studio.sqlite3`。

## 部署（摘要 — 完整记录在 `AGENTS.md`）

生产环境运行在 Debian-12 服务器（`/root/label-studio-1.23`）上，基于官方 `heartexlabs/label-studio:1.23.0` 镜像用 `Dockerfile.cn` 构建为**覆盖层**（COPY `label_studio/` + 根目录 `dist/`，部署时无 poetry/yarn 构建）。代码同步为 本地 → Gitee（`git push gitee main`）→ 服务器 `git pull`；GitHub `origin` 仅作备份。更新：`docker build -f Dockerfile.cn -t label-studio:migrated . && docker compose up -d`。端口 8080 在 nginx 之后；Postgres 用 compose `db` 服务（首次启动自动 migrate）。
