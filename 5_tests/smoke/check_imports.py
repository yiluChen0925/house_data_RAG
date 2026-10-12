# -*- coding: utf-8 -*-
"""逐个导入项目模块，确认依赖清单没有漏项。

注意：会真的 import load_to_chromadb_origin——它曾经没有 __main__ 守卫，
import 就会重写向量库。现在已加守卫，这个脚本顺带验证这一点。

    python 5_tests/smoke/check_imports.py
"""

import ast
import importlib
import os
import sys

sys.path.insert(0, __file__.rsplit("5_tests", 1)[0] + "5_tests")
import paths  # noqa: E402

paths.offline()
paths.add_paths()

MODULES = [
    'hybrid_retriever', 'reranker', '_offline_setup',
    'merge_and_clean', 'merge_and_clean_today', 'ETL_cleaners',
    'html_parser', 'html_parser_ftx', 'daily_ingest',
    'load_to_chromadb', 'load_to_chromadb_origin',
    'push_report', 'daily_report', 'weekly_report',
    'smoke_test_rag', 'ragas_eval',
]


def main():
    import chromadb
    col = chromadb.PersistentClient(path=paths.CHROMA).get_collection('house_data')
    before = col.count()

    fail = []
    for name in MODULES:
        try:
            importlib.import_module(name)
            print('  OK   ' + name)
        except Exception as e:
            fail.append(name)
            print('  FAIL ' + name + ' -> ' + type(e).__name__ + ': ' + str(e)[:140])

    app = os.path.join(paths.SCRIPTS, 'app.py')
    try:
        ast.parse(open(app, encoding='utf-8').read())
        print('  OK   app.py（只做语法校验，导入会执行页面代码）')
    except SyntaxError as e:
        fail.append('app.py')
        print('  FAIL app.py: ' + str(e))

    after = chromadb.PersistentClient(path=paths.CHROMA).get_collection('house_data').count()
    print()
    print('向量库条数 %d -> %d %s' % (before, after, '（无副作用）' if before == after else '（被改动了！）'))
    print('导入失败 %d 个' % len(fail))
    return 1 if fail or before != after else 0


if __name__ == "__main__":
    sys.exit(main())
