# -*- coding: utf-8 -*-
"""能不能把向量库里的向量一次性读回内存，代价多大。

    python 5_tests/diag/embedding_cache.py
"""

import sys
import time

sys.path.insert(0, __file__.rsplit("5_tests", 1)[0] + "5_tests")
import paths  # noqa: E402

paths.offline()

import numpy as np  # noqa: E402
import chromadb  # noqa: E402


def main():
    t0 = time.perf_counter()
    client = chromadb.PersistentClient(path=paths.CHROMA)
    col = client.get_collection('house_data')
    t1 = time.perf_counter()
    print('打开库+取集合: %.0f ms, count=%d' % ((t1 - t0) * 1000, col.count()))

    res = col.get(include=['embeddings'])
    t2 = time.perf_counter()
    ids = [int(i) for i in res['ids']]
    emb = np.asarray(res['embeddings'], dtype=np.float32)
    print('collection.get(embeddings): %.0f ms' % ((t2 - t1) * 1000))
    print('  ids=%d shape=%s 内存≈%.1f MB' % (len(ids), emb.shape, emb.nbytes / 1024 / 1024))
    print('  id 范围 %d~%d，是否递增: %s' % (min(ids), max(ids), ids == sorted(ids)))
    print('  范数样例(应为 1，说明库里存的是归一化向量): %s'
          % np.round(np.linalg.norm(emb[:3], axis=1), 4))

    q = np.random.rand(emb.shape[1]).astype(np.float32)
    q /= np.linalg.norm(q)
    t3 = time.perf_counter()
    sims = emb @ q
    t4 = time.perf_counter()
    print('全库余弦(%d x %d 矩阵乘): %.1f ms, top1=%.4f'
          % (emb.shape[0], emb.shape[1], (t4 - t3) * 1000, sims.max()))


if __name__ == "__main__":
    main()
