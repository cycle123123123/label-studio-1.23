#!/usr/bin/env bash
set -euo pipefail

# 一键部署【短衣版（口径 B 216 张 / 411 框）】Label Studio 服务并建项目导入
export MODE="short"
export DEPLOY_DIR="${DEPLOY_DIR:-$HOME/ls-short}"
export HTTP_PORT="${HTTP_PORT:-8082}"
export HTTPS_PORT="${HTTPS_PORT:-8083}"
export COMPOSE_PROJECT="${COMPOSE_PROJECT:-ls-short}"

if [[ "${USE_GITEE:-0}" == "1" ]]; then
  MAIN_REPO_URL="${MAIN_REPO_URL:-https://gitee.com/cycle12/label-studio-1.23.git}"
else
  MAIN_REPO_URL="${MAIN_REPO_URL:-https://github.com/cycle123123123/label-studio-1.23.git}"
fi
export MAIN_REPO_URL

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/_deploy_all_common.sh" ]]; then
  exec bash "${SCRIPT_DIR}/_deploy_all_common.sh"
fi

if [[ ! -d "${DEPLOY_DIR}/.git" ]]; then
  mkdir -p "$(dirname "$DEPLOY_DIR")"
  git clone "$MAIN_REPO_URL" "$DEPLOY_DIR"
else
  git -C "$DEPLOY_DIR" pull --ff-only
fi

exec bash "${DEPLOY_DIR}/scripts/deploy_ls_v2/_deploy_all_common.sh"
