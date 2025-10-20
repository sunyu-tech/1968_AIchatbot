# D:\github\1968_SMART_CHAT_BACK\core\intent_router.py
import os, json, asyncio
from typing import Tuple, Dict, Any
from dotenv import load_dotenv, find_dotenv
from langchain_openai.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from prompts.all_zh import ROUTER_SYSTEM
from core.synonyms import router_hints, normalize_filters, load as load_synonyms

load_dotenv(find_dotenv(filename=".env", usecwd=True), override=False)

ROUTER_MODEL = os.getenv("ROUTER_MODEL", "gpt-4o-mini")
ROUTER_TIMEOUT_SEC = float(os.getenv("ROUTER_TIMEOUT_SEC", "2.5"))
_llm = None
def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is not None:
        return _llm
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 未設定；請在 .env 放入 OPENAI_API_KEY=xxxx")
    _llm = ChatOpenAI(model=ROUTER_MODEL, temperature=0, openai_api_key=api_key)
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
        try:
            data = json.loads(raw)
        except Exception:
            s, e = raw.find("{"), raw.rfind("}")
            data = json.loads(raw[s:e+1]) if (s != -1 and e != -1) else {"route":"incidents","filters":{},"reason":"router_json_parse_failed"}
        return data

    try:
        data = await asyncio.wait_for(_ask(), timeout=ROUTER_TIMEOUT_SEC)
        route = (data.get("route") or "qa").strip()
        if route not in ALLOWED_ROUTES:
            route = "qa"
        # 只有「明確非台灣交通/天氣」才允許 refuse；否則強制 qa
        if route == "refuse":
            reason = (data.get("reason") or "").lower()
            if not any(k in reason for k in ["non-traffic","non-weather","outside-taiwan","out-of-scope"]):
                route = "qa"
        filters = normalize_filters(data.get("filters") or {})
        reason = (data.get("reason") or "").strip()
        return route, filters, reason
    except Exception as e:
        # 路由異常也採用 qa
        return "qa", {}, f"router_error:{type(e).__name__}"
