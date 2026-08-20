import csv
from pathlib import Path
from typing import Any


EVALUATION_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = EVALUATION_DIR / "results"
OUTPUT_DIR = RESULTS_DIR / "stage8_final_table_v0"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def find_row(rows: list[dict[str, str]], **matches: str) -> dict[str, str]:
    for row in rows:
        if all(str(row.get(key)) == str(value) for key, value in matches.items()):
            return row
    raise LookupError(f"Cannot find row matching {matches}")


def fmt(value: Any) -> str:
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == int(number):
        return str(int(number))
    return f"{number:.4f}".rstrip("0").rstrip(".")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict[str, Any]], fields: list[str]) -> list[str]:
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return lines


def main() -> None:
    chunking = read_csv(
        RESULTS_DIR / "chunking_ablation_v0" / "chunking_ablation_v0_summary.csv"
    )
    chunk_stats = read_csv(
        RESULTS_DIR / "chunking_ablation_v0" / "chunking_ablation_v0_chunk_stats.csv"
    )
    hybrid = read_csv(
        RESULTS_DIR / "hybrid_retrieval_v0" / "hybrid_retrieval_v0_summary.csv"
    )
    rerank = read_csv(
        RESULTS_DIR / "rerank_ablation_v0" / "rerank_ablation_v0_summary.csv"
    )
    router = read_csv(
        RESULTS_DIR / "query_router_ablation_v0" / "query_router_ablation_v0_summary.csv"
    )
    metadata = read_csv(
        RESULTS_DIR
        / "metadata_filter_ablation_v0"
        / "metadata_filter_ablation_v0_multimodal_summary.csv"
    )
    incremental = read_csv(
        RESULTS_DIR
        / "incremental_index_ablation_v0"
        / "incremental_index_ablation_v0_summary.csv"
    )
    final_eval = read_csv(
        RESULTS_DIR / "final_eval_v0" / "final_eval_v0_summary.csv"
    )

    fixed_bm25 = find_row(chunking, chunking_strategy="fixed", retrieval_strategy="bm25", k="5")
    struct_bm25 = find_row(
        chunking, chunking_strategy="structure_aware", retrieval_strategy="bm25", k="5"
    )
    fixed_stats = find_row(chunk_stats, chunking_strategy="fixed")
    struct_stats = find_row(chunk_stats, chunking_strategy="structure_aware")

    bm25 = find_row(hybrid, strategy="bm25", k="5")
    vector = find_row(hybrid, strategy="vector", k="5")
    graph = find_row(hybrid, strategy="graph", k="5")
    bv_rrf = find_row(hybrid, strategy="bm25_vector_rrf", k="5")
    bvg_rrf = find_row(hybrid, strategy="bm25_vector_graph_rrf", k="5")

    no_rerank = find_row(rerank, strategy="bm25_vector_rrf")
    query_rerank = find_row(rerank, strategy="bm25_vector_rrf_query_rerank")
    graph_query_rerank = find_row(rerank, strategy="bm25_vector_graph_rrf_query_rerank")
    q015_rerank = find_row(rerank, strategy="bm25_vector_rrf_q015_rerank")

    router_safe = find_row(router, strategy="router_safe")
    router_graph = find_row(router, strategy="router_graph_rerank")
    router_bad = find_row(router, strategy="router_always_q015_rerank")

    meta_filtered = find_row(metadata, strategy="router_metadata_filter")
    meta_unfiltered = find_row(metadata, strategy="bm25_vector_rrf_unfiltered")

    inc_good = find_row(incremental, strategy="incremental_with_graph_cleanup")
    full_reindex = find_row(incremental, strategy="full_reindex")
    inc_no_hash = find_row(incremental, strategy="incremental_without_hash")
    inc_no_delete = find_row(incremental, strategy="incremental_without_delete")

    final_vector = find_row(final_eval, strategy="vector")
    final_router = find_row(final_eval, strategy="router")
    final_bm25 = find_row(final_eval, strategy="bm25")

    experiment_rows = [
        {
            "stage": "8.2",
            "module": "Structure-aware Chunking",
            "baseline": "fixed+bm25 Recall@5=" + fmt(fixed_bm25["avg_recall_at_k"]),
            "optimized": "structure+bm25 Recall@5=" + fmt(struct_bm25["avg_recall_at_k"]),
            "main_gain": (
                "heading_coverage "
                + fmt(fixed_stats["heading_coverage"])
                + " -> "
                + fmt(struct_stats["heading_coverage"])
                + "; tiny_chunks "
                + fmt(fixed_stats["tiny_chunk_count_lt_80_chars"])
                + " -> "
                + fmt(struct_stats["tiny_chunk_count_lt_80_chars"])
            ),
            "engineering_decision": "Keep structure-aware chunks for metadata and stable boundaries; tune top_k/rerank for recall.",
        },
        {
            "stage": "8.3",
            "module": "Single-route Retrieval",
            "baseline": "graph Recall@5=" + fmt(graph["avg_recall_at_k"]),
            "optimized": "vector Recall@5="
            + fmt(vector["avg_recall_at_k"])
            + "; bm25 MRR="
            + fmt(bm25["avg_mrr"]),
            "main_gain": "BM25 is fastest/exact; Vector has highest broad recall; Graph is not a universal default.",
            "engineering_decision": "Use BM25 and Vector as main retrieval branches; route Graph selectively.",
        },
        {
            "stage": "8.4",
            "module": "Hybrid Retrieval",
            "baseline": "bm25 Recall@5=" + fmt(bm25["avg_recall_at_k"]),
            "optimized": "bm25+vector RRF Recall@5=" + fmt(bv_rrf["avg_recall_at_k"]),
            "main_gain": "All-evidence-hit samples "
            + fmt(bm25["all_evidence_hit_samples"])
            + " -> "
            + fmt(bv_rrf["all_evidence_hit_samples"]),
            "engineering_decision": "Default hybrid should be BM25+Vector+RRF, not naive Graph fusion.",
        },
        {
            "stage": "8.4",
            "module": "Graph Fusion",
            "baseline": "bm25+vector RRF Recall@5=" + fmt(bv_rrf["avg_recall_at_k"]),
            "optimized": "bm25+vector+graph RRF Recall@5=" + fmt(bvg_rrf["avg_recall_at_k"]),
            "main_gain": "Adding Graph directly reduced retrieval quality in this dataset.",
            "engineering_decision": "Do not put Graph into every query; use router/metadata constraints first.",
        },
        {
            "stage": "8.5",
            "module": "Rerank",
            "baseline": "bm25+vector RRF Recall@5=" + fmt(no_rerank["recall_at_5"]),
            "optimized": "query-rerank Recall@5=" + fmt(query_rerank["recall_at_5"]),
            "main_gain": "Rerank lost "
            + fmt(query_rerank["evidence_lost_after_rerank"])
            + " evidence on already-strong BM25+Vector; Q015-only rerank Recall@5="
            + fmt(q015_rerank["recall_at_5"]),
            "engineering_decision": "Enable rerank only for routed complex/global cases, not globally.",
        },
        {
            "stage": "8.5",
            "module": "Graph Noise Repair",
            "baseline": "bm25+vector+graph RRF Recall@5=" + fmt(bvg_rrf["avg_recall_at_k"]),
            "optimized": "graph+query-rerank Recall@5=" + fmt(graph_query_rerank["recall_at_5"]),
            "main_gain": "Rerank gained "
            + fmt(graph_query_rerank["evidence_gained_after_rerank"])
            + " evidence after noisy Graph fusion.",
            "engineering_decision": "If Graph is included, rerank or filtering is needed to control noise.",
        },
        {
            "stage": "8.6",
            "module": "Query Router",
            "baseline": "fixed bm25+vector RRF Recall@5=" + fmt(no_rerank["recall_at_5"]),
            "optimized": "router_safe Recall@5=" + fmt(router_safe["recall_at_5"]),
            "main_gain": "Recall improved while rerank used on only "
            + fmt(router_safe["rerank_used_samples"])
            + "/20 samples.",
            "engineering_decision": "Use router_safe as current retrieval policy backbone.",
        },
        {
            "stage": "8.6",
            "module": "Over-aggressive Graph/Rerank",
            "baseline": "router_safe Recall@5=" + fmt(router_safe["recall_at_5"]),
            "optimized": "router_graph_rerank Recall@5=" + fmt(router_graph["recall_at_5"]),
            "main_gain": "Graph/rerank used on "
            + fmt(router_graph["graph_used_samples"])
            + "/20 samples and underperformed.",
            "engineering_decision": "Complex-looking questions still need conservative routing rules.",
        },
        {
            "stage": "8.7-8.8",
            "module": "Incremental Index",
            "baseline": "full_reindex embeddings=" + fmt(full_reindex["embedding_recompute_count"]),
            "optimized": "incremental embeddings=" + fmt(inc_good["embedding_recompute_count"]),
            "main_gain": "Embedding saved ratio="
            + fmt(inc_good["embedding_saved_ratio"])
            + "; stale chunks="
            + fmt(inc_good["stale_chunk_count"]),
            "engineering_decision": "Use document_id + stable chunk_id + content_hash + version with graph cleanup.",
        },
        {
            "stage": "8.8",
            "module": "Incremental Failure Modes",
            "baseline": "without_hash stale=" + fmt(inc_no_hash["stale_chunk_count"]),
            "optimized": "without_delete stale=" + fmt(inc_no_delete["stale_chunk_count"]),
            "main_gain": "Both negative controls have query_pass_rate="
            + fmt(inc_no_hash["query_pass_rate"])
            + "/"
            + fmt(inc_no_delete["query_pass_rate"]),
            "engineering_decision": "Hash detection and delete cleanup are mandatory, not optional.",
        },
        {
            "stage": "8.9",
            "module": "Metadata Filter",
            "baseline": "unfiltered multimodal ContextPrecision="
            + fmt(meta_unfiltered["avg_context_precision"]),
            "optimized": "filtered ContextPrecision="
            + fmt(meta_filtered["avg_context_precision"]),
            "main_gain": "Candidate space reduction="
            + fmt(meta_filtered["avg_candidate_space_reduction"])
            + "; content type precision="
            + fmt(meta_filtered["avg_content_type_precision"]),
            "engineering_decision": "For table/image/multimodal queries, filter by content_type before final context.",
        },
        {
            "stage": "7",
            "module": "Answer/Judge Baseline",
            "baseline": "bm25 strict_pass=" + fmt(final_bm25["strict_pass_rate"]),
            "optimized": "vector strict_pass=" + fmt(final_vector["strict_pass_rate"]),
            "main_gain": "router has best answer coverage="
            + fmt(final_router["answer_point_coverage"])
            + " but more unsupported claims than vector.",
            "engineering_decision": "Retrieval optimization must be verified with answer and faithfulness metrics.",
        },
    ]

    recommendation_rows = [
        {
            "component": "chunking",
            "final_choice": "structure-aware chunking",
            "reason": "Preserves section metadata, removes tiny broken chunks, supports stable chunk_id/hash for incremental index.",
        },
        {
            "component": "default retrieval",
            "final_choice": "BM25 + Vector + RRF",
            "reason": "Best stable retrieval backbone in current experiments: Recall@5 0.9625, MRR 1.0.",
        },
        {
            "component": "query router",
            "final_choice": "router_safe",
            "reason": "Recall@5 0.9875 with only one routed rerank call; avoids overusing Graph/rerank.",
        },
        {
            "component": "graph retrieval",
            "final_choice": "selective, not default",
            "reason": "Graph alone and naive graph fusion underperformed; use for entity/global cases after routing.",
        },
        {
            "component": "rerank",
            "final_choice": "conditional",
            "reason": "Useful for noisy Graph/global-summary cases, harmful when applied blindly.",
        },
        {
            "component": "metadata filter",
            "final_choice": "enable for table/image/multi-hop",
            "reason": "Multimodal Context Precision improved from 0.25 to 1.0 while Recall@5 stayed 1.0.",
        },
        {
            "component": "incremental index",
            "final_choice": "chunk-level diff with graph cleanup",
            "reason": "Embedding recompute count dropped from 34 to 2 with no stale chunks.",
        },
    ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT_DIR / "stage8_final_experiment_table.csv", experiment_rows)
    write_csv(OUTPUT_DIR / "stage8_final_recommendation.csv", recommendation_rows)

    lines = [
        "# Stage 8 Final Experiment Table v0",
        "",
        "## Module-Level Conclusions",
        "",
    ]
    lines.extend(
        markdown_table(
            experiment_rows,
            [
                "stage",
                "module",
                "baseline",
                "optimized",
                "main_gain",
                "engineering_decision",
            ],
        )
    )
    lines.extend(["", "## Final Optimized Pipeline", ""])
    lines.extend(markdown_table(recommendation_rows, ["component", "final_choice", "reason"]))
    lines.append("")
    lines.append("## Recommended Pipeline")
    lines.append("")
    lines.append("```text")
    lines.append("Document -> MinerU/Parser -> Structure-aware Chunk")
    lines.append("-> document_id/chunk_id/content_hash/version")
    lines.append("-> BM25 Index + Vector Store + selective Graph Store")
    lines.append("-> Query Router")
    lines.append("-> Metadata Filter for table/image")
    lines.append("-> BM25 + Vector + RRF by default")
    lines.append("-> Conditional Graph and Conditional Rerank")
    lines.append("-> Final Top-K Context -> LLM Answer")
    lines.append("-> Retrieval/Answer/Faithfulness Evaluation")
    lines.append("```")
    (OUTPUT_DIR / "stage8_final_experiment_table.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    print(f"Saved outputs to {OUTPUT_DIR}")
    for row in experiment_rows:
        print(row)


if __name__ == "__main__":
    main()
