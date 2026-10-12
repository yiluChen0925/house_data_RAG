# -*- coding: utf-8 -*-
"""依赖清单的生成依据：扫描项目里真实的第三方 import。

结论是 12 个直接依赖（原 requirements.txt 有 243 个，是整个虚拟环境的转储）。

    python 5_tests/tools/scan_imports.py
"""

import ast
import os
import sys

sys.path.insert(0, __file__.rsplit("5_tests", 1)[0] + "5_tests")
import paths  # noqa: E402

import importlib.metadata as md  # noqa: E402

SKIP_DIRS = {'.git', '__pycache__', '.idea', 'venv', '.venv'}

LOCAL_MODULES = {
    'merge_and_clean', 'merge_and_clean_today', 'ETL_cleaners',
    'hybrid_retriever', 'reranker', '_offline_setup', 'app', 'paths',
    'push_report', 'daily_report', 'weekly_report',
    'html_parser', 'html_parser_ftx', 'daily_ingest',
    'load_to_chromadb', 'load_to_chromadb_origin', 'ragas_eval',
    'config', 'models', 'smoke_test_rag',
    'rag',  # 2_scripts/rag 是本地包，不是 PyPI 上的 rag
    'sqlalchemy',  # 3_api/models.py 里是早期 MySQL 遗留代码，主流程不依赖
}

IMPORT_TO_DIST = {
    'dotenv': 'python-dotenv',
    'bs4': 'beautifulsoup4',
    'sentence_transformers': 'sentence-transformers',
    'PIL': 'pillow',
    'yaml': 'PyYAML',
}


def collect():
    found = {}
    for dirpath, dirnames, filenames in os.walk(paths.ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith('.py'):
                continue
            path = os.path.join(dirpath, fn)
            try:
                tree = ast.parse(open(path, encoding='utf-8').read())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        found.setdefault(a.name.split('.')[0], set()).add(fn)
                elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                    found.setdefault(node.module.split('.')[0], set()).add(fn)
    return found


def is_stdlib(name):
    return name in sys.builtin_module_names or name in getattr(sys, 'stdlib_module_names', set())


def main():
    third = {k: v for k, v in collect().items() if k not in LOCAL_MODULES and not is_stdlib(k)}
    print('%-24s %-24s %-12s %s' % ('import 名', '发行名', '版本', '文件数'))
    print('-' * 74)
    for name in sorted(third):
        dist = IMPORT_TO_DIST.get(name, name)
        try:
            ver = md.version(dist)
        except md.PackageNotFoundError:
            ver = '(未安装)'
        print('%-24s %-24s %-12s %d' % (name, dist, ver, len(third[name])))
    print()
    print('直接依赖 %d 个（requirements.txt 里已按此收敛）' % len(third))


if __name__ == "__main__":
    main()
