# -*- coding: utf-8 -*-
"""个人电脑本地一键部署【短衣版（口径 B 216 张 / 411 框）】。

支持单独复制本文件到别人电脑运行：
  python pc_deploy_short.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

GITHUB_REPO = "https://github.com/cycle123123123/label-studio-1.23.git"
GITEE_REPO = "https://gitee.com/cycle12/label-studio-1.23.git"
DEFAULT_DIR = "./ls-short"
DEFAULT_PORT = 8082


def _peek_flag(flag: str, default: str = "") -> str:
    for i, a in enumerate(sys.argv[1:], 1):
        if a == flag and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return default


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    local_common = os.path.join(here, "_pc_deploy_common.py")
    if os.path.exists(local_common):
        sys.path.insert(0, here)
        from _pc_deploy_common import main as common_main  # type: ignore

        common_main(default_mode="short", default_dir=DEFAULT_DIR, default_port=DEFAULT_PORT)
        return

    # 裸机单文件自举：先拉取修改版仓库，再转交仓库内 _pc_deploy_common.py
    git_exe = shutil.which("git")
    if not git_exe:
        raise SystemExit("[错误] 未检测到 git，请先安装 Git。")
    deploy_dir = os.path.abspath(_peek_flag("--dir", DEFAULT_DIR))
    use_gitee = "--gitee" in sys.argv[1:]
    repo_url = _peek_flag("--repo-url", GITEE_REPO if use_gitee else GITHUB_REPO)

    if not os.path.exists(os.path.join(deploy_dir, ".git")):
        os.makedirs(os.path.dirname(deploy_dir), exist_ok=True)
        print(f"[自举] 正在拉取修改版 Label Studio 仓库到 {deploy_dir} ...")
        subprocess.run([git_exe, "clone", repo_url, deploy_dir], check=True)
    else:
        subprocess.run([git_exe, "-C", deploy_dir, "pull", "--ff-only"], check=True)

    target = os.path.join(deploy_dir, "scripts", "deploy_ls_v2", "_pc_deploy_common.py")
    cmd = [sys.executable, target, "--mode", "short", "--dir", deploy_dir, "--port", str(DEFAULT_PORT), *sys.argv[1:]]
    raise SystemExit(subprocess.run(cmd).returncode)


if __name__ == "__main__":
    main()
