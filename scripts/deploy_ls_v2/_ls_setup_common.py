# -*- coding: utf-8 -*-
"""Label Studio 云端 S3 项目一键创建与导入公共逻辑（兼容 1.23.0 PAT/JWT 与 Legacy Token）。"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, Optional
from urllib.parse import urlsplit

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_XML = os.path.join(BASE_DIR, "label_studio_xiqu.xml")


def parse_args(default_title: str) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=f"一键创建 Label Studio 项目：{default_title}")
    ap.add_argument("--ls-url", default=os.getenv("LS_URL", "http://127.0.0.1:8080"), help="Label Studio 服务地址")
    ap.add_argument("--token", default=os.getenv("LS_API_TOKEN", ""), help="Label Studio API Token（兼容 PAT/JWT 与 Legacy Token）")
    ap.add_argument("--title", default=default_title, help="项目名称")
    ap.add_argument("--s3-endpoint", default=os.getenv("MINIO_ENDPOINT", "https://s3.nacta.edu.cn"), help="MinIO/S3 Endpoint")
    ap.add_argument("--s3-bucket", default=os.getenv("MINIO_BUCKET", "lable-studio"), help="S3 Bucket 名称（注意原始拼写 lable-studio）")
    ap.add_argument(
        "--s3-ak",
        default=os.getenv("MINIO_ACCESS_KEY") or os.getenv("AWS_ACCESS_KEY_ID") or "",
        help="S3 Access Key（若容器已配 AWS_ACCESS_KEY_ID 兜底可留空）",
    )
    ap.add_argument(
        "--s3-sk",
        default=os.getenv("MINIO_SECRET_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY") or "",
        help="S3 Secret Key（若容器已配 AWS_SECRET_ACCESS_KEY 兜底可留空）",
    )
    ap.add_argument("--presign-ttl", type=int, default=15, help="S3 预签名有效期（分钟）")
    ap.add_argument("--xml", default=DEFAULT_XML, help="Label Studio XML 配置文件路径")
    return ap.parse_args()


def require_nonempty(val: str, name: str) -> str:
    v = (val or "").strip()
    if not v:
        raise SystemExit(f"[错误] 缺少必填参数或环境变量：{name}")
    return v


def build_auth_headers(ls_url: str, raw_token: str) -> Dict[str, str]:
    tok = raw_token.strip()
    for prefix in ("Bearer ", "bearer ", "Token ", "token "):
        if tok.startswith(prefix):
            tok = tok[len(prefix):].strip()
            break

    if tok.count(".") == 2:
        # 1.23.0 默认 Personal Access Token (JWT Refresh Token) -> 换取 Access Token
        try:
            r_ref = requests.post(
                f"{ls_url}/api/token/refresh/",
                json={"refresh": tok},
                timeout=15,
            )
            if r_ref.status_code == 200 and r_ref.json().get("access"):
                headers = {"Authorization": f"Bearer {r_ref.json()['access']}"}
            else:
                headers = {"Authorization": f"Bearer {tok}"}
        except Exception:
            headers = {"Authorization": f"Bearer {tok}"}
    else:
        headers = {"Authorization": f"Token {tok}"}

    r_me = requests.get(f"{ls_url}/api/current-user/whoami", headers=headers, timeout=15)
    if r_me.status_code != 200:
        raise SystemExit(
            f"[错误] Token 鉴权失败 (HTTP {r_me.status_code})。\n"
            "  请确认从 Label Studio 右上角 Account & Settings 复制了有效的 Personal Access Token (PAT) 或 Legacy Token。"
        )
    me = r_me.json()
    print(f"[鉴权] 当前登录用户: {me.get('email') or me.get('username') or me.get('id')}")
    return headers


def find_project_by_title(ls_url: str, headers: Dict[str, str], title: str) -> Optional[dict]:
    url: Optional[str] = f"{ls_url}/api/projects/?page_size=100"
    while url:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        for p in data.get("results", []):
            if p.get("title") == title:
                return p
        nxt = data.get("next")
        if nxt and nxt.startswith("/"):
            nxt = f"{ls_url}{nxt}"
        url = nxt
    return None


def setup_project(
    default_title: str,
    json_rel_path: str,
    expected_tasks: int,
) -> None:
    args = parse_args(default_title)
    ls_url = args.ls_url.rstrip("/")
    raw_token = require_nonempty(args.token, "--token / LS_API_TOKEN")
    s3_ak = (args.s3_ak or "").strip()
    s3_sk = (args.s3_sk or "").strip()

    json_path = os.path.join(BASE_DIR, json_rel_path)
    if not os.path.exists(json_path):
        raise SystemExit(f"[错误] 找不到导入文件：{json_path}")
    if not os.path.exists(args.xml):
        raise SystemExit(f"[错误] 找不到 XML 配置：{args.xml}")

    with open(args.xml, "r", encoding="utf-8") as f:
        xml_cfg = f.read()

    # 1. 检查服务连通性与 Token 鉴权
    r_health = requests.get(f"{ls_url}/health", timeout=10)
    r_health.raise_for_status()
    print(f"[1/5] Label Studio 服务连通正常: {ls_url}")
    headers = build_auth_headers(ls_url, raw_token)

    # 2. 创建或更新项目及 XML v2（全量翻页检索防重）
    proj = find_project_by_title(ls_url, headers, args.title)
    if proj is None:
        r_create = requests.post(
            f"{ls_url}/api/projects/",
            headers=headers,
            json={"title": args.title, "label_config": xml_cfg},
            timeout=30,
        )
        r_create.raise_for_status()
        proj = r_create.json()
        print(f"[2/5] 已创建新项目 ID={proj['id']} | {proj['title']}")
    else:
        r_patch = requests.patch(
            f"{ls_url}/api/projects/{proj['id']}/",
            headers=headers,
            json={"label_config": xml_cfg},
            timeout=30,
        )
        r_patch.raise_for_status()
        proj = r_patch.json()
        print(f"[2/5] 同名项目已存在 ID={proj['id']}，已更新 XML v2 配置")

    pid = proj["id"]

    # 3. 绑定云端 S3 Source Storage（支持容器环境变量 AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY 兜底）
    r_s3s = requests.get(f"{ls_url}/api/storages/s3?project={pid}", headers=headers, timeout=15)
    r_s3s.raise_for_status()
    if not r_s3s.json():
        s3_payload: Dict[str, object] = {
            "project": pid,
            "title": "xiqu-s3",
            "bucket": args.s3_bucket,
            "prefix": "",
            "s3_endpoint": args.s3_endpoint,
            "presign": True,
            "presign_ttl": args.presign_ttl,
            "use_blob_urls": False,
        }
        if s3_ak and s3_sk:
            s3_payload["aws_access_key_id"] = s3_ak
            s3_payload["aws_secret_access_key"] = s3_sk
        else:
            print("  [提示] 未显式传入 S3 密钥，将由服务器容器环境变量 AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY 兜底")

        r_s3 = requests.post(
            f"{ls_url}/api/storages/s3",
            headers=headers,
            json=s3_payload,
            timeout=20,
        )
        r_s3.raise_for_status()
        print(f"[3/5] 已绑定云端 S3 存储: {args.s3_endpoint} / {args.s3_bucket} (presign=True)")
    else:
        print("[3/5] S3 存储已存在，跳过重复绑定")

    # 4. 导入预测 JSON（若任务数为 0）
    r_proj = requests.get(f"{ls_url}/api/projects/{pid}/", headers=headers, timeout=15)
    r_proj.raise_for_status()
    cur_tasks = r_proj.json().get("task_number") or 0
    if cur_tasks == 0:
        with open(json_path, "rb") as f:
            r_imp = requests.post(
                f"{ls_url}/api/projects/{pid}/import",
                headers=headers,
                files={"file": (os.path.basename(json_path), f, "application/json")},
                timeout=180,
            )
        r_imp.raise_for_status()
        res_imp = r_imp.json()
        print(
            f"[4/5] 导入成功: task_count={res_imp.get('task_count')}, "
            f"prediction_count={res_imp.get('prediction_count')}"
        )
    else:
        print(f"[4/5] 项目当前已有 {cur_tasks} 条任务，跳过重复导入")

    # 5. 首图 S3 预签名连通自检（不打印带签名 query 的完整 URL）
    r_tasks = requests.get(f"{ls_url}/api/tasks/?project={pid}&page_size=1", headers=headers, timeout=15)
    r_tasks.raise_for_status()
    tlist = r_tasks.json().get("tasks") or []
    if tlist:
        img_val = str(tlist[0].get("data", {}).get("image", ""))
        if img_val.startswith("/"):
            r_res = requests.get(f"{ls_url}{img_val}", headers=headers, allow_redirects=False, timeout=15)
            loc = r_res.headers.get("Location", "")
            loc_parts = urlsplit(loc)
            safe_loc = f"{loc_parts.scheme}://{loc_parts.netloc}{loc_parts.path}"[:60] if loc else ""
            print(f"[5/5] 首图预签名自检: HTTP {r_res.status_code} | 目标={safe_loc or '(无重定向)'}")
        else:
            print(f"[5/5] 首图地址检查: {img_val[:60]}")
    else:
        print("[5/5] 未获取到任务用于自检")

    r_fin = requests.get(f"{ls_url}/api/projects/{pid}/", headers=headers, timeout=15)
    r_fin.raise_for_status()
    pj = r_fin.json()
    print(
        f"[完成] 项目地址: {ls_url}/projects/{pid}/data | "
        f"task_number={pj.get('task_number')} (预期 {expected_tasks}) | "
        f"total_predictions={pj.get('total_predictions_number')}"
    )
