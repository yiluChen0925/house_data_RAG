# -*- coding: utf-8 -*-
"""向量检索方案对比：候选集精确余弦 vs ChromaDB 的 ANN 查询。

用来回答"为什么不用 collection.query()"——两个指标一起看：
延迟，以及两种方案 top20 的重合度（重合度低说明 ANN 在牺牲结果质量）。

    python 5_tests/bench/bench_vector_search.py
"""

import sys
import time

sys.path.insert(0, __file__.rsplit("5_tests", 1)[0] + "5_tests")
import paths  # noqa: E402

paths.offline()

import numpy as np  # noqa: E402

QUERIES = [
    ("深圳南山区500万以下三房", dict(city="深圳", district="南山区", max_price=500.0, layout="三房")),
    ("广州天河区500万以下", dict(city="广州", district="天河区", max_price=500.0)),
    ("佛山南海区地铁房", dict(city="佛山", district="南海区")),
    ("深圳前海两房", dict(city="深圳", layout="两房")),
    ("东莞松山湖三房", dict(city="东莞", district="松山湖", layout="三房")),
]


def structured_filter(df, **kw):
    f = df.copy()
    if kw.get("city"):
        f = f[f['城市'].astype(str).str.contains(kw["city"], na=False)]
    if kw.get("district"):
        d = kw["district"].replace('区', '')
        f = f[f['区域'].astype(str).str.contains(d, na=False)]
    if kw.get("max_price") is not None:
        f = f[f['总价'] <= kw["max_price"]]
    if kw.get("layout"):
        m = {"三房": ["3室", "3厅"], "两房": ["2室", "2厅"], "一房": ["1室"]}.get(kw["layout"], [kw["layout"]])
        mask = False
        for p in m:
            mask = mask | f['户型'].astype(str).str.contains(p, na=False)
        f = f[mask]
    return f


def main():
    from hybrid_retriever import HybridRetriever

    r = HybridRetriever()
    print("CSV %d 行, 向量库 %d 条" % (len(r.df), r.collection.count()))
    print()
    print("%-24s %6s %9s %9s %8s %8s" % ("查询", "候选", "精确ms", "ANN ms", "top20交", "top5同"))
    print("-" * 72)

    for query, kw in QUERIES:
        cand = structured_filter(r.df, **kw)
        if len(cand) == 0:
            continue

        docs = ["%s %s %s %s" % (x['城市'], x['区域'], x['户型'], x['小区名称'])
                for _, x in cand.iterrows()]
        t0 = time.perf_counter()
        qe = r.model.encode(query, normalize_embeddings=True)
        embs = r.model.encode(docs, normalize_embeddings=True, show_progress_bar=False)
        sims = embs @ qe
        t_exact = (time.perf_counter() - t0) * 1000
        order_exact = [cand.index[i] for i in np.argsort(-sims)]

        t0 = time.perf_counter()
        res = r.collection.query(query_texts=[query], n_results=min(3000, r.collection.count()))
        got = [int(i) for i in res['ids'][0]]
        cand_set = set(cand.index)
        order_ann = [i for i in got if i in cand_set]
        t_ann = (time.perf_counter() - t0) * 1000

        overlap = len(set(order_exact[:20]) & set(order_ann[:20]))
        same5 = "是" if order_exact[:5] == order_ann[:5] else "否"
        print("%-24s %6d %9.1f %9.1f %8d %8s" % (query[:22], len(cand), t_exact, t_ann, overlap, same5))

    print()
    print("top20交 满分是 20。偏低说明 ANN 返回的是全库近邻，未必落在结构化过滤出的候选集里。")


if __name__ == "__main__":
    main()
