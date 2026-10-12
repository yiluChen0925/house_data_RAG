# -*- coding: utf-8 -*-
"""
【已废弃】全量入库脚本（早期版本）

跟 2_scripts/load_to_chromadb.py 功能重复，而且有两个问题：
    1. 它用 uuid 当向量 id，而 hybrid_retriever 靠"id = dataframe 行号"把向量对回
       房源（_load_embeddings_from_store）。用这个脚本建的库，检索侧的向量分量会
       拿不到向量，等于退化成纯 BM25。
    2. 原本没有 __main__ 守卫，光 import 就会写库，能静默覆盖正式向量库
       （实际踩过一次，15063 条被盖成 6902 条）。

重建向量库请用 `python 2_scripts/load_to_chromadb.py`。这里只作历史参考，
代码已包进 main()，import 不再有副作用。
"""

import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag"))
import _offline_setup  # noqa: F401,E402  必须早于 sentence_transformers

import chromadb  # noqa: E402
import pandas as pd  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

# ==================== 配置 ====================
BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CSV_PATH = os.path.join(BASE_PATH, "1_data", "cleaned_data", "house_cleaned.csv")
CHROMA_PATH = os.path.join(BASE_PATH, "1_data", "chroma_db")
COLLECTION_NAME = "house_data"
MODEL_NAME = "all-MiniLM-L6-v2"


class CustomEmbeddingFunction:
    def __init__(self, model):
        self.model = model

    def __call__(self, input):
        return self.model.encode(input).tolist()


def main():
    print("!! 这是已废弃的入库脚本，建议改用 2_scripts/load_to_chromadb.py")
    print("!! 它会用 uuid 作 id，与检索侧的 id=行号 约定不兼容")

    print("加载本地模型...")
    model = SentenceTransformer(MODEL_NAME)
    embedding_func = CustomEmbeddingFunction(model)

    print("读取清洗后的数据...")
    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    df = df.dropna(subset=["城市", "户型", "面积"])
    print("总数据量: " + str(len(df)) + " 条")

    print("连接ChromaDB...")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    existing_collections = [c.name for c in client.list_collections()]
    if COLLECTION_NAME in existing_collections:
        print("删除已有集合...")
        client.delete_collection(COLLECTION_NAME)
    collection = client.create_collection(name=COLLECTION_NAME, embedding_function=embedding_func)
    print("创建新集合")

    print("开始全量入库...")
    batch_size = 100
    total = len(df)
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_df = df.iloc[start:end]
        documents, metadatas, ids = [], [], []
        for idx, row in batch_df.iterrows():
            doc_text = f"""
        城市：{row['城市']}
        区域：{row['区域'] if pd.notna(row['区域']) else '未知'}
        户型：{row['户型']}
        总价：{row['总价'] if pd.notna(row['总价']) else 0}万元
        面积：{row['面积']}㎡
        单价：{row['单价'] if pd.notna(row['单价']) else 0}元/㎡
        小区：{row['小区名称'] if pd.notna(row['小区名称']) else '未知'}
        数据来源：{row['数据来源']}
        """
            documents.append(doc_text)
            metadatas.append({
                "城市": str(row['城市']),
                "区域": str(row['区域']) if pd.notna(row['区域']) else "",
                "户型": str(row['户型']),
                "总价": float(row['总价']) if pd.notna(row['总价']) else 0.0,
                "面积": float(row['面积']),
                "单价": float(row['单价']) if pd.notna(row['单价']) else 0.0,
                "小区名称": str(row['小区名称']) if pd.notna(row['小区名称']) else "",
                "数据来源": str(row['数据来源']),
                "爬取时间": str(row['爬取时间']) if pd.notna(row['爬取时间']) else "",
            })
            ids.append(str(uuid.uuid4()))
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        print("  进度: " + str(end) + "/" + str(total))

    print("全量入库完成")
    print("   - 总数据: " + str(collection.count()) + " 条")


if __name__ == "__main__":
    main()
