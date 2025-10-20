# 1968_SMART_CHAT_BACK

"D:\github\1968_AIchatbot\front"前端 demo 用
前端啟動 php -S 127.0.0.1:8080
後端啟動 python -m uvicorn process_pdf:app --host 0.0.0.0 --port 8108 --reload

前端
發布測試 fetch("https://59.126.242.4:8108/chatback/query", {
本機測試 fetch("http://127.0.0.1:8108/chatback/query/", {

打包 docker build -t 1968_smart_chatbot:latest .  
 docker save -o D:\github\1968_SMART_CHAT_BACK\1968_smart_chatbot.tar 1968_smart_chatbot:latest

主程式：`process_pdf.py`（**啟動設定請勿修改**）

## 專案結構

D:\github\1968_SMART_CHAT_BACK\
├─ .env
├─ Dockerfile
├─ README.md
├─ process_pdf.py ← 單一入口（FastAPI）；LLM 路由 + RAG + 5s SLA
├─ requirements.txt
├─ service.log
├─ IIS\
│ ├─ 59_126_242_4.key
│ └─ 59_126_242_4.pem
├─ PDF\
│ ├─ 1968_QA.pdf
│ └─ all_text.json
├─ faiss_index\
│ ├─ index.faiss
│ └─ index.pkl
├─ core\
│ ├─ config.py ← 參數（SLA/Timeout/DB 等）
│ ├─ endpoints.py ← 【新增】所有 API/XML 的統一登錄檔
│ ├─ geocoding.py ← 【新增】Google Maps（可選）+ Nominatim
│ ├─ http_client.py
│ ├─ intent_router.py ← 【新增】LLM 路由（無關鍵字）
│ └─ textnorm.py ← 可留（僅作輕量清理，不參與路由判斷）
├─ models\
│ └─ incidents.py
├─ parsers\
│ └─ incidents_parser.py
├─ prompts\
│ └─ all_zh.py ← 【新增】所有 prompt 合一
├─ services\
│ ├─ alt_routes_service.py ← 改從 endpoints 取 URL
│ ├─ incidents_service.py ← 改從 endpoints 取 URL
│ ├─ parking_service.py ← 改從 endpoints 取 URL
│ ├─ shoulder_service.py ← 改從 endpoints 取 URL
│ └─ thb_service.py ← 仍可暫停
└─ \_archive\ ← 被移除/備份檔（可選）
├─ composer.json
├─ composer.lock
├─ index.php
├─ process_pdf.php
├─ app.py
├─ test.py
└─ routers\traffic_incidents.py

## 已接資料源

- 路況事件：`http://210.241.131.244/xml/1min_incident_data_[north|center|south|pinglin].xml`
- 替代道路/旅行時間：`http://210.241.131.244/xml/30min_alternative_data.xml`
- 開放路肩（即時/配置）：
  - `http://210.241.131.244/xml/1min_scs_operation_data.xml`
  - `http://210.241.131.244/xml/1day_scs_config_data.xml`
- 服務區停車位：`https://tisv.tcloud.freeway.gov.tw/xml/motc_parking/availbility_freeway.xml`
- 公路局即時路段資料：`https://thbtrafficapp.thb.gov.tw/opendata/section/livetrafficdata/LiveTrafficList.xml`
- 天氣：Open-Meteo（免金鑰，已在主程式內整合）

## 回覆規則（重點）

- **不要反問**：事件類（事故/施工/出口壅塞）與其他資料源一律直接回「🛰 標題 + 揭示數筆要點」，每筆用 `•` 斷行。
- 事件查無資料時回：「目前查無符合條件的事件。」
- 公用免責會自動附加：`— 以上內容由AI…`
- RAG 僅在前述都不命中時才備援。
- **台灣限定**：問句含明確國外詞且不含國道語彙時，將加註婉拒訊息。

## .env

請放在：`D:\github\1968_SMART_CHAT_BACK\.env`

OPENAI_API_KEY="你的 Key"
DB_HOST=...
DB_USER=...
DB_PASSWORD=...
DB_NAME=...
DB_PORT=3306

go
複製程式碼

> 啟動指令與 cert 參數已在 `process_pdf.py` 固定，依你的要求未改動。

建議的打包步驟

# 在專案根目錄

docker build -t 1968_smart_chatbot:v20251003-2 --no-cache .

# 存成 tar

docker save -o D:\github\1968_SMART_CHAT_BACK\1968_smart_chatbot_v20251003-2.tar 1968_smart_chatbot:v20251003-2

# 正式機

docker load -i D:\Project\1968_SMART_CHAT_BACK\1968_smart_chatbot_v20251003-2.tar
