# -*- coding: utf-8 -*-
"""
每日增量入库脚本
从 house_cleaned.csv 读取今天的新数据，增量添加到 ChromaDB
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

# ==================== 初始化ChromaDB ====================
print("连接ChromaDB...")
client = chromadb.PersistentClient(path=CHROMA_PATH)

existing_collections = [c.name for c in client.list_collections()]
if COLLECTION_NAME in existing_collections:
    collection = client.get_collection(COLLECTION_NAME)
    print("已有集合，当前向量数: " + str(collection.count()))

    existing_data = collection.get(limit=10000)
    existing_ids = set(existing_data['ids'])
    print("   - 已有房源编码: " + str(len(existing_ids)) + " 个")
else:
    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_func
    )
    print("创建新集合")
    existing_ids = set()

# ==================== 筛选今天的新数据 ====================
today_str = datetime.datetime.now().strftime('%Y-%m-%d')
df_today = df[df['爬取时间'].str.startswith(today_str) if '爬取时间' in df.columns else pd.Series(False)]

if '爬取时间' not in df.columns and '采集日期' in df.columns:
    df_today = df[df['采集日期'].str.startswith(today_str)]

if len(df_today) == 0:
    print("今日 " + today_str + " 没有新数据，无需入库")
    exit(0)

print("今日新增: " + str(len(df_today)) + " 条")

# ==================== 去重 ====================
if "房源编码" in df_today.columns:
    df_today['_key'] = df_today['房源编码'].astype(str)
else:
    df_today['_key'] = df_today['小区名称'].astype(str) + "|" + df_today['户型'].astype(str) + "|" + df_today[
        '总价'].astype(str)

df_new = df_today[~df_today['_key'].isin(existing_ids)]
df_new = df_new.drop(columns=['_key'])

if len(df_new) == 0:
    print("今日数据已全部入库，无需重复添加")
    exit(0)

print("实际新增: " + str(len(df_new)) + " 条")

# ==================== 批量入库 ====================
print("开始入库...")
batch_size = 100
total = len(df_new)

for start in range(0, total, batch_size):
    end = min(start + batch_size, total)
    batch_df = df_new.iloc[start:end]

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

# ==================== 统计 ====================
print("增量入库完成")
print("   - 今日新增: " + str(len(df_new)) + " 条")
print("   - 当前总量: " + str(collection.count()) + " 条")