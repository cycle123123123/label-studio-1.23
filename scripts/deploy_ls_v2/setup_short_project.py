# -*- coding: utf-8 -*-
"""一键在服务器上创建【短衣范围调整｜口径B（216张/411框）】Label Studio 项目（云端 S3 图源）。"""
from _ls_setup_common import setup_project

if __name__ == "__main__":
    setup_project(
        default_title="短衣范围调整｜口径B（216张/411框）",
        json_rel_path="data/ls_import_216_short_B_s3.json",
        expected_tasks=216,
    )
