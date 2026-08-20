import asyncio
import csv
import json
import re
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

from hybrid_retrieval import BM25Retriever, load_chunks_from_text_store, normalize
from lightrag import LightRAG, QueryParam
from lightrag.llm.ollama import ollama_embed, ollama_model_complete
from lightrag.utils import EmbeddingFunc


DATASET_PATH = EVALUATION_DIR / "datasets" / "eval_v0_20.jsonl"
OUTPUT_DIR = EVALUATION_DIR / "results" / "retrieval_eval_v0"
RUN_ID = "retrieval_eval_v0_001"
K_VALUES = [1, 3, 5, 10]
MAX_K = max(K_VALUES)

LLM_MODEL = "qwen2.5:3b"
EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_DIM = 768
OLLAMA_HOST = "http://localhost:11434"

STORAGE_SPECS = [
    {
        "name": "structure_aware",
        "storage_dir": MINI_DIR / "storage_structure_aware",
        "text_chunks": MINI_DIR
        / "storage_structure_aware"
        / "kv_store_text_chunks.json",
    },
    {
        "name": "multimodal",
        "storage_dir": MINI_DIR / "storage_multimodal",
        "text_chunks": MINI_DIR / "storage_multimodal" / "kv_store_text_chunks.json",
    },
]


@dataclass
class StoreRuntime:
    name: str
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


def load_corpus() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    all_chunks = []
    chunks_by_store = {}
    for spec in STORAGE_SPECS:
        raw = json.loads(spec["text_chunks"].read_text(encoding="utf-8"))
        chunks = load_chunks_from_text_store(raw)
        for chunk in chunks:
            chunk["store_name"] = spec["name"]
        chunks_by_store[spec["name"]] = chunks
        all_chunks.extend(chunks)
    return all_chunks, chunks_by_store


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


async def build_store_runtimes(
    chunks_by_store: dict[str, list[dict[str, Any]]]
) -> list[StoreRuntime]:
    runtimes = []
    for spec in STORAGE_SPECS:
        runtimes.append(
            StoreRuntime(
                name=spec["name"],
                storage_dir=spec["storage_dir"],
                chunks=chunks_by_store[spec["name"]],
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
        "store_name": chunk.get("store_name"),
        "content": chunk.get("content", ""),
        "rank": rank,
        "score": score,
        "source": strategy,
        "metadata": chunk.get("metadata") or {},
    }


def bm25_retrieve(
    query: str,
    chunks: list[dict[str, Any]],
    top_k: int,
    content_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    filtered = chunks
    if content_types:
        wanted = set(content_types)
        filtered = [chunk for chunk in chunks if chunk.get("content_type") in wanted]
    if not filtered:
        return []
    retriever = BM25Retriever(filtered)
    return [
        to_candidate(candidate.to_dict(), "bm25", rank, candidate.score)
        for rank, candidate in enumerate(retriever.retrieve(query, top_k), start=1)
    ]


async def vector_retrieve(
    query: str,
    runtimes: list[StoreRuntime],
    chunks_by_id: dict[str, dict[str, Any]],
    top_k: int,
    content_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    candidates = []
    for runtime in runtimes:
        results = await runtime.rag.chunks_vdb.query(query, top_k=top_k)
        ids = [item["id"] for item in results]
        rows = await runtime.rag.text_chunks.get_by_ids(ids)
        for result, row in zip(results, rows):
            row = row or {}
            chunk = chunks_by_id[result["id"]]
            content_type = row.get("content_type") or chunk.get("content_type")
            if content_types and content_type not in set(content_types):
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
                    "vector",
                    rank=0,
                    score=float(result.get("distance", 0.0)),
                )
            )

    candidates.sort(key=lambda item: (-(item["score"] or 0.0), item["chunk_id"]))
    for rank, candidate in enumerate(candidates[:top_k], start=1):
        candidate["rank"] = rank
    return candidates[:top_k]


async def graph_retrieve(
    query: str,
    runtimes: list[StoreRuntime],
    chunks_by_content: dict[str, dict[str, Any]],
    mode: str,
    top_k: int,
) -> list[dict[str, Any]]:
    matched = []
    seen = set()
    for runtime in runtimes:
        context = await runtime.rag.aquery(
            query,
            param=QueryParam(
                mode=mode,
                top_k=top_k,
                chunk_top_k=top_k,
                only_need_context=True,
                enable_rerank=False,
                stream=False,
            ),
        )
        for chunk in extract_chunks_from_context(context, chunks_by_content):
            if chunk["chunk_id"] in seen:
                continue
            seen.add(chunk["chunk_id"])
            matched.append(chunk)

    return [
        to_candidate(chunk, mode, rank, 1.0 / rank)
        for rank, chunk in enumerate(matched[:top_k], start=1)
    ]


def extract_chunks_from_context(
    context: str, chunks_by_content: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    contents = []
    for line in (context or "").splitlines():
        line = line.strip()
        if not (line.startswith("{") and '"content"' in line):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = parsed.get("content")
        if isinstance(content, str) and content.strip():
            contents.append(content)

    matched = []
    seen = set()
    for content in contents:
        chunk = chunks_by_content.get(normalize(content))
        if chunk and chunk["chunk_id"] not in seen:
            matched.append(chunk)
            seen.add(chunk["chunk_id"])

    if matched:
        return matched

    normalized_context = normalize(context)
    positioned = []
    for content_key, chunk in chunks_by_content.items():
        position = normalized_context.find(content_key)
        if position >= 0:
            positioned.append((position, chunk))
    positioned.sort(key=lambda item: (item[0], item[1]["chunk_id"]))
    return [chunk for _, chunk in positioned]


def rrf_fuse(candidate_lists: dict[str, list[dict[str, Any]]], top_k: int) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for source, candidates in candidate_lists.items():
        for rank, candidate in enumerate(candidates, start=1):
            item = merged.setdefault(
                candidate["chunk_id"],
                {**candidate, "sources": {}, "metadata": dict(candidate.get("metadata") or {})},
            )
            item["sources"][source] = {
                "rank": rank,
                "score": candidate.get("score"),
            }

    fused = []
    for item in merged.values():
        score = sum(1.0 / (60 + src["rank"]) for src in item["sources"].values())
        item = {**item}
        item["score"] = score
        item["source"] = "rrf"
        item["metadata"] = {**item.get("metadata", {}), "rrf_score": score}
        fused.append(item)

    fused.sort(
        key=lambda item: (
            -(item["score"] or 0.0),
            min(src["rank"] for src in item["sources"].values()),
            item["chunk_id"],
        )
    )
    for rank, item in enumerate(fused[:top_k], start=1):
        item["rank"] = rank
    return fused[:top_k]


async def router_retrieve(
    sample: dict[str, Any],
    chunks: list[dict[str, Any]],
    runtimes: list[StoreRuntime],
    chunks_by_id: dict[str, dict[str, Any]],
    chunks_by_content: dict[str, dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    qtype = sample["question_type"]
    query = sample["question"]
    if qtype == "table":
        return bm25_retrieve(query, chunks, top_k, content_types=["table"])
    if qtype == "image":
        return bm25_retrieve(query, chunks, top_k, content_types=["image"])
    if qtype in {"fact", "numeric", "entity_relation"}:
        return bm25_retrieve(query, chunks, top_k)

    bm25 = bm25_retrieve(query, chunks, top_k=MAX_K)
    vector = await vector_retrieve(query, runtimes, chunks_by_id, top_k=MAX_K)
    graph = await graph_retrieve(query, runtimes, chunks_by_content, mode="hybrid", top_k=MAX_K)
    return rrf_fuse({"bm25": bm25, "vector": vector, "graph": graph}, top_k=top_k)


def evidence_hits(candidates: list[dict[str, Any]], sample: dict[str, Any]) -> dict[str, int]:
    hits: dict[str, int] = {}
    for rank, candidate in enumerate(candidates, start=1):
        content = candidate.get("content", "")
        chunk_id = candidate.get("chunk_id")
        for evidence in sample["expected_evidence"]:
            if not evidence.get("must_hit", True):
                continue
            evidence_id = evidence["evidence_id"]
            if evidence_id in hits:
                continue
            text_hit = normalize(evidence["evidence_text"]) in normalize(content)
            chunk_hit = evidence.get("chunk_id") and evidence.get("chunk_id") == chunk_id
            if text_hit or chunk_hit:
                hits[evidence_id] = rank
    return hits


def relevant_chunk_count(candidates: list[dict[str, Any]], sample: dict[str, Any]) -> int:
    count = 0
    for candidate in candidates:
        content = candidate.get("content", "")
        chunk_id = candidate.get("chunk_id")
        for evidence in sample["expected_evidence"]:
            if not evidence.get("must_hit", True):
                continue
            if normalize(evidence["evidence_text"]) in normalize(content):
                count += 1
                break
            if evidence.get("chunk_id") and evidence.get("chunk_id") == chunk_id:
                count += 1
                break
    return count


def metric_record(
    sample: dict[str, Any],
    strategy: str,
    candidates: list[dict[str, Any]],
    k: int,
    latency_ms: float,
) -> dict[str, Any]:
    top_candidates = candidates[:k]
    required_evidence = [e for e in sample["expected_evidence"] if e.get("must_hit", True)]
    hits = evidence_hits(top_candidates, sample)
    first_hit_rank = min(hits.values()) if hits else None
    returned = len(top_candidates)
    relevant_chunks = relevant_chunk_count(top_candidates, sample)

    return {
        "run_id": RUN_ID,
        "sample_id": sample["sample_id"],
        "question_type": sample["question_type"],
        "difficulty": sample["difficulty"],
        "modalities": " | ".join(sample["modalities"]),
        "strategy": strategy,
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
        "content_types": " | ".join(candidate.get("content_type", "") for candidate in top_candidates),
        "hit_evidence_ids": " | ".join(sorted(hits)),
        "question": sample["question"],
    }


async def retrieve_strategy(
    strategy: str,
    sample: dict[str, Any],
    chunks: list[dict[str, Any]],
    runtimes: list[StoreRuntime],
    chunks_by_id: dict[str, dict[str, Any]],
    chunks_by_content: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], float]:
    started = time.perf_counter()
    query = sample["question"]

    if strategy == "bm25":
        candidates = bm25_retrieve(query, chunks, MAX_K)
    elif strategy == "vector":
        candidates = await vector_retrieve(query, runtimes, chunks_by_id, MAX_K)
    elif strategy == "graph_hybrid":
        candidates = await graph_retrieve(query, runtimes, chunks_by_content, "hybrid", MAX_K)
    elif strategy == "mix":
        candidates = await graph_retrieve(query, runtimes, chunks_by_content, "mix", MAX_K)
    elif strategy == "router":
        candidates = await router_retrieve(
            sample, chunks, runtimes, chunks_by_id, chunks_by_content, MAX_K
        )
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    latency_ms = (time.perf_counter() - started) * 1000
    return candidates, latency_ms


def aggregate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for record in records:
        groups.setdefault((record["strategy"], record["k"]), []).append(record)

    rows = []
    for (strategy, k), items in sorted(groups.items()):
        rows.append(
            {
                "strategy": strategy,
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


def write_outputs(records: list[dict[str, Any]], summary: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = OUTPUT_DIR / "retrieval_eval_v0_records.jsonl"
    records_csv = OUTPUT_DIR / "retrieval_eval_v0_records.csv"
    summary_csv = OUTPUT_DIR / "retrieval_eval_v0_summary.csv"

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


async def main() -> None:
    samples = load_jsonl(DATASET_PATH)
    chunks, chunks_by_store = load_corpus()
    chunks_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    chunks_by_content = {normalize(chunk["content"]): chunk for chunk in chunks}
    runtimes = await build_store_runtimes(chunks_by_store)

    strategies = ["bm25", "vector", "graph_hybrid", "mix", "router"]
    records = []
    try:
        print(
            f"Running retrieval eval: samples={len(samples)} chunks={len(chunks)} "
            f"strategies={strategies}",
            flush=True,
        )
        for sample in samples:
            print(f"Running {sample['sample_id']} {sample['question_type']} ...", flush=True)
            for strategy in strategies:
                candidates, latency_ms = await retrieve_strategy(
                    strategy,
                    sample,
                    chunks,
                    runtimes,
                    chunks_by_id,
                    chunks_by_content,
                )
                for k in K_VALUES:
                    records.append(metric_record(sample, strategy, candidates, k, latency_ms))
                k5 = records[-2]
                print(
                    f"  {strategy} K=5 recall={k5['recall_at_k']} "
                    f"hit={k5['hit_at_k']} chunks={k5['chunk_ids']}",
                    flush=True,
                )
    finally:
        for runtime in runtimes:
            await runtime.rag.finalize_storages()

    summary = aggregate(records)
    write_outputs(records, summary)

    print("\nSummary @ K=5")
    for row in summary:
        if row["k"] == 5:
            print(
                f"  {row['strategy']}: hit={row['avg_hit_at_k']:.3f} "
                f"recall={row['avg_recall_at_k']:.3f} "
                f"mrr={row['avg_mrr']:.3f} "
                f"precision={row['avg_context_precision']:.3f} "
                f"latency={row['avg_latency_ms']:.2f}ms",
                flush=True,
            )
    print(f"Saved outputs to {OUTPUT_DIR}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
