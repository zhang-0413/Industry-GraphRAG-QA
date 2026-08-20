import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Any


EVALUATION_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = EVALUATION_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from run_answer_eval_v0 import (  # noqa: E402
    DEFAULT_LLM_MODEL,
    OLLAMA_HOST,
    build_context,
    call_ollama_generate,
)
from run_retrieval_eval_v0 import load_corpus, load_jsonl  # noqa: E402


RUN_ID = "llm_judge_eval_v0_001"
ANSWER_RECORDS_PATH = (
    EVALUATION_DIR / "results" / "answer_eval_v0" / "answer_eval_v0_records.jsonl"
)
DATASET_PATH = EVALUATION_DIR / "datasets" / "eval_v0_20.jsonl"
OUTPUT_DIR = EVALUATION_DIR / "results" / "llm_judge_eval_v0"
DEFAULT_TOP_K = 5


def load_answer_records(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def split_chunk_ids(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split("|") if item.strip()]


def chunks_for_record(
    record: dict[str, Any], chunks_by_id: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    candidates = []
    for rank, chunk_id in enumerate(split_chunk_ids(record.get("context_chunk_ids", "")), start=1):
        chunk = chunks_by_id.get(chunk_id)
        if not chunk:
            continue
        candidates.append(
            {
                **chunk,
                "rank": rank,
                "source": record["strategy"],
                "score": None,
            }
        )
    return candidates


def build_judge_prompt(
    sample: dict[str, Any],
    answer_record: dict[str, Any],
    context: str,
) -> str:
    expected_points = "\n".join(
        f"- {point}" for point in sample["expected_answer_points"]
    )
    return f"""You are a strict evaluator for a Retrieval-Augmented Generation system.
Use ONLY the provided context and the user question. Do not use outside knowledge.

Evaluate two things:

1. Faithfulness:
   Break the generated answer into factual claims. A claim is supported only if the context directly supports it.
   If a claim is plausible but not supported by the context, mark it unsupported.
   Use at most 5 important factual claims from the generated answer. Do not invent claims that are not in the answer.

2. Answer relevance:
   Judge whether the generated answer directly answers the user question and covers the expected answer points.
   The expected answer points below are the ONLY required points. Do not invent extra required points.
   Extra details should not reduce relevance if they are supported by the context and do not distract from the answer.
   Penalize answers that are incomplete, too vague, answer only a phrase, contradict the question, or mainly discuss irrelevant details.

Return ONLY valid JSON with this exact shape:
{{
  "faithfulness": {{
    "score": 0.0,
    "claims": [
      {{"claim": "...", "verdict": "supported|unsupported", "reason": "..."}}
    ]
  }},
  "answer_relevance": {{
    "score": 0.0,
    "directly_answers": true,
    "missing_answer_points": ["..."],
    "irrelevant_or_extra_parts": ["..."],
    "reason": "..."
  }}
}}

Scoring rules:
- faithfulness.score = supported claims / all factual claims.
- answer_relevance.score = 1.0 means directly answers the question and covers all expected points.
- If all expected answer points are covered, answer_relevance.score should be at least 0.9 unless the answer is mostly irrelevant.
- answer_relevance.score around 0.5 means partially answers but misses important points.
- answer_relevance.score near 0 means does not answer the question.
- missing_answer_points must contain only exact strings copied from the Expected answer points list.
- irrelevant_or_extra_parts should contain only unsupported, contradictory, or clearly distracting parts.
- Keep every reason under 12 words.
- Do not quote long context text.
- Do not include newline characters inside JSON strings.

Question:
{answer_record["question"]}

Gold answer:
{answer_record["gold_answer"]}

Expected answer points:
{expected_points}

Generated answer:
{answer_record["generated_answer"]}

Context:
{context}
"""


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    if start < 0:
        raise ValueError("No JSON object found")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start : index + 1])
    raise ValueError("Incomplete JSON object")


def clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(min(max(score, 0.0), 1.0), 4)


def normalize_judge_result(raw: dict[str, Any]) -> dict[str, Any]:
    faithfulness = raw.get("faithfulness") or {}
    relevance = raw.get("answer_relevance") or {}
    claims = faithfulness.get("claims") or []
    normalized_claims = []
    supported = 0
    unsupported = 0
    for claim in claims:
        verdict = str(claim.get("verdict", "")).lower()
        verdict = "supported" if verdict == "supported" else "unsupported"
        if verdict == "supported":
            supported += 1
        else:
            unsupported += 1
        normalized_claims.append(
            {
                "claim": str(claim.get("claim", "")),
                "verdict": verdict,
                "reason": str(claim.get("reason", "")),
            }
        )

    if normalized_claims:
        faithfulness_score = round(supported / len(normalized_claims), 4)
    else:
        faithfulness_score = clamp_score(faithfulness.get("score"))

    missing = relevance.get("missing_answer_points") or []
    irrelevant = relevance.get("irrelevant_or_extra_parts") or []
    return {
        "llm_faithfulness": faithfulness_score,
        "llm_answer_relevance": clamp_score(relevance.get("score")),
        "supported_claim_count": supported,
        "unsupported_claim_count": unsupported,
        "claim_count": len(normalized_claims),
        "missing_answer_point_count": len(missing),
        "irrelevant_or_extra_count": len(irrelevant),
        "directly_answers": bool(relevance.get("directly_answers", False)),
        "claims": normalized_claims,
        "missing_answer_points": missing,
        "irrelevant_or_extra_parts": irrelevant,
        "relevance_reason": str(relevance.get("reason", "")),
    }


def fallback_judge_result(error: str) -> dict[str, Any]:
    return {
        "llm_faithfulness": 0.0,
        "llm_answer_relevance": 0.0,
        "supported_claim_count": 0,
        "unsupported_claim_count": 0,
        "claim_count": 0,
        "missing_answer_point_count": 0,
        "irrelevant_or_extra_count": 0,
        "directly_answers": False,
        "claims": [],
        "missing_answer_points": [],
        "irrelevant_or_extra_parts": [],
        "relevance_reason": f"Judge parse failed: {error}",
    }


def judge_record(
    sample: dict[str, Any],
    answer_record: dict[str, Any],
    chunks_by_id: dict[str, dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    candidates = chunks_for_record(answer_record, chunks_by_id)
    context = build_context(candidates, top_k=args.top_k)
    prompt = build_judge_prompt(sample, answer_record, context)
    started = time.perf_counter()
    raw_text, generation_latency_ms = call_ollama_generate(
        prompt,
        model=args.model,
        host=args.host,
        num_predict=args.num_predict,
        temperature=args.temperature,
    )
    judge_latency_ms = (time.perf_counter() - started) * 1000

    parse_error = ""
    try:
        parsed = extract_json_object(raw_text)
        normalized = normalize_judge_result(parsed)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        parse_error = str(exc)
        normalized = fallback_judge_result(parse_error)

    strict_pass = (
        float(answer_record["answer_point_coverage"]) >= 0.8
        and normalized["llm_faithfulness"] >= 0.8
        and normalized["llm_answer_relevance"] >= 0.8
    )
    return {
        "run_id": RUN_ID,
        "sample_id": answer_record["sample_id"],
        "question_type": answer_record["question_type"],
        "difficulty": answer_record["difficulty"],
        "modalities": answer_record["modalities"],
        "strategy": answer_record["strategy"],
        "top_k": answer_record["top_k"],
        "question": answer_record["question"],
        "generated_answer": answer_record["generated_answer"],
        "answer_point_coverage": answer_record["answer_point_coverage"],
        "faithfulness_proxy": answer_record["faithfulness_proxy"],
        "answer_relevance_proxy": answer_record["answer_relevance_proxy"],
        "llm_faithfulness": normalized["llm_faithfulness"],
        "llm_answer_relevance": normalized["llm_answer_relevance"],
        "supported_claim_count": normalized["supported_claim_count"],
        "unsupported_claim_count": normalized["unsupported_claim_count"],
        "claim_count": normalized["claim_count"],
        "missing_answer_point_count": normalized["missing_answer_point_count"],
        "irrelevant_or_extra_count": normalized["irrelevant_or_extra_count"],
        "directly_answers": int(normalized["directly_answers"]),
        "strict_pass": int(strict_pass),
        "judge_latency_ms": round(judge_latency_ms, 2),
        "generation_latency_ms": round(generation_latency_ms, 2),
        "context_chunk_ids": answer_record["context_chunk_ids"],
        "claims_json": json.dumps(normalized["claims"], ensure_ascii=False),
        "missing_answer_points_json": json.dumps(
            normalized["missing_answer_points"], ensure_ascii=False
        ),
        "irrelevant_or_extra_parts_json": json.dumps(
            normalized["irrelevant_or_extra_parts"], ensure_ascii=False
        ),
        "relevance_reason": normalized["relevance_reason"],
        "judge_raw_text": raw_text,
        "judge_parse_error": parse_error,
    }


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
                "strict_pass_rate": round(
                    sum(i["strict_pass"] for i in items) / len(items), 4
                ),
                "avg_answer_point_coverage": round(
                    sum(float(i["answer_point_coverage"]) for i in items) / len(items),
                    4,
                ),
                "avg_proxy_faithfulness": round(
                    sum(float(i["faithfulness_proxy"]) for i in items) / len(items), 4
                ),
                "avg_llm_faithfulness": round(
                    sum(i["llm_faithfulness"] for i in items) / len(items), 4
                ),
                "avg_proxy_answer_relevance": round(
                    sum(float(i["answer_relevance_proxy"]) for i in items) / len(items),
                    4,
                ),
                "avg_llm_answer_relevance": round(
                    sum(i["llm_answer_relevance"] for i in items) / len(items), 4
                ),
                "avg_unsupported_claims": round(
                    sum(i["unsupported_claim_count"] for i in items) / len(items), 4
                ),
                "avg_missing_answer_points": round(
                    sum(i["missing_answer_point_count"] for i in items) / len(items), 4
                ),
                "avg_judge_latency_ms": round(
                    sum(i["judge_latency_ms"] for i in items) / len(items), 2
                ),
                "parse_failures": sum(1 for i in items if i["judge_parse_error"]),
            }
        )
    return rows


def write_outputs(records: list[dict[str, Any]], summary: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records_jsonl = OUTPUT_DIR / "llm_judge_eval_v0_records.jsonl"
    records_csv = OUTPUT_DIR / "llm_judge_eval_v0_records.csv"
    summary_csv = OUTPUT_DIR / "llm_judge_eval_v0_summary.csv"

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


def run(args: argparse.Namespace) -> None:
    samples = {sample["sample_id"]: sample for sample in load_jsonl(DATASET_PATH)}
    answer_records = load_answer_records(ANSWER_RECORDS_PATH)
    if args.strategies:
        wanted = {item.strip() for item in args.strategies.split(",") if item.strip()}
        answer_records = [r for r in answer_records if r["strategy"] in wanted]
    if args.limit:
        answer_records = answer_records[: args.limit]

    chunks, _ = load_corpus()
    chunks_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    records = []
    print(f"Running LLM judge eval: records={len(answer_records)}", flush=True)
    for index, answer_record in enumerate(answer_records, start=1):
        print(
            f"Judging {index}/{len(answer_records)} "
            f"{answer_record['sample_id']} {answer_record['strategy']} ...",
            flush=True,
        )
        records.append(
            judge_record(
                samples[answer_record["sample_id"]],
                answer_record,
                chunks_by_id,
                args,
            )
        )

    summary = aggregate(records)
    write_outputs(records, summary)
    print(f"Saved outputs to {OUTPUT_DIR}", flush=True)
    for row in summary:
        print(row, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local LLM judge evaluation v0.")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--strategies", default="")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--model", default=DEFAULT_LLM_MODEL)
    parser.add_argument("--host", default=OLLAMA_HOST)
    parser.add_argument("--num-predict", type=int, default=450)
    parser.add_argument("--temperature", type=float, default=0.0)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
