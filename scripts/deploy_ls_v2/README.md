# 戏曲服饰标注 v2｜服务器端一键部署与建项目指南（性别版 & 短衣版）

提供两套独立的服务器端部署入口，支持**从零拉代码、拉前端 `dist`、构建 Docker 镜像、启动 PostgreSQL + Label Studio、自动初始化管理员、配置 XML v2、绑定云端 S3（`https://s3.nacta.edu.cn` / `lable-studio`）并导入数据**；两套版本端口与数据卷完全隔离，可在同一台服务器同时运行：

- **性别版（`deploy_gender.sh`）**：默认目录 `~/ls-gender`、端口 `8080`、项目 **「戏曲服饰v2｜全量性别预识别（699张/1710框）」**
- **短衣版（`deploy_short.sh`）**：默认目录 `~/ls-short`、端口 `8082`、项目 **「短衣范围调整｜口径B（216张/411框）」**

---

## 方式一：从零全自动一键部署（推荐）

只需把单个 `deploy_gender.sh` 或 `deploy_short.sh` 拷到服务器（或在已 clone 仓库内直接运行），宿主机无需安装 Python 依赖，也无需手工去网页复制 Token：

```bash
export MINIO_ACCESS_KEY="<你的_S3_ACCESS_KEY>"
export MINIO_SECRET_KEY="<你的_S3_SECRET_KEY>"
# 可选：自定义管理员账号/密码（不填则默认 admin@xiqu.local 并自动生成随机密码）
# export ADMIN_EMAIL="admin@xiqu.local"
# export ADMIN_PASSWORD="your-password"
# 若服务器走 Gitee 镜像拉主仓库，加 USE_GITEE=1
# export USE_GITEE=1

# 1. 部署【性别版】（默认 8080 端口，目录 ~/ls-gender）
bash deploy_gender.sh

# 2. 部署【短衣版】（默认 8082 端口，目录 ~/ls-short）
bash deploy_short.sh
```

> 若未提前 export `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`，交互式运行脚本时会提示安全输入，并写入部署目录内 `chmod 600` 的 `.deploy.env`。

---

## 方式二：在已有 Label Studio 中仅建项目

如果服务器上已经跑着 Label Studio，只需在现有实例里创建这两个项目：

```bash
pip install requests
export LS_URL="http://127.0.0.1:8080"        # 服务器 Label Studio 地址
export LS_API_TOKEN="<Account & Settings 里的 Token>"
export MINIO_ENDPOINT="https://s3.nacta.edu.cn"
export MINIO_BUCKET="lable-studio"           # 保持原始拼写 lable-studio
export MINIO_ACCESS_KEY="<你的_S3_ACCESS_KEY>"   # 若容器已配 AWS_* 兜底可省略
export MINIO_SECRET_KEY="<你的_S3_SECRET_KEY>"   # 若容器已配 AWS_* 兜底可省略

python setup_gender_project.py
python setup_short_project.py
```

---

## 建完后必做：任务分配（定制版强制分配模式）
本仓库定制版开启了**强制任务分配模式**：非管理员（owner）账号只能看到、只能标注明确分配给自己的任务。
两个项目创建并导入完成后，请务必：
- 用管理员登录，进入项目 **Settings → 任务分配**（或调用 `/api/projects/{id}/assignments/`）把任务分派给对应的标注员，否则标注员登录后任务列表为空。

---

## 并行分工与后期合并说明
- **性别版（全量 699 张）**：核对**性别、颜色、款式**与删旧鞋靴框（`P0` 分歧框已在 `costume_note` 标明 `[P0...]` 提示）；**不要重拉任何短衣框坐标**。
- **短衣版（短衣 216 张）**：仅保留了 411 个短衣框且均带有 `[待调短衣范围:{款式}]` 备注，专心调整**框范围或拆成上衣/下装**，尽量不改性别字段。
- **后期导出与合并**：两边全部 Submit 完成后，均导出为**完整 `JSON`（不要选 `JSON-MIN`）**，以保证保留区域 `id` 与完整路径（合并时需对 S3 `fileuri` 解码并结合 `id` + 坐标 IoU 对齐）。
