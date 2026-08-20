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
    aggregate,
    bm25_retrieve,
    build_store_runtimes,
    load_corpus,
    load_jsonl,
    metric_record,
    normalize,
    rrf_fuse,
    to_candidate,
    vector_retrieve,
)


RUN_ID = "metadata_filter_ablation_v0_001"
OUTPUT_DIR = EVALUATION_DIR / "results" / "metadata_filter_ablation_v0"
K_VALUES = [1, 3, 5]


def target_content_types(sample: dict[str, Any]) -> list[str]:
    qtype = sample.get("question_type")
    modalities = {str(item).lower() for item in sample.get("modalities", [])}
    query = (sample.get("question") or "").lower()

    targets = []
    if qtype == "table" or "table" in modalities or "table" in query:
        targets.append("table")
    if qtype == "image" or "image" in modalities or "diagram" in query:
        targets.append("image")
    if not targets:
        targets.append("text")
    return targets


def is_multimodal_target(sample: dict[str, Any]) -> bool:
    targets = set(target_content_types(sample))
    return bool(targets & {"table", "image"})


def filtered_candidate_space(
    chunks: list[dict[str, Any]], content_types: list[str]
) -> int:
    wanted = set(content_types)
    return sum(1 for chunk in chunks if chunk.get("content_type") in wanted)


async def vector_metadata_post_filter(
    query: str,
    runtimes: list[Any],
    chunks_by_id: dict[str, dict[str, Any]],
    top_k: int,
    content_types: list[str],
) -> list[dict[str, Any]]:
    wanted = set(content_types)
    candidates = []

    for runtime in runtimes:
        results = await runtime.rag.chunks_vdb.query(query, top_k=len(runtime.chunks))
        ids = [item["id"] for item in results]
        rows = await runtime.rag.text_chunks.get_by_ids(ids)
        for result, row in zip(results, rows):
            row = row or {}
            chunk = chunks_by_id[result["id"]]
            content_type = row.get("content_type") or chunk.get("content_type") or "text"
            if content_type not in wanted:
                continue
            merged = {
                **chunk,
                "content": row.get("content", chunk.get("content", "")),
                "content_type": content_type,
                "metadata": row.get("metadata") or chunk.get("metadata") or {},
                "store_name": runtime.name,
            }
            candidates.append(
                to_candidate(
                    merged,
                    "vector_metadata_post_filter",
                    rank=0,
                    score=float(result.get("distance", 0.0)),
                )
            )

    candidates.sort(key=lambda item: (-(item["score"] or 0.0), item["chunk_id"]))
    for rank, candidate in enumerate(candidates[:top_k], start=1):
        candidate["rank"] = rank
    return candidates[:top_k]


async def retrieve_routes(
    sample: dict[str, Any],
    chunks: list[dict[str, Any]],
    runtimes: list[Any],
    chunks_by_id: dict[str, dict[str, Any]],
) -> dict[str, tuple[list[dict[str, Any]], float, dict[str, Any]]]:
    query = sample["question"]
    targets = target_content_types(sample)
    route_results = {}

    started = time.perf_counter()
    bm25 = bm25_retrieve(query, chunks, MAX_K)
    bm25_latency = (time.perf_counter() - started) * 1000
    route_results["bm25_unfiltered"] = (
        bm25,
        bm25_latency,
        {
            "target_content_types": "all",
            "candidate_space": len(chunks),
            "filtered_candidate_space": len(chunks),
        },
    )

    started = time.perf_counter()
    bm25_filtered = bm25_retrieve(query, chunks, MAX_K, content_types=targets)
    bm25_filtered_latency = (time.perf_counter() - started) * 1000
    route_results["bm25_metadata_filtered"] = (
        bm25_filtered,
        bm25_filtered_latency,
        {
            "target_content_types": " | ".join(targets),
            "candidate_space": len(chunks),
            "filtered_candidate_space": filtered_candidate_space(chunks, targets),
        },
    )

    started = time.perf_counter()
    vector = await vector_retrieve(query, runtimes, chunks_by_id, MAX_K)
    vector_latency = (time.perf_counter() - started) * 1000
    route_results["vector_unfiltered"] = (
        vector,
        vector_latency,
        {
            "target_content_types": "all",
            "candidate_space": len(chunks),
            "filtered_candidate_space": len(chunks),
        },
    )

    started = time.perf_counter()
    vector_filtered = await vector_metadata_post_filter(
        query, runtimes, chunks_by_id, MAX_K, targets
    )
    vector_filtered_latency = (time.perf_counter() - started) * 1000
    route_results["vector_metadata_post_filter"] = (
        vector_filtered,
        vector_filtered_latency,
        {
            "target_content_types": " | ".join(targets),
            "candidate_space": len(chunks),
            "filtered_candidate_space": filtered_candidate_space(chunks, targets),
        },
    )

    started = time.perf_counter()
    rrf = rrf_fuse({"bm25": bm25, "vector": vector}, MAX_K)
    rrf_latency = bm25_latency + vector_latency + (time.perf_counter() - started) * 1000
    route_results["bm25_vector_rrf_unfiltered"] = (
        rrf,
        rrf_latency,
        {
            "target_content_types": "all",
            "candidate_space": len(chunks),
            "filtered_candidate_space": len(chunks),
        },
    )

    started = time.perf_counter()
    filtered_rrf = rrf_fuse(
        {"bm25": bm25_filtered, "vector": vector_filtered},
        MAX_K,
    )
    filtered_rrf_latency = (
        bm25_filtered_latency
        + vector_filtered_latency
        + (time.perf_counter() - started) * 1000
    )
    route_results["bm25_vector_rrf_metadata_filtered"] = (
        filtered_rrf,
        filtered_rrf_latency,
        {
            "target_content_types": " | ".join(targets),
            "candidate_space": len(chunks),
            "filtered_candidate_space": filtered_candidate_space(chunks, targets),
        },
    )

    if is_multimodal_target(sample):
        router_candidates = filtered_rrf
        router_latency = filtered_rrf_latency
        router_info = {
            "target_content_types": " | ".join(targets),
            "candidate_space": len(chunks),
            "filtered_candidate_space": filtered_candidate_space(chunks, targets),
            "router_route": "metadata_filtered_multimodal",
        }
    else:
        router_candidates = rrf
        router_latency = rrf_latency
        router_info = {
            "target_content_types": "all",
            "candidate_space": len(chunks),
            "filtered_candidate_space": len(chunks),
            "router_route": "unfiltered_text_default",
        }
    route_results["router_metadata_filter"] = (
        router_candidates,
        router_latency,
        router_info,
    )

    return route_results


def add_metadata_fields(
    record: dict[str, Any],
    sample: dict[str, Any],
    info: dict[str, Any],
) -> dict[str, Any]:
    candidates_types = [
        item.strip()
        for item in (record.get("content_types") or "").split("|")
        if item.strip()
    ]
    expected_types = {
        evidence.get("content_type")
        for evidence in sample.get("expected_evidence", [])
        if evidence.get("must_hit", True)
    }
    matched_types = sum(1 for item in candidates_types if item in expected_types)
    record = dict(record)
    record["run_id"] = RUN_ID
    record["target_content_types"] = info.get("target_content_types", "")
    record["candidate_space"] = info.get("candidate_space", 0)
    record["filtered_candidate_space"] = info.get("filtered_candidate_space", 0)
    record["candidate_space_reduction"] = round(
        1
        - float(info.get("filtered_candidate_space", 0))
        / max(float(info.get("candidate_space", 0)), 1.0),
        4,
    )
    record["router_route"] = info.get("router_route", "")
    record["expected_content_types"] = " | ".join(sorted(expected_types))
    record["content_type_precision"] = round(
        matched_types / max(len(candidates_types), 1), 4
    )
    record["is_multimodal_target"] = is_multimodal_target(sample)
    return record


def write_outputs(records: list[dict[str, Any]], summary: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records_jsonl = OUTPUT_DIR / "metadata_filter_ablation_v0_records.jsonl"
    records_csv = OUTPUT_DIR / "metadata_filter_ablation_v0_records.csv"
    summary_csv = OUTPUT_DIR / "metadata_filter_ablation_v0_summary.csv"

    with records_jsonl.open("w", encoding="utf-8") as f:
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


def summarize_multimodal(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    filtered = [
        row
        for row in records
        if row["is_multimodal_target"] and int(row["k"]) == 5
    ]
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in filtered:
        groups.setdefault(row["strategy"], []).append(row)
    for strategy, items in groups.items():
        rows.append(
            {
                "strategy": strategy,
                "samples": len(items),
                "avg_hit_at_5": round(sum(i["hit_at_k"] for i in items) / len(items), 4),
                "avg_recall_at_5": round(
                    sum(i["recall_at_k"] for i in items) / len(items), 4
                ),
                "avg_mrr": round(sum(i["mrr"] for i in items) / len(items), 4),
                "avg_context_precision": round(
                    sum(i["context_precision"] for i in items) / len(items), 4
                ),
                "avg_content_type_precision": round(
                    sum(i["content_type_precision"] for i in items) / len(items), 4
                ),
                "avg_candidate_space_reduction": round(
                    sum(i["candidate_space_reduction"] for i in items) / len(items), 4
                ),
                "avg_latency_ms": round(
                    sum(i["latency_ms"] for i in items) / len(items), 2
                ),
            }
        )
    rows.sort(
        key=lambda row: (
            -row["avg_recall_at_5"],
            -row["avg_context_precision"],
            -row["avg_content_type_precision"],
            row["avg_latency_ms"],
        )
    )
    return rows


def write_markdown(
    full_summary: list[dict[str, Any]],
    multimodal_summary: list[dict[str, Any]],
) -> None:
    lines = [
        "# Metadata Filter Ablation v0 Summary",
        "",
        "## Multimodal subset at K=5",
        "",
    ]
    fields = [
        "strategy",
        "avg_hit_at_5",
        "avg_recall_at_5",
        "avg_mrr",
        "avg_context_precision",
        "avg_content_type_precision",
        "avg_candidate_space_reduction",
        "avg_latency_ms",
    ]
    lines.append("| " + " | ".join(fields) + " |")
    lines.append("| " + " | ".join(["---"] * len(fields)) + " |")
    for row in multimodal_summary:
        lines.append("| " + " | ".join(str(row[field]) for field in fields) + " |")

    lines.extend(
        [
            "",
            "## Full dataset at K=5",
            "",
        ]
    )
    full_rows = [row for row in full_summary if int(row["k"]) == 5]
    full_fields = [
        "strategy",
        "avg_hit_at_k",
        "avg_recall_at_k",
        "avg_mrr",
        "avg_context_precision",
        "avg_latency_ms",
    ]
    lines.append("| " + " | ".join(full_fields) + " |")
    lines.append("| " + " | ".join(["---"] * len(full_fields)) + " |")
    for row in full_rows:
        lines.append("| " + " | ".join(str(row[field]) for field in full_fields) + " |")

    lines.extend(
        [
            "",
            "Notes:",
            "",
            "- Metadata filtering uses `content_type` to narrow the candidate space.",
            "- Vector filtering is post-filtering in this experiment because NanoVectorDB is queried before filtering.",
            "- The most important subset is table/image/multi-hop, where target evidence is not plain text.",
            "",
        ]
    )
    (OUTPUT_DIR / "metadata_filter_ablation_v0_summary.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


async def main() -> None:
    samples = load_jsonl(DATASET_PATH)
    chunks, chunks_by_store = load_corpus()
    chunks_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    runtimes = await build_store_runtimes(chunks_by_store)
    records = []

    try:
        print(f"Running metadata filter ablation: samples={len(samples)}", flush=True)
        for sample in samples:
            targets = target_content_types(sample)
            print(
                f"Running {sample['sample_id']} type={sample['question_type']} "
                f"target={targets} ...",
                flush=True,
            )
            route_results = await retrieve_routes(sample, chunks, runtimes, chunks_by_id)
            for strategy, (candidates, latency_ms, info) in route_results.items():
                for k in K_VALUES:
                    record = metric_record(sample, strategy, candidates, k, latency_ms)
                    records.append(add_metadata_fields(record, sample, info))
    finally:
        for runtime in runtimes:
            await runtime.rag.finalize_storages()

    full_summary = aggregate(records)
    multimodal_summary = summarize_multimodal(records)
    write_outputs(records, full_summary)
    with (OUTPUT_DIR / "metadata_filter_ablation_v0_multimodal_summary.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        if multimodal_summary:
            writer = csv.DictWriter(f, fieldnames=list(multimodal_summary[0].keys()))
            writer.writeheader()
            writer.writerows(multimodal_summary)
    write_markdown(full_summary, multimodal_summary)

    print(f"Saved outputs to {OUTPUT_DIR}", flush=True)
    for row in multimodal_summary:
        print(row, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
