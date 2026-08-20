import csv
from pathlib import Path
from typing import Any


EVALUATION_DIR = Path(__file__).resolve().parents[1]
INPUT_RECORDS = (
    EVALUATION_DIR
    / "results"
    / "retrieval_eval_v0"
    / "retrieval_eval_v0_records.csv"
)
OUTPUT_DIR = EVALUATION_DIR / "results" / "single_route_retrieval_v0"

K = 5
STRATEGY_MAP = {
    "bm25": "bm25",
    "vector": "vector",
    "graph_hybrid": "graph",
}


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


def mean(items: list[dict[str, Any]], field: str) -> float:
    return round(sum(as_float(item[field]) for item in items) / max(len(items), 1), 4)


def load_single_route_records() -> list[dict[str, Any]]:
    rows = []
    for row in read_csv(INPUT_RECORDS):
        if as_int(row["k"]) != K:
            continue
        if row["strategy"] not in STRATEGY_MAP:
            continue
        row = dict(row)
        row["route"] = STRATEGY_MAP[row["strategy"]]
        rows.append(row)
    return rows


def aggregate(
    records: list[dict[str, Any]],
    group_fields: list[str],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for record in records:
        key = tuple(record[field] for field in group_fields)
        groups.setdefault(key, []).append(record)

    rows = []
    for key, items in sorted(groups.items()):
        row = {field: key[index] for index, field in enumerate(group_fields)}
        row.update(
            {
                "samples": len(items),
                "hit_at_5": mean(items, "hit_at_k"),
                "recall_at_5": mean(items, "recall_at_k"),
                "mrr": mean(items, "mrr"),
                "context_precision": mean(items, "context_precision"),
                "context_recall": mean(items, "context_recall"),
                "latency_ms": round(
                    sum(as_float(item["latency_ms"]) for item in items) / max(len(items), 1),
                    2,
                ),
                "all_evidence_hit_samples": sum(
                    1
                    for item in items
                    if as_int(item["hit_evidence_count"])
                    == as_int(item["expected_evidence_count"])
                ),
            }
        )
        rows.append(row)
    return rows


def winner_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_sample: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_sample.setdefault(record["sample_id"], []).append(record)

    rows = []
    for sample_id, items in sorted(by_sample.items()):
        ranked = sorted(
            items,
            key=lambda item: (
                -as_float(item["recall_at_k"]),
                -as_float(item["mrr"]),
                -as_float(item["context_precision"]),
                as_float(item["latency_ms"]),
            ),
        )
        best = ranked[0]
        ties = [
            item["route"]
            for item in ranked
            if as_float(item["recall_at_k"]) == as_float(best["recall_at_k"])
            and as_float(item["mrr"]) == as_float(best["mrr"])
        ]
        rows.append(
            {
                "sample_id": sample_id,
                "question_type": best["question_type"],
                "difficulty": best["difficulty"],
                "best_routes": " | ".join(ties),
                "best_recall_at_5": best["recall_at_k"],
                "best_mrr": best["mrr"],
                "question": best["question"],
            }
        )
    return rows


def failure_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        if as_float(record["recall_at_k"]) >= 1.0:
            continue
        rows.append(
            {
                "sample_id": record["sample_id"],
                "question_type": record["question_type"],
                "difficulty": record["difficulty"],
                "route": record["route"],
                "expected_evidence_count": record["expected_evidence_count"],
                "hit_evidence_count": record["hit_evidence_count"],
                "recall_at_5": record["recall_at_k"],
                "mrr": record["mrr"],
                "chunk_ids": record["chunk_ids"],
                "question": record["question"],
            }
        )
    return sorted(rows, key=lambda item: (item["sample_id"], item["route"]))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def md_table(rows: list[dict[str, Any]], fields: list[str]) -> str:
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row[field]) for field in fields) + " |")
    return "\n".join(lines)


def write_markdown(
    overall: list[dict[str, Any]],
    by_type: list[dict[str, Any]],
    winners: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> None:
    overall_fields = [
        "route",
        "samples",
        "hit_at_5",
        "recall_at_5",
        "mrr",
        "context_precision",
        "latency_ms",
    ]
    type_fields = [
        "question_type",
        "route",
        "samples",
        "hit_at_5",
        "recall_at_5",
        "mrr",
        "context_precision",
    ]
    winner_fields = [
        "sample_id",
        "question_type",
        "best_routes",
        "best_recall_at_5",
        "best_mrr",
    ]
    failure_fields = [
        "sample_id",
        "question_type",
        "route",
        "hit_evidence_count",
        "expected_evidence_count",
        "recall_at_5",
        "mrr",
    ]

    md = [
        "# Single-Route Retrieval v0",
        "",
        "This analysis compares BM25, vector retrieval, and LightRAG graph retrieval at K=5.",
        "",
        "Graph is represented by the existing `graph_hybrid` retrieval results from `retrieval_eval_v0`.",
        "",
        "## Overall",
        "",
        md_table(overall, overall_fields),
        "",
        "## By Question Type",
        "",
        md_table(by_type, type_fields),
        "",
        "## Best Route Per Sample",
        "",
        md_table(winners, winner_fields),
        "",
        "## Incomplete Evidence Recall",
        "",
        md_table(failures, failure_fields),
        "",
    ]
    (OUTPUT_DIR / "single_route_retrieval_v0_summary.md").write_text(
        "\n".join(md), encoding="utf-8"
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = load_single_route_records()
    overall = aggregate(records, ["route"])
    by_type = aggregate(records, ["question_type", "route"])
    winners = winner_rows(records)
    failures = failure_rows(records)

    overall.sort(key=lambda row: (-row["recall_at_5"], -row["mrr"], row["latency_ms"]))
    by_type.sort(key=lambda row: (row["question_type"], -row["recall_at_5"], -row["mrr"]))

    write_csv(OUTPUT_DIR / "single_route_overall.csv", overall)
    write_csv(OUTPUT_DIR / "single_route_by_question_type.csv", by_type)
    write_csv(OUTPUT_DIR / "single_route_winners.csv", winners)
    write_csv(OUTPUT_DIR / "single_route_failures.csv", failures)
    write_markdown(overall, by_type, winners, failures)

    print(f"Saved single-route analysis to {OUTPUT_DIR}")
    for row in overall:
        print(row)


if __name__ == "__main__":
    main()
