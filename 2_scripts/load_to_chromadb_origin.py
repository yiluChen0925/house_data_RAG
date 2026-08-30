# -*- coding: utf-8 -*-
"""
全量入库脚本 - 只运行一次
把所有数据灌入 ChromaDB（用于初始化）
"""

import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import pandas as pd
import chromadb
import uuid
import datetime
from sentence_transformers import SentenceTransformer

# ==================== 配置 ====================
CSV_PATH = r"D:\MyProject\house_data_RAG\1_data\cleaned_data\house_cleaned.csv"
CHROMA_PATH = r"D:\MyProject\house_data_RAG\1_data\chroma_db"
COLLECTION_NAME = "house_data"
MODEL_NAME = "all-MiniLM-L6-v2"

# ==================== 加载本地模型 ====================
print("加载本地模型...")
model = SentenceTransformer(MODEL_NAME)

class CustomEmbeddingFunction:
    def __init__(self, model):
        self.model = model
    def __call__(self, input):
        return self.model.encode(input).tolist()

embedding_func = CustomEmbeddingFunction(model)

# ==================== 读取数据 ====================
print("读取清洗后的数据...")
df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
df = df.dropna(subset=["城市", "户型", "面积"])
print("总数据量: " + str(len(df)) + " 条")

# ==================== 连接 ChromaDB ====================
print("连接ChromaDB...")
client = chromadb.PersistentClient(path=CHROMA_PATH)

existing_collections = [c.name for c in client.list_collections()]
if COLLECTION_NAME in existing_collections:
    print("删除已有集合...")
    client.delete_collection(COLLECTION_NAME)

collection = client.create_collection(
    name=COLLECTION_NAME,
    embedding_function=embedding_func
)
print("创建新集合")

# ==================== 全量入库 ====================
print("开始全量入库...")
batch_size = 100
total = len(df)

for start in range(0, total, batch_size):
    end = min(start + batch_size, total)
    batch_df = df.iloc[start:end]

    documents = []
    metadatas = []
    ids = []

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

        if "房源编码" in batch_df.columns and pd.notna(row['房源编码']):
            ids.append(str(row['房源编码']))
        else:
            ids.append(str(uuid.uuid4()))

    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    print("  进度: " + str(end) + "/" + str(total))

print("全量入库完成")
print("   - 总数据: " + str(collection.count()) + " 条")