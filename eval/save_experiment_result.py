import json
from pathlib import Path


RESULTS_DIR = Path(__file__).with_name("results")
RESULT_FILE = RESULTS_DIR / "hybrid_retriever_weight_experiment.json"


CURRENT_RESULTS = [
    {
        "experiment_name": "hybrid_retriever_weight_baseline",
        "retriever_config": {
            "BM25": 0.5,
            "FAISS": 0.5,
        },
        "metrics": {
            "hit@1": 0.2,
            "hit@3": 1.0,
            "recall@3": 1.0,
            "mrr": 0.6,
        },
    },
    {
        "experiment_name": "hybrid_retriever_weight_optimized",
        "retriever_config": {
            "BM25": 0.3,
            "FAISS": 0.7,
        },
        "metrics": {
            "hit@1": 0.9,
            "hit@3": 1.0,
            "recall@3": 1.0,
            "mrr": 0.95,
        },
    },
]


def save_results(results):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_group": "Phase 4.8.2 Hybrid Retrieval Weight Experiment",
        "results": results,
    }
    with RESULT_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_all_results():
    experiments = []
    for path in sorted(RESULTS_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        for item in payload.get("results", []):
            experiments.append(item)
    return experiments


def format_config(config):
    return f"BM25={config['BM25']:.1f}, FAISS={config['FAISS']:.1f}"


def print_summary(experiments):
    print("Experiment Tracking Summary")
    print()
    print("| experiment_name | retriever_config | hit@1 | hit@3 | recall@3 | mrr |")
    print("| --- | --- | ---: | ---: | ---: | ---: |")
    for experiment in experiments:
        metrics = experiment["metrics"]
        print(
            "| "
            f"{experiment['experiment_name']} | "
            f"{format_config(experiment['retriever_config'])} | "
            f"{metrics['hit@1']:.4f} | "
            f"{metrics['hit@3']:.4f} | "
            f"{metrics['recall@3']:.4f} | "
            f"{metrics['mrr']:.4f} |"
        )


def main():
    save_results(CURRENT_RESULTS)
    print_summary(load_all_results())
    print()
    print(f"Saved: {RESULT_FILE}")


if __name__ == "__main__":
    main()
