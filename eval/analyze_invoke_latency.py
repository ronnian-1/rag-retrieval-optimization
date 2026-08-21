import json
import logging
import statistics
import sys
import time
import warnings
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API.*")

with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
    import jieba
    from langchain.retrievers import EnsembleRetriever
    from langchain_community.retrievers import BM25Retriever
    from langchain_community.vectorstores import FAISS

    from knowledgebase_server.kb_routes import get_embedding_model

jieba.setLogLevel(logging.ERROR)


EVALUATION_FILE = PROJECT_ROOT / "eval" / "evaluation.json"
KB_PATH = PROJECT_ROOT / "knowledgebases" / "test.faiss"
TOP_K = 4
WEIGHTS = [0.5, 0.5]


def load_cases():
    with EVALUATION_FILE.open("r", encoding="utf-8") as f:
        cases = json.load(f)
    if not isinstance(cases, list):
        raise ValueError("evaluation.json must contain a list")
    return cases


def build_retrievers():
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
        weights=WEIGHTS,
    )
    return embedding_model, vector_store, bm25_retriever, ensemble_retriever


def timed(callable_):
    start = time.perf_counter()
    result = callable_()
    return result, time.perf_counter() - start


def summarize(values):
    return {
        "avg": sum(values) / len(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def print_stats(title, values):
    stats = summarize(values)
    print(f"## {title}")
    print()
    print(f"avg: {stats['avg']:.4f}s")
    print(f"median: {stats['median']:.4f}s")
    print(f"min: {stats['min']:.4f}s")
    print(f"max: {stats['max']:.4f}s")
    print()


def root_cause(stage_timings):
    averages = {name: summarize(values)["avg"] for name, values in stage_timings.items()}
    winner = max(averages, key=averages.get)
    labels = {
        "embedding": "A. embedding API",
        "faiss": "B. FAISS",
        "bm25": "C. BM25",
        "fusion": "D. fusion",
    }
    return labels[winner], averages


def recommendation(cause):
    if cause.startswith("A."):
        return [
            "P0: Cache query embeddings for repeated or normalized queries, and consider request-level timeout/retry metrics for the embedding provider.",
            "P1: Batch or prefetch embeddings for evaluation and high-volume workflows where queries are known ahead of time.",
            "P2: Add provider latency telemetry, including p50/p95/p99, status code, and model name, to separate network/API variance from local retriever cost.",
        ]
    if cause.startswith("B."):
        return [
            "P0: Reuse loaded FAISS indexes instead of loading/searching through a fresh stack for every request.",
            "P1: Tune FAISS index type and k for larger knowledge bases.",
            "P2: Track FAISS latency by doc_count/index size to catch scale-related regressions.",
        ]
    if cause.startswith("C."):
        return [
            "P0: Cache BM25 retrievers per knowledge base instead of rebuilding or retokenizing on each request.",
            "P1: Pre-warm jieba and persist tokenized corpora for stable startup behavior.",
            "P2: Evaluate BM25 only when lexical recall is useful, or gate it behind query classification.",
        ]
    return [
        "P0: Keep the retriever outputs small before fusion and avoid duplicate-heavy candidate lists.",
        "P1: Cache fused results for identical queries and knowledge-base versions.",
        "P2: Add fusion-specific timing to production logs if candidate counts grow.",
    ]


def main():
    if not KB_PATH.exists():
        raise FileNotFoundError(f"Knowledge base not found: {KB_PATH}")

    cases = load_cases()
    embedding_model, vector_store, bm25_retriever, ensemble_retriever = build_retrievers()
    timings = {
        "embedding": [],
        "faiss": [],
        "bm25": [],
        "fusion": [],
    }

    for case in cases:
        query = case["query"]

        embedding, elapsed = timed(lambda: embedding_model.embed_query(query))
        timings["embedding"].append(elapsed)

        faiss_results, elapsed = timed(
            lambda: vector_store.similarity_search_with_score_by_vector(
                embedding,
                k=TOP_K,
            )
        )
        timings["faiss"].append(elapsed)
        faiss_docs = [doc for doc, _score in faiss_results]

        bm25_docs, elapsed = timed(lambda: bm25_retriever.invoke(query))
        timings["bm25"].append(elapsed)

        _fused_docs, elapsed = timed(
            lambda: ensemble_retriever.weighted_reciprocal_rank(
                [bm25_docs, faiss_docs]
            )
        )
        timings["fusion"].append(elapsed)

    cause, averages = root_cause(timings)

    print("# Retrieval Invoke Breakdown")
    print()
    print_stats("Embedding Latency", timings["embedding"])
    print_stats("FAISS Search", timings["faiss"])
    print_stats("BM25 Search", timings["bm25"])
    print_stats("Ensemble Fusion", timings["fusion"])
    print("## Root Cause")
    print()
    print(f"Current invoke latency is mainly from: {cause}")
    print()
    print("avg_by_stage:")
    print(f"embedding: {averages['embedding']:.4f}s")
    print(f"faiss: {averages['faiss']:.4f}s")
    print(f"bm25: {averages['bm25']:.4f}s")
    print(f"fusion: {averages['fusion']:.4f}s")
    print()
    print("## Recommendation")
    print()
    for line in recommendation(cause):
        print(line)


if __name__ == "__main__":
    main()
