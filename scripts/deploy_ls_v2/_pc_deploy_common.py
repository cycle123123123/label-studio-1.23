# -*- coding: utf-8 -*-
"""个人电脑本地全自动一键部署公共逻辑（仅依赖 Python 标准库）。

全流程：检查环境 -> 拉取仓库 -> 创建 .venv 安装后端 -> 编译前端 web/dist ->
初始化独立 SQLite 与管理员 -> 启动 Label Studio -> 自动建项目配 XML v2 + S3 + 导入数据 -> 打开浏览器。
"""
from __future__ import annotations

import argparse
import getpass
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from typing import Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

GITHUB_REPO = "https://github.com/cycle123123123/label-studio-1.23.git"
GITEE_REPO = "https://gitee.com/cycle12/label-studio-1.23.git"


def run_cmd(cmd: List[str], cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> None:
    print(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def venv_python(venv_dir: str) -> str:
    if os.name == "nt":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def read_env_file(path: str) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not os.path.exists(path):
        return data
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def write_env_file(path: str, data: Dict[str, str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for k, v in data.items():
            f.write(f"{k}={v}\n")
    if os.name != "nt":
        os.chmod(path, 0o600)


def check_prereqs(skip_web_build: bool) -> Dict[str, str]:
    if sys.version_info < (3, 10):
        raise SystemExit(f"[错误] 需要 Python >= 3.10，当前版本为 {sys.version.split()[0]}")
    git_exe = shutil.which("git")
    if not git_exe:
        raise SystemExit("[错误] 未检测到 git，请先安装 Git 并加入 PATH。")

    tools: Dict[str, str] = {"git": git_exe}
    if not skip_web_build:
        node_exe = shutil.which("node")
        yarn_exe = shutil.which("yarn")
        if not node_exe:
            raise SystemExit("[错误] 未检测到 node，请先安装 Node.js（建议 v18/v20 LTS），或传入 --skip-web-build。")
        if not yarn_exe:
            npm_exe = shutil.which("npm")
            corepack_exe = shutil.which("corepack")
            if corepack_exe:
                print("  [提示] 未检测到 yarn，尝试通过 corepack enable 启用...")
                subprocess.run([corepack_exe, "enable"], check=False)
                yarn_exe = shutil.which("yarn")
            if not yarn_exe and npm_exe:
                print("  [提示] 未检测到 yarn，尝试通过 npm install -g yarn 安装...")
                subprocess.run([npm_exe, "install", "-g", "yarn"], check=False)
                yarn_exe = shutil.which("yarn")
        if not yarn_exe:
            raise SystemExit("[错误] 未检测到 yarn，请先执行 `npm install -g yarn` 后再重试。")
        tools["node"] = node_exe
        tools["yarn"] = yarn_exe
    return tools


def parse_args(
    default_mode: Optional[str] = None,
    default_dir: Optional[str] = None,
    default_port: Optional[int] = None,
) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="个人电脑本地一键部署修改版 Label Studio（拉代码->编译前端->建项目导入）")
    ap.add_argument("--mode", choices=["gender", "short"], default=default_mode, required=(default_mode is None), help="部署版本：gender（全量699张）或 short（短衣216张）")
    ap.add_argument("--dir", default=default_dir, help="本地部署目录（默认 ./ls-gender 或 ./ls-short）")
    ap.add_argument("--port", type=int, default=default_port, help="本地服务端口（默认 8080 或 8082）")
    ap.add_argument("--repo-url", default="", help="修改版 Label Studio 仓库地址")
    ap.add_argument("--gitee", action="store_true", help="使用 Gitee 镜像拉取主仓库")
    ap.add_argument("--s3-endpoint", default=os.getenv("MINIO_ENDPOINT", "https://s3.nacta.edu.cn"), help="MinIO/S3 Endpoint")
    ap.add_argument("--s3-bucket", default=os.getenv("MINIO_BUCKET", "lable-studio"), help="S3 Bucket（保持 lable-studio）")
    ap.add_argument("--s3-ak", default="", help="S3 Access Key")
    ap.add_argument("--s3-sk", default="", help="S3 Secret Key")
    ap.add_argument("--admin-email", default=os.getenv("ADMIN_EMAIL", "admin@xiqu.local"), help="本地管理员登录邮箱")
    ap.add_argument("--admin-password", default=os.getenv("ADMIN_PASSWORD", ""), help="本地管理员密码（不填则首次自动生成）")
    ap.add_argument("--pypi-mirror", default="https://pypi.tuna.tsinghua.edu.cn/simple", help="PyPI 镜像源")
    ap.add_argument("--npm-registry", default="https://registry.npmmirror.com", help="Yarn/NPM 镜像源")
    ap.add_argument("--skip-web-build", action="store_true", help="跳过前端编译（若已有 web/dist 或仅调试后端时使用）")
    ap.add_argument("--rebuild-web", action="store_true", help="强制重新编译前端")
    ap.add_argument("--reinstall-py", action="store_true", help="强制重新安装 Python 依赖")
    ap.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器")
    args = ap.parse_args()
    if not args.dir:
        args.dir = "./ls-gender" if args.mode == "gender" else "./ls-short"
    if not args.port:
        args.port = 8080 if args.mode == "gender" else 8082
    if not args.repo_url:
        args.repo_url = GITEE_REPO if args.gitee else GITHUB_REPO
    return args


def resolve_credentials(args: argparse.Namespace, env_file: str) -> Dict[str, str]:
    saved = read_env_file(env_file)
    s3_ak = (
        args.s3_ak
        or os.getenv("MINIO_ACCESS_KEY")
        or os.getenv("AWS_ACCESS_KEY_ID")
        or saved.get("AWS_ACCESS_KEY_ID", "")
    ).strip()
    s3_sk = (
        args.s3_sk
        or os.getenv("MINIO_SECRET_KEY")
        or os.getenv("AWS_SECRET_ACCESS_KEY")
        or saved.get("AWS_SECRET_ACCESS_KEY", "")
    ).strip()

    if not s3_ak:
        if sys.stdin.isatty():
            s3_ak = input(f"请输入 MinIO/S3 Access Key ({args.s3_endpoint}): ").strip()
        if not s3_ak:
            raise SystemExit("[错误] 缺少 S3 Access Key，请通过 --s3-ak 或 MINIO_ACCESS_KEY 传入。")
    if not s3_sk:
        if sys.stdin.isatty():
            s3_sk = getpass.getpass("请输入 MinIO/S3 Secret Key: ").strip()
        if not s3_sk:
            raise SystemExit("[错误] 缺少 S3 Secret Key，请通过 --s3-sk 或 MINIO_SECRET_KEY 传入。")

    admin_email = (args.admin_email or saved.get("ADMIN_EMAIL") or "admin@xiqu.local").strip()
    admin_pass = (args.admin_password or saved.get("ADMIN_PASSWORD") or "").strip()
    generated_pass = False
    if not admin_pass:
        admin_pass = secrets.token_hex(8)
        generated_pass = True

    write_env_file(
        env_file,
        {
            "AWS_ACCESS_KEY_ID": s3_ak,
            "AWS_SECRET_ACCESS_KEY": s3_sk,
            "S3_ENDPOINT": args.s3_endpoint,
            "ADMIN_EMAIL": admin_email,
            "ADMIN_PASSWORD": admin_pass,
        },
    )
    return {
        "s3_ak": s3_ak,
        "s3_sk": s3_sk,
        "admin_email": admin_email,
        "admin_pass": admin_pass,
        "generated_pass": "1" if generated_pass else "0",
    }


def wait_health(url: str, proc: subprocess.Popen, log_path: str, timeout_sec: int = 180) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if proc.poll() is not None:
            tail = ""
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    tail = "".join(f.readlines()[-40:])
            raise SystemExit(f"[错误] Label Studio 进程提前退出 (code={proc.returncode})。\n最近日志：\n{tail}")
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=2) as resp:
                if resp.status == 200:
                    return
        except Exception:
            pass
        time.sleep(2)
    raise SystemExit(f"[错误] 等待 Label Studio 就绪超时 ({timeout_sec}s)，请检查日志：{log_path}")


def main(
    default_mode: Optional[str] = None,
    default_dir: Optional[str] = None,
    default_port: Optional[int] = None,
) -> None:
    args = parse_args(default_mode, default_dir, default_port)
    deploy_dir = os.path.abspath(args.dir)
    lsdata_dir = os.path.join(deploy_dir, ".lsdata")
    venv_dir = os.path.join(deploy_dir, ".venv")
    env_file = os.path.join(lsdata_dir, ".deploy_local.env")

    mode_label = "性别版（全量 699 张 / 1710 框）" if args.mode == "gender" else "短衣版（口径 B 216 张 / 411 框）"
    print("=" * 64)
    print(f"  Label Studio v2 本地一键部署 | {mode_label}")
    print(f"  部署目录: {deploy_dir}")
    print(f"  访问端口: http://127.0.0.1:{args.port}")
    print("=" * 64)

    # [1/7] 检查前置工具
    print("[1/7] 检查本机环境（Python / Git / Node / Yarn）...")
    tools = check_prereqs(args.skip_web_build)

    # [2/7] 拉取或更新仓库
    print("[2/7] 拉取或更新修改版 Label Studio 仓库...")
    if not os.path.exists(os.path.join(deploy_dir, ".git")):
        os.makedirs(os.path.dirname(deploy_dir), exist_ok=True)
        run_cmd([tools["git"], "clone", args.repo_url, deploy_dir])
    else:
        r_pull = subprocess.run([tools["git"], "-C", deploy_dir, "pull", "--ff-only"])
        if r_pull.returncode != 0:
            print("  [警告] git pull 失败（网络波动或离线），继续使用本地现有代码。")

    # [3/7] 创建独立 .venv 并安装后端依赖
    print("[3/7] 准备 Python 独立虚拟环境与后端依赖...")
    vpy = venv_python(venv_dir)
    if not os.path.exists(vpy):
        run_cmd([sys.executable, "-m", "venv", venv_dir])

    need_py = args.reinstall_py
    if not need_py:
        chk = subprocess.run([vpy, "-c", "import label_studio, requests"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        need_py = chk.returncode != 0
    if need_py:
        run_cmd([vpy, "-m", "pip", "install", "-U", "pip", "wheel", "setuptools", "poetry-core>=2.0.0,<3.0.0", "-i", args.pypi_mirror])
        run_cmd([vpy, "-m", "pip", "install", "--no-build-isolation", "-e", ".", "sentry-sdk==2.16.0", "-i", args.pypi_mirror], cwd=deploy_dir)
    else:
        print("  检测到 .venv 后端依赖已就绪，跳过安装（可用 --reinstall-py 强制重装）")

    # [4/7] 编译前端 web/dist
    main_js = os.path.join(deploy_dir, "web", "dist", "apps", "labelstudio", "main.js")
    if args.skip_web_build:
        print("[4/7] 已指定 --skip-web-build，跳过前端编译")
    elif args.rebuild_web or not os.path.exists(main_js):
        print("[4/7] 安装前端依赖并编译前端（首次耗时约 3–8 分钟，请耐心等待）...")
        web_dir = os.path.join(deploy_dir, "web")
        yarn_exe = tools["yarn"]
        node_modules = os.path.join(web_dir, "node_modules")
        if args.rebuild_web or not os.path.exists(node_modules):
            run_cmd([yarn_exe, "install", "--frozen-lockfile", "--registry", args.npm_registry], cwd=web_dir)
        # 防 Windows/Yarn 并发解压残包：检查是否存在缺少 package.json 的空壳包
        if os.path.exists(node_modules):
            broken_dirs = []
            for entry in os.listdir(node_modules):
                full = os.path.join(node_modules, entry)
                if not os.path.isdir(full) or entry.startswith("."):
                    continue
                if entry.startswith("@"):
                    for sub in os.listdir(full):
                        sfull = os.path.join(full, sub)
                        if os.path.isdir(sfull) and not os.path.exists(os.path.join(sfull, "package.json")):
                            broken_dirs.append(sfull)
                elif not os.path.exists(os.path.join(full, "package.json")):
                    broken_dirs.append(full)
            if broken_dirs:
                print(f"  [修复] 检测到 {len(broken_dirs)} 个残缺前端包，清理后重装...")
                for b in broken_dirs:
                    shutil.rmtree(b, ignore_errors=True)
                integrity = os.path.join(node_modules, ".yarn-integrity")
                if os.path.exists(integrity):
                    os.remove(integrity)
                run_cmd([yarn_exe, "install", "--frozen-lockfile", "--registry", args.npm_registry], cwd=web_dir)
        build_env = {**os.environ, "NODE_ENV": "production"}
        run_cmd([yarn_exe, "ls:build"], cwd=web_dir, env=build_env)
    else:
        print("[4/7] 检测到前端编译产物 web/dist 已存在，跳过编译（可用 --rebuild-web 强制重编）")

    # [5/7] 收集凭据、迁移独立 SQLite 并初始化管理员账号
    print("[5/7] 初始化独立数据库与管理员账号...")
    creds = resolve_credentials(args, env_file)
    rt_env = {
        **os.environ,
        "BASE_DATA_DIR": lsdata_dir,
        "LABEL_STUDIO_BASE_DATA_DIR": lsdata_dir,
        "LABEL_STUDIO_ENABLE_LEGACY_API_TOKEN": "true",
        "AWS_ACCESS_KEY_ID": creds["s3_ak"],
        "AWS_SECRET_ACCESS_KEY": creds["s3_sk"],
        "S3_ENDPOINT": args.s3_endpoint,
        "PYTHONPATH": os.path.join(deploy_dir, "label_studio"),
        "PYTHONIOENCODING": "utf-8",
    }
    manage_py = os.path.join(deploy_dir, "label_studio", "manage.py")
    run_cmd([vpy, manage_py, "migrate", "--no-input"], cwd=deploy_dir, env=rt_env)

    init_code = (
        "import os\n"
        "from django.contrib.auth import get_user_model\n"
        "from organizations.models import Organization\n"
        "from rest_framework_simplejwt.tokens import RefreshToken\n"
        "User = get_user_model()\n"
        "email = os.environ['INIT_ADMIN_EMAIL']\n"
        "pw = os.environ['INIT_ADMIN_PASS']\n"
        "u = User.objects.filter(email=email).first() or User.objects.filter(is_superuser=True).first() or User.objects.first()\n"
        "if u is None:\n"
        "    u = User.objects.create_superuser(email=email, username=email.split('@')[0], password=pw)\n"
        "org = getattr(u, 'active_organization', None) or Organization.objects.first()\n"
        "if org is None:\n"
        "    org = Organization.create_organization(created_by=u, title='戏曲服饰标注')\n"
        "else:\n"
        "    if org.created_by is None:\n"
        "        org.created_by = u\n"
        "        org.save(update_fields=['created_by'])\n"
        "    if not org.has_user(u):\n"
        "        org.add_user(u)\n"
        "if getattr(u, 'active_organization_id', None) != org.id:\n"
        "    u.active_organization = org\n"
        "    u.save(update_fields=['active_organization'])\n"
        "if hasattr(org, 'jwt'):\n"
        "    org.jwt.legacy_api_tokens_enabled = True\n"
        "    org.jwt.save()\n"
        "print('__LS_ADMIN__=' + u.email)\n"
        "print('__LS_TOKEN__=' + str(RefreshToken.for_user(u)))\n"
    )
    init_res = subprocess.run(
        [vpy, manage_py, "shell", "-c", init_code],
        cwd=deploy_dir,
        env={**rt_env, "INIT_ADMIN_EMAIL": creds["admin_email"], "INIT_ADMIN_PASS": creds["admin_pass"]},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    ls_admin = ""
    ls_token = ""
    for line in init_res.stdout.splitlines():
        if line.startswith("__LS_ADMIN__="):
            ls_admin = line.split("=", 1)[1].strip()
        elif line.startswith("__LS_TOKEN__="):
            ls_token = line.split("=", 1)[1].strip()
    if not ls_token:
        raise SystemExit("[错误] 未能从本地数据库获取管理员 Token。")
    print(f"  管理员账号已就绪: {ls_admin}")

    # [6/7] 后台启动 Label Studio 并一键创建项目导入数据
    print(f"[6/7] 启动本地 Label Studio (127.0.0.1:{args.port}) 并导入数据...")
    log_path = os.path.join(lsdata_dir, "server.log")
    log_fp = open(log_path, "w", encoding="utf-8", errors="replace")
    srv_proc = subprocess.Popen(
        [vpy, "-m", "label_studio.server", "start", "--port", str(args.port), "--no-browser"],
        cwd=deploy_dir,
        env=rt_env,
        stdout=log_fp,
        stderr=subprocess.STDOUT,
    )
    try:
        ls_url = f"http://127.0.0.1:{args.port}"
        wait_health(ls_url, srv_proc, log_path)
        setup_script = "setup_gender_project.py" if args.mode == "gender" else "setup_short_project.py"
        setup_path = os.path.join(deploy_dir, "scripts", "deploy_ls_v2", setup_script)
        run_cmd(
            [vpy, setup_path, "--ls-url", ls_url, "--s3-endpoint", args.s3_endpoint, "--s3-bucket", args.s3_bucket],
            cwd=os.path.dirname(setup_path),
            env={
                **rt_env,
                "LS_API_TOKEN": ls_token,
                "MINIO_ACCESS_KEY": creds["s3_ak"],
                "MINIO_SECRET_KEY": creds["s3_sk"],
            },
        )

        # [7/7] 打开浏览器并保持服务运行
        print("[7/7] 全部就绪！")
        print("=" * 64)
        print(f"  版本: {mode_label}")
        print(f"  打开浏览器访问: {ls_url}")
        print(f"  登录邮箱: {ls_admin}")
        if creds["generated_pass"] == "1":
            print(f"  初始密码: {creds['admin_pass']}  (已保存于 {env_file})")
        else:
            print(f"  登录密码: 使用已有记录（见 {env_file}）")
        print("  [提示] 单人电脑上直接用上述管理员账号登录，即可直接看到全部任务开始标注；")
        print("         若有多人账号协作，请到项目 Settings -> 任务分配 中分派任务。")
        print("  按 Ctrl+C 可停止本地服务；下次再运行本脚本会跳过编译直接秒开。")
        print("=" * 64)

        if not args.no_browser:
            webbrowser.open(ls_url)

        srv_proc.wait()
    except KeyboardInterrupt:
        print("\n收到 Ctrl+C，正在停止 Label Studio...")
    finally:
        if srv_proc.poll() is None:
            srv_proc.terminate()
            try:
                srv_proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                srv_proc.kill()
        log_fp.close()


if __name__ == "__main__":
    main()
