# D:\github\1968_SMART_CHAT_BACK\core\textnorm.py
import re

LEAD = re.compile(r"^\s*(請問|我想|我想要|幫我|麻煩|想知道|可不可以|能不能|請協助|問一下|Q[:：]?|想查)\s*", re.I)

def normalize(q: str) -> str:
    return LEAD.sub("", (q or "").strip())
