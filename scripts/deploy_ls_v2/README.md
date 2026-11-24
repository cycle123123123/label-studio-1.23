# 戏曲服饰标注 v2｜一键部署与建项目指南（性别版 & 短衣版）

提供面向**个人电脑本地（推荐）**与**服务器 Docker**的独立部署入口，分成两个完全隔离的版本：
- **性别版**：项目 **「戏曲服饰v2｜全量性别预识别（699张/1710框）」**（默认端口 `8080`）
- **短衣版**：项目 **「短衣范围调整｜口径B（216张/411框）」**（默认端口 `8082`）

---

## 方式一：在别人电脑上本地一键部署（拉代码 → 编译前端 → 建项目导入，推荐）

### 前置软件（目标电脑需提前安装）
- **Git**、**Python 3.10+**、**Node.js（建议 v18/v20 LTS）**、**Yarn**（若未装 Yarn，脚本会尝试自动启用或安装）

### 一键运行（只需把单个 `.py` 发给目标电脑，或拉仓库后直接跑）
支持跨 Windows / macOS / Linux，且**全部幂等**：首次自动拉代码 → 建 `.venv` 装后端 → `yarn ls:build` 编译前端 → 初始化独立 SQLite 与管理员 → 启服务建项目并自动打开浏览器；**二次运行会跳过安装与编译直接秒开**。

```bash
# 1. 部署【性别版】（默认目录 ./ls-gender，端口 8080）
python pc_deploy_gender.py

# 2. 部署【短衣版】（默认目录 ./ls-short，端口 8082，可与性别版同机并行）
python pc_deploy_short.py
```

- **Windows 用户**也可以直接双击：`一键部署_性别版.bat` 或 `一键部署_短衣版.bat`。
- 运行中若未提前设置 `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`，会提示安全输入 S3 凭据并缓存在 `.lsdata/.deploy_local.env`。
- **单人电脑使用提示**：直接用终端打印出的管理员账号（默认 `admin@xiqu.local`）登录，**无需额外分配任务即可直接看到全部图片并开始标注**；若多人协作再用管理员进 **Settings → 任务分配** 分派给其他账号。
- 若对方网络走 Gitee 更快，可附加参数 `--gitee`。

---

## 方式二：Linux 服务器 Docker 全自动一键部署

只需把单个 `deploy_gender.sh` 或 `deploy_short.sh` 拷到装有 Docker 的服务器上运行：

```bash
export MINIO_ACCESS_KEY="<你的_S3_ACCESS_KEY>"
export MINIO_SECRET_KEY="<你的_S3_SECRET_KEY>"

bash deploy_gender.sh   # 性别版（8080 端口，目录 ~/ls-gender）
bash deploy_short.sh    # 短衣版（8082 端口，目录 ~/ls-short）
```

---

## 方式三：在已有 Label Studio 中仅建项目

```bash
pip install requests
export LS_URL="http://127.0.0.1:8080"
export LS_API_TOKEN="<Account & Settings 里的 Token>"
export MINIO_ACCESS_KEY="<你的_S3_ACCESS_KEY>"
export MINIO_SECRET_KEY="<你的_S3_SECRET_KEY>"

python setup_gender_project.py
python setup_short_project.py
```

---

## 并行分工与后期合并说明
- **性别版（全量 699 张）**：核对**性别、颜色、款式**与删旧鞋靴框（`P0` 分歧框已在 `costume_note` 标明 `[P0...]` 提示）；**不要重拉任何短衣框坐标**。
- **短衣版（短衣 216 张）**：仅保留了 411 个短衣框且均带有 `[待调短衣范围:{款式}]` 备注，专心调整**框范围或拆成上衣/下装**，尽量不改性别字段。
- **后期导出与合并**：两边全部 Submit 完成后，均导出为**完整 `JSON`（不要选 `JSON-MIN`）**，以保证保留区域 `id` 与完整路径（合并时需对 S3 `fileuri` 解码并结合 `id` + 坐标 IoU 对齐）。
