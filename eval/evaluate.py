import json
import os
import sys
from pathlib import Path
from urllib import error, request


EVALUATION_FILE = Path(__file__).with_name("evaluation.json")
API_URL = os.getenv("EVAL_API_URL", "http://127.0.0.1:6605/kbs/search_kb")
KB_NAME = os.getenv("EVAL_KB_NAME", "test")
TOP_K = int(os.getenv("EVAL_TOP_K", "3"))
TIMEOUT = int(os.getenv("EVAL_TIMEOUT", "60"))


def load_cases(path):
    with path.open("r", encoding="utf-8") as f:
        cases = json.load(f)
    if not isinstance(cases, list):
        raise ValueError("evaluation.json must contain a list")
    return cases


def search_kb(query):
    payload = json.dumps({"kb_name": KB_NAME, "query": query}).encode("utf-8")
    req = request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
    except error.URLError as exc:
        raise RuntimeError(f"Failed to call search_kb API: {exc}") from exc

    data = json.loads(body)
    results = data.get("results", [])
    if not isinstance(results, list):
        raise ValueError("search_kb response field 'results' must be a list")
    return results


def normalize_chunk_id(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def find_hit_rank(results, expected_filename, expected_chunk_id):
    expected_chunk_id = normalize_chunk_id(expected_chunk_id)
    for idx, item in enumerate(results, start=1):
        filename = item.get("filename")
        chunk_id = normalize_chunk_id(item.get("chunk_id"))
        if filename == expected_filename and chunk_id == expected_chunk_id:
            return idx
    return None


def format_retrieved(results):
    retrieved = []
    for item in results[:TOP_K]:
        retrieved.append(
            {
                "rank": item.get("rank"),
                "filename": item.get("filename"),
                "chunk_id": item.get("chunk_id"),
                "source": item.get("source"),
            }
        )
    return retrieved


def main():
    cases = load_cases(EVALUATION_FILE)
    details = []
    hit_at_1 = 0
    hit_at_3 = 0
    reciprocal_rank_sum = 0.0

    for case in cases:
        query = case["query"]
        expected_filename = case["expected_filename"]
        expected_chunk_id = case["expected_chunk_id"]
        results = search_kb(query)
        hit_rank = find_hit_rank(results, expected_filename, expected_chunk_id)

        if hit_rank == 1:
            hit_at_1 += 1
        if hit_rank is not None and hit_rank <= TOP_K:
            hit_at_3 += 1
        if hit_rank is not None:
            reciprocal_rank_sum += 1.0 / hit_rank

        details.append(
            {
                "query": query,
                "expected": {
                    "filename": expected_filename,
                    "chunk_id": expected_chunk_id,
                },
                "retrieved": format_retrieved(results),
                "hit_rank": hit_rank,
            }
        )

    total = len(cases)
    recall_at_3 = hit_at_3 / total if total else 0.0
    mrr = reciprocal_rank_sum / total if total else 0.0

    print("================ Evaluation Result ================")
    print(f"Total: {total}")
    print(f"Hit@1: {hit_at_1}/{total} ({hit_at_1 / total:.4f})" if total else "Hit@1: 0/0 (0.0000)")
    print(f"Hit@3: {hit_at_3}/{total} ({hit_at_3 / total:.4f})" if total else "Hit@3: 0/0 (0.0000)")
    print(f"Recall@3: {recall_at_3:.4f}")
    print(f"MRR: {mrr:.4f}")
    print()

    for detail in details:
        print("query:", detail["query"])
        print("expected:", json.dumps(detail["expected"], ensure_ascii=False))
        print("retrieved:", json.dumps(detail["retrieved"], ensure_ascii=False))
        print("hit_rank:", detail["hit_rank"])
        print()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        sys.exit(1)
