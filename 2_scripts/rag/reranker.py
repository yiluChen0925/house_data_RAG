# -*- coding: utf-8 -*-
"""
重排序模块
使用 Cross-Encoder 对召回结果精排
"""

import os
import numpy as np
from sentence_transformers import CrossEncoder

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# ==================== 配置 ====================
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class Reranker:
    def __init__(self, model_name=RERANKER_MODEL):
        print("加载重排序模型: " + model_name + "...")
        self.model = CrossEncoder(model_name)
        print("模型加载完成")

    def rerank(self, query, candidates, top_k=5):
        if not candidates:
            return []

        # 构建 Query-Document 对
        pairs = []
        for c in candidates:
            doc = f"{c.get('城市', '')} {c.get('区域', '')} {c.get('户型', '')} {c.get('小区名称', '')}"
            pairs.append([query, doc])

        # 计算相关性分数
        scores = self.model.predict(pairs)

        # 排序
        for i, c in enumerate(candidates):
            c['rerank_score'] = float(scores[i])

        candidates.sort(key=lambda x: x['rerank_score'], reverse=True)
        return candidates[:top_k]


# ==================== 测试 ====================
if __name__ == "__main__":
    # 模拟候选
    candidates = [
        {'小区名称': '城市主场', '城市': '深圳', '区域': '福田区', '户型': '1室1厅', '总价': 209},
        {'小区名称': '南荔苑', '城市': '深圳', '区域': '南山区', '户型': '1室1厅', '总价': 192},
        {'小区名称': '海印长城', '城市': '深圳', '区域': '南山区', '户型': '5室1厅', '总价': 900},
        {'小区名称': '珠江园', '城市': '广州', '区域': '越秀区', '户型': '3室2厅', '总价': 176},
    ]

    reranker = Reranker()
    results = reranker.rerank("深圳南山区三房推荐", candidates, top_k=3)

    print("\n重排序结果:")
    for i, r in enumerate(results, 1):
        print(str(i) + ". " + r['小区名称'] + " | " + r['城市'] + r['区域'] + " | 总分:" + str(r['rerank_score']))