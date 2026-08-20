import json
import sys
from pathlib import Path
from typing import Any


EVALUATION_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = EVALUATION_DIR / "evaluation_schema.json"
DEFAULT_DATASET = EVALUATION_DIR / "datasets" / "eval_v0_20.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_no}: invalid JSON: {exc}") from exc
    return rows


def validate_sample(sample: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors = []
    required = schema["required"]
    for field in required:
        if field not in sample:
            errors.append(f"missing required field: {field}")

    question_types = set(schema["properties"]["question_type"]["enum"])
    if sample.get("question_type") not in question_types:
        errors.append(f"invalid question_type: {sample.get('question_type')}")

    difficulties = set(schema["properties"]["difficulty"]["enum"])
    if sample.get("difficulty") not in difficulties:
        errors.append(f"invalid difficulty: {sample.get('difficulty')}")

    modality_enum = set(schema["properties"]["modalities"]["items"]["enum"])
    for modality in sample.get("modalities", []):
        if modality not in modality_enum:
            errors.append(f"invalid modality: {modality}")

    if not sample.get("expected_answer_points"):
        errors.append("expected_answer_points must not be empty")
    if not sample.get("expected_evidence"):
        errors.append("expected_evidence must not be empty")

    evidence_enum = set(
        schema["properties"]["expected_evidence"]["items"]["properties"]["content_type"]["enum"]
    )
    seen_evidence_ids = set()
    for evidence in sample.get("expected_evidence", []):
        for field in ["evidence_id", "document_id", "file_name", "evidence_text", "content_type"]:
            if field not in evidence:
                errors.append(f"evidence missing field: {field}")
        if evidence.get("evidence_id") in seen_evidence_ids:
            errors.append(f"duplicate evidence_id: {evidence.get('evidence_id')}")
        seen_evidence_ids.add(evidence.get("evidence_id"))
        if evidence.get("content_type") not in evidence_enum:
            errors.append(f"invalid evidence content_type: {evidence.get('content_type')}")
        if not evidence.get("evidence_text"):
            errors.append(f"empty evidence_text: {evidence.get('evidence_id')}")

    route_enum = set(schema["properties"]["recommended_routes"]["items"]["enum"])
    for route in sample.get("recommended_routes", []):
        if route not in route_enum:
            errors.append(f"invalid recommended route: {route}")

    return errors


def main() -> None:
    dataset_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATASET
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    samples = load_jsonl(dataset_path)

    errors = []
    sample_ids = set()
    for row_no, sample in enumerate(samples, start=1):
        sample_id = sample.get("sample_id", f"line-{row_no}")
        if sample_id in sample_ids:
            errors.append(f"{sample_id}: duplicate sample_id")
        sample_ids.add(sample_id)
        for error in validate_sample(sample, schema):
            errors.append(f"{sample_id}: {error}")

    counts: dict[str, int] = {}
    difficulty_counts: dict[str, int] = {}
    modality_counts: dict[str, int] = {}
    evidence_count = 0
    for sample in samples:
        counts[sample["question_type"]] = counts.get(sample["question_type"], 0) + 1
        difficulty_counts[sample["difficulty"]] = difficulty_counts.get(sample["difficulty"], 0) + 1
        evidence_count += len(sample["expected_evidence"])
        for modality in sample["modalities"]:
            modality_counts[modality] = modality_counts.get(modality, 0) + 1

    if errors:
        print("Dataset validation failed:")
        for error in errors:
            print(f"  - {error}")
        raise SystemExit(1)

    print(f"Dataset validation passed: {dataset_path}")
    print(f"  samples: {len(samples)}")
    print(f"  evidence items: {evidence_count}")
    print(f"  question_type counts: {json.dumps(counts, ensure_ascii=False, sort_keys=True)}")
    print(f"  difficulty counts: {json.dumps(difficulty_counts, ensure_ascii=False, sort_keys=True)}")
    print(f"  modality counts: {json.dumps(modality_counts, ensure_ascii=False, sort_keys=True)}")


if __name__ == "__main__":
    main()
