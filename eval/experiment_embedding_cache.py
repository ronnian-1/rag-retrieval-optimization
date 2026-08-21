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


QUERY = "公司名称是什么？"
KB_PATH = PROJECT_ROOT / "knowledgebases" / "test.faiss"
TOP_K = 4
REPEAT_COUNT = 10
WEIGHTS = [0.5, 0.5]


def percentile(values, pct):
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def build_retrieval_stack():
    embedding_model = get_embedding_model()
    vector_store = FAISS.load_local(
        str(KB_PATH),
        embedding_model,
        allow_dangerous_deserialization=True,
    )
    docs = list(vector_store.docstore._dict.values())

    bm25_retriever = BM25Retriever.from_documents(
        docs,
        preprocess_func=jieba.lcut_for_search,
    )
    bm25_retriever.k = TOP_K
    faiss_retriever = vector_store.as_retriever(search_kwargs={"k": TOP_K})
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, faiss_retriever],
        weights=WEIGHTS,
    )
    return embedding_model, vector_store, bm25_retriever, ensemble_retriever


def retrieve_once(query, embedding_model, vector_store, bm25_retriever, ensemble_retriever, cache=None):
    api_called = False
    start = time.perf_counter()

    if cache is not None and query in cache:
        embedding = cache[query]
    else:
        embedding = embedding_model.embed_query(query)
        api_called = True
        if cache is not None:
            cache[query] = embedding

    faiss_results = vector_store.similarity_search_with_score_by_vector(
        embedding,
        k=TOP_K,
    )
    faiss_docs = [doc for doc, _score in faiss_results]
    bm25_docs = bm25_retriever.invoke(query)
    ensemble_retriever.weighted_reciprocal_rank([bm25_docs, faiss_docs])

    return time.perf_counter() - start, api_called


def run_scenario(cache_enabled):
    embedding_model, vector_store, bm25_retriever, ensemble_retriever = build_retrieval_stack()
    cache = {} if cache_enabled else None
    latencies = []
    api_calls = 0

    for _ in range(REPEAT_COUNT):
        latency, api_called = retrieve_once(
            QUERY,
            embedding_model,
            vector_store,
            bm25_retriever,
            ensemble_retriever,
            cache=cache,
        )
        latencies.append(latency)
        if api_called:
            api_calls += 1

    return {
        "latencies": latencies,
        "api_calls": api_calls,
    }


def summarize(result):
    latencies = result["latencies"]
    return {
        "avg": sum(latencies) / len(latencies),
        "p50": statistics.median(latencies),
        "p95": percentile(latencies, 0.95),
        "api_calls": result["api_calls"],
    }


def print_summary(title, summary):
    print(f"## {title}")
    print()
    print(f"avg latency: {summary['avg']:.4f}s")
    print(f"p50: {summary['p50']:.4f}s")
    print(f"p95: {summary['p95']:.4f}s")
    print()


def main():
    if not KB_PATH.exists():
        raise FileNotFoundError(f"Knowledge base not found: {KB_PATH}")

    baseline = summarize(run_scenario(cache_enabled=False))
    cached = summarize(run_scenario(cache_enabled=True))

    latency_reduction = (
        (baseline["avg"] - cached["avg"]) / baseline["avg"] if baseline["avg"] else 0.0
    )
    api_call_reduction = (
        (baseline["api_calls"] - cached["api_calls"]) / baseline["api_calls"]
        if baseline["api_calls"]
        else 0.0
    )

    print("# Embedding Cache Experiment")
    print()
    print_summary("Baseline", baseline)
    print_summary("Cache Enabled", cached)
    print("## Improvement")
    print()
    print(f"latency reduction: {latency_reduction:.2%}")
    print(f"API call reduction: {api_call_reduction:.2%}")
    print(f"baseline API calls: {baseline['api_calls']}/{REPEAT_COUNT}")
    print(f"cache API calls: {cached['api_calls']}/{REPEAT_COUNT}")
    print()
    print("## Recommendation")
    print()
    if latency_reduction >= 0.3 and api_call_reduction >= 0.8:
        print("Worth promoting to production code behind a small, bounded query embedding cache.")
    else:
        print("Keep as an experiment until latency and API-call reduction are consistently significant.")


if __name__ == "__main__":
    main()
