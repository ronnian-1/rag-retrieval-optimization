import sys
import types
import warnings
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API.*")

import jieba
try:
    from langchain.retrievers import EnsembleRetriever
except ModuleNotFoundError:
    from langchain_classic.retrievers import EnsembleRetriever

    retrievers_module = types.ModuleType("langchain.retrievers")
    retrievers_module.EnsembleRetriever = EnsembleRetriever
    sys.modules.setdefault("langchain.retrievers", retrievers_module)

from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS

try:
    from knowledgebase_server.kb_routes import get_embedding_model
except ModuleNotFoundError:
    from langchain_openai import OpenAIEmbeddings
    try:
        from langchain.embeddings.base import Embeddings
    except ModuleNotFoundError:
        from langchain_core.embeddings import Embeddings

    from configs.settings import api_key, base_url, embedding_model_name

    class CustomEmbeddingModel(Embeddings):
        def __init__(self, model, model_name):
            self.model = model
            self.model_name = model_name

        def embed_documents(self, texts):
            return [
                self.model.client.create(model=self.model_name, input=text).data[0].embedding
                for text in texts
            ]

        def embed_query(self, text):
            return self.model.client.create(model=self.model_name, input=text).data[0].embedding

    _embedding_model = None

    def get_embedding_model():
        global _embedding_model
        if _embedding_model is None:
            embedding = OpenAIEmbeddings(api_key=api_key, base_url=base_url)
            _embedding_model = CustomEmbeddingModel(embedding, embedding_model_name)
        return _embedding_model


QUERY = "公司名称是什么？"
KB_PATH = PROJECT_ROOT / "knowledgebases" / "test.faiss"
TOP_K = 4


def doc_key(doc):
    return (
        doc.metadata.get("source"),
        doc.metadata.get("filename"),
        doc.metadata.get("chunk_id"),
        doc.page_content,
    )


def chunk_id(doc):
    return doc.metadata.get("chunk_id")


def filename(doc):
    return doc.metadata.get("filename") or ""


def summarize(content, max_len=90):
    text = " ".join((content or "").split())
    return text if len(text) <= max_len else f"{text[:max_len]}..."


def format_ranking(title, docs):
    lines = [f"## {title}", ""]
    for rank, doc in enumerate(docs, start=1):
        lines.extend(
            [
                f"rank: {rank}",
                f"chunk_id: {chunk_id(doc)}",
                f"filename: {filename(doc)}",
                f"content摘要: {summarize(doc.page_content)}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def rank_map(docs):
    return {doc_key(doc): rank for rank, doc in enumerate(docs, start=1)}


def first_doc_by_chunk(docs, target_chunk_id):
    for doc in docs:
        if chunk_id(doc) == target_chunk_id:
            return doc
    return None


def diagnose(faiss_docs, bm25_docs, ensemble_docs):
    faiss_ranks = rank_map(faiss_docs)
    bm25_ranks = rank_map(bm25_docs)
    ensemble_ranks = rank_map(ensemble_docs)

    chunk0 = first_doc_by_chunk(ensemble_docs + faiss_docs + bm25_docs, 0)
    chunk1 = first_doc_by_chunk(ensemble_docs + faiss_docs + bm25_docs, 1)
    if chunk0 is None or chunk1 is None:
        return "Unable to diagnose because chunk_id=0 or chunk_id=1 was not returned."

    chunk0_key = doc_key(chunk0)
    chunk1_key = doc_key(chunk1)
    f0 = faiss_ranks.get(chunk0_key)
    f1 = faiss_ranks.get(chunk1_key)
    b0 = bm25_ranks.get(chunk0_key)
    b1 = bm25_ranks.get(chunk1_key)
    e0 = ensemble_ranks.get(chunk0_key)
    e1 = ensemble_ranks.get(chunk1_key)

    facts = [
        f"chunk_id=0 ranks: FAISS={f0}, BM25={b0}, Ensemble={e0}",
        f"chunk_id=1 ranks: FAISS={f1}, BM25={b1}, Ensemble={e1}",
    ]

    if f1 is not None and f0 is not None and f1 < f0:
        cause = "FAISS语义误排"
    elif b1 is not None and b0 is not None and b1 < b0:
        cause = "BM25关键词误排"
    elif e1 is not None and e0 is not None and e1 < e0:
        cause = "Ensemble RRF融合导致"
    else:
        cause = "No reproduced inversion between chunk_id=1 and chunk_id=0"

    return "\n".join(facts + [f"judgement: {cause}"])


def recommendation(root_cause):
    if "BM25关键词误排" in root_cause:
        return (
            "BM25 is over-rewarding lexical overlap in chunk_id=1. Keep business code unchanged for this "
            "experiment, but consider future evaluation of field-aware chunking, query expansion for 公司名称, "
            "or metadata/title boosting so the explicit 公司名称 chunk is favored."
        )
    if "FAISS语义误排" in root_cause:
        return (
            "FAISS is ranking chunk_id=1 above the explicit company-name chunk. Future experiments should inspect "
            "embedding similarity scores and consider chunk-size/overlap or field-label normalization changes."
        )
    if "Ensemble RRF融合导致" in root_cause:
        return (
            "The individual retrievers do not both explain the inversion, so the RRF fusion order/weights should be "
            "tested separately before changing production behavior."
        )
    return "No production recommendation yet; first reproduce the baseline inversion with the local retriever stack."


def main():
    if not KB_PATH.exists():
        raise FileNotFoundError(f"Knowledge base not found: {KB_PATH}")

    embedding_model = get_embedding_model()
    vector_store = FAISS.load_local(
        str(KB_PATH),
        embedding_model,
        allow_dangerous_deserialization=True,
    )
    docs = list(vector_store.docstore._dict.values())

    faiss_retriever = vector_store.as_retriever(search_kwargs={"k": TOP_K})
    bm25_retriever = BM25Retriever.from_documents(
        docs,
        preprocess_func=jieba.lcut_for_search,
    )
    bm25_retriever.k = TOP_K
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, faiss_retriever],
        weights=[0.5, 0.5],
    )

    faiss_docs = faiss_retriever.invoke(QUERY)
    bm25_docs = bm25_retriever.invoke(QUERY)
    ensemble_docs = ensemble_retriever.invoke(QUERY)
    root_cause = diagnose(faiss_docs, bm25_docs, ensemble_docs)

    print("# Retrieval Attribution Report")
    print()
    print(format_ranking("FAISS ranking", faiss_docs))
    print()
    print(format_ranking("BM25 ranking", bm25_docs))
    print()
    print(format_ranking("Ensemble ranking", ensemble_docs))
    print()
    print("## Root Cause")
    print()
    print(root_cause)
    print()
    print("## Recommendation")
    print()
    print(recommendation(root_cause))


if __name__ == "__main__":
    main()
