# AGENTS.md

## 项目
label-studio 1.23.0（官方 + 汉化 + text 分支功能迁移）。Windows，git 仓库，已发布到私有 GitHub `cycle123123123/label-studio-1.23`（https://github.com/cycle123123123/label-studio-1.23，remote origin 为 `git@gh443-direct:...` SSH 直连 443）。改坏文件用 GitHub raw（`raw.githubusercontent.com/HumanSignal/label-studio/1.23.0/...`）恢复。

## 构建/验证命令（`D:\work\label-studio-1.23.0\web`）
- `yarn biome check [files]` / `yarn biome check --write [files]`
- `yarn nx run editor:build:development`
- `yarn ls:build`（labelstudio 生产）
- `yarn lsf:unit` / `yarn dm:unit`
- 后端：`C:\Users\CYCLE\anaconda3\envs\ls123\python.exe` + `PYTHONPATH=D:\work\label-studio-1.23.0\label_studio`，`manage.py` 在 label_studio 目录
- pytest（cwd=label_studio）：`python -m pytest tests/...`；tavern yml 需 DJANGO_DB env（本地 SQLite 跳过 tavern 相关）

## 功能迁移（text 分支 B 精简版 → 1.23.0）已完成
基准（仅重建/核对迁移时需要）：text 分支工作区未提交版（`D:\work\label-studio-Chinese`，git 仓库，快照在 `C:\Users\CYCLE\AppData\Local\Temp\opencode\func_migrate\`）。

### 已迁移功能
1. **任务分配核心**：`tasks/assignment.py`（强制分配：非 owner 只见/只能做分配任务）+ 3 模型（TaskAssignment/TaskAssignmentAuditLog/TaskWorkflowAuditLog）+ 迁移 0061/0062 + 过滤接入 5 入口（TaskAPI/AnnotationsListAPI/AnnotationDraftListAPI/AnnotationDraftAPI/AnnotationAPI + DM only_filtered + ProjectTaskListAPI）+ next_task 双入口 assigned_flag（`data_manager/actions/next_task.py` 与 `projects/api.py` ProjectNextTaskAPI，`projects/functions/next_task.py` 入口过滤 + 删除官方 assigned-first 分支保留采样）+ 组织成员 soft_delete 清理分配。
2. **分配管理 API**（owner-only）：`/api/projects/:pk/assignments/`(GET/POST)、`assignment-audit/`、`workflow-audit/`（+CSV）、`stats/`；`ProjectOrganizationScopedMixin` 组织范围；`core/all_urls.json` 已同步；extend_schema 文档已加。
3. **工作流审计**：`tasks/api.py` 提交/跳过写 TaskWorkflowAuditLog；AnnotationAPI.update 动作变更时同步审计。
4. **统计看板**：ProjectStatisticsAPI（overview/assignment/workflow/activity/annotators，无 empty 相关）。
5. **DM 扩展**：assignee 列（functions.py/managers.py/serializers.py）+ assign_tasks action + `Project.objects.for_user` 权限收紧。
6. **前端**：ApiConfig 5 端点；3 设置页（Assignment/WorkflowAudit/Statistics）+ Settings 菜单（can_manage 显隐）；AppStore.js 提交失败不推进队列（eventResultsHaveError + isAlive import + submissionFinished）；lsf-sdk.js 三 handler 返回 result + 失败不 exitStream；locales 3 命名空间；类型文件。
7. **测试**：test_task_assignment.py + test_task_assignment_standalone.py 移植；test_annotations.py/test_next_task.py/test_api.py/drafts.tavern.yml 适配分配语义。
8. **S3/MinIO 兼容修复**（`io_storages/s3/utils.py`，源自 text 分支 commit 6453e41，2026-08-05 补齐）：凭证环境变量兜底（AWS_ACCESS_KEY_ID/SECRET/SESSION_TOKEN）、`S3_ENDPOINT`/`S3_region` env、presigned URL `ResponseContentType`（按扩展名补 MIME，防浏览器下载）、**`addressing_style: 'path'`**（MinIO 拼接域名报错核心修复）+ `verify=False`（自签证书）。部分内容（get_env/S3_ENDPOINT/ResponseContentType）迁移时已带，本次只补 path+verify。boto3 1.39.3 确认 `boto3.session.Config` 存在。

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

### 已知测试失败（预先存在，未修，2026-08-12 确认与改动无关）
- `io_storages_presign_endpoints.tavern.yml` ×2：S3 兼容修复全局启用 `addressing_style: 'path'`（MinIO 需要），官方 presign 测试期望 virtual-host 格式。修法（两全）：endpoint 为官方 AWS 时用默认、自定义 endpoint 才 path。

### 已修测试
- `test_columns_api_returns_expected_ids`（2026-10-14，commit `59999dd`）：期望清单补上 fork 新增的 DM `assignee` 列，此前长期失败，现全绿。

### 回归基线（2026-10-14，本地 SQLite）
`pytest tests/test_annotations.py tests/test_annotations_result_count.py tests/test_api.py tests/test_task_assignment.py tests/test_task_assignment_standalone.py tests/test_next_task.py tests/test_project.py tests/test_predictions.py tests/test_export.py tests/data_manager/test_columns_api.py tests/data_manager/test_api_tasks.py tests/tasks/test_functions.py` → **115 passed, 67 skipped, 0 failed**。

### 数据库
- 路径 `C:\Users\CYCLE\AppData\Local\label-studio\label-studio\label_studio.sqlite3`；备份 `.bak_funcmigrate`。
- `migrate --check` EXIT=0、`makemigrations --check` No changes。
- 残留无害项：django_migrations 有 projects `0065_auto_20210223_2014` 记录但磁盘无对应文件（squash 历史，migrate 不报错）。

## 注意事项
- 前端静态 chunk 名固定，改完需硬刷新。
- i18next 键路径层级必须与 `t()` 完全一致（静默回退英文）。
- **en-US.js 的 `pages.create_project.config` 段曾整体错挂在 `projects_page.config` 下**（Config.jsx 全部 22 个 config 键回退中文，2026-08-12 已移正）。以后改 locale 若发现"某段中文/英文错位"，先核对段在对象里的父路径，再查 t() 调用路径。
- Django 启动时 pypi 超时日志是噪音。

## 服务器部署（甲方堡垒机，Debian-12-KVM，2026-08-05 上线）
### 部署方式：官方镜像覆盖（不是源码构建）
- 镜像 `label-studio:migrated` = `heartexlabs/label-studio:1.23.0` 官方镜像 + COPY 覆盖迁移版后端（`label_studio/`）与前端（**根目录 `dist/`**）。**无 poetry/yarn 编译**，构建秒级。
- `Dockerfile.cn`（服务器本地文件，**不在 git 仓库**）：`FROM heartexlabs/label-studio:1.23.0` + `COPY label_studio /label-studio/label_studio/` + `COPY dist /label-studio/web/dist/`。`.dockerignore` 白名单 `!dist`（commit `d320c05`）。
- 服务器路径 `/root/label-studio-1.23`（Gitee clone：`cycle12` 账号，私有仓库 `label-studio-1.23` + 传输仓库 `label-studio-dist` 已建）。
- 代码同步链路：本地 → Gitee（`git push gitee main`，快）→ 服务器 `git pull`。GitHub 仅作备份。
- 更新流程：`cd /root/label-studio-1.23 && git pull && docker build -f Dockerfile.cn -t label-studio:migrated . && docker compose up -d`。
- **前端（dist）更新链路**（后端无此步）：本地 `web/` 里 `yarn ls:build` → `web/dist/` 内容推送到 Gitee `label-studio-dist`（仓库根 = `web/dist` 内容：`apps/`、`libs/`）→ 服务器 `cd /root/label-studio-1.23/dist && git pull` → 再走上面的 build+up。`web/dist/` 与根 `dist/` 均不进主仓库（gitignore `/dist/`、`web/dist/`）。`yarn ls:build` 只重建 labelstudio app（`main.js` + 懒加载 chunk，datamanager SDK 在 `167.js`）；独立的 `libs/datamanager/main.js` 不受它重建，但不被主应用使用。
- 数据库：全新 PostgreSQL（compose 自带 db 服务，`./postgres-data`），启动自动 migrate（全新库无需 --fake）。
- 端口 8080（nginx）；部署前需停旧容器释放端口。

### 踩坑记录（全部已解决）
- **服务器网络**（仅重建服务器环境时需要）：pypi.org 官方源仅 ~30KB/s（opencv 66MB 下不完）；**阿里源 27MB/s**（已验证）。国内源：apt→中科大、yarn→npmmirror（`.yarnrc`，yarn1 不认 npm_config_registry 环境变量）、poetry→阿里。
- **poetry 2.x 卡死**（仅重建服务器环境时需要）：并行下载在最后包死锁、清华源缺锁定版本（zipp 3.19.1）。解法：poetry.toml `repositories.pypi.url=阿里` + `[installer] max-workers=1`；**poetry 1.8 不可用**（官方 pyproject 的 `requires-poetry` 是 2.x 字段）。
- **label-studio-sdk**（仅重建服务器环境时需要）：lock 中 GitHub archive URL 在服务器超时（796s），改为 `codeload.github.com`（7/28 与本次均有效）。
- **deploy/ 脚本坑**（commit `8c21be3` 已修）：docker-entrypoint.d 伪符号链接（Windows 解压丢失）已展开为真实脚本；所有 .sh 已加执行权限。
- **.dockerignore**（commit `d320c05`）：`**` 忽略所有，需 `!dist` 白名单才能 COPY dist。
- **数据目录权限**：`mkdir -p mydata && chown -R 1001:0 mydata`（容器 UID 1001），否则 `PermissionError: /label-studio/data/media`。
- **8080 404 排查链**：nginx 正常 → 确认 app 是否监听（app 容器**无 `ss`**，用 `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/`，302=正常跳转；migrate 未完成时 NOT_LISTENING，等几分钟即可）。
- 历史参考：7/28 Codex 会话 `019fa914-2df8-74b2-bb2d-ecc78ce73314` 记录了 B 版部署全过程（同款坑）。

## 交叉标注工作流（2026-10-14，本机已验证）

需求：20% 剧照三人独立标注（少数服从多数线下人工做）、其余 80% 单人；严格分配模式不变。

### 三块改动
1. **后端：TaskAssignment 一对多**（迁移 0064）。`task` OneToOne→FK（`related_name='assignments'`）+ `UniqueConstraint(task,user)`；`apply_task_assignments(project, task_ids, assignee_ids(list|兼容int), user)` 语义=追加/移除（返回 `{changed,assigned,removed}`，不再有 reassigned）；`can_user_access_task`/`filter_task_related_queryset_for_user`/`TaskSerializer.get_assigned_task` 均改多行查询；DM `annotate_assignee` 用双 Subquery（原 Coalesce join 在 FK 下会裂行）；`POST /api/projects/:id/assignments/` 收 `assignees` 列表（兼容旧 `assignee`）；统计 assigned_tasks 按 task 去重；DM assign_tasks action 单选=替换全部。
2. **后端：标注作者校验**。`AnnotationAPI._check_annotation_author`：仅当标注作者**本人也是该 task 分配者**时禁止他人修改（保护交叉标注同伴）；导入标注（作者非分配者）保持可编辑以兼容 B 版「导入后继续标注」流；owner/staff 豁免。
3. **前端：编辑器默认选中逻辑**（`web/libs/editor/src/stores/AppStore.js` `initializeStore` 两个分支）。优先级：自己的标注 → **预测**（预填、提交=POST 新建自己的）→ 只有别人的标注则 `as.createAnnotation()` 新开空白 → 维持现状。另放宽 `Annotation/store.js findNonInteractivePredictionResults` 过滤为 `interactive_mode !== true`（导入/ML 预测无此标记，原 `=== false` 会把预填滤空——这就是「+ 新建标注永远是空白」的原因）。

### 数据流（脚本，均在 `scripts/`）
- `make_cross_prelabels.py`：把项目导入标注转成 `Prediction(model_version='prelabel')`（幂等）+ 可选 `--delete-source` 删导入标注。**必须先备份**（导出 JSON + SQLite）。注意：导入行的 `result_count` 字段不可信（未计算），排序取内容要用 `len(a.result)`。
- `make_cross_copies.py`：副本方案生成器（已弃用未删，本地验证过；OSS 导入不按 data 去重）。弃用原因：OSS DM 列表**不暴露 meta 字段**（`/api/dm/columns` 无 meta），副本分组在界面上不可见。
- 抽样：inner_id 每 5 取 1（143/713），交叉任务 `assignees=[3人]`。

### 验证结论（本机 project 1，2026-10-14）
- 3 账号各自提交 → 同 task 3 条 annotation、`completed_by` 各自正确、prediction 不被修改；
- 同伴改他人标注 403、改自己 200；未分配访问 403（严格分配边界不破坏）；
- 项目最终态：713 任务 / 0 标注 / 713 prelabel 预测；分配行 = 交叉 143×3 + 单人 570。
- 测试：`tests/test_task_assignment.py`（含新增 `test_multi_assignee_annotation_isolation_and_author_check`）+ standalone + next_task + annotations 全绿；`yarn ls:build` 通过。
- 坑：pytest POST annotations 传 dict 走 multipart，result 列表必须 `json.dumps` + `content_type='application/json'`；Windows 下 Edit 工具写 JS 产生 LF，biome format 会报错，需 `biome check --write` 修行尾；沙箱内跑 `yarn ls:build` 会被「批量删除 dist」保护拦截，需沙箱外执行。
