# label-studio-1.23 · 戏曲服饰标注定制版

基于 [Label Studio](https://github.com/HumanSignal/label-studio) **1.23.0** 的私有定制分支，为「戏曲剧照服饰标注」项目改造：多人交叉标注 + 严格任务分配 + 工作流审计 + 中文界面。

> 上游项目：https://github.com/HumanSignal/label-studio ｜ 版本基线：`1.23.0` ｜ 许可：Apache-2.0（见 `LICENSE` / `NOTICE`）

---

## 和上游的差异

### 1. 任务分配（强制分配模式）
- 新增 `tasks/assignment.py`：非 owner 用户只能看到、只能标注分配给自己的任务
- `TaskAssignment` 支持 **一个任务多个标注员**（交叉标注：同一张图多人独立标，线下少数服从多数）
- `next_task` 只返回分配给当前用户的任务，删除上游「assigned-first 优先」分支
- 过滤接入 5 个入口：TaskAPI、AnnotationsListAPI、AnnotationDraftListAPI、AnnotationDraftAPI、AnnotationAPI，以及 Data Manager 的 `only_filtered`、ProjectTaskListAPI

### 2. 分配管理与审计
| 端点 | 作用 |
|---|---|
| `/api/projects/:pk/assignments/` | 查询 / 批量分配（收 `assignees` 列表） |
| `/api/projects/:pk/assignment-audit/` | 分配变更审计 |
| `/api/projects/:pk/workflow-audit/` | 提交 / 跳过 / 修改审计（支持 CSV 导出） |
| `/api/projects/:pk/stats/` | 统计看板数据（overview / assignment / workflow / activity / annotators） |

### 3. Data Manager 扩展
- 新增 `assignee` 列
- 新增 `assign_tasks` 批量操作

### 4. 前端
- 设置页新增 **任务分配 / 工作流审计 / 统计看板** 三页（`can_manage` 控制显隐）
- 全站中文汉化
- 提交失败不推进队列（避免漏标被跳过）

### 5. 存储兼容
- S3 / MinIO：`addressing_style: 'path'`、自签证书 `verify=False`、presigned URL 补 `ResponseContentType`、凭证支持环境变量兜底

---

## 部署

采用**官方镜像覆盖**方式，不重新编译前端/后端：

```bash
# 1. 拉代码
git clone <this-repo> && cd label-studio-1.23

# 2. 服务器本地维护 Dockerfile.cn（不在仓库内）
#    FROM heartexlabs/label-studio:1.23.0
#    COPY label_studio /label-studio/label_studio/
#    COPY dist /label-studio/web/dist/

# 3. 构建并启动
docker build -f Dockerfile.cn -t label-studio:migrated .
docker compose up -d
```

- 前端产物 `dist/` 不进主仓库，单独通过 `label-studio-dist` 仓库推送
- 数据目录需授权：`mkdir -p mydata && chown -R 1001:0 mydata`
- 默认端口 `8080`（nginx）
- 数据库为 compose 自带 PostgreSQL，启动自动 migrate

---

## 本地开发

```bash
# 后端
python manage.py migrate
python manage.py runserver

# 前端
cd web
yarn install
yarn ls:build          # 生产构建
yarn nx run editor:build:development
```

**回归基线**（本地 SQLite）：`115 passed, 67 skipped, 0 failed`

```bash
python -m pytest tests/test_annotations.py tests/test_api.py tests/test_task_assignment.py \
  tests/test_next_task.py tests/test_project.py tests/data_manager/test_columns_api.py
```

---

## 与上游的已知差异

- 未迁移 409 提交冲突检测、`skip_reason` / `is_empty_submission` 字段
- 手动分配模式与「多 annotator 共享任务池」不兼容，相关 `test_next_task` 用例已 skip
- `io_storages_presign_endpoints.tavern.yml` 2 例失败：MinIO 需要 path 风格 presign，与官方 virtual-host 断言冲突

---

## 许可

Apache License 2.0。本项目为 Label Studio 的衍生作品，原始版权归 HumanSignal, Inc. 所有，详见 `NOTICE`。
