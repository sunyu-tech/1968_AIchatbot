# 使用官方 Python 3.10 精簡映像
FROM python:3.10-slim

# 設定工作目錄
WORKDIR /app

# 複製 requirements.txt 先安裝依賴，加快快取機制
COPY requirements.txt /app/requirements.txt

# 更新 pip 並安裝依賴
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

# 複製程式碼與其他檔案進容器（包含 .env、PDF、faiss_index）
COPY . /app

# 設定環境變數
ENV PYTHONUNBUFFERED=1 \
    PDF_JSON_PATH=/app/PDF/all_text.json

# 開放 port（FastAPI 埠號 8108）
EXPOSE 8108

# 執行 FastAPI 主程式（process_pdf.py）
CMD ["python", "process_pdf.py"]
