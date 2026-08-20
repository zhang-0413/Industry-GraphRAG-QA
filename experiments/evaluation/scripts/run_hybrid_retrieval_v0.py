import asyncio
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any


EVALUATION_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = EVALUATION_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from run_retrieval_eval_v0 import (  # noqa: E402
    DATASET_PATH,
    MAX_K,
    K_VALUES,
    aggregate,
    bm25_retrieve,
    build_store_runtimes,
    graph_retrieve,
    load_corpus,
    load_jsonl,
    metric_record,
    normalize,
    rrf_fuse,
    vector_retrieve,
)


RUN_ID = "hybrid_retrieval_v0_001"
OUTPUT_DIR = EVALUATION_DIR / "results" / "hybrid_retrieval_v0"

STRATEGIES = [
    "bm25",
    "vector",
    "graph",
    "bm25_vector_rrf",
    "bm25_vector_graph_rrf",
]


async def retrieve_all_routes(
    sample: dict[str, Any],
    chunks: list[dict[str, Any]],
    runtimes: list[Any],
    chunks_by_id: dict[str, dict[str, Any]],
    chunks_by_content: dict[str, dict[str, Any]],
) -> dict[str, tuple[list[dict[str, Any]], float]]:
    query = sample["question"]
    route_results: dict[str, tuple[list[dict[str, Any]], float]] = {}

    started = time.perf_counter()
    bm25 = bm25_retrieve(query, chunks, MAX_K)
    route_results["bm25"] = (bm25, (time.perf_counter() - started) * 1000)

    started = time.perf_counter()
    vector = await vector_retrieve(query, runtimes, chunks_by_id, MAX_K)
    route_results["vector"] = (vector, (time.perf_counter() - started) * 1000)

    started = time.perf_counter()
    graph = await graph_retrieve(query, runtimes, chunks_by_content, "hybrid", MAX_K)
    route_results["graph"] = (graph, (time.perf_counter() - started) * 1000)

    started = time.perf_counter()
    bm25_vector = rrf_fuse({"bm25": bm25, "vector": vector}, MAX_K)
    route_results["bm25_vector_rrf"] = (
        bm25_vector,
        route_results["bm25"][1] + route_results["vector"][1] + (time.perf_counter() - started) * 1000,
    )

    started = time.perf_counter()
    bm25_vector_graph = rrf_fuse(
        {"bm25": bm25, "vector": vector, "graph": graph},
        MAX_K,
    )
    route_results["bm25_vector_graph_rrf"] = (
        bm25_vector_graph,
        route_results["bm25"][1]
        + route_results["vector"][1]
        + route_results["graph"][1]
        + (time.perf_counter() - started) * 1000,
    )

    return route_results


def write_outputs(records: list[dict[str, Any]], summary: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = OUTPUT_DIR / "hybrid_retrieval_v0_records.jsonl"
    records_csv = OUTPUT_DIR / "hybrid_retrieval_v0_records.csv"
    summary_csv = OUTPUT_DIR / "hybrid_retrieval_v0_summary.csv"

    with jsonl_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    if records:
        with records_csv.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)

    if summary:
        with summary_csv.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
            writer.writeheader()
            writer.writerows(summary)


def write_markdown(summary: list[dict[str, Any]]) -> None:
    rows = [row for row in summary if int(row["k"]) == 5]
    rows.sort(
        key=lambda item: (
            -float(item["avg_recall_at_k"]),
            -float(item["avg_mrr"]),
            -float(item["avg_context_precision"]),
            float(item["avg_latency_ms"]),
        )
    )
    fields = [
        "strategy",
        "avg_hit_at_k",
        "avg_recall_at_k",
        "avg_mrr",
        "avg_context_precision",
        "avg_latency_ms",
        "all_evidence_hit_samples",
    ]
    lines = [
        "# Hybrid Retrieval v0 Summary",
        "",
        "This table compares single-route retrieval and RRF-fused hybrid retrieval at K=5.",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row[field]) for field in fields) + " |")
    lines.extend(
        [
            "",
            "Notes:",
            "",
            "- `bm25_vector_rrf` fuses BM25 and vector candidates with Reciprocal Rank Fusion.",
            "- `bm25_vector_graph_rrf` adds LightRAG graph-hybrid candidates to the same fusion.",
            "- This stage does not use rerank; rerank is evaluated separately.",
            "",
        ]
    )
    (OUTPUT_DIR / "hybrid_retrieval_v0_summary.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


async def main() -> None:
    samples = load_jsonl(DATASET_PATH)
    chunks, chunks_by_store = load_corpus()
    chunks_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    chunks_by_content = {normalize(chunk["content"]): chunk for chunk in chunks}
    runtimes = await build_store_runtimes(chunks_by_store)
    records = []

    try:
        print(
            f"Running hybrid retrieval eval: samples={len(samples)} "
            f"strategies={STRATEGIES}",
            flush=True,
        )
        for sample in samples:
            print(f"Running {sample['sample_id']} {sample['question_type']} ...", flush=True)
            route_results = await retrieve_all_routes(
                sample,
                chunks,
                runtimes,
                chunks_by_id,
                chunks_by_content,
            )
            for strategy in STRATEGIES:
                candidates, latency_ms = route_results[strategy]
                for k in K_VALUES:
                    record = metric_record(sample, strategy, candidates, k, latency_ms)
                    record["run_id"] = RUN_ID
                    records.append(record)
    finally:
        for runtime in runtimes:
            await runtime.rag.finalize_storages()

    summary = aggregate(records)
    write_outputs(records, summary)
    write_markdown(summary)

    print(f"Saved outputs to {OUTPUT_DIR}", flush=True)
    for row in summary:
        if row["k"] == 5:
            print(row, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
