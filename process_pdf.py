# D:\github\1968_SMART_CHAT_BACK\process_pdf.py
import os
from dotenv import load_dotenv, find_dotenv
# 先載 .env（override=False：保留環境上既有設定）
load_dotenv(find_dotenv(filename=".env", usecwd=True), override=False)

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json, logging, asyncio, time, re
from datetime import datetime
from functools import lru_cache
import requests

# === LangChain / OpenAI（向量檢索 + 直接 LLM） ===
from langchain_openai.chat_models import ChatOpenAI
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.schema import Document, SystemMessage, HumanMessage

# === DB ===
import pymysql

# === 路由 / 服務 ===
from core.intent_router import route_question
from core.geocoding import geocode
from core.config import SLA_SEC
from services.incidents_service import query_incidents_by_filters
from services.alt_routes_service import summarize_alt_routes
from services.shoulder_service import summarize_scs
from services.parking_service import summarize_parking

# === Prompts / 標題（不使用 QA_PREFIX，避免出現 📘 前綴） ===
from prompts.all_zh import (
    ANSWER_DISCLAIMER,
    INCIDENTS_PREFIX, ALT_ROUTES_PREFIX, SCS_PREFIX, PARKING_PREFIX, WEATHER_PREFIX,
    SOFT_REFUSAL,
)

REFUSAL_ENABLED = (os.getenv("REFUSAL_ENABLED", "false").lower() == "true")

# =============================================================================
# FastAPI
# =============================================================================
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
    # 讓前端 F12 → Network → Headers 看得到這些欄位
    expose_headers=["X-Route","X-Filters","X-Reason","X-Forced-QA","X-Fallback","X-Timings-ms"],
)

logging.basicConfig(
    filename="service.log", level=logging.INFO,
    format="%(asctime)s - %(message)s", encoding="utf-8"
)

# =============================================================================
# 向量庫（PDF 兜底用）
# =============================================================================
PDF_JSON_PATH = os.getenv("PDF_JSON_PATH", os.path.join(os.getcwd(), "PDF", "all_text.json"))

embeddings = OpenAIEmbeddings()
rag_llm = ChatOpenAI(model=os.getenv("RAG_MODEL", "gpt-4o-mini"), temperature=0)
qa_llm  = ChatOpenAI(model=os.getenv("QA_MODEL",  "gpt-4o-mini"), temperature=0)

text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)

def build_vector_from_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        pages = json.load(f)
    documents = []
    for idx, page_text in enumerate(pages):
        if not page_text:
            continue
        chunks = text_splitter.split_text(page_text)
        for chunk in chunks:
            documents.append(Document(page_content=chunk, metadata={"page": idx + 1}))
    return FAISS.from_documents(documents, embeddings)

FAISS_INDEX_DIR = "faiss_index"
FAISS_INDEX_FILE = os.path.join(FAISS_INDEX_DIR, "index.faiss")
if os.path.exists(FAISS_INDEX_FILE):
    vector_store = FAISS.load_local(FAISS_INDEX_DIR, embeddings, allow_dangerous_deserialization=True)
else:
    vector_store = build_vector_from_json(PDF_JSON_PATH)
    vector_store.save_local(FAISS_INDEX_DIR)

retriever = vector_store.as_retriever(search_type="mmr", search_kwargs={"k": 5, "lambda_mult": 0.3})

# —— RAG：中立版 Prompt（不包含任何婉拒指示）——
RAG_PROMPT_NEUTRAL = (
    "請只根據以下內容回答，回覆必須使用繁體中文。"
    "若無法在內容中直接找到答案，請簡短提供可行的查詢方向或需要補充的資訊，不要婉拒。\n"
    "【內容】\n{context}\n\n【問題】\n{question}"
)

def rag_answer(question: str) -> str:
    """自取向量庫內容 + 中立 prompt 丟給 LLM。"""
    try:
        docs = retriever.get_relevant_documents(question) or []
        context = "\n\n".join([d.page_content for d in docs]) if docs else ""
        prompt_text = RAG_PROMPT_NEUTRAL.format(context=context, question=question)
        resp = rag_llm.invoke([HumanMessage(content=prompt_text)])
        return (resp.content or "").strip()
    except Exception as e:
        logging.error(f"[RAG] {type(e).__name__}: {e}")
        return ""

# —— 偵測「RAG 回覆無幫助」：太短或常見打槍/指引句型，就視為無幫助 —— 
_UNHELPFUL_PAT = re.compile(
    r"(無法.*查詢|找不到|無法直接|資料不足|未提供|沒有提供|無相關資料|"
    r"請.*使用.*APP|建議.*查詢|請.*至.*官方網站|僅供參考)",
    re.I
)
def _rag_is_unhelpful(ans: str) -> bool:
    if not ans or len(ans.strip()) < 30:
        return True
    return bool(_UNHELPFUL_PAT.search(ans))

def qa_free_answer(question: str) -> str:
    """沒有 API 的一般問答（例如最近交流道/休息站/服務區設施）。"""
    msgs = [
        SystemMessage(content=(
            "你是台灣高速公路/交通資訊助理。"
            "對於『最近的交流道』『附近的休息站』『服務區有哪些設施』等沒有即時 API 的問題，"
            "請用常識與地理知識給出可行建議或查詢步驟，並告知需要的補充資訊（如國道號、方向、里程、服務區名稱）。"
            "回覆使用繁體中文、簡潔扼要；不確定的資訊需標示為建議或需查證。"
        )),
        HumanMessage(content=question[:1000])
    ]
    try:
        resp = qa_llm.invoke(msgs)
        return (resp.content or "").strip()
    except Exception as e:
        logging.error(f"[QA_FREE] {type(e).__name__}: {e}")
        return ""

# =============================================================================
# 共用：即時天氣（Open-Meteo）
# =============================================================================
@lru_cache(maxsize=256)
def openmeteo_current(lat, lon):
    try:
        js = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": round(float(lat), 2),
                "longitude": round(float(lon), 2),
                "current": "temperature_2m,precipitation,weather_code,wind_speed_10m",
                "timezone": "Asia/Taipei",
            },
            timeout=6
        ).json()
        cur = js.get("current", {})
        return {
            "temp_c": cur.get("temperature_2m"),
            "wind_ms": cur.get("wind_speed_10m"),
            "rain_mm": cur.get("precipitation", 0),
        }
    except Exception:
        return {}

def add_disclaimer(ans: str) -> str:
    if not ans:
        return ANSWER_DISCLAIMER
    if ANSWER_DISCLAIMER in ans:
        return ans
    sep = "\n" if ans.endswith(("。", "！", "!", "？」", "？")) else "\n\n"
    return f"{ans}{sep}{ANSWER_DISCLAIMER}"

# —— 只顯示台灣縣市名稱用的工具 ——
_TW_CITY_LIST = [
    "台北市","臺北市","新北市","桃園市","台中市","臺中市","台南市","臺南市","高雄市",
    "基隆市","新竹市","嘉義市",
    "新竹縣","苗栗縣","彰化縣","南投縣","雲林縣","嘉義縣","屏東縣",
    "宜蘭縣","花蓮縣","台東縣","臺東縣","澎湖縣","金門縣","連江縣"
]
_CITY_REGEX = re.compile(r"([^\d\s]{1,6}[市縣])")  # 找第一個以 市/縣 結尾的片段

def _only_city_name(label: str, fallback_text: str = "") -> str:
    """從 geocode 的 label 抓出縣市名；取不到就用備援字串；統一『臺』為『台』。"""
    x = (label or "") + " " + (fallback_text or "")
    for n in _TW_CITY_LIST:
        if n in x:
            return n.replace("臺", "台")
    m = _CITY_REGEX.search(x)
    if m:
        return m.group(1).replace("臺", "台")
    x = (fallback_text or label or "").replace("臺", "台")
    m2 = _CITY_REGEX.search(x)
    return (m2.group(1) if m2 else x)

# =============================================================================
# 強制 QA（沒有 API 的需求）
# =============================================================================
_QA_HINT = re.compile(
    r"(服務區|休息站|設施|廁所|餐廳|餐飲|加油|充電|超商|哺乳室|"
    r"最近的?交流道|最近交流道|附近交流道|公里處|里程處|幾K)",
    re.I
)

def _should_force_qa(q: str, route: str, filters: dict) -> bool:
    if route == "qa":
        return False
    x = q or ""
    if _QA_HINT.search(x):
        # 若被判到 incidents 但條件幾乎空，視為誤判 → 改 QA
        if route == "incidents":
            sig = any([
                (filters.get("road")), (filters.get("direction")),
                (filters.get("exit")), (filters.get("places"))
            ])
            return not sig
        return True
    # 包含「服務區」但不是問停車/車位 → QA
    if ("服務區" in x) and not any(k in x for k in ["停車", "車位"]):
        return True
    return False

# =============================================================================
# 後置保險路由（關鍵字極簡補救：保證 parking / incidents / weather 能命中）
# =============================================================================
_ROAD_PAT = re.compile(
    r"(中山高|北二高|二高|"
    r"國道?\s*[0-9０-９一二三四五六七八九十]+號?|"
    r"國?\s*[0-9０-９一二三四五六七八九十]|"
    r"台?\s*[0-9０-９一二三四五六七八九十]+線|"
    r"省道?\s*[0-9０-９一二三四五六七八九十]+號)",
    re.I
)
_DIR_PAT  = re.compile(r"(南下|北上|東行|西行|順向|逆向)")
_PARKING_PAT = re.compile(r"(?P<name>[\u4e00-\u9fa5]{2,6})(?:服務區)?(?:.*?)(車位|停車|停車位|空位|剩餘|可用)")

# 將全形、中文數字轉成可辨識的國道/台線字串
def _normalize_digits(s: str) -> str:
    # 全形→半形
    s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    # 中文數字（常用到 1~10）
    s = (s.replace("一", "1").replace("二", "2").replace("三", "3")
           .replace("四","4").replace("五","5").replace("六","6")
           .replace("七","7").replace("八","8").replace("九","9")
           .replace("十","10"))
    return s

def _normalize_road_name(expr: str) -> str:
    x = _normalize_digits(expr.replace(" ", ""))
    x = x.replace("臺", "台")
    # 別名映射
    if "中山高" in x:
        return "國道1號"
    if "北二高" in x or x == "二高":
        return "國道3號"
    # 統一常見縮寫：國1→國道1號、國3→國道3號
    m = re.search(r"^國?道?(\d{1,2})號?$", x)
    if m:
        return f"國道{m.group(1)}號"
    # 台線/省道保持原樣（ex：台74線）
    m2 = re.search(r"^(台|省道)(\d{1,3})(號|線)?$", x)
    if m2:
        prefix = "台" if m2.group(1).startswith("台") else "省道"
        suf = "線" if (m2.group(3) or "") == "線" else "號"
        return f"{prefix}{m2.group(2)}{suf}"
    return expr  # 萬一抓不準，就原樣回傳

def _fallback_route(q: str, route: str, filters: dict):
    x = q or ""

    # parking：命中「OO服務區 + 車位/停車/空位…」→ 直接導到 parking
    m = _PARKING_PAT.search(x)
    if route not in ("parking",) and m:
        name = (m.group("name") or "").strip()
        if name:
            pname = name if name.endswith("服務區") else (name + "服務區")
            return "parking", {"parking_name": pname}, "fallback_parking"

    # weather：看到「天氣/氣象」→ 導 weather，地點就用整句（下游會 geocode）
    if route not in ("weather",) and ("天氣" in x or "氣象" in x):
        place = re.sub(r"(現在|目前|的|天氣|氣象|如何|狀況|\?|？)", "", x).strip() or x
        return "weather", {"place": place}, "fallback_weather"

    # incidents：同時看見道路與路況關鍵詞 → 導 incidents 並補 road/type/direction
        # incidents：同時看見道路與路況關鍵詞 → 導 incidents 並補 road/type/direction
    if route not in ("incidents",) and _ROAD_PAT.search(x) and re.search(r"(路況|施工|事故|封閉|壅塞|回堵)", x):
        raw = _ROAD_PAT.search(x).group(1)
        road = _normalize_road_name(raw)  # ★ 改這行：統一路名
        itype = None
        if "施工" in x or "養護" in x or "封閉" in x:
            itype = "construction"
        elif "事故" in x or "車禍" in x or "擦撞" in x or "追撞" in x or "翻覆" in x:
            itype = "accident"
        elif "壅塞" in x or "回堵" in x or "出口" in x or "交流道" in x:
            itype = "exit_congestion"
        dire = _DIR_PAT.search(x).group(1) if _DIR_PAT.search(x) else None
        f = {"road": road}
        if itype: f["type"] = itype
        if dire:  f["direction"] = dire
        return "incidents", f, "fallback_incidents"

    return route, filters, ""

# =============================================================================
# API
# =============================================================================
class QueryInput(BaseModel):
    question: str

@app.get("/")
async def root():
    return {"message": "1968 智能客服 API（LLM 路由 + RAG/QA 兜底）"}

@app.post("/chatback/query/")
async def query_pdf(input: QueryInput, request: Request, response: Response):
    q = (input.question or "").strip()
    user_ip = request.client.host
    user_agent = request.headers.get("user-agent", "未知")

    logging.info("=" * 50)
    logging.info(f"問題：{q}")
    logging.info(f"IP：{user_ip}")
    logging.info(f"裝置：{user_agent}")

    answer = ""
    t0 = time.perf_counter()
    route = "incidents"
    filters = {}
    reason = ""
    forced_qa = False
    fallback_reason = ""

    try:
        # 1) 唯一路由：LLM
        route, filters, reason = await route_question(q)

        # 1.1) 強制 QA（最近交流道/休息站/服務區設施等）
        if _should_force_qa(q, route, filters):
            route, filters, reason = "qa", {}, f"{reason}|forced_qa"
            forced_qa = True

        # 1.2) 後置保險路由（確保 parking / incidents / weather 能命中）
        route, filters, fb = _fallback_route(q, route, filters)
        if fb:
            fallback_reason = fb

        # 2) 依 route 執行；以 SLA 限時守門
        async def _do():
            nonlocal answer, route, filters

            # 若不啟用硬性婉拒，將 refuse 改走 QA（避免硬拒）
            if (route == "refuse") and (not REFUSAL_ENABLED):
                route = "qa"
                filters = {}

            if route == "incidents":
                res = await asyncio.get_running_loop().run_in_executor(
                    None, lambda: query_incidents_by_filters(filters, limit=5)
                )
                summary = (res or {}).get("summary") or "目前查無符合條件的事件。"
                answer = add_disclaimer(f"{INCIDENTS_PREFIX}\n{summary}")

            elif route == "alt_routes":
                summary = await asyncio.get_running_loop().run_in_executor(None, summarize_alt_routes)
                answer = add_disclaimer(f"{ALT_ROUTES_PREFIX}\n{summary}")

            elif route == "scs":
                summary = await asyncio.get_running_loop().run_in_executor(None, summarize_scs)
                answer = add_disclaimer(f"{SCS_PREFIX}\n{summary}")

            elif route == "parking":
                kw = (filters.get("parking_name") or "").strip()
                if not kw:
                    answer = add_disclaimer("請提供要查詢的服務區名稱（例如：關西服務區）。")
                    return
                summary = await asyncio.get_running_loop().run_in_executor(
                    None, lambda: summarize_parking(keyword=kw, limit=8)
                )
                answer = add_disclaimer(f"{PARKING_PREFIX}\n{summary}")

            elif route == "weather":
                place = (filters.get("place") or "").strip()
                if not place:
                    place = q
                coord = await asyncio.get_running_loop().run_in_executor(None, geocode, place)
                if coord:
                    lat, lon, label, _ = coord
                    display_name = _only_city_name(label, place)  # ★ 只取縣市名
                    weather = await asyncio.get_running_loop().run_in_executor(None, openmeteo_current, lat, lon)
                    if weather:
                        ans = f"「{display_name}」目前：{weather.get('temp_c','—')}°C、降雨 {weather.get('rain_mm',0)} mm、風速 {weather.get('wind_ms','—')} m/s"
                    else:
                        ans = "目前無法取得該地即時天氣。"
                    answer = add_disclaimer(f"{WEATHER_PREFIX}{ans}")
                else:
                    answer = add_disclaimer("無法辨識天氣查詢地點，請提供更明確的地名或地址。")

            elif route == "qa":
                # 先試 RAG（PDF / 系統 QA）
                rag_ans = rag_answer(q)
                # RAG 有料且不是打槍/無幫助 → 用 RAG；否則 → free QA
                if rag_ans and not _rag_is_unhelpful(rag_ans):
                    answer = add_disclaimer(rag_ans.strip())
                else:
                    free = qa_free_answer(q)
                    if free:
                        answer = add_disclaimer(free)
                    else:
                        answer = add_disclaimer(
                            "目前無法直接從資料中查到精準答案；"
                            "你可以補充國道號、方向與里程或服務區名稱，我再幫你查。"
                        )

            else:  # refuse（只有在 REFUSAL_ENABLED=true 時才可能走到）
                # 先試 RAG（中立提示），若無幫助則用軟性說法
                rag_ans = rag_answer(q)
                if rag_ans and not _rag_is_unhelpful(rag_ans):
                    answer = add_disclaimer(rag_ans.strip())
                else:
                    answer = add_disclaimer(SOFT_REFUSAL)

        # SLA 守門（預留 200ms 緩衝）
        remain = max(0.1, SLA_SEC - (time.perf_counter() - t0) - 0.2)
        await asyncio.wait_for(_do(), timeout=remain)

        # 若極端情況仍是空字串，補一個友善訊息（避免前端出現「找不到答案」）
        if not answer:
            answer = add_disclaimer(SOFT_REFUSAL)

        # 3) 寫 DB（不中斷）
        try:
            DB_CONFIG = {
                "host": os.getenv("DB_HOST"),
                "user": os.getenv("DB_USER"),
                "password": os.getenv("DB_PASSWORD"),
                "database": os.getenv("DB_NAME"),
                "port": int(os.getenv("DB_PORT", 3306)),
                "charset": "utf8mb4"
            }
            if DB_CONFIG["host"]:
                conn = pymysql.connect(**DB_CONFIG)
                with conn.cursor() as cursor:
                    sql = "INSERT INTO chat_history (ip_address, device_info, sender, message, created_at) VALUES (%s,%s,%s,%s,%s)"
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute(sql, (user_ip, user_agent, "user", q[:1000], now))
                    cursor.execute(sql, (user_ip, user_agent, "bot", (answer[:1000] if answer else "[NO_ANSWER]"), now))
                conn.commit(); conn.close()
        except Exception as db_err:
            logging.error(f"[❌] 寫入資料庫失敗：{db_err}")

        # ===== 回傳除錯資訊（F12 可見）=====
        timings_ms = int((time.perf_counter() - t0) * 1000)
        debug = {
            "route": route,
            "filters": filters,
            "reason": reason,
            "forced_qa": forced_qa,
            "fallback": fallback_reason,
            "timings_ms": timings_ms,
        }
        logging.info(f"[router] {json.dumps(debug, ensure_ascii=False)}")

        # 設定可在 F12→Network 的 Response Headers 直接看到
        try:
            response.headers["X-Route"] = route
            response.headers["X-Filters"] = json.dumps(filters, ensure_ascii=False)
            response.headers["X-Reason"] = reason
            response.headers["X-Forced-QA"] = "true" if forced_qa else "false"
            response.headers["X-Fallback"] = fallback_reason or ""
            response.headers["X-Timings-ms"] = str(timings_ms)
        except Exception:
            pass

        return {
            "answer": answer,
            "route": route,
            "filters": filters,
            "reason": reason,
            "debug": debug
        }

    except asyncio.TimeoutError:
        return {"answer": add_disclaimer("系統繁忙，請稍後再試。"),
                "debug": {"error": "timeout"}}
    except Exception as e:
        logging.error(f"查詢錯誤：{e}")
        return {"answer": add_disclaimer("查詢失敗，請稍後再試。"),
                "debug": {"error": str(e)}}

# =============================================================================
# 啟動
# =============================================================================
if __name__ == "__main__":
    uvicorn.run(
        app, host="0.0.0.0", port=8108,
        ssl_certfile="/app/IIS/59.126.242.4.pem",
        ssl_keyfile="/app/IIS/59.126.242.4.key"
    )
