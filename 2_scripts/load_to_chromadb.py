# -*- coding: utf-8 -*-
"""全量重建向量库：house_cleaned.csv -> ChromaDB 的 house_data 集合。

先删旧集合再建，重复跑结果一致。原来的版本只挑"爬取时间是今天"的行做增量，
数据换过之后跑它会因为"今日无新数据"直接退出，库还是旧的。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag"))
import _offline_setup  # noqa: F401  必须早于 sentence_transformers，见该模块说明

import chromadb  # noqa: E402
import pandas as pd  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CSV_PATH = os.path.join(BASE_PATH, "1_data", "cleaned_data", "house_cleaned.csv")
CHROMA_PATH = os.path.join(BASE_PATH, "1_data", "chroma_db")
COLLECTION_NAME = "house_data"
MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 256


class CustomEmbeddingFunction:
    """必须与 hybrid_retriever.CustomEmbeddingFunction 的接口保持一致。

    两边的 name() 返回值也要一样，否则 Chroma 会认为集合的嵌入函数变了而报警告。
    """

    def __init__(self, model):
        self.model = model

    def embed_documents(self, texts):
        return self.model.encode(list(texts), show_progress_bar=False).tolist()

    def embed_query(self, input):
        return self.model.encode(input, show_progress_bar=False).tolist()

    def __call__(self, input):
        if isinstance(input, str):
            return self.embed_query(input)
        return self.embed_documents(input)

    def name(self):
        return "custom_embedding_function"


def build_document(row):
    """入库文本：给向量/BM25 用的房源描述。"""
    def val(key, default="未知"):
        v = row.get(key)
        if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ("", "nan"):
            return default
        return v

    return (
        "\n        城市：" + str(val("城市")) +
        "\n        区域：" + str(val("区域")) +
        "\n        户型：" + str(val("户型")) +
        "\n        总价：" + str(val("总价", 0)) + "万元" +
        "\n        面积：" + str(val("面积", 0)) + "㎡" +
        "\n        单价：" + str(val("单价", 0)) + "元/㎡" +
        "\n        朝向：" + str(val("朝向")) +
        "\n        小区：" + str(val("小区名称")) +
        "\n        数据来源：" + str(val("数据来源")) +
        "\n        "
    )


def build_metadata(row):
    def num(key):
        try:
            v = float(row.get(key))
            return 0.0 if pd.isna(v) else v
        except (TypeError, ValueError):
            return 0.0

    def text(key):
        v = row.get(key)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        return str(v)

    return {
        "城市": text("城市"),
        "区域": text("区域"),
        "户型": text("户型"),
        "总价": num("总价"),
        "面积": num("面积"),
        "单价": num("单价"),
        "小区名称": text("小区名称"),
        "朝向": text("朝向"),
        "数据来源": text("数据来源"),
        "爬取时间": text("爬取时间"),
    }


def main():
    print("CSV: " + CSV_PATH)
    print("向量库: " + CHROMA_PATH)
    if not os.path.exists(CSV_PATH):
        print("找不到清洗后的 CSV，请先运行 2_scripts/etl/merge_and_clean.py")
        return 1

    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    df = df.dropna(subset=["城市"])
    print("待入库数据: " + str(len(df)) + " 条")

    print("加载本地模型 " + MODEL_NAME + " ...")
    model = SentenceTransformer(MODEL_NAME)
    embedding_func = CustomEmbeddingFunction(model)

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    existing = [c.name for c in client.list_collections()]
    if COLLECTION_NAME in existing:
        before = client.get_collection(COLLECTION_NAME).count()
        print("删除旧集合 " + COLLECTION_NAME + "（原 " + str(before) + " 条向量）")
        client.delete_collection(COLLECTION_NAME)
    collection = client.create_collection(name=COLLECTION_NAME, embedding_function=embedding_func)
    print("已创建新集合: " + COLLECTION_NAME)

    total = len(df)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batch = df.iloc[start:end]
        collection.add(
            documents=[build_document(row) for _, row in batch.iterrows()],
            metadatas=[build_metadata(row) for _, row in batch.iterrows()],
            ids=[str(i) for i in batch.index],
        )
        print("  进度: " + str(end) + "/" + str(total), flush=True)

    print("重建完成，当前向量数: " + str(collection.count()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
