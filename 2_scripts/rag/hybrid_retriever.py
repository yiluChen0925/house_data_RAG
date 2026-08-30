# -*- coding: utf-8 -*-
"""
混合检索器
BM25 关键词检索 + 向量语义检索 + RRF 融合
"""

import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
import jieba
import numpy as np
import os

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

MODEL_NAME = "all-MiniLM-L6-v2"
CHROMA_PATH = r"D:\MyProject\house_data_RAG\1_data\chroma_db"
CSV_PATH = r"D:\MyProject\house_data_RAG\1_data\cleaned_data\house_cleaned.csv"


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

        self.metadata_map = {}
        for idx, row in self.df.iterrows():
            key = (row.get('城市'), row.get('区域'), row.get('小区名称'))
            self.metadata_map[key] = idx

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

        # 第三步：BM25 检索
        tokenized_query = list(jieba.cut(query))
        bm25_scores = bm25.get_scores(tokenized_query)
        if bm25_scores.max() > 0:
            bm25_scores = bm25_scores / bm25_scores.max()

        # 第四步：向量检索
        query_embedding = self.model.encode(query)
        filtered_embeddings = self.model.encode(documents)

        from numpy.linalg import norm
        vector_scores = []
        for emb in filtered_embeddings:
            sim = np.dot(query_embedding, emb) / (norm(query_embedding) * norm(emb))
            vector_scores.append(sim)
        vector_scores = np.array(vector_scores)

        # 第五步：融合排序
        candidates = []
        for i in range(len(filtered_df)):
            fused_score = alpha * bm25_scores[i] + (1 - alpha) * vector_scores[i]
            candidates.append({
                'index': i,
                'bm25': bm25_scores[i],
                'vector': vector_scores[i],
                'fused': fused_score,
                'metadata': metadatas[i]
            })

        candidates.sort(key=lambda x: x['fused'], reverse=True)
        candidates = candidates[:20]

        # 第六步：重排序
        from reranker import Reranker
        reranker = Reranker()
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
                '小区名称': r.get('小区名称', ''),
                '城市': r.get('城市', ''),
                '区域': r.get('区域', ''),
                '户型': r.get('户型', ''),
                '总价': r.get('总价', 0),
                '面积': r.get('面积', 0),
                '单价': r.get('单价', 0),
                '数据来源': r.get('数据来源', ''),
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
            print(str(i) + ". " + r['小区名称'] + " | " + r['城市'] + r['区域'] + " | " + r['户型'] + " | 重排分:" + str(r['rerank_score']))