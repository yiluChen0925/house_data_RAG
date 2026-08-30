
# 珠三角房产智能问答系统

基于 RAG（检索增强生成）的房产智能问答系统，支持自然语言检索、多轮对话记忆、混合检索、结构化过滤及自动化日报/周报生成。


## 项目简介

本系统覆盖珠三角五城（广州、深圳、佛山、东莞、惠州）7735 条真实房源数据，通过 RAG + 混合检索 + 重排序 技术链路，实现精准的房产信息语义检索与智能推荐。同时提供日报/周报自动生成与多渠道推送（本地存档 + 钉钉 + 邮件），形成从数据采集到价值输出的完整闭环。


## 核心功能

| 功能模块 | 说明 |
|---------|------|
| 智能问答 | 自然语言检索房源，支持多轮对话记忆与上下文理解 |
| 混合检索 | BM25 关键词检索 + 向量语义检索 + RRF 融合，兼顾精确与语义 |
| 重排序 | Cross-Encoder 精排，提升 Top-K 结果的精准度 |
| 结构化过滤 | 自动提取城市、区域、价格、户型等条件，先过滤后检索 |
| 日报/周报 | 自动生成市场分析报告，推送至钉钉群、邮件并本地存档 |
| 量化评估 | 基于 DeepSeek 自评的 RAGAS 指标（忠实度 0.76，相关性 0.49） |
| 增量数据 | 支持每日新增数据的自动合并与向量库增量入库 |


## 技术架构

```
用户提问
    ↓
结构化过滤（城市/区域/价格/户型）
    ↓
混合检索（BM25 + 向量 + RRF融合）
    ↓
重排序（Cross-Encoder 精排）
    ↓
DeepSeek 大模型生成回答
```

| 层级 | 技术选型 |
|------|---------|
| 向量数据库 | ChromaDB |
| 嵌入模型 | Sentence Transformer (all-MiniLM-L6-v2) |
| 重排序模型 | Cross-Encoder (ms-marco-MiniLM-L-6-v2) |
| 大模型 | DeepSeek API |
| Web 框架 | Streamlit |
| 数据处理 | Pandas, NumPy |
| 分词 | jieba |
| 容器化 | Docker |


## 快速启动

### 1. 克隆项目

```bash
git clone https://github.com/你的用户名/house_data_RAG.git
cd house_data_RAG
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key
```

.env.example 内容：

```
DEEPSEEK_API_KEY=sk-请替换为你的真实密钥
DINGTALK_WEBHOOK=请替换为你的钉钉机器人 Webhook（可选）
DINGTALK_SECRET=请替换为你的钉钉加签密钥（可选）
EMAIL_SENDER=你的邮箱@qq.com（可选）
EMAIL_PASSWORD=你的邮箱授权码（可选）
```

### 4. 准备数据

将原始数据放入 1_data/raw_data/，然后运行：

```bash
# 全量合并与清洗（仅首次运行）
python 2_scripts/etl/merge_and_clean.py

# 构建向量库
python 2_scripts/load_to_chromadb.py
```

### 5. 启动 Web 界面

```bash
streamlit run 2_scripts/app.py
```

访问 http://localhost:8501

### 6. 生成日报/周报

```bash
# 日报
python 2_scripts/report/daily_report.py

# 周报
python 2_scripts/report/weekly_report.py
```

### 7. Docker 部署

```bash
docker build -t house-rag -f 6_deploy/Dockerfile .
docker run -p 8501:8501 house-rag
```


## 项目结构

```
house_data_RAG/
├── 1_data/                     # 数据目录
│   ├── cleaned_data/           # 清洗后数据（house_cleaned.csv）
│   ├── raw_data/               # 原始数据（不上传 GitHub）
│   ├── chroma_db/              # ChromaDB 向量库（不上传 GitHub）
│   ├── daily_raw/              # 每日解析数据
│   └── reports/                # 日报/周报存档
├── 2_scripts/                  # 核心代码
│   ├── app.py                  # Streamlit Web 主程序
│   ├── load_to_chromadb.py     # 向量入库脚本
│   ├── etl/                    # ETL 清洗合并
│   ├── rag/                    # 混合检索 + 重排序
│   ├── report/                 # 日报/周报生成 + 推送
│   ├── crawler/                # HTML 解析爬虫
│   └── evaluate/               # RAGAS 评估
├── 3_api/                      # API 接口（预留）
├── 6_deploy/                   # Dockerfile 部署配置
├── requirements.txt            # Python 依赖
├── .env.example                # 环境变量模板
├── .gitignore                  # Git 忽略规则
└── README.md                   # 项目说明
```


## 评估结果

基于 5 个真实查询的 RAGAS 风格评估：

| 指标 | 分数 |
|------|------|
| 忠实度（Faithfulness） | 0.76 |
| 答案相关性（Answer Relevancy） | 0.49 |


## 数据说明

- 数据来源：房天下 + 58同城
- 覆盖城市：广州、深圳、佛山、东莞、惠州
- 数据量：7735 条真实房源
- 字段数：30+（城市、区域、户型、总价、面积、单价等）

完整数据因体积较大未上传至 GitHub，仓库中包含演示数据。


## 联系方式

- 邮箱：13330222744@163.com
