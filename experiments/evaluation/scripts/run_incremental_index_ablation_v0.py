import asyncio
import csv
import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass, replace
from functools import partial
from pathlib import Path
from typing import Any


EVALUATION_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = EVALUATION_DIR.parents[1]
MINI_DIR = REPO_DIR / "experiments" / "baseline_industry_mini"
sys.path.insert(0, str(MINI_DIR))

from hybrid_retrieval import BM25Retriever, load_chunks_from_text_store  # noqa: E402
from lightrag.llm.ollama import ollama_embed  # noqa: E402


RUN_ID = "incremental_index_ablation_v0_001"
TEXT_CHUNKS_PATH = MINI_DIR / "storage_structure_aware" / "kv_store_text_chunks.json"
OUTPUT_DIR = EVALUATION_DIR / "results" / "incremental_index_ablation_v0"
EMBEDDING_MODEL = "nomic-embed-text"
OLLAMA_HOST = "http://localhost:11434"


@dataclass(frozen=True)
class ChunkSnapshot:
    chunk_id: str
    document_id: str
    file_path: str
    content: str
    content_hash: str
    version: int
    chunk_order_index: int | None
    content_type: str
    heading: Any
    metadata: dict[str, Any]

    def to_chunk(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "file_path": self.file_path,
            "content": self.content,
            "content_type": self.content_type,
            "heading": heading_text(self.heading),
            "metadata": {
                **self.metadata,
                "content_hash": self.content_hash,
                "version": self.version,
            },
            "search_text": f"{heading_text(self.heading) or ''}\n{self.content}",
        }


@dataclass(frozen=True)
class ChunkAction:
    transition: str
    action: str
    chunk_id: str
    document_id: str
    old_hash: str | None
    new_hash: str | None
    old_version: int | None
    new_version: int | None
    affected_stores: list[str]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["affected_stores"] = " | ".join(self.affected_stores)
        row["run_id"] = RUN_ID
        return row


def normalize_for_hash(text: str) -> str:
    return "\n".join(line.rstrip() for line in (text or "").strip().splitlines())


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_for_hash(text).encode("utf-8")).hexdigest()


def heading_text(heading: Any) -> str | None:
    if isinstance(heading, dict):
        return heading.get("heading")
    if isinstance(heading, str):
        return heading
    return None


def load_v1_snapshot() -> dict[str, ChunkSnapshot]:
    raw = json.loads(TEXT_CHUNKS_PATH.read_text(encoding="utf-8"))
    chunks = load_chunks_from_text_store(raw)
    snapshots = {}
    for chunk in chunks:
        chunk_id = chunk["chunk_id"]
        raw_chunk = raw[chunk_id]
        metadata = raw_chunk.get("metadata") or {}
        content = raw_chunk.get("content", "")
        snapshots[chunk_id] = ChunkSnapshot(
            chunk_id=chunk_id,
            document_id=chunk.get("document_id") or raw_chunk.get("full_doc_id") or "",
            file_path=chunk.get("file_path") or raw_chunk.get("file_path") or "",
            content=content,
            content_hash=metadata.get("content_hash") or content_hash(content),
            version=1,
            chunk_order_index=raw_chunk.get("chunk_order_index"),
            content_type=chunk.get("content_type") or raw_chunk.get("content_type") or "text",
            heading=raw_chunk.get("heading") or chunk.get("heading"),
            metadata=metadata,
        )
    return snapshots


def make_v2_threshold_update(
    old: dict[str, ChunkSnapshot],
) -> dict[str, ChunkSnapshot]:
    new = dict(old)
    target_id = "doc_002_safety_rules-chunk-001"
    target = new[target_id]
    new_content = target.content.replace("9.5 MPa", "9.2 MPa")
    metadata = {**target.metadata, "change_note": "alarm threshold updated"}
    new[target_id] = replace(
        target,
        content=new_content,
        content_hash=content_hash(new_content),
        version=2,
        metadata=metadata,
    )
    return new


def make_v3_add_followup(
    old: dict[str, ChunkSnapshot],
) -> dict[str, ChunkSnapshot]:
    new = dict(old)
    new_content = (
        "# Incident Report IR-2024-017\n"
        "## Follow-up Verification\n\n"
        "After maintenance, the team scheduled a follow-up inspection for "
        "Filter-F33 and Pipeline-7A within 30 days."
    )
    chunk_id = "doc_003_incident_report-chunk-004"
    new[chunk_id] = ChunkSnapshot(
        chunk_id=chunk_id,
        document_id="doc_003_incident_report",
        file_path="doc_003_incident_report.md",
        content=new_content,
        content_hash=content_hash(new_content),
        version=3,
        chunk_order_index=4,
        content_type="text",
        heading={
            "level": 2,
            "heading": "Follow-up Verification",
            "parent_headings": ["Incident Report IR-2024-017"],
        },
        metadata={
            "document_id": "doc_003_incident_report",
            "file_name": "doc_003_incident_report.md",
            "chapter": "Incident Report IR-2024-017",
            "section": "Follow-up Verification",
            "page_start": None,
            "page_end": None,
            "chunking_strategy": "markdown_structure_aware",
        },
    )
    return new


def make_v4_delete_control_system(
    old: dict[str, ChunkSnapshot],
) -> dict[str, ChunkSnapshot]:
    new = dict(old)
    new.pop("doc_001_equipment-chunk-002", None)
    return new


def diff_snapshots(
    transition: str,
    old: dict[str, ChunkSnapshot],
    new: dict[str, ChunkSnapshot],
) -> list[ChunkAction]:
    actions = []
    for chunk_id in sorted(set(old) | set(new)):
        old_chunk = old.get(chunk_id)
        new_chunk = new.get(chunk_id)
        if old_chunk is None and new_chunk is not None:
            actions.append(
                ChunkAction(
                    transition=transition,
                    action="added",
                    chunk_id=chunk_id,
                    document_id=new_chunk.document_id,
                    old_hash=None,
                    new_hash=new_chunk.content_hash,
                    old_version=None,
                    new_version=new_chunk.version,
                    affected_stores=[
                        "text_chunks",
                        "chunks_vdb",
                        "graph_store",
                        "entities_vdb",
                        "relationships_vdb",
                        "doc_status",
                    ],
                    reason="New chunk_id appears in the new snapshot.",
                )
            )
        elif old_chunk is not None and new_chunk is None:
            actions.append(
                ChunkAction(
                    transition=transition,
                    action="deleted",
                    chunk_id=chunk_id,
                    document_id=old_chunk.document_id,
                    old_hash=old_chunk.content_hash,
                    new_hash=None,
                    old_version=old_chunk.version,
                    new_version=None,
                    affected_stores=[
                        "text_chunks",
                        "chunks_vdb",
                        "graph_store",
                        "entities_vdb",
                        "relationships_vdb",
                        "doc_status",
                    ],
                    reason="Old chunk_id is absent from the new snapshot.",
                )
            )
        elif old_chunk and new_chunk and old_chunk.content_hash != new_chunk.content_hash:
            actions.append(
                ChunkAction(
                    transition=transition,
                    action="modified",
                    chunk_id=chunk_id,
                    document_id=new_chunk.document_id,
                    old_hash=old_chunk.content_hash,
                    new_hash=new_chunk.content_hash,
                    old_version=old_chunk.version,
                    new_version=new_chunk.version,
                    affected_stores=[
                        "text_chunks",
                        "chunks_vdb",
                        "graph_store",
                        "entities_vdb",
                        "relationships_vdb",
                        "llm_response_cache",
                        "doc_status",
                    ],
                    reason="Same chunk_id but content_hash changed.",
                )
            )
        elif old_chunk and new_chunk:
            actions.append(
                ChunkAction(
                    transition=transition,
                    action="unchanged",
                    chunk_id=chunk_id,
                    document_id=new_chunk.document_id,
                    old_hash=old_chunk.content_hash,
                    new_hash=new_chunk.content_hash,
                    old_version=old_chunk.version,
                    new_version=new_chunk.version,
                    affected_stores=[],
                    reason="Same chunk_id and same content_hash.",
                )
            )
    return actions


def apply_incremental(
    old: dict[str, ChunkSnapshot],
    new: dict[str, ChunkSnapshot],
    actions: list[ChunkAction],
    strategy: str,
) -> dict[str, ChunkSnapshot]:
    if strategy == "full_reindex":
        return dict(new)

    if strategy == "incremental_with_graph_cleanup":
        result = dict(old)
        for action in actions:
            if action.action in {"added", "modified"}:
                result[action.chunk_id] = new[action.chunk_id]
            elif action.action == "deleted":
                result.pop(action.chunk_id, None)
        return result

    if strategy == "incremental_without_delete":
        result = dict(old)
        for action in actions:
            if action.action in {"added", "modified"}:
                result[action.chunk_id] = new[action.chunk_id]
        return result

    if strategy == "incremental_without_hash":
        result = dict(old)
        for chunk_id, new_chunk in new.items():
            if chunk_id not in old:
                result[chunk_id] = new_chunk
        for chunk_id in set(old) - set(new):
            result.pop(chunk_id, None)
        return result

    if strategy == "unstable_chunk_id":
        renamed = {}
        for index, chunk in enumerate(new.values()):
            new_id = f"{chunk.document_id}-unstable-{chunk.version}-{index:03d}"
            renamed[new_id] = replace(
                chunk,
                chunk_id=new_id,
                content_hash=chunk.content_hash,
            )
        return renamed

    raise ValueError(f"Unknown strategy: {strategy}")


def action_counts(actions: list[ChunkAction]) -> dict[str, int]:
    counts = {"unchanged": 0, "added": 0, "modified": 0, "deleted": 0}
    for action in actions:
        counts[action.action] += 1
    return counts


def cost_for_strategy(
    strategy: str,
    old: dict[str, ChunkSnapshot],
    new: dict[str, ChunkSnapshot],
    actions: list[ChunkAction],
) -> dict[str, int]:
    counts = action_counts(actions)
    if strategy == "full_reindex":
        return {
            "embedding_recompute_count": len(new),
            "text_upsert_count": len(new),
            "delete_count": len(old),
            "graph_cleanup_count": len(old),
            "graph_rebuild_count": len(new),
        }
    if strategy == "incremental_with_graph_cleanup":
        return {
            "embedding_recompute_count": counts["added"] + counts["modified"],
            "text_upsert_count": counts["added"] + counts["modified"],
            "delete_count": counts["deleted"],
            "graph_cleanup_count": counts["modified"] + counts["deleted"],
            "graph_rebuild_count": counts["added"] + counts["modified"],
        }
    if strategy == "incremental_without_delete":
        return {
            "embedding_recompute_count": counts["added"] + counts["modified"],
            "text_upsert_count": counts["added"] + counts["modified"],
            "delete_count": 0,
            "graph_cleanup_count": counts["modified"],
            "graph_rebuild_count": counts["added"] + counts["modified"],
        }
    if strategy == "incremental_without_hash":
        return {
            "embedding_recompute_count": counts["added"],
            "text_upsert_count": counts["added"],
            "delete_count": counts["deleted"],
            "graph_cleanup_count": counts["deleted"],
            "graph_rebuild_count": counts["added"],
        }
    if strategy == "unstable_chunk_id":
        return {
            "embedding_recompute_count": len(new),
            "text_upsert_count": len(new),
            "delete_count": len(old),
            "graph_cleanup_count": len(old),
            "graph_rebuild_count": len(new),
        }
    raise ValueError(f"Unknown strategy: {strategy}")


def stale_chunk_count(
    applied: dict[str, ChunkSnapshot],
    target: dict[str, ChunkSnapshot],
) -> int:
    stale = 0
    for chunk_id, chunk in applied.items():
        target_chunk = target.get(chunk_id)
        if target_chunk is None or target_chunk.content_hash != chunk.content_hash:
            stale += 1
    return stale


def missing_chunk_count(
    applied: dict[str, ChunkSnapshot],
    target: dict[str, ChunkSnapshot],
) -> int:
    return sum(1 for chunk_id in target if chunk_id not in applied)


def retrieve_bm25(snapshot: dict[str, ChunkSnapshot], query: str, top_k: int = 5) -> list[dict]:
    chunks = [chunk.to_chunk() for chunk in snapshot.values()]
    retriever = BM25Retriever(chunks)
    return [candidate.to_dict() for candidate in retriever.retrieve(query, top_k)]


def query_checks(version: str, applied: dict[str, ChunkSnapshot]) -> list[dict[str, Any]]:
    checks = []
    if version == "v2":
        checks.append(
            make_query_check(
                version,
                "INC-Q002",
                applied,
                "What is the alarm threshold for Pipeline-7A?",
                required_terms=["alarm threshold for pipeline-7a is 9.2 mpa"],
                forbidden_terms=[
                    "alarm threshold for pipeline-7a is 9.5 mpa",
                    "pressure reaches 9.5 mpa",
                ],
            )
        )
    if version == "v3":
        checks.append(
            make_query_check(
                version,
                "INC-Q004",
                applied,
                "When is the follow-up inspection scheduled?",
                required_terms=["follow-up inspection", "30 days"],
                forbidden_terms=[],
            )
        )
    if version == "v4":
        checks.append(
            make_query_check(
                version,
                "INC-Q005",
                applied,
                "What does ControlSystem-CS1 start when either sensor reports an abnormal event?",
                required_terms=[],
                forbidden_terms=[
                    "controlsystem-cs1 starts an inspection workflow when either sensor reports an abnormal event"
                ],
            )
        )
    return checks


def make_query_check(
    version: str,
    check_id: str,
    snapshot: dict[str, ChunkSnapshot],
    query: str,
    required_terms: list[str],
    forbidden_terms: list[str],
) -> dict[str, Any]:
    candidates = retrieve_bm25(snapshot, query, top_k=5)
    joined_context = "\n".join(candidate["content"] for candidate in candidates).lower()
    required_ok = all(term in joined_context for term in required_terms)
    forbidden_ok = all(term not in joined_context for term in forbidden_terms)
    return {
        "run_id": RUN_ID,
        "version": version,
        "check_id": check_id,
        "query": query,
        "required_terms": " | ".join(required_terms),
        "forbidden_terms": " | ".join(forbidden_terms),
        "query_pass": required_ok and forbidden_ok,
        "top_chunk_ids": " | ".join(candidate["chunk_id"] for candidate in candidates),
        "top_context_preview": joined_context[:300].replace("\n", " "),
    }


async def measure_embedding_latency(texts: list[str]) -> tuple[int, float, int | None]:
    if not texts:
        return 0, 0.0, None
    started = time.perf_counter()
    embeddings = await ollama_embed.func(
        texts,
        embed_model=EMBEDDING_MODEL,
        host=OLLAMA_HOST,
        timeout=300,
    )
    latency_ms = (time.perf_counter() - started) * 1000
    dim = int(embeddings.shape[1]) if len(embeddings.shape) == 2 else None
    return len(texts), latency_ms, dim


def changed_texts_for_strategy(
    strategy: str,
    old: dict[str, ChunkSnapshot],
    new: dict[str, ChunkSnapshot],
    actions: list[ChunkAction],
) -> list[str]:
    if strategy in {"full_reindex", "unstable_chunk_id"}:
        return [chunk.content for chunk in new.values()]
    if strategy in {"incremental_with_graph_cleanup", "incremental_without_delete"}:
        return [
            new[action.chunk_id].content
            for action in actions
            if action.action in {"added", "modified"}
        ]
    if strategy == "incremental_without_hash":
        return [
            new[action.chunk_id].content
            for action in actions
            if action.action == "added"
        ]
    raise ValueError(f"Unknown strategy: {strategy}")


def build_transitions() -> list[tuple[str, str, dict[str, ChunkSnapshot], dict[str, ChunkSnapshot]]]:
    v1 = load_v1_snapshot()
    v2 = make_v2_threshold_update(v1)
    v3 = make_v3_add_followup(v2)
    v4 = make_v4_delete_control_system(v3)
    return [
        ("v1_to_v2_threshold_update", "v2", v1, v2),
        ("v2_to_v3_add_followup", "v3", v2, v3),
        ("v3_to_v4_delete_control_system", "v4", v3, v4),
    ]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(summary_rows: list[dict[str, Any]]) -> None:
    fields = [
        "strategy",
        "transitions",
        "embedding_recompute_count",
        "embedding_saved_ratio",
        "stale_chunk_count",
        "missing_chunk_count",
        "query_pass_rate",
        "measured_embedding_latency_ms",
    ]
    lines = [
        "# Incremental Index Ablation v0 Summary",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in summary_rows:
        lines.append("| " + " | ".join(str(row[field]) for field in fields) + " |")
    lines.append("")
    lines.append("Notes:")
    lines.append("")
    lines.append("- `full_reindex` is the baseline that embeds every new chunk after each update.")
    lines.append("- `incremental_with_graph_cleanup` embeds only added/modified chunks and deletes stale chunks.")
    lines.append("- `incremental_without_delete`, `incremental_without_hash`, and `unstable_chunk_id` are negative controls.")
    (OUTPUT_DIR / "incremental_index_ablation_v0_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


async def main() -> None:
    strategies = [
        "full_reindex",
        "incremental_with_graph_cleanup",
        "incremental_without_delete",
        "incremental_without_hash",
        "unstable_chunk_id",
    ]
    transitions = build_transitions()
    action_rows = []
    record_rows = []
    query_rows = []
    version_states = {strategy: transitions[0][2] for strategy in strategies}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for transition_name, new_version, old_snapshot, new_snapshot in transitions:
        canonical_old = old_snapshot
        canonical_new = new_snapshot
        actions = diff_snapshots(transition_name, canonical_old, canonical_new)
        action_rows.extend(action.to_dict() for action in actions)
        full_cost = cost_for_strategy("full_reindex", canonical_old, canonical_new, actions)
        full_embedding_count = full_cost["embedding_recompute_count"]

        for strategy in strategies:
            state_before = version_states[strategy]
            applied_state = apply_incremental(
                state_before,
                canonical_new,
                actions,
                strategy,
            )
            version_states[strategy] = applied_state
            costs = cost_for_strategy(strategy, state_before, canonical_new, actions)
            texts_to_embed = changed_texts_for_strategy(
                strategy, state_before, canonical_new, actions
            )
            measured_count, measured_latency_ms, embedding_dim = await measure_embedding_latency(
                texts_to_embed
            )
            checks = query_checks(new_version, applied_state)
            for check in checks:
                query_rows.append({"strategy": strategy, "transition": transition_name, **check})

            saved_ratio = (
                1 - costs["embedding_recompute_count"] / full_embedding_count
                if full_embedding_count
                else 0.0
            )
            record_rows.append(
                {
                    "run_id": RUN_ID,
                    "transition": transition_name,
                    "new_version": new_version,
                    "strategy": strategy,
                    "old_chunk_count": len(state_before),
                    "target_new_chunk_count": len(canonical_new),
                    "applied_chunk_count": len(applied_state),
                    "unchanged_count": action_counts(actions)["unchanged"],
                    "added_count": action_counts(actions)["added"],
                    "modified_count": action_counts(actions)["modified"],
                    "deleted_count": action_counts(actions)["deleted"],
                    **costs,
                    "embedding_saved_ratio": round(saved_ratio, 4),
                    "stale_chunk_count": stale_chunk_count(applied_state, canonical_new),
                    "missing_chunk_count": missing_chunk_count(applied_state, canonical_new),
                    "query_pass_count": sum(1 for check in checks if check["query_pass"]),
                    "query_check_count": len(checks),
                    "measured_embedding_count": measured_count,
                    "measured_embedding_latency_ms": round(measured_latency_ms, 2),
                    "embedding_dim": embedding_dim,
                }
            )

    summary_rows = []
    for strategy in strategies:
        items = [row for row in record_rows if row["strategy"] == strategy]
        full_embedding_total = sum(
            row["target_new_chunk_count"]
            for row in record_rows
            if row["strategy"] == "full_reindex"
        )
        recompute_total = sum(row["embedding_recompute_count"] for row in items)
        query_total = sum(row["query_check_count"] for row in items)
        query_pass = sum(row["query_pass_count"] for row in items)
        summary_rows.append(
            {
                "run_id": RUN_ID,
                "strategy": strategy,
                "transitions": len(items),
                "embedding_recompute_count": recompute_total,
                "embedding_saved_ratio": round(
                    1 - recompute_total / full_embedding_total, 4
                ),
                "text_upsert_count": sum(row["text_upsert_count"] for row in items),
                "delete_count": sum(row["delete_count"] for row in items),
                "graph_cleanup_count": sum(row["graph_cleanup_count"] for row in items),
                "graph_rebuild_count": sum(row["graph_rebuild_count"] for row in items),
                "stale_chunk_count": sum(row["stale_chunk_count"] for row in items),
                "missing_chunk_count": sum(row["missing_chunk_count"] for row in items),
                "query_pass_rate": round(query_pass / query_total if query_total else 0, 4),
                "measured_embedding_latency_ms": round(
                    sum(row["measured_embedding_latency_ms"] for row in items), 2
                ),
            }
        )
    summary_rows.sort(
        key=lambda row: (
            -row["query_pass_rate"],
            row["stale_chunk_count"],
            -row["embedding_saved_ratio"],
            row["measured_embedding_latency_ms"],
        )
    )

    write_csv(OUTPUT_DIR / "incremental_index_ablation_v0_actions.csv", action_rows)
    write_csv(OUTPUT_DIR / "incremental_index_ablation_v0_records.csv", record_rows)
    write_csv(OUTPUT_DIR / "incremental_index_ablation_v0_query_check.csv", query_rows)
    write_csv(OUTPUT_DIR / "incremental_index_ablation_v0_summary.csv", summary_rows)
    with (OUTPUT_DIR / "incremental_index_ablation_v0_records.jsonl").open(
        "w", encoding="utf-8"
    ) as f:
        for row in record_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_markdown(summary_rows)

    print(f"Saved outputs to {OUTPUT_DIR}")
    for row in summary_rows:
        print(row)


if __name__ == "__main__":
    asyncio.run(main())
