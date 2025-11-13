# D:\github\1968_SMART_CHAT_BACK\core\intent_router.py
import os, json, asyncio
from typing import Tuple, Dict, Any
from dotenv import load_dotenv, find_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from prompts.all_zh import ROUTER_SYSTEM  # 不再使用別名，直接用 ROUTER_SYSTEM
from core.synonyms import router_hints, normalize_filters, load as load_synonyms

load_dotenv(find_dotenv(filename=".env", usecwd=True), override=False)

ROUTER_MODEL = os.getenv("ROUTER_MODEL", "gpt-4o-mini")
ROUTER_TIMEOUT_SEC = float(os.getenv("ROUTER_TIMEOUT_SEC", "2.5"))
_llm = None

ROUTER_SYSTEM = """
你是「台灣交通/氣象智能路由器」。請將使用者問題分類到其中一個 route，並同時抽取查詢參數 filters。
不得只依靠關鍵字；要能理解多種說法、口語、同義詞、縮寫。

可用 route：
- incidents（路況事件/施工/出口壅塞）
- alt_routes（替代道路/旅行時間）
- scs（開放路肩）
- parking（服務區停車位）
- weather（天氣/氣象）
- refuse（明確與交通/氣象無關）
- qa（沒有即時 API 的一般諮詢：最近交流道／服務區設施等）

filters 結構（不確定就留空字串）：
{
  "type": "事故|施工|出口壅塞|",
  "region": "north|center|south|pinglin|",
  "road": "國道1號|台64線|省道61號|",
  "direction": "南下|北上|東行|西行|順向|逆向|",
  "exit": "○○交流道|○○出口|",
  "parking_name": "○○服務區|",
  "place": "地名或地址（僅用於 weather）"
}

【分類補充規則】
- 「開放路肩/路肩開放/硬路肩/路肩是否開放」→ route = "scs"。
- 問「服務區停車/車位/剩餘」→ route = "parking"。
- 問「國道/台線在 A 到 B 的路況/施工/事故/出口壅塞」→ route = "incidents"，filters 填上 road / direction / exit / places。
- 問天氣/氣象 → route = "weather" 並在 filters.place 填地名。
- 問「最近的交流道、里程處最近交流道、附近休息站／服務區、服務區有哪些設施」→ route = "qa"（因沒有即時 API）。
- 僅在明確「非台灣或與交通/氣象無關」時才使用 route = "refuse"。

請輸出嚴格 JSON：
{
  "route": "incidents|alt_routes|scs|parking|weather|refuse|qa",
  "filters": {...},
  "reason": "10~30字中文簡述"
}
不要輸出多餘文字。
"""

def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is not None:
        return _llm
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 未設定")
    org = os.getenv("OPENAI_ORG_ID", "").strip() or None
    project = os.getenv("OPENAI_PROJECT", "").strip() or None
    mk = {}
    if project: mk["openai_project"] = project  # 正確位置：model_kwargs
    _llm = ChatOpenAI(
        model=ROUTER_MODEL,
        temperature=0,
        openai_api_key=api_key,
        openai_organization=org,
        model_kwargs=mk
    )
    return _llm

ALLOWED_ROUTES = {"incidents","alt_routes","scs","parking","weather","qa","refuse"}

async def route_question(question: str) -> Tuple[str, Dict[str, Any], str]:
    """(route, filters, reason)。不確定時一律回 incidents。"""
    async def _ask():
        load_synonyms()  # 檔案變更會自動重載
        msgs = [
            SystemMessage(content=ROUTER_SYSTEM),
            SystemMessage(content=router_hints()),
            HumanMessage(content=question[:1000]),
        ]
        llm = _get_llm()
        resp = await asyncio.get_running_loop().run_in_executor(None, lambda: llm.invoke(msgs))
        raw = (resp.content or "").strip()

        # ---- 解析嚴格 JSON，失敗就嘗試抓第一個 {...} 區段 ----
        try:
            data = json.loads(raw)
        except Exception:
            s, e = raw.find("{"), raw.rfind("}")
            if s != -1 and e != -1 and e > s:
                try:
                    data = json.loads(raw[s:e+1])
                except Exception:
                    data = {"route":"incidents","filters":{},"reason":"router_json_parse_failed"}
            else:
                data = {"route":"incidents","filters":{},"reason":"router_json_parse_failed"}

        # ---- 計算/補齊 confidence ----
        try:
            conf = float(data.get("confidence", 0.0))
        except Exception:
            conf = 0.0
        f = (data.get("filters") or {})
        rule = 0.0
        rule += 0.3 if f.get("road") else 0.0
        rule += 0.2 if f.get("direction") else 0.0
        rule += 0.2 if f.get("type") else 0.0
        rule += 0.2 if (f.get("exit") or f.get("places")) else 0.0
        data["confidence"] = max(conf, min(1.0, rule))
        return data

    try:
        data = await asyncio.wait_for(_ask(), timeout=ROUTER_TIMEOUT_SEC)
        route = (data.get("route") or "qa").strip()
        if route not in ALLOWED_ROUTES:
            route = "qa"

        # 只有「明確非台灣交通/天氣」才允許 refuse；否則強制 qa
        if route == "refuse":
            reason_l = (data.get("reason") or "").lower()
            if not any(k in reason_l for k in ["non-traffic","non-weather","outside-taiwan","out-of-scope"]):
                route = "qa"

        filters = normalize_filters(data.get("filters") or {})
        # 把 confidence 放到 filters，供外層取用
        filters["_confidence"] = float(data.get("confidence", 0.0))
        reason = (data.get("reason") or "").strip()
        return route, filters, reason

    except Exception as e:
        # 路由異常也採用 qa
        return "qa", {}, f"router_error:{type(e).__name__}"
