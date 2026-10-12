# -*- coding: utf-8 -*-
"""查 hybrid_retriever 的导入链里，是谁把 huggingface_hub.constants 拉进来并冻结了离线开关。

    python 5_tests/diag/import_chain.py
"""

import sys

sys.path.insert(0, __file__.rsplit("5_tests", 1)[0] + "5_tests")
import paths  # noqa: E402

paths.add_paths()


def frozen_now():
    if 'huggingface_hub.constants' in sys.modules:
        from huggingface_hub import constants
        return '已导入(冻结值=%s)' % constants.HF_HUB_OFFLINE
    return '未导入'


def main():
    import os
    print('起点:', frozen_now(), '| HF_HUB_OFFLINE =', repr(os.environ.get('HF_HUB_OFFLINE')))

    # 模拟 hybrid_retriever 顶部的做法
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    print('设完 os.environ 后:', frozen_now())

    import pandas  # noqa: F401
    print('import pandas 后:', frozen_now())

    import chromadb  # noqa: F401
    print('import chromadb 后:', frozen_now(), '  <-- 关键一步')

    from sentence_transformers import SentenceTransformer  # noqa: F401
    print('import sentence_transformers 后:', frozen_now())

    from huggingface_hub import constants
    print('最终常量 =', constants.HF_HUB_OFFLINE)

    import importlib.metadata as md
    print()
    print('chromadb 的依赖里含:', [r for r in (md.requires('chromadb') or [])
                                   if 'huggingface' in r.lower() or 'tokenizers' in r.lower()])


if __name__ == "__main__":
    main()
