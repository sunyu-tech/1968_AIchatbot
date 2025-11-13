# scripts/build_faq_index.py
import os, json, pathlib
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

PDF_JSON = os.path.join(os.getcwd(), "PDF", "1968_QA.json")  # 將 1968_QA.pdf 預處理成 json：每頁一段
OUT_DIR  = os.path.join("faiss_index", "faq_1968")
cs = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=60)
emb = OpenAIEmbeddings()

def main():
    pages = json.load(open(PDF_JSON, "r", encoding="utf-8"))
    docs = []
    for i, txt in enumerate(pages, start=1):
        if not txt: continue
        for c in cs.split_text(txt):
            from langchain.schema import Document
            docs.append(Document(page_content=c, metadata={"doc":"1968_QA.pdf","page":i}))
    vs = FAISS.from_documents(docs, emb)
    pathlib.Path(OUT_DIR).mkdir(parents=True, exist_ok=True)
    vs.save_local(OUT_DIR)
    print(f"OK -> {OUT_DIR}")

if __name__ == "__main__":
    main()
