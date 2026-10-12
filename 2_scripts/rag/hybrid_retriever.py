# -*- coding: utf-8 -*-
"""
混合检索器
结构化过滤 + BM25 关键词检索 + 向量语义检索 + RRF 按排名融合

融合方式：Reciprocal Rank Fusion（按排名，见 search() 里的说明），
不是"alpha * BM25 + (1-alpha) * 向量相似度"——后者把两个不同量纲的分数量纲
直接线性相加，alpha 没有明确含义。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _offline_setup  # noqa: F401  必须早于 sentence_transformers，见该模块说明

import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
import jieba
import numpy as np

MODEL_NAME = "all-MiniLM-L6-v2"
# 从文件位置推项目根：这个项目被复制过一份，"复制后路径写死"是踩过的坑
BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CHROMA_PATH = os.path.join(BASE_PATH, "1_data", "chroma_db")
CSV_PATH = os.path.join(BASE_PATH, "1_data", "cleaned_data", "house_cleaned.csv")


def _as_text(value):
    """空值读回来是 float('nan')，和字符串拼接会抛 TypeError。"""
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


class CustomEmbeddingFunction:
    def __init__(self, model_name):
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts):
        return self.model.encode(texts).tolist()

    def embed_query(self, input):
        return self.model.encode(input).tolist()

    def __call__(self, input):
        if isinstance(input, str):
            return self.embed_query(input)
        else:
            return self.embed_documents(input)

    def name(self):
        return "custom_embedding_function"


class HybridRetriever:
    def __init__(self):
        self.model = SentenceTransformer(MODEL_NAME)
        self.client = chromadb.PersistentClient(path=CHROMA_PATH)

        embedding_fn = CustomEmbeddingFunction(MODEL_NAME)
        self.collection = self.client.get_collection(
            name="house_data",
            embedding_function=embedding_fn
        )

        self.df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
        self._build_bm25_index()
        self._load_embeddings_from_store()

        self.metadata_map = {}
        for idx, row in self.df.iterrows():
            key = (row.get('城市'), row.get('区域'), row.get('小区名称'))
            self.metadata_map[key] = idx

        # 重排模型只加载一次（原来每次 search() 都 new 一个 Reranker，
        # 等于每次查询重新加载一遍 Cross-Encoder）
        self._reranker = None

    @property
    def reranker(self):
        if self._reranker is None:
            from reranker import Reranker
            self._reranker = Reranker()
        return self._reranker

    def _load_embeddings_from_store(self):
        """把向量库里的向量一次性读进内存。

        原来是每个查询都对候选集重新 encode 一遍，候选上千条时要 600~900ms。
        库里存的本来就是归一化向量，一次取回约 0.5s / 22MB，之后算余弦只是矩阵乘。
        """
        result = self.collection.get(include=['embeddings'])
        ids = [int(i) for i in result['ids']]
        matrix = np.asarray(result['embeddings'], dtype=np.float32)

        # 写库时 id 用的就是 dataframe 行号，靠它把向量对回 df
        self._emb_position = {row_id: pos for pos, row_id in enumerate(ids)}
        self._emb_matrix = matrix
        print("已从向量库缓存 " + str(matrix.shape[0]) + " 条向量（"
              + str(round(matrix.nbytes / 1024 / 1024, 1)) + " MB）")

    def _vector_scores_for(self, positions, query_embedding):
        """对 df 的指定行位置算余弦（缺向量的行返回 -1）。"""
        scores = np.full(len(positions), -1.0, dtype=np.float32)
        rows, vecs = [], []
        for i, pos in enumerate(positions):
            emb_pos = self._emb_position.get(pos)
            if emb_pos is not None:
                rows.append(i)
                vecs.append(self._emb_matrix[emb_pos])
        if rows:
            scores[rows] = np.asarray(vecs, dtype=np.float32) @ query_embedding
        return scores

    def _build_bm25_index(self):
        self.documents = []
        for _, row in self.df.iterrows():
            doc = f"{row['城市']} {row['区域']} {row['户型']} {row['小区名称']}"
            self.documents.append(doc)
        self.tokenized_docs = [list(jieba.cut(doc)) for doc in self.documents]
        self.bm25 = BM25Okapi(self.tokenized_docs)
        self.metadatas = self.df.to_dict('records')

    def search(self, query, top_k=5, alpha=0.5,
               city=None, district=None, max_price=None, min_price=None,
               layout=None, min_area=None, max_area=None):

        # 第一步：结构化过滤
        filtered_df = self.df.copy()

        if city:
            filtered_df = filtered_df[filtered_df['城市'].astype(str).str.contains(city, na=False, case=False)]
            print("after city(" + city + "): " + str(len(filtered_df)))

        if district:
            district_clean = district.replace('区', '')
            filtered_df = filtered_df[
                filtered_df['区域'].astype(str).str.contains(district_clean, na=False, case=False)]
            print("after district(" + district + "): " + str(len(filtered_df)))

        if max_price is not None:
            filtered_df = filtered_df[filtered_df['总价'] <= max_price]
            print("after max_price(" + str(max_price) + "): " + str(len(filtered_df)))

        if min_price is not None:
            filtered_df = filtered_df[filtered_df['总价'] >= min_price]
            print("after min_price(" + str(min_price) + "): " + str(len(filtered_df)))

        if layout:
            layout_map = {
                '一房': ['1室', '1厅'],
                '两房': ['2室', '2厅'],
                '三房': ['3室', '3厅'],
                '四房': ['4室'],
                '五房': ['5室'],
                '一室': ['1室'],
                '两室': ['2室'],
                '三室': ['3室'],
                '四室': ['4室'],
                '五室': ['5室'],
            }
            if layout in layout_map:
                patterns = layout_map[layout]
                mask = False
                for p in patterns:
                    mask = mask | filtered_df['户型'].astype(str).str.contains(p, na=False)
                filtered_df = filtered_df[mask]
            else:
                filtered_df = filtered_df[filtered_df['户型'].astype(str).str.contains(layout, na=False)]
            print("after layout(" + layout + "): " + str(len(filtered_df)))

        if min_area is not None:
            filtered_df = filtered_df[filtered_df['面积'] >= min_area]
            print("after min_area(" + str(min_area) + "): " + str(len(filtered_df)))

        if max_area is not None:
            filtered_df = filtered_df[filtered_df['面积'] <= max_area]
            print("after max_area(" + str(max_area) + "): " + str(len(filtered_df)))

        if len(filtered_df) == 0:
            print("过滤后无数据")
            return []

        # 第二步：对过滤后的数据建立临时索引
        documents = []
        metadatas = []
        for _, row in filtered_df.iterrows():
            doc = f"{row['城市']} {row['区域']} {row['户型']} {row['小区名称']}"
            documents.append(doc)
            metadatas.append(row.to_dict())

        tokenized_docs = [list(jieba.cut(doc)) for doc in documents]
        bm25 = BM25Okapi(tokenized_docs)

        # 第三步：BM25 检索（保留原始分，仅用于展示）
        tokenized_query = list(jieba.cut(query))
        bm25_scores = np.asarray(bm25.get_scores(tokenized_query), dtype=float)

        # 第四步：向量检索（用向量库里缓存的向量，不重新编码候选集）
        query_embedding = self.model.encode(query, normalize_embeddings=True)
        positions = list(filtered_df.index)
        vector_scores = self._vector_scores_for(positions, query_embedding)

        # 第五步：RRF 融合（按排名，不用分数）
        # 原来写的是 alpha*BM25 + (1-alpha)*余弦。BM25 归一化后是 0~1，余弦是 -1~1，
        # 两个尺度不可比，alpha 的实际含义随数据变，没法调。
        # RRF 只用排名，k=60 是常用的平滑值，alpha 在这里就是纯权重，0.5 等权。
        RRF_K = 60

        bm25_order = np.argsort(-bm25_scores)
        vector_order = np.argsort(-vector_scores)

        bm25_rank = np.empty(len(filtered_df), dtype=int)
        vector_rank = np.empty(len(filtered_df), dtype=int)
        bm25_rank[bm25_order] = np.arange(len(filtered_df))
        vector_rank[vector_order] = np.arange(len(filtered_df))

        candidates = []
        for i in range(len(filtered_df)):
            rrf = (alpha * (1.0 / (RRF_K + bm25_rank[i]))
                   + (1 - alpha) * (1.0 / (RRF_K + vector_rank[i])))
            candidates.append({
                'index': i,
                'bm25': bm25_scores[i],
                'vector': vector_scores[i],
                'bm25_rank': int(bm25_rank[i]),
                'vector_rank': int(vector_rank[i]),
                'fused': rrf,
                'metadata': metadatas[i]
            })

        candidates.sort(key=lambda x: x['fused'], reverse=True)
        candidates = candidates[:20]

        # 第六步：重排序（reranker 是模块级缓存的，不会每次查询重新加载模型）
        reranker = self.reranker
        rerank_candidates = []
        for c in candidates:
            meta = c['metadata']
            rerank_candidates.append({
                '小区名称': meta.get('小区名称', ''),
                '城市': meta.get('城市', ''),
                '区域': meta.get('区域', ''),
                '户型': meta.get('户型', ''),
                '总价': meta.get('总价', 0),
                '面积': meta.get('面积', 0),
                '单价': meta.get('单价', 0),
                '数据来源': meta.get('数据来源', ''),
            })

        reranked = reranker.rerank(query, rerank_candidates, top_k=top_k)

        results = []
        for r in reranked:
            results.append({
                '小区名称': _as_text(r.get('小区名称')),
                '城市': _as_text(r.get('城市')),
                '区域': _as_text(r.get('区域')),
                '户型': _as_text(r.get('户型')),
                '总价': r.get('总价', 0),
                '面积': r.get('面积', 0),
                '单价': r.get('单价', 0),
                '数据来源': _as_text(r.get('数据来源')),
                'rerank_score': r.get('rerank_score', 0)
            })
        return results


if __name__ == "__main__":
    retriever = HybridRetriever()
    queries = [
        "深圳南山区三房",
        "广州天河区500万以下",
        "佛山南海区地铁房"
    ]
    for q in queries:
        print("\n" + "=" * 50)
        print("查询: " + q)
        print("=" * 50)
        results = retriever.search(q, top_k=3)
        for i, r in enumerate(results, 1):
            print(str(i) + ". " + r['小区名称'] + " | " + r['城市'] + r['区域']
                  + " | " + r['户型'] + " | 重排分:" + str(r['rerank_score']))