# -*- coding: utf-8 -*-
"""检索延迟与结果：优化前后的对比依据。

原来每个查询都重新 encode 候选集、每次 new 一个 Reranker；
现在向量从库里缓存、Reranker 复用。这个脚本打印当前实现的单查询延迟。

    python 5_tests/bench/bench_retriever.py
"""

import sys
import time

sys.path.insert(0, __file__.rsplit("5_tests", 1)[0] + "5_tests")
import paths  # noqa: E402

paths.offline()

QUERIES = [
    ("深圳南山区500万以下三房", dict(city="深圳", district="南山区", max_price=500.0, layout="三房")),
    ("广州天河区500万以下", dict(city="广州", district="天河区", max_price=500.0)),
    ("佛山南海区地铁房", dict(city="佛山", district="南海区")),
    ("深圳前海两房", dict(city="深圳", layout="两房")),
    ("东莞松山湖三房", dict(city="东莞", district="松山湖", layout="三房")),
]


def main():
    from hybrid_retriever import HybridRetriever

    t0 = time.perf_counter()
    r = HybridRetriever()
    print("初始化 %.1f s（含加载模型 + 缓存向量）" % (time.perf_counter() - t0))
    print()

    total = 0.0
    for query, kw in QUERIES:
        t = time.perf_counter()
        res = r.search(query, top_k=3, **kw)
        ms = (time.perf_counter() - t) * 1000
        total += ms
        print("%-22s %6.0f ms" % (query[:20], ms))
        for i, x in enumerate(res, 1):
            print("    %d. %s | %s%s | %s | 重排 %.2f"
                  % (i, x['小区名称'], x['城市'], x['区域'],
                     x['户型'] or "-", x['rerank_score']))
    print()
    print("平均 %.0f ms/查询（改之前是 600~900 ms）" % (total / len(QUERIES)))


if __name__ == "__main__":
    main()
