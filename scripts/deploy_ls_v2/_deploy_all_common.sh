#!/usr/bin/env bash
set -euo pipefail

# 服务器全自动一键部署公共脚本（支持性别版 MODE=gender 与短衣版 MODE=short）
MODE="${MODE:?必须指定 MODE=gender 或 MODE=short}"
DEPLOY_DIR="${DEPLOY_DIR:?必须指定 DEPLOY_DIR}"
HTTP_PORT="${HTTP_PORT:?必须指定 HTTP_PORT}"
HTTPS_PORT="${HTTPS_PORT:?必须指定 HTTPS_PORT}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:?必须指定 COMPOSE_PROJECT}"

if [[ "${USE_GITEE:-0}" == "1" ]]; then
  MAIN_REPO_URL="${MAIN_REPO_URL:-https://gitee.com/cycle12/label-studio-1.23.git}"
else
  MAIN_REPO_URL="${MAIN_REPO_URL:-https://github.com/cycle123123123/label-studio-1.23.git}"
fi
DIST_REPO_URL="${DIST_REPO_URL:-https://gitee.com/cycle12/label-studio-dist.git}"
BASE_IMAGE="${BASE_IMAGE:-heartexlabs/label-studio:1.23.0}"
IMAGE_TAG="${IMAGE_TAG:-label-studio:migrated}"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-https://s3.nacta.edu.cn}"
MINIO_BUCKET="${MINIO_BUCKET:-lable-studio}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@xiqu.local}"

# 1. 前置命令检查
for cmd in git docker curl; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[错误] 缺少必需命令: $cmd，请先安装后再运行。" >&2
    exit 1
  fi
done
if ! docker compose version >/dev/null 2>&1; then
  echo "[错误] 当前 docker 不支持 'docker compose' 子命令，请升级 Docker Compose v2。" >&2
  exit 1
fi

echo "============================================================"
echo "  Label Studio v2 全自动部署 (${MODE})"
echo "  目录: ${DEPLOY_DIR} | 端口: ${HTTP_PORT}/${HTTPS_PORT} | 项目: ${COMPOSE_PROJECT}"
echo "============================================================"

# 2. 拉取/更新主仓库与前端 dist/
echo "[1/7] 拉取或更新代码仓库与前端构建产物..."
if [[ ! -d "${DEPLOY_DIR}/.git" ]]; then
  mkdir -p "$(dirname "$DEPLOY_DIR")"
  git clone "$MAIN_REPO_URL" "$DEPLOY_DIR"
else
  git -C "$DEPLOY_DIR" pull --ff-only
fi

if [[ ! -d "${DEPLOY_DIR}/dist/.git" ]]; then
  git clone "$DIST_REPO_URL" "${DEPLOY_DIR}/dist"
else
  git -C "${DEPLOY_DIR}/dist" pull --ff-only
fi

cd "$DEPLOY_DIR"
mkdir -p mydata postgres-data
if [[ "$(id -u)" == "0" ]]; then
  chown -R 1001:0 mydata
else
  chown -R 1001:0 mydata 2>/dev/null || echo "  [提示] 若后续容器报 PermissionError，请手动执行: sudo chown -R 1001:0 ${DEPLOY_DIR}/mydata"
fi

# 3. 收集并持久化 S3 凭据与管理员密码到 chmod 600 的 .deploy.env
ENV_FILE="${DEPLOY_DIR}/.deploy.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

S3_AK="${MINIO_ACCESS_KEY:-${AWS_ACCESS_KEY_ID:-}}"
S3_SK="${MINIO_SECRET_KEY:-${AWS_SECRET_ACCESS_KEY:-}}"
if [[ -z "$S3_AK" ]]; then
  if [[ -t 0 ]]; then
    read -r -p "请输入 MinIO/S3 Access Key (${MINIO_ENDPOINT}): " S3_AK
  else
    echo "[错误] 缺少 MINIO_ACCESS_KEY / AWS_ACCESS_KEY_ID（非交互终端请通过环境变量传入）。" >&2
    exit 1
  fi
fi
if [[ -z "$S3_SK" ]]; then
  if [[ -t 0 ]]; then
    read -r -s -p "请输入 MinIO/S3 Secret Key: " S3_SK
    echo
  else
    echo "[错误] 缺少 MINIO_SECRET_KEY / AWS_SECRET_ACCESS_KEY（非交互终端请通过环境变量传入）。" >&2
    exit 1
  fi
fi

ADMIN_PASS="${ADMIN_PASSWORD:-}"
GENERATED_PASS=0
if [[ -z "$ADMIN_PASS" ]]; then
  if command -v openssl >/dev/null 2>&1; then
    ADMIN_PASS="$(openssl rand -hex 8)"
  else
    ADMIN_PASS="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 16)"
  fi
  GENERATED_PASS=1
fi

echo "[2/7] 生成 Dockerfile.cn、.deploy.env 与 docker-compose.deploy.yml..."
cat > "${DEPLOY_DIR}/Dockerfile.cn" <<EOF
FROM ${BASE_IMAGE}
COPY label_studio /label-studio/label_studio/
COPY dist /label-studio/web/dist/
EOF

umask 077
cat > "$ENV_FILE" <<EOF
AWS_ACCESS_KEY_ID=${S3_AK}
AWS_SECRET_ACCESS_KEY=${S3_SK}
S3_ENDPOINT=${MINIO_ENDPOINT}
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASS}
EOF
chmod 600 "$ENV_FILE"

cat > "${DEPLOY_DIR}/docker-compose.deploy.yml" <<EOF
services:
  nginx:
    image: ${IMAGE_TAG}
    restart: unless-stopped
    ports:
      - "${HTTP_PORT}:8085"
      - "${HTTPS_PORT}:8086"
    depends_on:
      - app
    environment:
      - LABEL_STUDIO_HOST=\${LABEL_STUDIO_HOST:-}
    volumes:
      - ./mydata:/label-studio/data:rw
      - ./deploy/nginx/certs:/certs:ro
    command: nginx

  app:
    stdin_open: true
    tty: true
    image: ${IMAGE_TAG}
    restart: unless-stopped
    expose:
      - "8000"
    depends_on:
      - db
    env_file:
      - .deploy.env
    environment:
      - DJANGO_DB=default
      - POSTGRE_NAME=postgres
      - POSTGRE_USER=postgres
      - POSTGRE_PASSWORD=
      - POSTGRE_PORT=5432
      - POSTGRE_HOST=db
      - LABEL_STUDIO_HOST=\${LABEL_STUDIO_HOST:-}
      - LABEL_STUDIO_ENABLE_LEGACY_API_TOKEN=true
      - UWSGI_PROCESSES=8
      - JSON_LOG=1
    volumes:
      - ./mydata:/label-studio/data:rw
      - ./scripts/deploy_ls_v2:/deploy_ls_v2:ro
    command: label-studio-uwsgi

  db:
    image: pgautoupgrade/pgautoupgrade:17-alpine
    hostname: db
    restart: unless-stopped
    environment:
      - POSTGRES_HOST_AUTH_METHOD=trust
      - POSTGRES_USER=postgres
    volumes:
      - ./postgres-data:/var/lib/postgresql/data
      - ./deploy/pgsql/certs:/var/lib/postgresql/certs:ro
EOF

# 4. 构建镜像并启动容器
echo "[3/7] 构建 Docker 镜像 ${IMAGE_TAG} 并启动服务..."
docker build -f Dockerfile.cn -t "${IMAGE_TAG}" .
docker compose -f docker-compose.deploy.yml -p "${COMPOSE_PROJECT}" up -d

# 5. 健康检查
echo "[4/7] 等待 Label Studio 服务就绪 (http://127.0.0.1:${HTTP_PORT}/health)..."
READY=0
for i in $(seq 1 100); do
  if curl -fsS "http://127.0.0.1:${HTTP_PORT}/health" >/dev/null 2>&1; then
    READY=1
    echo "  服务已就绪 (第 ${i} 次检查)"
    break
  fi
  sleep 3
done
if [[ "$READY" != "1" ]]; then
  echo "[错误] 服务在 5 分钟内未就绪，最近日志：" >&2
  docker compose -f docker-compose.deploy.yml -p "${COMPOSE_PROJECT}" logs --tail=50 app || true
  exit 1
fi

# 6. 容器内幂等初始化管理员账号并取出 Token（不打印 Token）
echo "[5/7] 初始化管理员账号并获取 API Token..."
INIT_OUT="$(docker compose -f docker-compose.deploy.yml -p "${COMPOSE_PROJECT}" exec -T app \
  python label_studio/manage.py shell <<'PYEOF'
import os
from django.contrib.auth import get_user_model
from organizations.models import Organization
from rest_framework.authtoken.models import Token

User = get_user_model()
email = os.environ.get('ADMIN_EMAIL', 'admin@xiqu.local').strip()
password = os.environ.get('ADMIN_PASSWORD', '').strip()

u = User.objects.filter(email=email).first()
if u is None:
    u = User.objects.filter(is_superuser=True).first() or User.objects.first()

if u is None:
    org = Organization.objects.first()
    if org is None:
        org = Organization.objects.create(title='戏曲服饰标注')
    u = User.objects.create_superuser(email=email, username=email.split('@')[0], password=password)
    org.add_user(u)
    u.active_organization = org
    u.save(update_fields=['active_organization'])
elif getattr(u, 'active_organization', None) is None:
    org = Organization.objects.first() or Organization.objects.create(title='戏曲服饰标注')
    org.add_user(u)
    u.active_organization = org
    u.save(update_fields=['active_organization'])

tok, _ = Token.objects.get_or_create(user=u)
print(f'__LS_ADMIN__={u.email}')
print(f'__LS_TOKEN__={tok.key}')
PYEOF
)"

LS_ADMIN_ACTUAL="$(printf '%s\n' "$INIT_OUT" | sed -n 's/^__LS_ADMIN__=//p' | tail -n1 | tr -d '\r')"
LS_TOKEN="$(printf '%s\n' "$INIT_OUT" | sed -n 's/^__LS_TOKEN__=//p' | tail -n1 | tr -d '\r')"
if [[ -z "$LS_TOKEN" ]]; then
  echo "[错误] 未能获取管理员 Token，初始化输出：" >&2
  printf '%s\n' "$INIT_OUT" >&2
  exit 1
fi
echo "  管理员账号已就绪: ${LS_ADMIN_ACTUAL}"

# 7. 容器内一键建项目、配 XML v2、绑 S3、导入数据
if [[ "$MODE" == "gender" ]]; then
  SETUP_SCRIPT="setup_gender_project.py"
  MODE_LABEL="性别版（全量 699 张 / 1710 框）"
elif [[ "$MODE" == "short" ]]; then
  SETUP_SCRIPT="setup_short_project.py"
  MODE_LABEL="短衣版（口径 B 216 张 / 411 框）"
else
  echo "[错误] 未知 MODE=$MODE" >&2
  exit 1
fi

echo "[6/7] 运行 ${SETUP_SCRIPT} 创建项目并导入数据..."
docker compose -f docker-compose.deploy.yml -p "${COMPOSE_PROJECT}" exec -T \
  -e "LS_API_TOKEN=${LS_TOKEN}" \
  app python "/deploy_ls_v2/${SETUP_SCRIPT}" \
  --ls-url "http://nginx:8085" \
  --s3-endpoint "${MINIO_ENDPOINT}" \
  --s3-bucket "${MINIO_BUCKET}"

# 8. 输出部署摘要
SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
SERVER_IP="${SERVER_IP:-<服务器IP>}"

echo "[7/7] 部署完成！"
echo "============================================================"
echo "  版本: ${MODE_LABEL}"
echo "  访问地址: http://${SERVER_IP}:${HTTP_PORT}"
echo "  登录邮箱: ${LS_ADMIN_ACTUAL}"
if [[ "$GENERATED_PASS" == "1" ]]; then
  echo "  初始密码: ${ADMIN_PASS}  (已保存至 ${ENV_FILE})"
else
  echo "  登录密码: 已沿用 ${ENV_FILE} 或环境变量中的 ADMIN_PASSWORD"
fi
echo "  日常管理:"
echo "    停止: cd ${DEPLOY_DIR} && docker compose -f docker-compose.deploy.yml -p ${COMPOSE_PROJECT} down"
echo "    重启: cd ${DEPLOY_DIR} && docker compose -f docker-compose.deploy.yml -p ${COMPOSE_PROJECT} up -d"
echo "  [重要] 定制版开启了强制任务分配模式，建完后请用管理员登录，在项目 Settings -> 任务分配 中把任务分派给标注员！"
echo "============================================================"
