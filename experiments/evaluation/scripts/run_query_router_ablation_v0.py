import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


EVALUATION_DIR = Path(__file__).resolve().parents[1]
DATASET_PATH = EVALUATION_DIR / "datasets" / "eval_v0_20.jsonl"
RERANK_RECORDS_PATH = (
    EVALUATION_DIR
    / "results"
    / "rerank_ablation_v0"
    / "rerank_ablation_v0_records.csv"
)
OUTPUT_DIR = EVALUATION_DIR / "results" / "query_router_ablation_v0"
RUN_ID = "query_router_ablation_v0_001"


EXACT_PATTERN = re.compile(
    r"\b(?:ir-\d{4}-\d+|[a-z]+-[a-z]*\d+[a-z0-9-]*|\d+(?:\.\d+)?\s*mpa)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RouterDecision:
    router_name: str
    route: str
    selected_strategy: str
    use_graph: bool
    use_rerank: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_strategy_records(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    records = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            converted = dict(row)
            for key in (
                "hit_at_k",
                "recall_at_k",
                "mrr",
                "context_precision",
                "context_recall",
                "latency_ms",
            ):
                converted[key] = float(converted[key])
            for key in (
                "k",
                "expected_evidence_count",
                "hit_evidence_count",
                "evidence_rank_improved",
                "evidence_rank_worsened",
                "evidence_lost_after_rerank",
                "evidence_gained_after_rerank",
            ):
                converted[key] = int(float(converted[key]))
            records[(converted["sample_id"], converted["strategy"])] = converted
    return records


def text_signals(sample: dict[str, Any]) -> tuple[str, str, set[str]]:
    query = (sample.get("question") or "").lower()
    qtype = (sample.get("question_type") or "").lower()
    modalities = {str(item).lower() for item in sample.get("modalities", [])}
    return query, qtype, modalities


def is_exact_or_numeric(query: str, qtype: str) -> bool:
    if qtype in {"fact", "numeric"}:
        return True
    exact_words = (
        "what is",
        "which",
        "when must",
        "design pressure",
        "alarm threshold",
        "status",
    )
    return bool(EXACT_PATTERN.search(query)) or any(word in query for word in exact_words)


def safe_router(sample: dict[str, Any]) -> RouterDecision:
    query, qtype, modalities = text_signals(sample)

    if qtype == "global_summary" or any(
        word in query for word in ("summarize", "summary", "overall", "across")
    ):
        return RouterDecision(
            "router_safe",
            "global_summary",
            "bm25_vector_rrf_q015_rerank",
            use_graph=False,
            use_rerank=True,
            reason=(
                "Global summary needs a wider candidate pool and a summary-aware reranker."
            ),
        )

    if qtype == "table" or "table" in modalities or "table" in query:
        return RouterDecision(
            "router_safe",
            "table_lookup",
            "bm25_vector_rrf",
            use_graph=False,
            use_rerank=False,
            reason="Table queries in this dataset are already stable with BM25+Vector RRF.",
        )

    if qtype == "image" or "image" in modalities or "diagram" in query:
        return RouterDecision(
            "router_safe",
            "image_lookup",
            "bm25_vector_rrf",
            use_graph=False,
            use_rerank=False,
            reason="Image chunks are retrieved well by text/caption embeddings here.",
        )

    if qtype in {"cross_document", "cross_paragraph", "causal_reasoning", "multi_hop"}:
        return RouterDecision(
            "router_safe",
            "multi_evidence",
            "bm25_vector_rrf",
            use_graph=False,
            use_rerank=False,
            reason=(
                "Multi-evidence questions can contain exact IDs, but need broader "
                "BM25+Vector coverage instead of pure BM25."
            ),
        )

    if is_exact_or_numeric(query, qtype):
        return RouterDecision(
            "router_safe",
            "exact_or_numeric",
            "bm25",
            use_graph=False,
            use_rerank=False,
            reason="Exact IDs, entity names, and numeric values are safest with BM25.",
        )

    return RouterDecision(
        "router_safe",
        "semantic_or_multi_evidence",
        "bm25_vector_rrf",
        use_graph=False,
        use_rerank=False,
        reason="Use BM25+Vector RRF as the stable default for multi-evidence questions.",
    )


def graph_rerank_router(sample: dict[str, Any]) -> RouterDecision:
    query, qtype, modalities = text_signals(sample)

    if qtype == "global_summary" or any(
        word in query for word in ("summarize", "summary", "overall", "across")
    ):
        return RouterDecision(
            "router_graph_rerank",
            "global_summary",
            "bm25_vector_graph_rrf_q015_rerank",
            use_graph=True,
            use_rerank=True,
            reason="Aggressively include Graph for global summary, then rerank.",
        )

    if qtype in {
        "entity_relation",
        "cross_document",
        "causal_reasoning",
        "table",
        "image",
        "multi_hop",
    } or {"table", "image"} & modalities:
        return RouterDecision(
            "router_graph_rerank",
            "graph_enriched",
            "bm25_vector_graph_rrf_query_rerank",
            use_graph=True,
            use_rerank=True,
            reason="Use Graph-enriched fusion and query-aware rerank for complex questions.",
        )

    if is_exact_or_numeric(query, qtype):
        return RouterDecision(
            "router_graph_rerank",
            "exact_or_numeric",
            "bm25",
            use_graph=False,
            use_rerank=False,
            reason="Keep exact/numeric questions on BM25.",
        )

    return RouterDecision(
        "router_graph_rerank",
        "default_hybrid",
        "bm25_vector_rrf",
        use_graph=False,
        use_rerank=False,
        reason="Default to BM25+Vector RRF.",
    )


def always_q015_rerank_router(sample: dict[str, Any]) -> RouterDecision:
    return RouterDecision(
        "router_always_q015_rerank",
        "always_rerank",
        "bm25_vector_rrf_q015_rerank",
        use_graph=False,
        use_rerank=True,
        reason="Negative-control router: always applies a summary-biased reranker.",
    )


def oracle_type_router(
    sample: dict[str, Any],
    records: dict[tuple[str, str], dict[str, Any]],
    samples_by_id: dict[str, dict[str, Any]],
) -> RouterDecision:
    qtype = sample["question_type"]
    same_type_ids = [
        sample_id
        for sample_id, row in samples_by_id.items()
        if row["question_type"] == qtype
    ]
    strategies = {
        strategy
        for sample_id, strategy in records
        if sample_id in same_type_ids and not strategy.startswith("router")
    }
    best_strategy = max(
        strategies,
        key=lambda strategy: (
            avg_metric(records, same_type_ids, strategy, "recall_at_k"),
            avg_metric(records, same_type_ids, strategy, "mrr"),
            avg_metric(records, same_type_ids, strategy, "context_precision"),
            -avg_metric(records, same_type_ids, strategy, "latency_ms"),
        ),
    )
    return RouterDecision(
        "router_oracle_by_type",
        f"oracle_{qtype}",
        best_strategy,
        use_graph="graph" in best_strategy,
        use_rerank="rerank" in best_strategy,
        reason=(
            "Upper-bound router: chooses the best historical strategy for this question_type."
        ),
    )


def avg_metric(
    records: dict[tuple[str, str], dict[str, Any]],
    sample_ids: list[str],
    strategy: str,
    metric: str,
) -> float:
    values = [
        records[(sample_id, strategy)][metric]
        for sample_id in sample_ids
        if (sample_id, strategy) in records
    ]
    if not values:
        return 0.0
    return sum(values) / len(values)


def selected_record(
    sample: dict[str, Any],
    decision: RouterDecision,
    records: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    base = records[(sample["sample_id"], decision.selected_strategy)]
    output = dict(base)
    output["run_id"] = RUN_ID
    output["strategy"] = decision.router_name
    output.update(decision.to_dict())
    return output


def aggregate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        groups.setdefault(record["strategy"], []).append(record)

    rows = []
    for strategy, items in sorted(groups.items()):
        rows.append(
            {
                "strategy": strategy,
                "samples": len(items),
                "hit_at_5": round(sum(i["hit_at_k"] for i in items) / len(items), 4),
                "recall_at_5": round(
                    sum(i["recall_at_k"] for i in items) / len(items), 4
                ),
                "mrr": round(sum(i["mrr"] for i in items) / len(items), 4),
                "context_precision": round(
                    sum(i["context_precision"] for i in items) / len(items), 4
                ),
                "context_recall": round(
                    sum(i["context_recall"] for i in items) / len(items), 4
                ),
                "latency_ms": round(sum(i["latency_ms"] for i in items) / len(items), 2),
                "all_evidence_hit_samples": sum(
                    1
                    for i in items
                    if i["hit_evidence_count"] == i["expected_evidence_count"]
                ),
                "rerank_used_samples": sum(1 for i in items if i["use_rerank"]),
                "graph_used_samples": sum(1 for i in items if i["use_graph"]),
            }
        )

    rows.sort(
        key=lambda row: (
            -row["recall_at_5"],
            -row["mrr"],
            -row["context_precision"],
            row["latency_ms"],
        )
    )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(summary: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> None:
    fields = [
        "strategy",
        "hit_at_5",
        "recall_at_5",
        "mrr",
        "context_precision",
        "latency_ms",
        "all_evidence_hit_samples",
        "rerank_used_samples",
        "graph_used_samples",
    ]
    lines = [
        "# Query Router Ablation v0 Summary",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in summary:
        lines.append("| " + " | ".join(str(row[field]) for field in fields) + " |")

    lines.extend(
        [
            "",
            "## Router Decision Counts",
            "",
            "| router_name | route | selected_strategy | count |",
            "| --- | --- | --- | ---: |",
        ]
    )
    counts: dict[tuple[str, str, str], int] = {}
    for decision in decisions:
        key = (
            decision["router_name"],
            decision["route"],
            decision["selected_strategy"],
        )
        counts[key] = counts.get(key, 0) + 1
    for (router_name, route, selected_strategy), count in sorted(counts.items()):
        lines.append(f"| {router_name} | {route} | {selected_strategy} | {count} |")

    (OUTPUT_DIR / "query_router_ablation_v0_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    if not RERANK_RECORDS_PATH.exists():
        raise FileNotFoundError(
            f"Missing {RERANK_RECORDS_PATH}. Run run_rerank_ablation_v0.py first."
        )

    samples = load_jsonl(DATASET_PATH)
    samples_by_id = {sample["sample_id"]: sample for sample in samples}
    cached_records = load_strategy_records(RERANK_RECORDS_PATH)
    output_records = []
    decisions = []

    for sample in samples:
        router_decisions = [
            safe_router(sample),
            graph_rerank_router(sample),
            always_q015_rerank_router(sample),
            oracle_type_router(sample, cached_records, samples_by_id),
        ]
        for decision in router_decisions:
            output_records.append(selected_record(sample, decision, cached_records))
            decisions.append(
                {
                    "sample_id": sample["sample_id"],
                    "question_type": sample["question_type"],
                    "question": sample["question"],
                    **decision.to_dict(),
                }
            )

    summary = aggregate(output_records)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT_DIR / "query_router_ablation_v0_records.csv", output_records)
    write_csv(OUTPUT_DIR / "query_router_ablation_v0_summary.csv", summary)
    write_csv(OUTPUT_DIR / "query_router_ablation_v0_decisions.csv", decisions)
    with (OUTPUT_DIR / "query_router_ablation_v0_records.jsonl").open(
        "w", encoding="utf-8"
    ) as f:
        for record in output_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    write_markdown(summary, decisions)

    print(f"Saved outputs to {OUTPUT_DIR}")
    for row in summary:
        print(row)


if __name__ == "__main__":
    main()
