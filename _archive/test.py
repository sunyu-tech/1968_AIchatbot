import pdfplumber
import json
import os

pdf_path = r"D:\github\1968_SMART_CHAT_BACK\PDF\1968_QA.pdf"
json_output_path = r"D:\github\1968_SMART_CHAT_BACK\PDF\all_text.json"

# 確保輸出資料夾存在
os.makedirs(os.path.dirname(json_output_path), exist_ok=True)

try:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [page.extract_text() for page in pdf.pages if page.extract_text()]

    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)

    print(f"已成功儲存 JSON：{json_output_path}")

except Exception as e:
    print(f"錯誤：{e}")
