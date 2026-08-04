# AGENTS.md

## 项目
label-studio 1.23.0（官方 + 汉化 + text 分支功能迁移）。Windows，非 git 仓库；改坏文件用 GitHub raw（`raw.githubusercontent.com/HumanSignal/label-studio/1.23.0/...`）恢复。

## 构建/验证命令（`D:\work\label-studio-1.23.0\web`）
- `yarn biome check [files]` / `yarn biome check --write [files]`
- `yarn nx run editor:build:development`
- `yarn ls:build`（labelstudio 生产）
- `yarn lsf:unit` / `yarn dm:unit`
- 后端：`C:\Users\CYCLE\anaconda3\envs\ls123\python.exe` + `PYTHONPATH=D:\work\label-studio-1.23.0\label_studio`，`manage.py` 在 label_studio 目录
- pytest（cwd=label_studio）：`python -m pytest tests/...`；tavern yml 需 DJANGO_DB env（本地 SQLite 跳过 tavern 相关）

## 功能迁移（text 分支 B 精简版 → 1.23.0）已完成
基准：text 分支工作区未提交版（`D:\work\label-studio-Chinese`，git 仓库，快照在 `C:\Users\CYCLE\AppData\Local\Temp\opencode\func_migrate\`）。

### 已迁移功能
1. **任务分配核心**：`tasks/assignment.py`（强制分配：非 owner 只见/只能做分配任务）+ 3 模型（TaskAssignment/TaskAssignmentAuditLog/TaskWorkflowAuditLog）+ 迁移 0061/0062 + 过滤接入 5 入口（TaskAPI/AnnotationsListAPI/AnnotationDraftListAPI/AnnotationDraftAPI/AnnotationAPI + DM only_filtered + ProjectTaskListAPI）+ next_task 双入口 assigned_flag（`data_manager/actions/next_task.py` 与 `projects/api.py` ProjectNextTaskAPI，`projects/functions/next_task.py` 入口过滤 + 删除官方 assigned-first 分支保留采样）+ 组织成员 soft_delete 清理分配。
2. **分配管理 API**（owner-only）：`/api/projects/:pk/assignments/`(GET/POST)、`assignment-audit/`、`workflow-audit/`（+CSV）、`stats/`；`ProjectOrganizationScopedMixin` 组织范围；`core/all_urls.json` 已同步；extend_schema 文档已加。
3. **工作流审计**：`tasks/api.py` 提交/跳过写 TaskWorkflowAuditLog；AnnotationAPI.update 动作变更时同步审计。
4. **统计看板**：ProjectStatisticsAPI（overview/assignment/workflow/activity/annotators，无 empty 相关）。
5. **DM 扩展**：assignee 列（functions.py/managers.py/serializers.py）+ assign_tasks action + `Project.objects.for_user` 权限收紧。
6. **前端**：ApiConfig 5 端点；3 设置页（Assignment/WorkflowAudit/Statistics）+ Settings 菜单（can_manage 显隐）；AppStore.js 提交失败不推进队列（eventResultsHaveError + isAlive import + submissionFinished）；lsf-sdk.js 三 handler 返回 result + 失败不 exitStream；locales 3 命名空间；类型文件。
7. **测试**：test_task_assignment.py + test_task_assignment_standalone.py 移植；test_annotations.py/test_next_task.py/test_api.py/drafts.tavern.yml 适配分配语义。

### 未迁移（用户决策）
409 提交冲突检测（validate_submission_conflict/TaskSubmissionConflictError）、skip_reason/is_empty_submission/require_comment_on_skip 字段及逻辑、empty 统计。

### 关键修复
- `AnnotationSerializer.create` 用 `transaction.atomic()` 包裹（SQLite 下 IntegrityError 后事务恢复，官方 bug）。
- `tasks/api.py` mixin/装饰器顺序：类定义不能插在 @method_decorator 链中间。
- 迁移记录名必须与文件名一致（0062 改名教训）。
- `can_user_access_task` 组织边界检查跳过 org=None 项目（FSM cold-start 兼容）。
- 子代理审查修复（2026-08-04）：`AnnotationsListAPI.perform_create` 补回 `transaction.atomic()`（B 版有，迁移漏）；`AnnotationConvertAPI` 补 `AssignmentScopedTaskObjectMixin`+get_queryset（B 版有，迁移漏）；`AnnotationDraftSerializer.user` 改回显式 `read_only=True`（read_only_fields 对显式声明字段无效）；`ProjectAssignmentAuditLogAPI` task_id 非法值返回 400 而非 500；workflow-audit CSV 加 UTF-8 BOM + task_inner_id 列（测试断言已同步更新）。

### 已知语义差异（官方测试 skip）
手动分配模式与多 annotator 共享任务池不兼容：test_next_task 的 breadth_first_simple/breadth_first_overlap_3/fetch_final_taken_task/overlap_first 已加 skip 标记（原因注释）。

### 数据库
- 路径 `C:\Users\CYCLE\AppData\Local\label-studio\label-studio\label_studio.sqlite3`；备份 `.bak_funcmigrate`。
- `migrate --check` EXIT=0、`makemigrations --check` No changes。
- 残留无害项：django_migrations 有 projects `0065_auto_20210223_2014` 记录但磁盘无对应文件（squash 历史，migrate 不报错）。

## 注意事项
- 前端静态 chunk 名固定，改完需硬刷新。
- i18next 键路径层级必须与 `t()` 完全一致（静默回退英文）。
- Django 启动时 pypi 超时日志是噪音。
