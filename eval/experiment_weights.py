import json
import logging
import sys
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
WEIGHTS = [
    (0.5, 0.5),
    (0.3, 0.7),
    (0.2, 0.8),
]


def normalize_chunk_id(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def load_cases():
    with EVALUATION_FILE.open("r", encoding="utf-8") as f:
        cases = json.load(f)
    if not isinstance(cases, list):
        raise ValueError("evaluation.json must contain a list")
    return cases


def build_base_retrievers():
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
    return bm25_retriever, faiss_retriever


def find_hit_rank(results, expected_filename, expected_chunk_id):
    expected_chunk_id = normalize_chunk_id(expected_chunk_id)
    for rank, doc in enumerate(results, start=1):
        filename = doc.metadata.get("filename")
        chunk_id = normalize_chunk_id(doc.metadata.get("chunk_id"))
        if filename == expected_filename and chunk_id == expected_chunk_id:
            return rank
    return None


def evaluate_weight(cases, bm25_retriever, faiss_retriever, weights):
    retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, faiss_retriever],
        weights=list(weights),
    )

    hit_at_1 = 0
    hit_at_3 = 0
    reciprocal_rank_sum = 0.0
    details = []

    for case in cases:
        results = retriever.invoke(case["query"])
        hit_rank = find_hit_rank(
            results,
            case["expected_filename"],
            case["expected_chunk_id"],
        )

        if hit_rank == 1:
            hit_at_1 += 1
        if hit_rank is not None and hit_rank <= 3:
            hit_at_3 += 1
        if hit_rank is not None:
            reciprocal_rank_sum += 1.0 / hit_rank

        details.append(
            {
                "query": case["query"],
                "expected_chunk_id": case["expected_chunk_id"],
                "top_chunk_id": normalize_chunk_id(results[0].metadata.get("chunk_id"))
                if results
                else None,
                "hit_rank": hit_rank,
            }
        )

    total = len(cases)
    return {
        "weights": weights,
        "hit_at_1": hit_at_1,
        "mrr": reciprocal_rank_sum / total if total else 0.0,
        "recall_at_3": hit_at_3 / total if total else 0.0,
        "details": details,
        "total": total,
    }


def score_result(result):
    return (
        result["hit_at_1"] / result["total"] if result["total"] else 0.0,
        result["mrr"],
        result["recall_at_3"],
    )


def format_weight(weights):
    return f"{weights[0]:.1f}/{weights[1]:.1f}"


def main():
    if not KB_PATH.exists():
        raise FileNotFoundError(f"Knowledge base not found: {KB_PATH}")

    cases = load_cases()
    bm25_retriever, faiss_retriever = build_base_retrievers()
    results = [
        evaluate_weight(cases, bm25_retriever, faiss_retriever, weights)
        for weights in WEIGHTS
    ]
    best_score = max(score_result(result) for result in results)
    best_results = [result for result in results if score_result(result) == best_score]
    best = min(
        best_results,
        key=lambda result: abs(result["weights"][0] - 0.5)
        + abs(result["weights"][1] - 0.5),
    )

    print("# Hybrid Weight Experiment")
    print()
    for result in results:
        weights = result["weights"]
        total = result["total"]
        print(f"## Weight {format_weight(weights)}")
        print()
        print(f"Hit@1: {result['hit_at_1']}/{total} ({result['hit_at_1'] / total:.4f})")
        print(f"MRR: {result['mrr']:.4f}")
        print(f"Recall@3: {result['recall_at_3']:.4f}")
        print()

    print("## Recommendation")
    print()
    if len(best_results) > 1:
        tied = ", ".join(format_weight(result["weights"]) for result in best_results)
        print(f"Best metric tie: {tied}")
    print(
        "Recommended weight: "
        f"{format_weight(best['weights'])} "
        f"(BM25={best['weights'][0]:.1f}, FAISS={best['weights'][1]:.1f})"
    )


if __name__ == "__main__":
    main()
