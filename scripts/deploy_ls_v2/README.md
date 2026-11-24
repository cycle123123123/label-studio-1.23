# 戏曲服饰标注 v2｜服务器端一键建项目脚本（云端 S3 版）

用于在服务器上运行的定制版 Label Studio（1.23.0）中一键创建两个并行校验项目，统一使用新版 **v2 四维配置**（`label_studio_xiqu.xml`）及云端 MinIO/S3 预签名图源：

1. **`setup_gender_project.py`**：创建 **「戏曲服饰v2｜全量性别预识别（699张/1710框）」**（导入 `data/ls_import_699_v2_predictions.json`，含 699 张图 / 1,710 个服装框 + 原有纹样/道具/盔箱/化装框）
2. **`setup_short_project.py`**：创建 **「短衣范围调整｜口径B（216张/411框）」**（导入 `data/ls_import_216_short_B_s3.json`，仅保留 411 个短衣待调框）

---

## 服务器使用步骤

### 1. 准备依赖
Python 3.9+，安装 `requests`：
```bash
pip install requests
```

### 2. 配置环境变量（勿提交到仓库）
- `LS_API_TOKEN`：登录服务器上的 Label Studio → 右上角头像 → **Account & Settings** → 复制 **Personal Access Token (JWT)** 或 **Legacy Token**（脚本已同时兼容这两种格式）。
- `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`：云端对象存储（`https://s3.nacta.edu.cn`，bucket `lable-studio`）的访问凭据。
  - 若服务器 Docker 容器内已配置 `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` 环境变量兜底，则 `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` 可不传。

```bash
export LS_URL="http://127.0.0.1:8080"        # 服务器 Label Studio 地址
export LS_API_TOKEN="<你的_LS_API_TOKEN>"
export MINIO_ENDPOINT="https://s3.nacta.edu.cn"
export MINIO_BUCKET="lable-studio"           # 保持原始拼写 lable-studio
export MINIO_ACCESS_KEY="<你的_S3_ACCESS_KEY>"   # 若容器已配 AWS_* 兜底可省略
export MINIO_SECRET_KEY="<你的_S3_SECRET_KEY>"   # 若容器已配 AWS_* 兜底可省略
```

### 3. 一键创建两个项目
```bash
# 创建项目一：全量性别预识别（699 张 / 1710 框）
python setup_gender_project.py

# 创建项目二：短衣范围调整｜口径 B（216 张 / 411 框）
python setup_short_project.py
```

也支持直接通过命令行参数传入：
```bash
python setup_gender_project.py --ls-url http://127.0.0.1:8080 --token "..." --s3-ak "..." --s3-sk "..."
```

### 4. 建完后必做：任务分配（定制版强制分配模式）
本仓库定制版开启了**强制任务分配模式**：非管理员（owner）账号只能看到、只能标注明确分配给自己的任务。
两个项目创建并导入完成后，请务必：
- 进入项目 **Settings → 任务分配**（或调用 `/api/projects/{id}/assignments/`）把任务分派给对应的标注员，否则标注员登录后任务列表为空。

---

## 并行分工与后期合并说明
- **项目一（全量 699 张）**：核对**性别、颜色、款式**与删旧鞋靴框（`P0` 分歧框已在 `costume_note` 标明 `[P0...]` 提示）；**不要重拉任何短衣框坐标**。
- **项目二（短衣 216 张）**：仅保留了 411 个短衣框且均带有 `[待调短衣范围:{款式}]` 备注，专心调整**框范围或拆成上衣/下装**，尽量不改性别字段。
- **后期导出与合并**：两边全部 Submit 完成后，均导出为**完整 `JSON`（不要选 `JSON-MIN`）**，以保证保留区域 `id` 与完整路径（合并时需对 S3 `fileuri` 解码并结合 `id` + 坐标 IoU 对齐）。
