# D:\github\1968_SMART_CHAT_BACK\core\faq_gate.py
import os, logging
from typing import List, Tuple
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

FAQ_INDEX_DIR = os.getenv("FAQ_INDEX_DIR", os.path.join("faiss_index", "faq_1968"))
FAQ_HIT_THRESHOLD = float(os.getenv("FAQ_HIT_THRESHOLD", "0.50"))  # 可用 .env 調整

_vs = None

def _load_index():
    global _vs
    if _vs is not None:
        return _vs
    idx_f = os.path.join(FAQ_INDEX_DIR, "index.faiss")
    idx_p = os.path.join(FAQ_INDEX_DIR, "index.pkl")
    if not (os.path.exists(idx_f) and os.path.exists(idx_p)):
        logging.warning(f"[faq_gate] 找不到索引：{idx_f} / {idx_p}")
        return None
    _vs = FAISS.load_local(FAQ_INDEX_DIR, OpenAIEmbeddings(), allow_dangerous_deserialization=True)
    logging.info(f"[faq_gate] FAQ 索引載入 → {FAQ_INDEX_DIR}")
    return _vs

def faq_gate(question: str) -> Tuple[bool, float, List[Document]]:
    """
    回傳: (是否命中, 命中分數(0~1), Top 文檔列表)
    規則：
      - 不做關鍵字硬命中，全部交給向量相似度的「名次分」粗略評估。
      - 只要第一名的名次分 >= FAQ_HIT_THRESHOLD 即視為命中。
    """
    vs = _load_index()
    if vs is None:
        return (False, 0.0, [])

    try:
        dense = vs.similarity_search(question, k=5) or []
    except Exception as e:
        logging.error(f"[faq_gate] similarity_search 例外：{type(e).__name__}: {e}")
        return (False, 0.0, [])

    scored = []
    for rank, d in enumerate(dense, start=1):
        score = max(0.0, 1.0 - (rank-1)*0.15)  # 1.00, 0.85, 0.70, 0.55, 0.40 ...
        scored.append((score, d))
    scored.sort(key=lambda x: x[0], reverse=True)

    hit_score = scored[0][0] if scored else 0.0
    hit = (hit_score >= FAQ_HIT_THRESHOLD)
    top_docs = [d for s, d in scored[:5]]
    return (hit, hit_score, top_docs)
