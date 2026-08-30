FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY 2_scripts/ ./2_scripts/
COPY 3_api/ ./3_api/
COPY 1_data/cleaned_data/ ./1_data/cleaned_data/

# 暴露端口
EXPOSE 8501

# 启动 Streamlit
CMD ["streamlit", "run", "2_scripts/app.py", "--server.port=8501", "--server.address=0.0.0.0"]