# D:\github\1968_SMART_CHAT_BACK\process_pdf.py
import os
import uuid
import traceback
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(filename=".env", usecwd=True), override=False)

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json, logging, asyncio, time, re
from functools import lru_cache
import requests
from datetime import datetime, timezone, timedelta

# === LangChain / OpenAI（新版匯入路徑） ===
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage

# === DB ===
import pymysql

# === 路由 / 服務 ===
from core.faq_gate import faq_gate
from services.faq_service import answer_from_docs
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

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("service.log", encoding="utf-8"),
        logging.StreamHandler()  # ← 這行會把 log 同步印到 console
    ]
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
    try:
        # dense（FAISS）
        try:
            # 新版 retriever 用 invoke；不支援就回退舊法
            docs_dense = retriever.invoke(question) if hasattr(retriever, "invoke") else retriever.get_relevant_documents(question)
        except Exception:
            docs_dense = []
        faiss_docs = (docs_dense or [])[:4]

        # sparse（BM25 可選）
        bm25_docs = []
        try:
            from langchain_community.retrievers import BM25Retriever
            bm25 = BM25Retriever.from_texts([d.page_content for d in vector_store.docstore._dict.values()])
            bm25.k = 4
            bm25_docs = bm25.get_relevant_documents(question)
        except Exception as e:
            logging.error(f"[RAG] BM25 略過：{type(e).__name__}: {e}")

        # union + 去重
        seen, docs = set(), []
        for arr in (faiss_docs, bm25_docs):
            for d in arr:
                key = (d.metadata.get("page"), d.page_content[:64])
                if key not in seen:
                    seen.add(key); docs.append(d)

        context = "\n\n".join([f"[第{d.metadata.get('page')}頁]\n{d.page_content}" for d in docs[:6]])
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
    if not ans:
        return True
    s = ans.strip()
    # ★ 放寬：短句但不含打槍詞，就當作有幫助（FAQ 常見）
    if len(s) < 50 and not _UNHELPFUL_PAT.search(s):
        return False
    return bool(_UNHELPFUL_PAT.search(s))

def qa_free_answer(question: str) -> str:
    msgs = [
        SystemMessage(content=(
            "你是台灣高速公路/交通資訊助理。"
            "對於『最近的交流道』『附近的休息站』『服務區有哪些設施』等沒有即時 API 的問題，"
            "請用常識與地理知識給出可行建議或查詢步驟，並告知需要的補充資訊（如國道號、方向、里程、服務區名稱）。"
            "回覆使用繁體中文、簡潔扼要；不確定的資訊需標示為建議或需查證。"
            "若判斷問題與台灣交通/氣象無關，請回覆："
            "「我主要協助台灣的交通/氣象查詢（國道路況、替代道路、服務區、天氣）。"
            "若問題不在這些範圍，可能無法完整回答；也歡迎告訴我要查的路段/交流道或地點，我會直接幫你查。」"
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

def _iso_ts_taipei() -> str:
    tz = timezone(timedelta(hours=8))
    s = datetime.now(tz).strftime("%Y-%m-%dT%H:%M%z")  # e.g., 2025-11-12T16:18+0800
    return f"{s[:-2]}:{s[-2:]}"  # → 2025-11-12T16:18+08:00

def add_disclaimer(ans: str) -> str:
    """在答案最後加上 Disclaimer（純文字，不含時間、不含 HTML 標籤）"""
    base = (ans or "").rstrip()

    # 如果本來字串裡就已經有 disclaimer 就不要重複加
    if ANSWER_DISCLAIMER in base:
        return base

    # 和主內容用換行隔開
    if base:
        return f"{base}\n{ANSWER_DISCLAIMER}"
    else:
        return ANSWER_DISCLAIMER

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
    r"(中山高|北二高|二高|一高|三高|北宜高|"
    r"國道?\s*[0-9０-９一二三四五六七八九十]+號?|"
    r"國?\s*[0-9０-９一二三四五六七八九十]|"
    r"台?\s*[0-9０-９一二三四五六七八九十]+線|"
    r"省道?\s*[0-9０-９一二三四五六七八九十]+號)",
    re.I
)

_DIR_PAT  = re.compile(
    r"(南下|北上|東行|西行|順向|逆向|往南|往北|往東|往西|南向|北向|東向|西向)"
)

_PARKING_PAT = re.compile(
    r"(?P<name>[\u4e00-\u9fa5]{2,8}?)(?:服務區)?"
    r"(?:的|目前|現在|還|是否|有沒有|有無|查|看)?"
    r"(?:.*?)(?:車位|停車|停車位|停車場|空位|剩餘|可用)",
    re.I
)

def _sanitize_sa_name(name: str) -> str:
    if not name:
        return ""
    n = re.sub(r"(服務區)?(的|目前|現在|還|是否|有沒有|有無)$", "", name.strip())
    n = n.replace("服務區", "")
    return n

# 將全形、中文數字轉成可辨識的國道/台線字串
def _normalize_digits(s: str) -> str:
    # 全形→半形
    s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    # 中文數字（常用到 1~10）
    s = (s.replace("一", "1").replace("二", "2").replace("三", "3")
           .replace("四", "4").replace("五", "5").replace("六", "6")
           .replace("七", "7").replace("八", "8").replace("九", "9")
           .replace("十", "10"))
    return s

def _normalize_road_name(expr: str) -> str:
    x = _normalize_digits(expr.replace(" ", ""))
    x = x.replace("臺", "台")

    # 先把可能黏在一起的方向字尾去掉（例：國一南下 → 國一）
    x = re.sub(r"(南下|北上|東行|西行|南向|北向|東向|西向|往南|往北|往東|往西)$", "", x)

    # 別名映射
    if "中山高" in x:
        return "國道1號"
    if "北二高" in x or x == "二高":
        return "國道3號"
    if "一高" in x:
        return "國道1號"
    if "三高" in x:
        return "國道3號"
    if "北宜高" in x:
        return "國道5號"

    # 統一常見縮寫：國1→國道1號、國3→國道3號（中文數字已轉成阿拉伯數字）
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
    if m:
        raw = (m.group("name") or "").strip()
        base = _sanitize_sa_name(raw)
        if base:
            pname = base + "服務區"
            new_filters = dict(filters or {})
            new_filters.setdefault("parking_name", pname)
            # 若原本 route 不是 parking，就強制改成 parking
            if route != "parking":
                return "parking", new_filters, "fallback_parking"
            else:
                return route, new_filters, "fallback_parking_enhance"

    # weather：看到「天氣/氣象」→ 導 weather
    if ("天氣" in x or "氣象" in x):
        place = re.sub(r"(現在|目前|的|天氣|氣象|如何|狀況|\?|？)", "", x).strip() or x
        new_filters = dict(filters or {})
        new_filters.setdefault("place", place)
        if route != "weather":
            return "weather", new_filters, "fallback_weather"
        else:
            return route, new_filters, "fallback_weather_enhance"

    # incidents：道路 + 路況關鍵詞 → 導 incidents 並補 road/type/direction
    if _ROAD_PAT.search(x) and re.search(r"(路況|施工|事故|封閉|壅塞|回堵)", x):
        raw = _ROAD_PAT.search(x).group(1)
        road = _normalize_road_name(raw)

        # 類型判斷
        itype = None
        if any(k in x for k in ["施工", "養護", "封閉"]):
            itype = "construction"
        elif any(k in x for k in ["事故", "車禍", "擦撞", "追撞", "翻覆"]):
            itype = "accident"
        elif any(k in x for k in ["壅塞", "回堵", "出口", "交流道"]):
            itype = "exit_congestion"

        # 方向判斷：把「往南 / 南向」都規一成「南下」之類
        dire = None
        mdir = _DIR_PAT.search(x)
        if mdir:
            raw_dir = mdir.group(1)
            if raw_dir in ("南下", "往南", "南向"):
                dire = "南下"
            elif raw_dir in ("北上", "往北", "北向"):
                dire = "北上"
            elif raw_dir in ("東行", "往東", "東向"):
                dire = "東行"
            elif raw_dir in ("西行", "往西", "西向"):
                dire = "西行"
            elif raw_dir in ("順向", "逆向"):
                dire = raw_dir

        new_filters = dict(filters or {})
        new_filters.setdefault("road", road)
        if itype and "type" not in new_filters:
            new_filters["type"] = itype
        if dire and "direction" not in new_filters:
            new_filters["direction"] = dire

        # 如果原本不是 incidents → 強制導到 incidents
        if route != "incidents":
            return "incidents", new_filters, "fallback_incidents"
        else:
            # 原本就是 incidents，只是幫忙補 road/direction/type
            return "incidents", new_filters, "fallback_incidents_enhance"

    # 沒命中任何保險規則 → 不動
    return route, filters, ""

def _db_ready(cfg: dict) -> bool:
    return all([
        cfg.get("host", "").strip() not in ("", "..."),
        cfg.get("user", "").strip() not in ("", "..."),
        cfg.get("password", "").strip() not in ("", "..."),
        cfg.get("database", "").strip() not in ("", "...")
    ])

def _latin1_safe(s: str, placeholder: str = "?") -> str:
    try:
        return (s or "").encode("latin-1", "replace").decode("latin-1")
    except Exception:
        return placeholder

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
    req_id = uuid.uuid4().hex[:8]  # ★ Request Trace ID
    q = (input.question or "").strip()
    user_ip = request.client.host
    user_agent = request.headers.get("user-agent", "未知")

    def ms_since(t0):  # 小工具：回傳經過毫秒
        return int((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    # logging.info(f"[{req_id}] === 新請求 ===")
    # logging.info(f"[{req_id}] 問題: {q}")
    # logging.info(f"[{req_id}] 來源: ip={user_ip} ua={user_agent}")

    answer = ""
    route = "incidents"
    filters: dict = {}
    reason = ""
    forced_qa = False
    fallback_reason = ""
    sources_used = []
    confidence = 0.0

    try:
        # 1) 唯一路由：LLM（先判斷要走哪種 API / QA）
        route, filters, reason = await route_question(q)
        confidence = float(filters.pop("_confidence", 0)) if "_confidence" in filters else 0.0
        logging.debug(f"[{req_id}] Router 結果 route={route} conf={confidence:.2f} filters={filters} reason={reason}")

        # 1.1) 強制 QA（最近交流道/休息站/服務區設施等）：
        #      → 只有這種“沒有即時 API”的問題才改成 QA
        if _should_force_qa(q, route, filters):
            logging.debug(f"[{req_id}] 觸發強制 QA（forced_qa）")
            route, filters, reason = "qa", {}, f"{reason}|forced_qa"
            forced_qa = True

        # 1.2) 後置保險路由（parking / incidents / weather 補救）
        route, filters, fb = _fallback_route(q, route, filters)
        if fb:
            logging.debug(f"[{req_id}] 後置保險路由觸發：{fb} → 新 route={route}, filters={filters}")
            fallback_reason = fb

        # 2) 執行主流程（以 SLA 限時）
        async def _do_main_route():
            nonlocal answer, route, filters, sources_used
            logging.debug(f"[{req_id}] 執行分支 route={route} filters={filters}")

            try:
                # 不允許硬拒絕 → 全部改走 QA/RAG
                if (route == "refuse") and (not REFUSAL_ENABLED):
                    logging.debug(f"[{req_id}] route=refuse 且 REFUSAL_DISABLED → 改走 qa")
                    route = "qa"
                    filters = {}

                # ========= 這裡開始：各種 API 優先 =========
                if route == "incidents":
                    res = await asyncio.get_running_loop().run_in_executor(
                        None, lambda: query_incidents_by_filters(filters, limit=5)
                    )
                    summary = (res or {}).get("summary") or "目前查無符合條件的事件。"
                    answer = add_disclaimer(f"{INCIDENTS_PREFIX}\n{summary}")
                    sources_used = [{"api": "incidents", "ts": time.time()}]
                    return

                elif route == "alt_routes":
                    summary = await asyncio.get_running_loop().run_in_executor(None, summarize_alt_routes)
                    answer = add_disclaimer(f"{ALT_ROUTES_PREFIX}\n{summary}")
                    sources_used = [{"api": "alt_routes", "ts": time.time()}]
                    return

                elif route == "scs":
                    summary = await asyncio.get_running_loop().run_in_executor(None, summarize_scs)
                    answer = add_disclaimer(f"{SCS_PREFIX}\n{summary}")
                    sources_used = [{"api": "scs", "ts": time.time()}]
                    return

                elif route == "parking":
                    # ★ 服務區停車位：一定優先走 API
                    kw = (filters.get("parking_name") or "").strip()
                    if not kw:
                        answer = add_disclaimer("請提供要查詢的服務區名稱（例如：關西服務區）。")
                        sources_used = []
                        return
                    summary = await asyncio.get_running_loop().run_in_executor(
                        None, lambda: summarize_parking(keyword=kw, limit=8)
                    )
                    answer = add_disclaimer(f"{PARKING_PREFIX}\n{summary}")
                    sources_used = [{"api": "parking", "ts": time.time(), "kw": kw}]
                    return

                elif route == "weather":
                    # 天氣 → Open-Meteo API（不是 PDF）
                    place = (filters.get("place") or "").strip() or q
                    coord = await asyncio.get_running_loop().run_in_executor(None, geocode, place)
                    if coord:
                        lat, lon, label, _ = coord
                        display_name = _only_city_name(label, place)
                        weather = await asyncio.get_running_loop().run_in_executor(None, openmeteo_current, lat, lon)
                        if weather:
                            ans = (
                                f"「{display_name}」目前："
                                f"{weather.get('temp_c', '—')}°C、"
                                f"降雨 {weather.get('rain_mm', 0)} mm、"
                                f"風速 {weather.get('wind_ms', '—')} m/s"
                            )
                        else:
                            ans = "目前無法取得該地即時天氣。"
                        answer = add_disclaimer(f"{WEATHER_PREFIX}{ans}")
                        sources_used = [{"api": "open-meteo", "lat": lat, "lon": lon, "ts": time.time()}]
                    else:
                        answer = add_disclaimer("無法辨識天氣查詢地點，請提供更明確的地名或地址。")
                        sources_used = []
                    return

                # ========= QA 類：這裡才會用到 PDF / RAG =========
                elif route == "qa":
                    # 2.1) 先查 1968_QA.pdf（FAQ）；只在 QA 類問題時才啟用
                    hit, hit_score, top_docs = faq_gate(q)
                    logging.debug(f"[{req_id}] FAQ Gate (QA) hit={hit} score={hit_score:.2f} top_docs={len(top_docs)}")

                    if hit:
                        # PDF 優先於 RAG/自由 QA
                        if top_docs:
                            pack = await asyncio.get_running_loop().run_in_executor(None, answer_from_docs, q, top_docs)
                            answer = add_disclaimer(pack["text"])
                            sources_used = pack.get("sources", [])
                        else:
                            # 僅規則命中時的保守答覆，可視情況調整
                            answer_text = "可於 1968 APP 的「管制措施」或首頁公告查詢相關資訊。"
                            answer = add_disclaimer(answer_text)
                            sources_used = [{"faq": "rule"}]
                        return

                    # 2.2) FAQ 沒中 → 再走 RAG + 自由 QA
                    rag_ans = rag_answer(q)
                    if rag_ans and not _rag_is_unhelpful(rag_ans):
                        answer = add_disclaimer(rag_ans.strip())
                        sources_used = [{"rag": "general"}]
                    else:
                        free = qa_free_answer(q)
                        if free:
                            answer = add_disclaimer(free)
                            sources_used = [{"qa": "free"}]
                        else:
                            answer = add_disclaimer(
                                "目前無法直接從資料中查到精準答案；"
                                "你可以補充國道號、方向與里程或服務區名稱，我再幫你查。"
                            )
                            sources_used = []
                    return

                else:
                    # 其它不預期的 route：保險 → RAG + 軟性說明
                    rag_ans = rag_answer(q)
                    if rag_ans and not _rag_is_unhelpful(rag_ans):
                        answer = add_disclaimer(rag_ans.strip())
                        sources_used = [{"rag": "refuse"}]
                    else:
                        answer = add_disclaimer(SOFT_REFUSAL)
                        sources_used = []
                    return

            except Exception:
                logging.error(f"[{req_id}] 分支執行錯誤 route={route}\n{traceback.format_exc()}")
                raise

        remain = max(0.1, SLA_SEC - (time.perf_counter() - t0) - 0.2)
        logging.debug(f"[{req_id}] SLA remain≈{remain:.2f}s")

        # 這裡不再做 parallel_faq，單純跑主路由邏輯
        await asyncio.wait_for(_do_main_route(), timeout=remain)

        # === API / QA 流程跑完，都會到這裡來 ===
        if not answer:
            logging.warning(f"[{req_id}] 無答案→回軟性說明")
            answer = add_disclaimer(SOFT_REFUSAL)

        # 3) 寫 DB（不中斷）
        try:
            DB_CONFIG = {
                "host": os.getenv("DB_HOST", "").strip(),
                "user": os.getenv("DB_USER", "").strip(),
                "password": os.getenv("DB_PASSWORD", "").strip(),
                "database": os.getenv("DB_NAME", "").strip(),
                "port": int(os.getenv("DB_PORT", 3306)),
                "charset": "utf8mb4"
            }
            if _db_ready(DB_CONFIG):
                conn = pymysql.connect(**DB_CONFIG)
                with conn.cursor() as cursor:
                    sql = "INSERT INTO chat_history (ip_address, device_info, sender, message, created_at) VALUES (%s,%s,%s,%s,%s)"
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute(sql, (user_ip, user_agent, "user", q[:1000], now))
                    cursor.execute(sql, (user_ip, user_agent, "bot", (answer[:1000] if answer else "[NO_ANSWER]"), now))
                conn.commit()
                conn.close()
            else:
                logging.debug(f"[{req_id}] 跳過寫DB（未配置）")
        except Exception:
            logging.error(f"[{req_id}] 寫 DB 失敗\n{traceback.format_exc()}")

        # ===== 回傳除錯資訊（F12 可見）=====
        timings_ms = ms_since(t0)
        debug = {
            "route": route,
            "filters": filters,
            "reason": reason,
            "forced_qa": forced_qa,
            "fallback": fallback_reason,
            "timings_ms": timings_ms,
            "confidence": round(confidence, 2),
            "sources": sources_used,
            "req_id": req_id,
        }
        # logging.info(f"[{req_id}] 完成 in {timings_ms} ms | route={route} conf={confidence:.2f} | sources={sources_used}")

        # Response Headers（含 Trace ID）
        try:
            response.headers["X-Route"] = _latin1_safe(route)
            response.headers["X-Filters"] = _latin1_safe(json.dumps(filters, ensure_ascii=False))
            response.headers["X-Reason"] = _latin1_safe(reason)
            response.headers["X-Forced-QA"] = "true" if forced_qa else "false"
            response.headers["X-Fallback"] = _latin1_safe(fallback_reason or "")
            response.headers["X-Timings-ms"] = str(timings_ms)
            response.headers["X-Confidence"] = f"{confidence:.2f}"
            response.headers["X-Trace-Id"] = req_id
        except Exception:
            logging.error(f"[{req_id}] 設定回應標頭失敗\n{traceback.format_exc()}")

        return {"answer": answer, "route": route, "filters": filters, "reason": reason, "debug": debug}

    except asyncio.TimeoutError:
        logging.error(f"[{req_id}] 全域逾時（SLA={SLA_SEC}s）")
        return {
            "answer": add_disclaimer("系統繁忙，請稍後再試。"),
            "debug": {"error": "timeout", "req_id": req_id}
        }
    except Exception:
        logging.error(f"[{req_id}] 全域例外\n{traceback.format_exc()}")
        return {
            "answer": add_disclaimer("查詢失敗，請稍後再試。"),
            "debug": {"error": "exception", "req_id": req_id}
        }

@app.get("/health")
def health():
    import time
    ok_key = bool(os.getenv("OPENAI_API_KEY", "").strip())
    key_mask = (os.getenv("OPENAI_API_KEY","").strip()[:7] + "…") if ok_key else ""
    faq_idx = os.path.exists(os.path.join(os.getenv("FAQ_INDEX_DIR", os.path.join("faiss_index","faq_1968")), "index.faiss"))
    faq_json = os.path.exists(os.getenv("FAQ_JSON_PATH", os.path.join("PDF","1968_QA.json")))
    return {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "openai_key_present": ok_key,
        "openai_key_mask": key_mask,
        "faq_index_exists": faq_idx,
        "faq_json_exists": faq_json
    }

# =============================================================================
# 啟動
# =============================================================================
if __name__ == "__main__":
    uvicorn.run(
        app, host="0.0.0.0", port=8108,
        ssl_certfile="/app/IIS/59.126.242.4.pem",
        ssl_keyfile="/app/IIS/59.126.242.4.key"
    )
