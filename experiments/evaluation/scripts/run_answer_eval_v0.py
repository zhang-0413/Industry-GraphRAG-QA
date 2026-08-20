import argparse
import asyncio
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


EVALUATION_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = EVALUATION_DIR.parents[1]
SCRIPTS_DIR = EVALUATION_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from run_retrieval_eval_v0 import (  # noqa: E402
    DATASET_PATH,
    MAX_K,
    OLLAMA_HOST,
    build_store_runtimes,
    load_corpus,
    load_jsonl,
    normalize as retrieval_normalize,
    retrieve_strategy,
)


RUN_ID = "answer_eval_v0_001"
OUTPUT_DIR = EVALUATION_DIR / "results" / "answer_eval_v0"
DEFAULT_STRATEGIES = ["bm25", "vector", "router"]
DEFAULT_TOP_K = 5
DEFAULT_LLM_MODEL = "qwen2.5:3b"
MAX_CONTEXT_CHARS = 6500
MAX_CHUNK_CHARS = 1400

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
    "must",
    "does",
    "according",
    "after",
    "before",
    "during",
    "under",
    "through",
    "into",
    "onto",
    "about",
    "were",
    "was",
    "are",
    "is",
    "its",
    "their",
    "because",
    "should",
    "would",
    "could",
    "been",
    "being",
    "have",
    "has",
    "had",
    "not",
    "yes",
    "no",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def key_terms(text: str) -> list[str]:
    terms = []
    for token in TOKEN_RE.findall(normalize_text(text)):
        if token in STOPWORDS:
            continue
        if len(token) < 3 and not any(ch.isdigit() for ch in token):
            continue
        terms.append(token)
    return terms


def stem_term(term: str) -> str:
    if len(term) <= 4 or "-" in term or any(ch.isdigit() for ch in term):
        return term
    for suffix in ("ing", "ied", "ed", "es", "s"):
        if term.endswith(suffix) and len(term) - len(suffix) >= 4:
            if suffix == "ied":
                return term[: -len(suffix)] + "y"
            return term[: -len(suffix)]
    return term


def is_critical_term(term: str) -> bool:
    return "-" in term or any(ch.isdigit() for ch in term) or term in {"mpa", "below"}


def token_set(text: str) -> set[str]:
    return set(key_terms(text))


def stemmed_token_set(text: str) -> set[str]:
    return {stem_term(term) for term in key_terms(text)}


def contains_term(text: str, term: str) -> bool:
    tokens = token_set(text)
    if term in tokens:
        return True
    if stem_term(term) in stemmed_token_set(text):
        return True
    normalized = normalize_text(text)
    return term in normalized


def score_answer_point(answer: str, point: str) -> dict[str, Any]:
    terms = key_terms(point)
    if not terms:
        return {"hit": False, "score": 0.0, "matched_terms": [], "missing_terms": []}

    matched = [term for term in terms if contains_term(answer, term)]
    missing = [term for term in terms if term not in matched]
    score = len(matched) / len(terms)
    critical_terms = [term for term in terms if is_critical_term(term)]
    critical_ok = critical_terms and all(term in matched for term in critical_terms)
    min_matches = 1 if len(terms) <= 2 else 2
    hit = (score >= 0.6 and len(matched) >= min_matches) or (
        critical_ok and score >= 0.5
    )
    return {
        "hit": hit,
        "score": round(score, 4),
        "matched_terms": matched,
        "missing_terms": missing,
    }


def gold_token_f1(answer: str, gold_answer: str) -> float:
    answer_terms = token_set(answer)
    gold_terms = token_set(gold_answer)
    if not answer_terms or not gold_terms:
        return 0.0
    overlap = len(answer_terms & gold_terms)
    precision = overlap / len(answer_terms)
    recall = overlap / len(gold_terms)
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def answer_relevance_proxy(answer: str, question: str) -> float:
    question_terms = token_set(question)
    if not question_terms:
        return 0.0
    answer_terms = token_set(answer)
    return round(len(question_terms & answer_terms) / len(question_terms), 4)


def faithfulness_proxy(answer: str, context: str, question: str) -> float:
    answer_terms = token_set(answer)
    question_terms = token_set(question)
    claim_terms = answer_terms - question_terms
    if not claim_terms:
        return 0.0
    context_terms = token_set(context)
    return round(len(claim_terms & context_terms) / len(claim_terms), 4)


def negative_violations(answer: str, negative_constraints: list[str]) -> list[str]:
    normalized_answer = normalize_text(answer)
    violations = []
    for item in negative_constraints or []:
        if normalize_text(item) in normalized_answer:
            violations.append(item)
    return violations


def build_context(candidates: list[dict[str, Any]], top_k: int) -> str:
    blocks = []
    total = 0
    for index, candidate in enumerate(candidates[:top_k], start=1):
        content = candidate.get("content", "").strip()
        if not content:
            continue
        content = content[:MAX_CHUNK_CHARS]
        header = (
            f"[{index}] chunk_id={candidate.get('chunk_id')} "
            f"document_id={candidate.get('document_id')} "
            f"content_type={candidate.get('content_type')} "
            f"heading={candidate.get('heading')}"
        )
        block = f"{header}\n{content}"
        if total + len(block) > MAX_CONTEXT_CHARS:
            break
        blocks.append(block)
        total += len(block)
    return "\n\n".join(blocks)


def build_prompt(sample: dict[str, Any], context: str) -> str:
    return f"""You are evaluating a retrieval-augmented QA system.
Answer the user question using ONLY the provided context.
If the context does not contain enough information, say: "Not enough information in the provided context."
Keep the answer concise and factual.

Question:
{sample["question"]}

Context:
{context}

Answer:"""


def call_ollama_generate(
    prompt: str,
    model: str,
    host: str,
    num_predict: int,
    temperature: float,
) -> tuple[str, float]:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
            "num_ctx": 4096,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{host.rstrip('/')}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Failed to connect to Ollama at {host}. Start it with: ollama serve"
        ) from exc
    latency_ms = (time.perf_counter() - started) * 1000
    return result.get("response", "").strip(), latency_ms


def evaluate_answer(
    sample: dict[str, Any],
    answer: str,
    context: str,
) -> dict[str, Any]:
    point_details = []
    for index, point in enumerate(sample["expected_answer_points"], start=1):
        detail = score_answer_point(answer, point)
        point_details.append(
            {
                "point_id": f"P{index}",
                "point": point,
                **detail,
            }
        )

    hit_points = [item for item in point_details if item["hit"]]
    violations = negative_violations(answer, sample.get("negative_constraints", []))
    coverage = len(hit_points) / max(len(point_details), 1)
    return {
        "answer_point_coverage": round(coverage, 4),
        "answer_point_hit_count": len(hit_points),
        "answer_point_count": len(point_details),
        "answer_point_details": point_details,
        "gold_token_f1": gold_token_f1(answer, sample["gold_answer"]),
        "faithfulness_proxy": faithfulness_proxy(answer, context, sample["question"]),
        "answer_relevance_proxy": answer_relevance_proxy(answer, sample["question"]),
        "negative_violation_count": len(violations),
        "negative_violations": violations,
        "passed": coverage >= 0.8 and not violations,
    }


def approx_tokens(text: str) -> int:
    return len(TOKEN_RE.findall(text))


async def run(args: argparse.Namespace) -> None:
    samples = load_jsonl(DATASET_PATH)
    if args.limit:
        samples = samples[: args.limit]

    chunks, chunks_by_store = load_corpus()
    chunks_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    chunks_by_content = {retrieval_normalize(chunk.get("content", "")): chunk for chunk in chunks}
    runtimes = await build_store_runtimes(chunks_by_store)

    strategies = [item.strip() for item in args.strategies.split(",") if item.strip()]
    records = []
    try:
        print(
            f"Running answer eval: samples={len(samples)} strategies={strategies} "
            f"top_k={args.top_k}",
            flush=True,
        )
        for sample in samples:
            print(f"Answering {sample['sample_id']} {sample['question_type']} ...", flush=True)
            for strategy in strategies:
                candidates, retrieval_latency_ms = await retrieve_strategy(
                    strategy,
                    sample,
                    chunks,
                    runtimes,
                    chunks_by_id,
                    chunks_by_content,
                )
                candidates = candidates[: args.top_k]
                context = build_context(candidates, args.top_k)
                prompt = build_prompt(sample, context)
                answer, generation_latency_ms = call_ollama_generate(
                    prompt,
                    model=args.model,
                    host=args.host,
                    num_predict=args.num_predict,
                    temperature=args.temperature,
                )
                scores = evaluate_answer(sample, answer, context)
                records.append(
                    {
                        "run_id": RUN_ID,
                        "sample_id": sample["sample_id"],
                        "question_type": sample["question_type"],
                        "difficulty": sample["difficulty"],
                        "modalities": " | ".join(sample["modalities"]),
                        "strategy": strategy,
                        "top_k": args.top_k,
                        "question": sample["question"],
                        "gold_answer": sample["gold_answer"],
                        "generated_answer": answer,
                        "answer_point_coverage": scores["answer_point_coverage"],
                        "answer_point_hit_count": scores["answer_point_hit_count"],
                        "answer_point_count": scores["answer_point_count"],
                        "gold_token_f1": scores["gold_token_f1"],
                        "faithfulness_proxy": scores["faithfulness_proxy"],
                        "answer_relevance_proxy": scores["answer_relevance_proxy"],
                        "negative_violation_count": scores["negative_violation_count"],
                        "passed": int(scores["passed"]),
                        "retrieval_latency_ms": round(retrieval_latency_ms, 2),
                        "generation_latency_ms": round(generation_latency_ms, 2),
                        "total_latency_ms": round(
                            retrieval_latency_ms + generation_latency_ms, 2
                        ),
                        "context_chunk_count": len(candidates),
                        "context_chunk_ids": " | ".join(
                            candidate["chunk_id"] for candidate in candidates
                        ),
                        "context_content_types": " | ".join(
                            candidate.get("content_type", "") for candidate in candidates
                        ),
                        "context_approx_tokens": approx_tokens(context),
                        "answer_approx_tokens": approx_tokens(answer),
                        "answer_point_details_json": json.dumps(
                            scores["answer_point_details"], ensure_ascii=False
                        ),
                        "negative_violations_json": json.dumps(
                            scores["negative_violations"], ensure_ascii=False
                        ),
                    }
                )
    finally:
        for runtime in runtimes:
            await runtime.rag.finalize_storages()

    summary = aggregate(records)
    write_outputs(records, summary)
    print(f"Saved outputs to {OUTPUT_DIR}", flush=True)
    for row in summary:
        print(row, flush=True)


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
                "top_k": items[0]["top_k"] if items else "",
                "pass_rate": round(sum(i["passed"] for i in items) / len(items), 4),
                "avg_answer_point_coverage": round(
                    sum(i["answer_point_coverage"] for i in items) / len(items), 4
                ),
                "avg_gold_token_f1": round(
                    sum(i["gold_token_f1"] for i in items) / len(items), 4
                ),
                "avg_faithfulness_proxy": round(
                    sum(i["faithfulness_proxy"] for i in items) / len(items), 4
                ),
                "avg_answer_relevance_proxy": round(
                    sum(i["answer_relevance_proxy"] for i in items) / len(items), 4
                ),
                "avg_retrieval_latency_ms": round(
                    sum(i["retrieval_latency_ms"] for i in items) / len(items), 2
                ),
                "avg_generation_latency_ms": round(
                    sum(i["generation_latency_ms"] for i in items) / len(items), 2
                ),
                "avg_total_latency_ms": round(
                    sum(i["total_latency_ms"] for i in items) / len(items), 2
                ),
                "avg_context_approx_tokens": round(
                    sum(i["context_approx_tokens"] for i in items) / len(items), 2
                ),
                "avg_answer_approx_tokens": round(
                    sum(i["answer_approx_tokens"] for i in items) / len(items), 2
                ),
            }
        )
    return rows


def write_outputs(records: list[dict[str, Any]], summary: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records_jsonl = OUTPUT_DIR / "answer_eval_v0_records.jsonl"
    records_csv = OUTPUT_DIR / "answer_eval_v0_records.csv"
    summary_csv = OUTPUT_DIR / "answer_eval_v0_summary.csv"

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local answer evaluation v0.")
    parser.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES))
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--model", default=DEFAULT_LLM_MODEL)
    parser.add_argument("--host", default=OLLAMA_HOST)
    parser.add_argument("--num-predict", type=int, default=120)
    parser.add_argument("--temperature", type=float, default=0.0)
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
