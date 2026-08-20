import json
from pathlib import Path
from typing import Any


EVALUATION_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = EVALUATION_DIR.parents[1]
MINI_DIR = REPO_DIR / "experiments" / "baseline_industry_mini"
QUESTIONS_PATH = MINI_DIR / "questions.jsonl"
OUTPUT_PATH = EVALUATION_DIR / "datasets" / "eval_v0_20.jsonl"


TYPE_MAP = {
    "Entity Fact": "fact",
    "Relation Fact": "entity_relation",
    "Cross Paragraph": "cross_paragraph",
    "Numeric": "numeric",
    "Numeric Relation": "numeric",
    "Event Summary": "causal_reasoning",
    "Cross Document": "cross_document",
    "Cross Document Numeric": "cross_document",
    "Event Fact": "causal_reasoning",
    "Global Summary": "global_summary",
}

DIFFICULTY_MAP = {
    "Entity Fact": "easy",
    "Relation Fact": "easy",
    "Cross Paragraph": "medium",
    "Numeric": "easy",
    "Numeric Relation": "medium",
    "Event Summary": "medium",
    "Cross Document": "hard",
    "Cross Document Numeric": "hard",
    "Event Fact": "medium",
    "Global Summary": "hard",
}

ROUTE_MAP = {
    "local": ["bm25", "graph", "vector"],
    "global": ["bm25", "graph"],
    "hybrid": ["bm25", "hybrid"],
    "naive": ["bm25", "vector"],
    "mix": ["bm25", "hybrid", "query_router"],
}

CHUNK_LOOKUP = {
    (
        "doc_001_equipment",
        "BluePump-X100 is a high-pressure pump in the refinery cooling system.",
    ): ("doc_001_equipment-chunk-000", "Refinery Cooling System Equipment Manual", "Pump Unit"),
    (
        "doc_001_equipment",
        "BluePump-X100 moves cooling water through Pipeline-7A during normal operation.",
    ): ("doc_001_equipment-chunk-000", "Refinery Cooling System Equipment Manual", "Pump Unit"),
    (
        "doc_001_equipment",
        "Filter-F33 is installed upstream of Pipeline-7A.",
    ): (
        "doc_001_equipment-chunk-003",
        "Refinery Cooling System Equipment Manual",
        "Maintenance Components",
    ),
    (
        "doc_001_equipment",
        "A partially blocked Filter-F33 can reduce cooling water flow to BluePump-X100.",
    ): (
        "doc_001_equipment-chunk-003",
        "Refinery Cooling System Equipment Manual",
        "Maintenance Components",
    ),
    (
        "doc_001_equipment",
        "Sensor T-200 reports abnormal temperature events to ControlSystem-CS1.",
    ): ("doc_001_equipment-chunk-001", "Refinery Cooling System Equipment Manual", "Sensors"),
    (
        "doc_001_equipment",
        "Sensor P-210 reports high-pressure alarms to ControlSystem-CS1.",
    ): ("doc_001_equipment-chunk-001", "Refinery Cooling System Equipment Manual", "Sensors"),
    (
        "doc_001_equipment",
        "ControlSystem-CS1 receives anomaly reports from Sensor T-200 and Sensor P-210.",
    ): (
        "doc_001_equipment-chunk-002",
        "Refinery Cooling System Equipment Manual",
        "Control System",
    ),
    (
        "doc_001_equipment",
        "Sensor T-200 monitors BluePump-X100 outlet temperature.",
    ): ("doc_001_equipment-chunk-001", "Refinery Cooling System Equipment Manual", "Sensors"),
    (
        "doc_001_equipment",
        "Sensor P-210 monitors Pipeline-7A pressure.",
    ): ("doc_001_equipment-chunk-001", "Refinery Cooling System Equipment Manual", "Sensors"),
    (
        "doc_002_safety_rules",
        "Safety-Regulation-42 requires BluePump-X100 to install ReliefValve-RV9.",
    ): ("doc_002_safety_rules-chunk-000", "Safety Regulation Manual", "Safety-Regulation-42"),
    (
        "doc_002_safety_rules",
        "Pipeline-7A design pressure is 10 MPa.",
    ): ("doc_002_safety_rules-chunk-001", "Safety Regulation Manual", "Pipeline-7A Pressure Rule"),
    (
        "doc_002_safety_rules",
        "The alarm threshold for Pipeline-7A is 9.5 MPa.",
    ): ("doc_002_safety_rules-chunk-001", "Safety Regulation Manual", "Pipeline-7A Pressure Rule"),
    (
        "doc_002_safety_rules",
        "Sensor P-210 must trigger a high-pressure alarm when Pipeline-7A pressure reaches 9.5 MPa.",
    ): ("doc_002_safety_rules-chunk-001", "Safety Regulation Manual", "Pipeline-7A Pressure Rule"),
    (
        "doc_002_safety_rules",
        "If ControlSystem-CS1 receives an abnormal temperature report from Sensor T-200, the maintenance team must inspect BluePump-X100, ReliefValve-RV9, and Filter-F33.",
    ): ("doc_002_safety_rules-chunk-002", "Safety Regulation Manual", "Inspection Rule"),
    (
        "doc_003_incident_report",
        "On 2024-07-12, Sensor T-200 reported abnormal outlet temperature for BluePump-X100.",
    ): ("doc_003_incident_report-chunk-000", "Incident Report IR-2024-017", "Event Summary"),
    (
        "doc_003_incident_report",
        "ControlSystem-CS1 triggered an inspection workflow for incident IR-2024-017.",
    ): ("doc_003_incident_report-chunk-000", "Incident Report IR-2024-017", "Event Summary"),
    (
        "doc_003_incident_report",
        "The abnormal temperature was associated with partial blockage in Filter-F33.",
    ): ("doc_003_incident_report-chunk-001", "Incident Report IR-2024-017", "Root Cause"),
    (
        "doc_003_incident_report",
        "ReliefValve-RV9 passed visual inspection and its set pressure record was verified.",
    ): ("doc_003_incident_report-chunk-002", "Incident Report IR-2024-017", "Inspection Result"),
    (
        "doc_003_incident_report",
        "The measured Pipeline-7A pressure during the inspection was 8.8 MPa, below the 9.5 MPa alarm threshold.",
    ): ("doc_003_incident_report-chunk-002", "Incident Report IR-2024-017", "Inspection Result"),
    (
        "doc_003_incident_report",
        "The maintenance team replaced Filter-F33 and cleaned the inlet screen of Pipeline-7A.",
    ): ("doc_003_incident_report-chunk-003", "Incident Report IR-2024-017", "Maintenance Action"),
    (
        "doc_003_incident_report",
        "After the replacement, Sensor T-200 returned to normal outlet temperature readings.",
    ): ("doc_003_incident_report-chunk-003", "Incident Report IR-2024-017", "Maintenance Action"),
}


def load_mini_questions() -> list[dict[str, Any]]:
    questions = []
    with QUESTIONS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


def routes_for(question: dict[str, Any]) -> list[str]:
    routes = ROUTE_MAP.get(question.get("recommended_mode"), ["query_router"])
    qtype = TYPE_MAP.get(question["question_type"], "fact")
    if qtype == "numeric" and "bm25" not in routes:
        routes = ["bm25", *routes]
    if qtype in {"global_summary", "causal_reasoning", "cross_document"}:
        routes = [*routes, "hybrid_rerank"]
    return sorted(set(routes))


def tags_for(question: dict[str, Any]) -> list[str]:
    tags = [TYPE_MAP.get(question["question_type"], "fact")]
    text = question["question"].lower()
    for signal in [
        "bluepump-x100",
        "pipeline-7a",
        "filter-f33",
        "sensor t-200",
        "sensor p-210",
        "safety-regulation-42",
        "ir-2024-017",
    ]:
        if signal in text:
            tags.append(signal)
    return sorted(set(tags))


def convert_evidence(question: dict[str, Any]) -> list[dict[str, Any]]:
    converted = []
    for index, item in enumerate(question["expected_evidence"], start=1):
        key = (item["document_id"], item["evidence_text"])
        chunk_id, chapter, section = CHUNK_LOOKUP.get(key, (None, None, None))
        converted.append(
            {
                "evidence_id": f"E{index}",
                "document_id": item["document_id"],
                "file_name": item["file_name"],
                "chunk_id": chunk_id,
                "content_type": "text",
                "chapter": chapter,
                "section": section,
                "page_start": None,
                "page_end": None,
                "bbox": None,
                "evidence_text": item["evidence_text"],
                "must_hit": True,
            }
        )
    return converted


def convert_question(index: int, question: dict[str, Any]) -> dict[str, Any]:
    qtype = TYPE_MAP.get(question["question_type"], "fact")
    return {
        "sample_id": f"EVAL-{index:04d}",
        "question": question["question"],
        "question_type": qtype,
        "sub_type": question["question_type"],
        "difficulty": DIFFICULTY_MAP.get(question["question_type"], "medium"),
        "modalities": ["text"],
        "gold_answer": question["gold_answer"],
        "expected_answer_points": question["expected_answer_points"],
        "expected_evidence": convert_evidence(question),
        "recommended_routes": routes_for(question),
        "negative_constraints": [],
        "evaluation": default_evaluation(),
        "tags": tags_for(question),
        "notes": question.get("notes"),
    }


def default_evaluation() -> dict[str, Any]:
    return {
        "retrieval_metrics": [
            "hit_at_k",
            "recall_at_k",
            "mrr",
            "context_precision",
            "context_recall",
        ],
        "answer_metrics": [
            "answer_point_coverage",
            "faithfulness",
            "answer_relevance",
        ],
        "top_k_values": [1, 3, 5, 10],
    }


def multimodal_samples(start_index: int) -> list[dict[str, Any]]:
    samples = [
        {
            "question": "What is the measured pressure of Pipeline-7A in the inspection table?",
            "question_type": "table",
            "sub_type": "pressure_value",
            "difficulty": "easy",
            "modalities": ["table"],
            "gold_answer": "The measured pressure of Pipeline-7A is 8.8 MPa.",
            "expected_answer_points": ["Pipeline-7A measured pressure is 8.8 MPa"],
            "expected_evidence": [
                table_evidence("E1", "Measured Pressure: 8.8 MPa"),
                table_evidence("E2", "| Pipeline-7A | 8.8 MPa | 9.5 MPa | Below threshold |"),
            ],
            "recommended_routes": ["bm25", "table_filter"],
            "tags": ["table", "pressure", "pipeline-7a"],
            "notes": "Table numeric lookup from simulated MinerU output.",
        },
        {
            "question": "Was Pipeline-7A below the alarm threshold according to the table?",
            "question_type": "table",
            "sub_type": "threshold_comparison",
            "difficulty": "medium",
            "modalities": ["table"],
            "gold_answer": "Yes. Pipeline-7A was below the alarm threshold because the measured pressure was 8.8 MPa and the threshold was 9.5 MPa.",
            "expected_answer_points": [
                "Measured pressure was 8.8 MPa",
                "Alarm threshold was 9.5 MPa",
                "Pipeline-7A was below threshold",
            ],
            "expected_evidence": [
                table_evidence("E1", "Measured Pressure: 8.8 MPa"),
                table_evidence("E2", "Alarm Threshold: 9.5 MPa"),
                table_evidence("E3", "Status: Below threshold"),
            ],
            "recommended_routes": ["bm25", "table_filter"],
            "tags": ["table", "comparison", "pressure", "pipeline-7a"],
            "notes": "Table comparison question.",
        },
        {
            "question": "Where is ReliefValve-RV9 installed according to the diagram?",
            "question_type": "image",
            "sub_type": "installation_diagram",
            "difficulty": "medium",
            "modalities": ["image", "caption", "ocr"],
            "gold_answer": "According to the diagram, ReliefValve-RV9 is installed on the discharge side of BluePump-X100 and connected near Pipeline-7A.",
            "expected_answer_points": [
                "ReliefValve-RV9 is installed on the discharge side of BluePump-X100",
                "ReliefValve-RV9 is connected near Pipeline-7A",
            ],
            "expected_evidence": [
                image_evidence("E1", "RV9 discharge side"),
                image_evidence(
                    "E2",
                    "ReliefValve-RV9 installed on the discharge side of BluePump-X100",
                ),
            ],
            "recommended_routes": ["bm25", "image_filter"],
            "tags": ["image", "diagram", "reliefvalve-rv9", "bluepump-x100"],
            "notes": "Image grounding based on caption, OCR, and VLM description.",
        },
        {
            "question": "Which equipment was reviewed after incident IR-2024-017?",
            "question_type": "fact",
            "sub_type": "inspection_overview",
            "difficulty": "easy",
            "modalities": ["text"],
            "gold_answer": "The inspection reviewed BluePump-X100, Pipeline-7A, ReliefValve-RV9, Sensor T-200, and Sensor P-210.",
            "expected_answer_points": [
                "BluePump-X100 was reviewed",
                "Pipeline-7A was reviewed",
                "ReliefValve-RV9 was reviewed",
                "Sensor T-200 was reviewed",
                "Sensor P-210 was reviewed",
            ],
            "expected_evidence": [
                text_evidence(
                    "E1",
                    "The inspection reviewed BluePump-X100, Pipeline-7A, ReliefValve-RV9, Sensor T-200, and Sensor P-210 after incident IR-2024-017.",
                )
            ],
            "recommended_routes": ["bm25", "vector"],
            "tags": ["text", "inspection", "ir-2024-017"],
            "notes": "Text overview from simulated MinerU output.",
        },
        {
            "question": "According to the table and diagram, what was Pipeline-7A's pressure status and where was ReliefValve-RV9 installed?",
            "question_type": "multi_hop",
            "sub_type": "table_image_join",
            "difficulty": "hard",
            "modalities": ["table", "image", "caption", "ocr"],
            "gold_answer": "Pipeline-7A was below threshold, with measured pressure 8.8 MPa versus a 9.5 MPa alarm threshold, and ReliefValve-RV9 was installed on the discharge side of BluePump-X100.",
            "expected_answer_points": [
                "Pipeline-7A measured pressure was 8.8 MPa",
                "Pipeline-7A alarm threshold was 9.5 MPa",
                "Pipeline-7A status was below threshold",
                "ReliefValve-RV9 was installed on the discharge side of BluePump-X100",
            ],
            "expected_evidence": [
                table_evidence("E1", "Status: Below threshold"),
                table_evidence("E2", "Measured Pressure: 8.8 MPa"),
                table_evidence("E3", "Alarm Threshold: 9.5 MPa"),
                image_evidence(
                    "E4",
                    "ReliefValve-RV9 installed on the discharge side of BluePump-X100",
                ),
            ],
            "recommended_routes": ["hybrid", "query_router", "table_filter", "image_filter"],
            "tags": ["multi_hop", "table", "image", "pipeline-7a", "reliefvalve-rv9"],
            "notes": "Cross-modal question requiring table and image evidence.",
        },
    ]

    converted = []
    for offset, sample in enumerate(samples):
        converted.append(
            {
                "sample_id": f"EVAL-{start_index + offset:04d}",
                "question": sample["question"],
                "question_type": sample["question_type"],
                "sub_type": sample["sub_type"],
                "difficulty": sample["difficulty"],
                "modalities": sample["modalities"],
                "gold_answer": sample["gold_answer"],
                "expected_answer_points": sample["expected_answer_points"],
                "expected_evidence": sample["expected_evidence"],
                "recommended_routes": sample["recommended_routes"],
                "negative_constraints": [],
                "evaluation": default_evaluation(),
                "tags": sample["tags"],
                "notes": sample["notes"],
            }
        )
    return converted


def table_evidence(evidence_id: str, text: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "document_id": "doc_004_pipeline_inspection",
        "file_name": "pipeline_inspection_report.pdf",
        "chunk_id": "doc_004_pipeline_inspection-chunk-001",
        "content_type": "table",
        "chapter": "Pipeline Inspection Report",
        "section": "Pressure Records",
        "page_start": 2,
        "page_end": 2,
        "bbox": [72, 130, 540, 260],
        "evidence_text": text,
        "must_hit": True,
    }


def image_evidence(evidence_id: str, text: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "document_id": "doc_004_pipeline_inspection",
        "file_name": "pipeline_inspection_report.pdf",
        "chunk_id": "doc_004_pipeline_inspection-chunk-002",
        "content_type": "image",
        "chapter": "Pipeline Inspection Report",
        "section": "Installation Diagram",
        "page_start": 3,
        "page_end": 3,
        "bbox": [80, 140, 520, 620],
        "evidence_text": text,
        "must_hit": True,
    }


def text_evidence(evidence_id: str, text: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "document_id": "doc_004_pipeline_inspection",
        "file_name": "pipeline_inspection_report.pdf",
        "chunk_id": "doc_004_pipeline_inspection-chunk-000",
        "content_type": "text",
        "chapter": "Pipeline Inspection Report",
        "section": "Inspection Overview",
        "page_start": 1,
        "page_end": 1,
        "bbox": [72, 175, 540, 235],
        "evidence_text": text,
        "must_hit": True,
    }


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    samples = [
        convert_question(index, question)
        for index, question in enumerate(load_mini_questions(), start=1)
    ]
    samples.extend(multimodal_samples(start_index=len(samples) + 1))

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"Created {len(samples)} samples: {OUTPUT_PATH}")
    counts: dict[str, int] = {}
    for sample in samples:
        counts[sample["question_type"]] = counts.get(sample["question_type"], 0) + 1
    print(json.dumps(counts, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
