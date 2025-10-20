import json  # 用於處理 JSON 文件
import argparse  # 用於命令行參數解析

def check_json_content(json_path):
    """
    檢查 JSON 文件中的頁面內容。

    參數:
        json_path (str): JSON 文件的路徑

    功能:
        - 讀取指定的 JSON 文件
        - 遍歷每頁內容，並顯示每頁前 100 個字符作為摘要
    """
    try:
        # 打開並讀取 JSON 文件
        with open(json_path, "r", encoding="utf-8") as f:
            pages = json.load(f)  # 將 JSON 文件解析為 Python 對象

        # 遍歷每頁內容並打印摘要
        for i, page in enumerate(pages):
            print(f"第 {i + 1} 頁內容：{page[:100]}...")  # 僅顯示每頁的前 100 個字符
    except Exception as e:
        # 捕捉異常並打印錯誤訊息
        print(f"檢查 JSON 文件時發生錯誤：{e}")


if __name__ == "__main__":
    # 定義命令行參數解析器
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True, help="JSON 文件路徑")  # 定義 --json 參數
    args = parser.parse_args()  # 解析命令行參數

    # 檢查 JSON 文件內容
    check_json_content(args.json)
