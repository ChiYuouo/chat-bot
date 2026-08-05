"""PDF 文档处理和 RAG 问答。"""

import os
import tempfile
from typing import Any, Dict, List

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import Config
from app.llm import create_chat_model


def process_pdf(pdf_bytes: bytes) -> List[Any]:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        docs = PyMuPDFLoader(tmp_path).load()
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP,
            is_separator_regex=True,
            keep_separator=False,
            separators=["(?<=。)", "(?<=！)", "(?<=？)", "(?<=，)", " "],
        )
        return splitter.split_documents(docs)
    finally:
        os.unlink(tmp_path)


def rag_answer(question: str, chunks: List[Any]) -> Dict[str, Any]:
    embeddings = DashScopeEmbeddings(model=Config.EMBEDDING_MODEL)
    store = Chroma.from_documents(chunks, embeddings)
    retriever = store.as_retriever(search_kwargs={"k": Config.RETRIEVAL_K})
    results = retriever.invoke(question)

    context_parts = []
    for doc in results:
        page_num = doc.metadata.get("page", doc.metadata.get("page_number", "未知"))
        context_parts.append(f"【第 {page_num} 页】\n{doc.page_content}")
    context = "\n\n".join(context_parts)

    citations = [
        {
            "page": doc.metadata.get("page", doc.metadata.get("page_number", "?")),
            "content": doc.page_content[:150] + "...",
        }
        for doc in results
    ]
    citation_guide = "\n".join(
        [f"- 第 {citation['page']} 页：{citation['content'][:100]}..." for citation in citations]
    )

    prompt = f"""根据以下文档内容回答问题。

文档内容（已标注页码）：
{context}

问题：{question}

引用来源参考：
{citation_guide}

要求：
1. 只根据文档内容回答，不要编造。
2. 如果文档中没有相关信息，请说“文档中未找到相关信息”。
3. 在答案中标注来源页码。
4. 每个关键信息都要说明具体来源页码。
"""

    response = create_chat_model(Config.LLM_MODEL, temperature=0).invoke(prompt)
    answer = response.content if isinstance(response.content, str) else response.content[0].get("text", "")
    return {"answer": answer, "citations": citations}
