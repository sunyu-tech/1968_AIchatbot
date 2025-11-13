# D:\github\1968_SMART_CHAT_BACK\services\faq_service.py
from typing import List

from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

def answer_from_docs(question: str, docs: List[Document], model: str = "gpt-4o-mini") -> dict:
    """
    從 FAQ PDF 向量（docs）產答案。
    規則：只輸出「精簡答案」本身，不要加『引用要點』或任何前綴/段落標題。
    """
    ctx = []
    sources = []
    for d in docs:
        page = d.metadata.get("page")
        ctx.append(f"[第{page}頁]\n{d.page_content}")
        sources.append({"doc":"1968_QA.pdf","page":page})

    prompt = (
        "你是台灣高速公路 1968 FAQ 專員。請僅根據下列資料回答，答案請使用繁體中文。\n"
        "【重要】只輸出「精簡答案」內容，不要加『引用要點』、『精簡答案』等前綴或任何多餘說明。\n\n"
        "【資料】\n" + "\n\n".join(ctx) + "\n\n【問題】\n" + question
    )

    llm = ChatOpenAI(model=model, temperature=0)
    resp = llm.invoke([SystemMessage(content="答案務必可被資料佐證，若無資料請直說不知道。"), HumanMessage(content=prompt)])
    return {"text": resp.content.strip(), "sources": sources}
