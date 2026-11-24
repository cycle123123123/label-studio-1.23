# -*- coding: utf-8 -*-
"""一键在服务器上创建【全量性别预识别（699张/1710框）】Label Studio 项目（云端 S3 图源）。"""
from _ls_setup_common import setup_project

if __name__ == "__main__":
    setup_project(
        default_title="戏曲服饰v2｜全量性别预识别（699张/1710框）",
        json_rel_path="data/ls_import_699_v2_predictions.json",
        expected_tasks=699,
    )
