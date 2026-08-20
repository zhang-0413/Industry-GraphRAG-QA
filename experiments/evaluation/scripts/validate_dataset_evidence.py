import json
import sys
from pathlib import Path
from typing import Any


EVALUATION_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = EVALUATION_DIR.parents[1]
DEFAULT_DATASET = EVALUATION_DIR / "datasets" / "eval_v0_20.jsonl"
TEXT_STORES = [
    REPO_DIR
    / "experiments"
    / "baseline_industry_mini"
    / "storage_structure_aware"
    / "kv_store_text_chunks.json",
    REPO_DIR
    / "experiments"
    / "baseline_industry_mini"
    / "storage_multimodal"
    / "kv_store_text_chunks.json",
]


def normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_chunks() -> dict[str, dict[str, Any]]:
    chunks = {}
    for store_path in TEXT_STORES:
        if not store_path.exists():
            continue
        raw = json.loads(store_path.read_text(encoding="utf-8"))
        chunks.update(raw)
    return chunks


def main() -> None:
    dataset_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATASET
    samples = load_jsonl(dataset_path)
    chunks = load_chunks()

    errors = []
    checked = 0
    for sample in samples:
        for evidence in sample["expected_evidence"]:
            checked += 1
            chunk_id = evidence.get("chunk_id")
            evidence_text = evidence["evidence_text"]
            sample_id = sample["sample_id"]
            evidence_id = evidence["evidence_id"]

            if not chunk_id:
                continue

            chunk = chunks.get(chunk_id)
            if chunk is None:
                errors.append(f"{sample_id}/{evidence_id}: chunk_id not found: {chunk_id}")
                continue

            if normalize(evidence_text) not in normalize(chunk.get("content", "")):
                errors.append(
                    f"{sample_id}/{evidence_id}: evidence_text not found in {chunk_id}"
                )

    if errors:
        print("Evidence validation failed:")
        for error in errors:
            print(f"  - {error}")
        raise SystemExit(1)

    print("Evidence validation passed")
    print(f"  samples: {len(samples)}")
    print(f"  evidence items checked: {checked}")
    print(f"  stores loaded: {len([p for p in TEXT_STORES if p.exists()])}")
    print(f"  chunks loaded: {len(chunks)}")


if __name__ == "__main__":
    main()
