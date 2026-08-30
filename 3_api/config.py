# ====================== MySQL配置（保留） ======================
MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "123456",        # 改成你的MySQL密码
    "db": "dirty_data_table",          # 改成你实际的数据库名（你之前是dirty_data_table）
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

# ====================== Redis配置（已弃用，保留注释） ======================
# REDIS_CONFIG = {
#     "host": "192.168.1.3",
#     "port": 6379,
#     "db": 0,
#     "password": "123456",
#     "decode_responses": True,
#     "socket_timeout": 10
# }