# -*- coding: utf-8 -*-
"""测试脚本共用的路径推导。所有脚本都从自己位置推，不写死绝对路径。"""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(TESTS_DIR, ".."))

SCRIPTS = os.path.join(ROOT, "2_scripts")
RAG = os.path.join(SCRIPTS, "rag")
ETL = os.path.join(SCRIPTS, "etl")
CRAWLER = os.path.join(SCRIPTS, "crawler")
REPORT = os.path.join(SCRIPTS, "report")
EVALUATE = os.path.join(SCRIPTS, "evaluate")

CHROMA = os.path.join(ROOT, "1_data", "chroma_db")
CLEANED_CSV = os.path.join(ROOT, "1_data", "cleaned_data", "house_cleaned.csv")
RAW_DATA = os.path.join(ROOT, "1_data", "raw_data")


def add_paths():
    """把项目里会被 import 的目录加进 sys.path。"""
    for p in (SCRIPTS, RAG, ETL, CRAWLER, REPORT, EVALUATE):
        if p not in sys.path:
            sys.path.insert(0, p)


def offline():
    """强制离线，必须在 transformers/sentence_transformers 之前调用。"""
    sys.path.insert(0, RAG)
    import _offline_setup  # noqa: F401
