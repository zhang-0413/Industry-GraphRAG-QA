import csv
from pathlib import Path
from typing import Any


EVALUATION_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = EVALUATION_DIR / "results"
OUTPUT_DIR = RESULTS_DIR / "final_eval_v0"

RETRIEVAL_SUMMARY = RESULTS_DIR / "retrieval_eval_v0" / "retrieval_eval_v0_summary.csv"
ANSWER_SUMMARY = RESULTS_DIR / "answer_eval_v0" / "answer_eval_v0_summary.csv"
JUDGE_SUMMARY = RESULTS_DIR / "llm_judge_eval_v0" / "llm_judge_eval_v0_summary.csv"

TOP_K = 5


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def fmt(value: Any, digits: int = 4) -> str:
    return f"{as_float(value):.{digits}f}"


def load_retrieval_by_strategy() -> dict[str, dict[str, Any]]:
    rows = read_csv(RETRIEVAL_SUMMARY)
    return {
        row["strategy"]: row
        for row in rows
        if as_int(row.get("k")) == TOP_K
    }


def load_by_strategy(path: Path) -> dict[str, dict[str, Any]]:
    return {row["strategy"]: row for row in read_csv(path)}


def strategy_note(strategy: str) -> str:
    notes = {
        "bm25": "Fastest retrieval; strong for exact IDs, numbers, table fields, and OCR/caption keywords.",
        "vector": "Best strict-pass result in this run; semantically grounded answers with fewer unsupported claims.",
        "router": "Best answer-point coverage; needs tighter context control to reduce unsupported expansions.",
    }
    return notes.get(strategy, "")


def recommendation(row: dict[str, Any]) -> str:
    strategy = row["strategy"]
    if strategy == "vector":
        return "Current best strict baseline"
    if strategy == "router":
        return "Best candidate for engineering optimization"
    if strategy == "bm25":
        return "Keep as exact-match branch in hybrid/router"
    return "Reference only"


def merge_rows() -> list[dict[str, Any]]:
    retrieval = load_retrieval_by_strategy()
    answer = load_by_strategy(ANSWER_SUMMARY)
    judge = load_by_strategy(JUDGE_SUMMARY)
    strategies = sorted(set(retrieval) & set(answer) & set(judge))

    merged = []
    for strategy in strategies:
        r = retrieval[strategy]
        a = answer[strategy]
        j = judge[strategy]
        row = {
            "strategy": strategy,
            "samples": r["samples"],
            "top_k": str(TOP_K),
            "retrieval_hit_at_5": fmt(r["avg_hit_at_k"]),
            "retrieval_recall_at_5": fmt(r["avg_recall_at_k"]),
            "retrieval_mrr": fmt(r["avg_mrr"]),
            "context_precision_at_5": fmt(r["avg_context_precision"]),
            "context_recall_at_5": fmt(r["avg_context_recall"]),
            "retrieval_latency_ms": fmt(r["avg_latency_ms"], digits=2),
            "answer_pass_rate": fmt(a["pass_rate"]),
            "answer_point_coverage": fmt(a["avg_answer_point_coverage"]),
            "gold_token_f1": fmt(a["avg_gold_token_f1"]),
            "proxy_faithfulness": fmt(a["avg_faithfulness_proxy"]),
            "proxy_answer_relevance": fmt(a["avg_answer_relevance_proxy"]),
            "generation_latency_ms": fmt(a["avg_generation_latency_ms"], digits=2),
            "total_answer_latency_ms": fmt(a["avg_total_latency_ms"], digits=2),
            "strict_pass_rate": fmt(j["strict_pass_rate"]),
            "llm_faithfulness": fmt(j["avg_llm_faithfulness"]),
            "llm_answer_relevance": fmt(j["avg_llm_answer_relevance"]),
            "unsupported_claims_avg": fmt(j["avg_unsupported_claims"]),
            "missing_answer_points_avg": fmt(j["avg_missing_answer_points"]),
            "judge_latency_ms": fmt(j["avg_judge_latency_ms"], digits=2),
            "judge_parse_failures": str(as_int(j["parse_failures"])),
            "recommendation": recommendation({"strategy": strategy}),
            "note": strategy_note(strategy),
        }
        merged.append(row)

    merged.sort(
        key=lambda item: (
            -as_float(item["strict_pass_rate"]),
            -as_float(item["answer_point_coverage"]),
            -as_float(item["retrieval_recall_at_5"]),
            as_float(item["total_answer_latency_ms"]),
        )
    )
    return merged


def markdown_table(rows: list[dict[str, Any]], fields: list[str]) -> str:
    header = "| " + " | ".join(fields) + " |"
    sep = "| " + " | ".join(["---"] * len(fields)) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(row[field] for field in fields) + " |")
    return "\n".join([header, sep, *body])


def write_outputs(rows: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "final_eval_v0_summary.csv"
    md_path = OUTPUT_DIR / "final_eval_v0_summary.md"

    if rows:
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    readme_fields = [
        "strategy",
        "retrieval_recall_at_5",
        "answer_point_coverage",
        "answer_pass_rate",
        "llm_faithfulness",
        "llm_answer_relevance",
        "strict_pass_rate",
        "retrieval_latency_ms",
        "total_answer_latency_ms",
        "recommendation",
    ]
    md = [
        "# Final Evaluation v0 Summary",
        "",
        "This table merges retrieval evaluation, answer evaluation, and LLM-judge evaluation.",
        "",
        markdown_table(rows, readme_fields),
        "",
        "Notes:",
        "",
        "- `retrieval_recall_at_5`: evidence recall in Top-5 retrieved chunks.",
        "- `answer_point_coverage`: rule-based coverage of expected answer points.",
        "- `strict_pass_rate`: answer_point_coverage >= 0.8, llm_faithfulness >= 0.8, and llm_answer_relevance >= 0.8.",
        "- `total_answer_latency_ms`: retrieval latency plus answer generation latency, excluding judge latency.",
        "- Judge results use local `qwen2.5:3b`, so they are useful for comparison but not a final human audit.",
        "",
        "Detailed rows are available in `final_eval_v0_summary.csv`.",
        "",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    rows = merge_rows()
    write_outputs(rows)
    print(f"Merged {len(rows)} strategies into {OUTPUT_DIR}")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
