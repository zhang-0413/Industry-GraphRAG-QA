import asyncio
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Any


EVALUATION_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = EVALUATION_DIR.parents[1]
MINI_DIR = REPO_DIR / "experiments" / "baseline_industry_mini"
sys.path.insert(0, str(EVALUATION_DIR / "scripts"))
sys.path.insert(0, str(MINI_DIR))

from hybrid_retrieval import LocalReranker  # noqa: E402
from run_retrieval_eval_v0 import (  # noqa: E402
    DATASET_PATH,
    MAX_K,
    bm25_retrieve,
    build_store_runtimes,
    evidence_hits,
    graph_retrieve,
    load_corpus,
    load_jsonl,
    metric_record,
    normalize,
    rrf_fuse,
    vector_retrieve,
)


RUN_ID = "rerank_ablation_v0_001"
OUTPUT_DIR = EVALUATION_DIR / "results" / "rerank_ablation_v0"
FINAL_TOP_K = 5
CANDIDATE_TOP_K = 10

TOKEN_RE = re.compile(r"[a-z]+(?:-[a-z0-9]+)+|\d+(?:\.\d+)?|[a-z0-9]{3,}")
STOPWORDS = {
    "the",
    "and",
    "for",
    "from",
    "that",
    "this",
    "with",
    "what",
    "which",
    "where",
    "when",
    "does",
    "did",
    "was",
    "were",
    "is",
    "are",
    "according",
    "after",
    "before",
    "during",
    "must",
    "should",
    "would",
    "could",
    "into",
    "onto",
    "through",
    "about",
    "than",
}


class QueryAwareLocalReranker:
    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int,
        sample: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        scored = []
        query_terms = key_terms(query)
        query_entities = [term for term in query_terms if is_entity_like(term)]
        wanted_types = wanted_content_types(sample or {})
        for pre_rank, candidate in enumerate(candidates, start=1):
            score, reasons = self._score(candidate, query_terms, query_entities, wanted_types)
            item = {**candidate}
            item["metadata"] = {
                **candidate.get("metadata", {}),
                "pre_rerank_rank": pre_rank,
                "rerank_score": score,
                "rerank_reasons": reasons,
            }
            scored.append(item)

        scored.sort(
            key=lambda item: (
                -item["metadata"]["rerank_score"],
                item["metadata"]["pre_rerank_rank"],
                item["chunk_id"],
            )
        )
        for rank, item in enumerate(scored[:top_k], start=1):
            item["rank"] = rank
            item["source"] = f"{item.get('source', 'rrf')}_query_rerank"
        return scored[:top_k]

    def _score(
        self,
        candidate: dict[str, Any],
        query_terms: list[str],
        query_entities: list[str],
        wanted_types: set[str],
    ) -> tuple[float, list[str]]:
        text = normalize(candidate.get("content", ""))
        heading = normalize(candidate.get("heading") or "")
        score = 0.0
        reasons = []

        for term in query_terms:
            if term in text:
                weight = 3.0 if is_entity_like(term) else 1.0
                score += weight
                reasons.append(f"query_term:{term}+{weight:g}")
            elif term in heading:
                score += 1.5
                reasons.append(f"heading:{term}+1.5")

        entity_hits = sum(1 for term in query_entities if term in text)
        if entity_hits >= 2:
            bonus = entity_hits * 1.5
            score += bonus
            reasons.append(f"entity_coverage:{entity_hits}+{bonus:g}")

        content_type = candidate.get("content_type") or "text"
        if wanted_types and content_type in wanted_types:
            score += 4.0
            reasons.append(f"content_type:{content_type}+4")

        sources = candidate.get("sources") or {}
        if len(sources) >= 2:
            score += 1.0
            reasons.append("multi_source+1")

        rrf_score = candidate.get("metadata", {}).get("rrf_score")
        if isinstance(rrf_score, (int, float)):
            score += rrf_score * 10
            reasons.append("rrf_prior")

        return score, reasons


def key_terms(text: str) -> list[str]:
    terms = []
    for token in TOKEN_RE.findall(normalize(text)):
        if token in STOPWORDS:
            continue
        if len(token) < 3 and not any(ch.isdigit() for ch in token):
            continue
        terms.append(token)
    return terms


def is_entity_like(term: str) -> bool:
    return "-" in term or any(ch.isdigit() for ch in term)


def wanted_content_types(sample: dict[str, Any]) -> set[str]:
    qtype = sample.get("question_type")
    modalities = set(sample.get("modalities") or [])
    wanted = set()
    if qtype == "table" or "table" in modalities:
        wanted.add("table")
    if qtype == "image" or "image" in modalities:
        wanted.add("image")
    return wanted


def q015_local_rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    reranker = LocalReranker()
    ranked = reranker.rerank(query, candidates, top_k)
    for rank, candidate in enumerate(ranked, start=1):
        candidate["rank"] = rank
        candidate["source"] = f"{candidate.get('source', 'rrf')}_q015_rerank"
    return ranked


def ranks_by_evidence(
    candidates: list[dict[str, Any]], sample: dict[str, Any]
) -> dict[str, int]:
    return evidence_hits(candidates, sample)


def movement_summary(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    sample: dict[str, Any],
) -> dict[str, Any]:
    before_hits = ranks_by_evidence(before, sample)
    after_hits = ranks_by_evidence(after, sample)
    improved = 0
    worsened = 0
    lost = 0
    gained = 0
    for evidence in sample["expected_evidence"]:
        if not evidence.get("must_hit", True):
            continue
        evidence_id = evidence["evidence_id"]
        before_rank = before_hits.get(evidence_id)
        after_rank = after_hits.get(evidence_id)
        if before_rank and after_rank:
            if after_rank < before_rank:
                improved += 1
            elif after_rank > before_rank:
                worsened += 1
        elif before_rank and not after_rank:
            lost += 1
        elif after_rank and not before_rank:
            gained += 1
    return {
        "evidence_rank_improved": improved,
        "evidence_rank_worsened": worsened,
        "evidence_lost_after_rerank": lost,
        "evidence_gained_after_rerank": gained,
    }


async def retrieve_base_candidates(
    sample: dict[str, Any],
    chunks: list[dict[str, Any]],
    runtimes: list[Any],
    chunks_by_id: dict[str, dict[str, Any]],
    chunks_by_content: dict[str, dict[str, Any]],
) -> dict[str, tuple[list[dict[str, Any]], float]]:
    query = sample["question"]
    results: dict[str, tuple[list[dict[str, Any]], float]] = {}

    started = time.perf_counter()
    bm25 = bm25_retrieve(query, chunks, MAX_K)
    bm25_latency = (time.perf_counter() - started) * 1000
    results["bm25"] = (bm25, bm25_latency)

    started = time.perf_counter()
    vector = await vector_retrieve(query, runtimes, chunks_by_id, MAX_K)
    vector_latency = (time.perf_counter() - started) * 1000
    results["vector"] = (vector, vector_latency)

    started = time.perf_counter()
    graph = await graph_retrieve(query, runtimes, chunks_by_content, "hybrid", MAX_K)
    graph_latency = (time.perf_counter() - started) * 1000
    results["graph"] = (graph, graph_latency)

    started = time.perf_counter()
    bv = rrf_fuse({"bm25": bm25, "vector": vector}, MAX_K)
    bv_latency = bm25_latency + vector_latency + (time.perf_counter() - started) * 1000
    results["bm25_vector_rrf"] = (bv, bv_latency)

    started = time.perf_counter()
    bvg = rrf_fuse({"bm25": bm25, "vector": vector, "graph": graph}, MAX_K)
    bvg_latency = (
        bm25_latency
        + vector_latency
        + graph_latency
        + (time.perf_counter() - started) * 1000
    )
    results["bm25_vector_graph_rrf"] = (bvg, bvg_latency)
    return results


def add_record(
    records: list[dict[str, Any]],
    sample: dict[str, Any],
    strategy: str,
    candidates: list[dict[str, Any]],
    latency_ms: float,
    base_candidates: list[dict[str, Any]] | None = None,
) -> None:
    record = metric_record(sample, strategy, candidates, FINAL_TOP_K, latency_ms)
    record["run_id"] = RUN_ID
    if base_candidates is not None:
        record.update(movement_summary(base_candidates, candidates, sample))
    else:
        record.update(
            {
                "evidence_rank_improved": 0,
                "evidence_rank_worsened": 0,
                "evidence_lost_after_rerank": 0,
                "evidence_gained_after_rerank": 0,
            }
        )
    records.append(record)


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
                "top_k": FINAL_TOP_K,
                "hit_at_5": round(sum(i["hit_at_k"] for i in items) / len(items), 4),
                "recall_at_5": round(sum(i["recall_at_k"] for i in items) / len(items), 4),
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
                "rank_improved": sum(i["evidence_rank_improved"] for i in items),
                "rank_worsened": sum(i["evidence_rank_worsened"] for i in items),
                "evidence_lost_after_rerank": sum(
                    i["evidence_lost_after_rerank"] for i in items
                ),
                "evidence_gained_after_rerank": sum(
                    i["evidence_gained_after_rerank"] for i in items
                ),
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


def write_outputs(records: list[dict[str, Any]], summary: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records_jsonl = OUTPUT_DIR / "rerank_ablation_v0_records.jsonl"
    records_csv = OUTPUT_DIR / "rerank_ablation_v0_records.csv"
    summary_csv = OUTPUT_DIR / "rerank_ablation_v0_summary.csv"
    summary_md = OUTPUT_DIR / "rerank_ablation_v0_summary.md"

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

    fields = [
        "strategy",
        "hit_at_5",
        "recall_at_5",
        "mrr",
        "context_precision",
        "all_evidence_hit_samples",
        "rank_improved",
        "rank_worsened",
        "evidence_lost_after_rerank",
        "evidence_gained_after_rerank",
    ]
    lines = [
        "# Rerank Ablation v0 Summary",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in summary:
        lines.append("| " + " | ".join(str(row[field]) for field in fields) + " |")
    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> None:
    samples = load_jsonl(DATASET_PATH)
    chunks, chunks_by_store = load_corpus()
    chunks_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    chunks_by_content = {normalize(chunk["content"]): chunk for chunk in chunks}
    runtimes = await build_store_runtimes(chunks_by_store)
    query_reranker = QueryAwareLocalReranker()
    records = []

    try:
        print(
            f"Running rerank ablation: samples={len(samples)} "
            f"candidate_top_k={CANDIDATE_TOP_K} final_top_k={FINAL_TOP_K}",
            flush=True,
        )
        for sample in samples:
            print(f"Running {sample['sample_id']} {sample['question_type']} ...", flush=True)
            base = await retrieve_base_candidates(
                sample,
                chunks,
                runtimes,
                chunks_by_id,
                chunks_by_content,
            )

            for strategy in [
                "bm25",
                "vector",
                "graph",
                "bm25_vector_rrf",
                "bm25_vector_graph_rrf",
            ]:
                candidates, latency_ms = base[strategy]
                add_record(records, sample, strategy, candidates[:FINAL_TOP_K], latency_ms)

            for base_strategy in ["bm25_vector_rrf", "bm25_vector_graph_rrf"]:
                base_candidates, base_latency = base[base_strategy]
                candidate_pool = base_candidates[:CANDIDATE_TOP_K]

                started = time.perf_counter()
                query_ranked = query_reranker.rerank(
                    sample["question"], candidate_pool, FINAL_TOP_K, sample=sample
                )
                query_latency = base_latency + (time.perf_counter() - started) * 1000
                add_record(
                    records,
                    sample,
                    f"{base_strategy}_query_rerank",
                    query_ranked,
                    query_latency,
                    base_candidates[:FINAL_TOP_K],
                )

                started = time.perf_counter()
                q015_ranked = q015_local_rerank(
                    sample["question"], candidate_pool, FINAL_TOP_K
                )
                q015_latency = base_latency + (time.perf_counter() - started) * 1000
                add_record(
                    records,
                    sample,
                    f"{base_strategy}_q015_rerank",
                    q015_ranked,
                    q015_latency,
                    base_candidates[:FINAL_TOP_K],
                )
    finally:
        for runtime in runtimes:
            await runtime.rag.finalize_storages()

    summary = aggregate(records)
    write_outputs(records, summary)
    print(f"Saved outputs to {OUTPUT_DIR}", flush=True)
    for row in summary:
        print(row, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
