import asyncio
import csv
import json
import sys
import time
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any


EVALUATION_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = EVALUATION_DIR.parents[1]
MINI_DIR = REPO_DIR / "experiments" / "baseline_industry_mini"
sys.path.insert(0, str(MINI_DIR))

from hybrid_retrieval import BM25Retriever, load_chunks_from_text_store, normalize  # noqa: E402
from lightrag import LightRAG  # noqa: E402
from lightrag.llm.ollama import ollama_embed, ollama_model_complete  # noqa: E402
from lightrag.utils import EmbeddingFunc  # noqa: E402


DATASET_PATH = EVALUATION_DIR / "datasets" / "eval_v0_20.jsonl"
OUTPUT_DIR = EVALUATION_DIR / "results" / "chunking_ablation_v0"
RUN_ID = "chunking_ablation_v0_001"

LLM_MODEL = "qwen2.5:3b"
EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_DIM = 768
OLLAMA_HOST = "http://localhost:11434"

K_VALUES = [1, 3, 5]
MAX_K = max(K_VALUES)
STRATEGIES = ["bm25", "vector"]

STORAGE_SPECS = [
    {
        "chunking_strategy": "fixed",
        "storage_dir": MINI_DIR / "storage",
        "text_chunks": MINI_DIR / "storage" / "kv_store_text_chunks.json",
    },
    {
        "chunking_strategy": "structure_aware",
        "storage_dir": MINI_DIR / "storage_structure_aware",
        "text_chunks": MINI_DIR
        / "storage_structure_aware"
        / "kv_store_text_chunks.json",
    },
]


@dataclass
class ChunkingRuntime:
    chunking_strategy: str
    storage_dir: Path
    chunks: list[dict[str, Any]]
    rag: LightRAG


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_text_samples() -> list[dict[str, Any]]:
    samples = load_jsonl(DATASET_PATH)
    return [
        sample
        for sample in samples
        if sample["sample_id"] <= "EVAL-0015"
        and set(sample.get("modalities", [])) == {"text"}
    ]


def load_chunks(spec: dict[str, Any]) -> list[dict[str, Any]]:
    raw = json.loads(spec["text_chunks"].read_text(encoding="utf-8"))
    chunks = load_chunks_from_text_store(raw)
    for chunk in chunks:
        chunk["chunking_strategy"] = spec["chunking_strategy"]
    return chunks


async def build_rag(storage_dir: Path) -> LightRAG:
    rag = LightRAG(
        working_dir=str(storage_dir),
        llm_model_func=ollama_model_complete,
        llm_model_name=LLM_MODEL,
        summary_max_tokens=800,
        llm_model_kwargs={
            "host": OLLAMA_HOST,
            "options": {"num_ctx": 4096, "temperature": 0},
            "timeout": 300,
        },
        embedding_func=EmbeddingFunc(
            embedding_dim=EMBEDDING_DIM,
            max_token_size=8192,
            model_name=EMBEDDING_MODEL,
            func=partial(
                ollama_embed.func,
                embed_model=EMBEDDING_MODEL,
                host=OLLAMA_HOST,
            ),
        ),
        chunk_token_size=120,
        chunk_overlap_token_size=0,
        entity_extract_max_gleaning=0,
        enable_content_headings=True,
    )
    await rag.initialize_storages()
    return rag


async def build_runtimes() -> list[ChunkingRuntime]:
    runtimes = []
    for spec in STORAGE_SPECS:
        chunks = load_chunks(spec)
        runtimes.append(
            ChunkingRuntime(
                chunking_strategy=spec["chunking_strategy"],
                storage_dir=spec["storage_dir"],
                chunks=chunks,
                rag=await build_rag(spec["storage_dir"]),
            )
        )
    return runtimes


def to_candidate(
    chunk: dict[str, Any],
    strategy: str,
    rank: int,
    score: float | None,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk["chunk_id"],
        "document_id": chunk.get("document_id"),
        "file_path": chunk.get("file_path"),
        "heading": chunk.get("heading"),
        "content_type": chunk.get("content_type") or "text",
        "content": chunk.get("content", ""),
        "rank": rank,
        "score": score,
        "source": strategy,
    }


def bm25_retrieve(query: str, chunks: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    retriever = BM25Retriever(chunks)
    return [
        to_candidate(candidate.to_dict(), "bm25", rank, candidate.score)
        for rank, candidate in enumerate(retriever.retrieve(query, top_k), start=1)
    ]


async def vector_retrieve(
    query: str,
    runtime: ChunkingRuntime,
    chunks_by_id: dict[str, dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    results = await runtime.rag.chunks_vdb.query(query, top_k=top_k)
    ids = [item["id"] for item in results]
    rows = await runtime.rag.text_chunks.get_by_ids(ids)
    candidates = []
    for rank, (result, row) in enumerate(zip(results, rows), start=1):
        row = row or {}
        chunk = chunks_by_id[result["id"]]
        merged = {
            **chunk,
            "content": row.get("content", chunk.get("content", "")),
            "content_type": row.get("content_type") or chunk.get("content_type") or "text",
            "metadata": row.get("metadata") or chunk.get("metadata") or {},
        }
        candidates.append(
            to_candidate(
                merged,
                "vector",
                rank=rank,
                score=float(result.get("distance", 0.0)),
            )
        )
    return candidates[:top_k]


def evidence_hits(candidates: list[dict[str, Any]], sample: dict[str, Any]) -> dict[str, int]:
    hits = {}
    for rank, candidate in enumerate(candidates, start=1):
        content = normalize(candidate.get("content", ""))
        for evidence in sample["expected_evidence"]:
            if not evidence.get("must_hit", True):
                continue
            evidence_id = evidence["evidence_id"]
            if evidence_id in hits:
                continue
            if normalize(evidence["evidence_text"]) in content:
                hits[evidence_id] = rank
    return hits


def relevant_chunk_count(candidates: list[dict[str, Any]], sample: dict[str, Any]) -> int:
    count = 0
    for candidate in candidates:
        content = normalize(candidate.get("content", ""))
        if any(
            evidence.get("must_hit", True)
            and normalize(evidence["evidence_text"]) in content
            for evidence in sample["expected_evidence"]
        ):
            count += 1
    return count


def metric_record(
    sample: dict[str, Any],
    chunking_strategy: str,
    retrieval_strategy: str,
    candidates: list[dict[str, Any]],
    k: int,
    latency_ms: float,
) -> dict[str, Any]:
    top_candidates = candidates[:k]
    required_evidence = [e for e in sample["expected_evidence"] if e.get("must_hit", True)]
    hits = evidence_hits(top_candidates, sample)
    first_hit_rank = min(hits.values()) if hits else None
    relevant_chunks = relevant_chunk_count(top_candidates, sample)
    returned = len(top_candidates)

    return {
        "run_id": RUN_ID,
        "sample_id": sample["sample_id"],
        "question_type": sample["question_type"],
        "difficulty": sample["difficulty"],
        "chunking_strategy": chunking_strategy,
        "retrieval_strategy": retrieval_strategy,
        "k": k,
        "expected_evidence_count": len(required_evidence),
        "hit_evidence_count": len(hits),
        "hit_at_k": 1 if hits else 0,
        "recall_at_k": round(len(hits) / max(len(required_evidence), 1), 4),
        "mrr": round(1.0 / first_hit_rank, 4) if first_hit_rank else 0.0,
        "context_precision": round(relevant_chunks / max(returned, 1), 4),
        "context_recall": round(len(hits) / max(len(required_evidence), 1), 4),
        "latency_ms": round(latency_ms, 2),
        "returned_chunks": returned,
        "chunk_ids": " | ".join(candidate["chunk_id"] for candidate in top_candidates),
        "question": sample["question"],
    }


def chunk_stats(runtime: ChunkingRuntime) -> dict[str, Any]:
    chunks = runtime.chunks
    lengths = [len(chunk.get("content", "")) for chunk in chunks]
    tiny_chunks = [chunk for chunk in chunks if len(chunk.get("content", "")) < 80]
    headed_chunks = [chunk for chunk in chunks if chunk.get("heading")]
    return {
        "chunking_strategy": runtime.chunking_strategy,
        "chunk_count": len(chunks),
        "avg_chars": round(sum(lengths) / max(len(lengths), 1), 2),
        "min_chars": min(lengths) if lengths else 0,
        "max_chars": max(lengths) if lengths else 0,
        "tiny_chunk_count_lt_80_chars": len(tiny_chunks),
        "heading_coverage": round(len(headed_chunks) / max(len(chunks), 1), 4),
    }


def aggregate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    for record in records:
        key = (
            record["chunking_strategy"],
            record["retrieval_strategy"],
            record["k"],
        )
        groups.setdefault(key, []).append(record)

    rows = []
    for (chunking_strategy, retrieval_strategy, k), items in sorted(groups.items()):
        rows.append(
            {
                "chunking_strategy": chunking_strategy,
                "retrieval_strategy": retrieval_strategy,
                "k": k,
                "samples": len(items),
                "avg_hit_at_k": round(sum(i["hit_at_k"] for i in items) / len(items), 4),
                "avg_recall_at_k": round(sum(i["recall_at_k"] for i in items) / len(items), 4),
                "avg_mrr": round(sum(i["mrr"] for i in items) / len(items), 4),
                "avg_context_precision": round(
                    sum(i["context_precision"] for i in items) / len(items), 4
                ),
                "avg_context_recall": round(
                    sum(i["context_recall"] for i in items) / len(items), 4
                ),
                "avg_latency_ms": round(sum(i["latency_ms"] for i in items) / len(items), 2),
                "all_evidence_hit_samples": sum(
                    1
                    for i in items
                    if i["hit_evidence_count"] == i["expected_evidence_count"]
                ),
            }
        )
    return rows


def write_outputs(
    records: list[dict[str, Any]],
    summary: list[dict[str, Any]],
    stats: list[dict[str, Any]],
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records_jsonl = OUTPUT_DIR / "chunking_ablation_v0_records.jsonl"
    records_csv = OUTPUT_DIR / "chunking_ablation_v0_records.csv"
    summary_csv = OUTPUT_DIR / "chunking_ablation_v0_summary.csv"
    stats_csv = OUTPUT_DIR / "chunking_ablation_v0_chunk_stats.csv"

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

    if stats:
        with stats_csv.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(stats[0].keys()))
            writer.writeheader()
            writer.writerows(stats)


async def main() -> None:
    samples = load_text_samples()
    runtimes = await build_runtimes()
    records = []
    stats = [chunk_stats(runtime) for runtime in runtimes]
    try:
        print(
            f"Running chunking ablation: samples={len(samples)} "
            f"strategies={STRATEGIES} k={K_VALUES}",
            flush=True,
        )
        for runtime in runtimes:
            chunks_by_id = {chunk["chunk_id"]: chunk for chunk in runtime.chunks}
            for sample in samples:
                for strategy in STRATEGIES:
                    started = time.perf_counter()
                    if strategy == "bm25":
                        candidates = bm25_retrieve(sample["question"], runtime.chunks, MAX_K)
                    elif strategy == "vector":
                        candidates = await vector_retrieve(
                            sample["question"], runtime, chunks_by_id, MAX_K
                        )
                    else:
                        raise ValueError(strategy)
                    latency_ms = (time.perf_counter() - started) * 1000
                    for k in K_VALUES:
                        records.append(
                            metric_record(
                                sample,
                                runtime.chunking_strategy,
                                strategy,
                                candidates,
                                k,
                                latency_ms,
                            )
                        )
        summary = aggregate(records)
        write_outputs(records, summary, stats)
    finally:
        for runtime in runtimes:
            await runtime.rag.finalize_storages()

    print(f"Saved outputs to {OUTPUT_DIR}", flush=True)
    for row in summary:
        print(row, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
