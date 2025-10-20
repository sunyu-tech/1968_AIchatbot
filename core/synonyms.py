# D:\github\1968_SMART_CHAT_BACK\core\synonyms.py
import os, time, yaml
from typing import Dict, Any

DEFAULT_PATH = os.getenv("SYNONYMS_PATH",
                         os.path.join(os.getcwd(), "synonyms", "synonyms.yml"))

_state = {"path": DEFAULT_PATH, "ts": 0.0, "data": {}}

def _load_file(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    # 確保都有字典
    for k in ("roads","regions","directions","types","cities","service_areas","parking_alias"):
        data.setdefault(k, {})
    return data

def load(force: bool = False) -> Dict[str, Any]:
    """讀取同義詞表（檔案改動自動重載）。"""
    path = _state["path"]
    ts = os.path.getmtime(path) if os.path.exists(path) else 0.0
    if force or (ts != _state["ts"]):
        _state["data"] = _load_file(path)
        _state["ts"] = ts
    return _state["data"]

def _canon(mapdict: Dict[str,str], val: str) -> str:
    if not val: return val
    v = val.strip()
    # 完全相等或去空白後相等
    if v in mapdict: return mapdict[v]
    v2 = v.replace(" ", "")
    if v2 in mapdict: return mapdict[v2]
    # 常見數字形式：一/1；臺/台
    v3 = v2.replace("臺", "台")
    return mapdict.get(v3, v)

def normalize_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    """
    將 LLM 輸出的 filters 正規化為系統標準值。
      - roads    → 國道x號 / 台x線 / 省道x號
      - regions  → north/center/south/pinglin
      - directions → 南下/北上/東行/西行/順向/逆向
      - types    → accident / construction / exit_congestion
      - cities   → 臺→台 等
      - parking_name → ○○服務區（補全「服務區」尾字）
    """
    syn = load()
    out = dict(filters or {})

    if out.get("road"):
        out["road"] = _canon(syn["roads"], out["road"])

    if out.get("region"):
        out["region"] = _canon(syn["regions"], out["region"]).lower()

    if out.get("direction"):
        out["direction"] = _canon(syn["directions"], out["direction"])

    if out.get("type"):
        out["type"] = _canon(syn["types"], out["type"])

    if out.get("place"):
        out["place"] = _canon(syn["cities"], out["place"])

    # 服務區別名（例如「關西」→「關西服務區」）
    p = out.get("parking_name") or ""
    if p:
        p2 = _canon(syn["service_areas"], p)
        if not p2.endswith("服務區"):
            p2 = p2 + "服務區"
        out["parking_name"] = p2

    return out

def router_hints() -> str:
    """
    產生給 LLM 的輔助說明，提醒要把別名映射到標準值。
    不包含整份表（避免 token 過大），只給規則與例子。
    """
    syn = load()
    def _some(d: Dict[str,str], n=8):
        items = list(d.items())[:n]
        return "；".join([f"{k}→{v}" for k,v in items]) if items else "—"

    return (
        "【同義詞/別名規範】\n"
        "請將輸入中的別名映射為標準值：\n"
        f"- 道路別名（例）：{_some(syn['roads'])}\n"
        f"- 區域代稱（例）：{_some(syn['regions'])}\n"
        f"- 方向別名（例）：{_some(syn['directions'])}\n"
        f"- 事件型別（例）：{_some(syn['types'])}\n"
        f"- 服務區別名（例）：{_some(syn['service_areas'])}\n"
        "輸出 filters 請直接填入標準值。"
    )

def reload():
    """手動重載（可掛在管理端 API 用）。"""
    load(force=True)
