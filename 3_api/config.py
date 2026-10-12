# ====================== MySQL配置（保留） ======================
# 注：这套配置最初从早期爬虫项目复用而来。
# 密码改为从环境变量读取，不再硬编码在源码里。
import os

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),   # ← 从环境变量读，勿写死
    "db": os.getenv("MYSQL_DB", "dirty_data_table"),
    "charset": "utf8mb4"
}

# # ====================== DeepSeek API配置（新增） ======================
# DEEPSEEK_CONFIG = {
#     "api_key": "sk-你的DeepSeek密钥",   # 替换成你充值后的真实API Key
#     "base_url": "https://api.deepseek.com/v1",
#     "model": "deepseek-chat",           # 或 deepseek-reasoner
#     "embedding_model": "deepseek-embedding"  # 如果DeepSeek支持，否则用替代方案
# }

# ====================== 向量数据库配置（新增） ======================
CHROMA_CONFIG = {
    "persist_directory": "./data/chroma_db",  # 向量库持久化路径
    "collection_name": "house_data"           # 集合名称
}

# ====================== 文件路径配置（新增） ======================
FILE_CONFIG = {
    "raw_data": "./data/raw_data/house_raw.csv",       # 原始数据
    "cleaned_data": "./data/cleaned/house_cleaned.csv",  # 清洗后数据
    "feedback_log": "./logs/feedback.jsonl"       # 反馈日志
}

# ====================== 保留（但不一定用） ======================
BATCH_SIZE = 20

# ====================== Redis配置（已弃用） ======================
# 早期爬虫用过 Redis 做去重，这里已不再使用，故删除（原配置含明文口令）。
# 如后续需要，用 os.getenv("REDIS_PASSWORD", "") 从环境变量读取。