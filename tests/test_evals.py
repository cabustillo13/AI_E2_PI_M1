import json
from pathlib import Path

from src.pipeline.guardrails import detect_prompt_injection


ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_dataset_has_required_categories():
    cases = load_jsonl(ROOT / "evals" / "dataset.jsonl")

    categories = {
        case["expected_category"]
        for case in cases
    }

    assert categories == {
        "billing",
        "technical",
        "account",
        "other",
    }


def test_adversarial_cases_are_detected():
    cases = load_jsonl(ROOT / "evals" / "adversarial.jsonl")

    assert len(cases) >= 10

    assert all(
        detect_prompt_injection(case["query"])
        for case in cases
    )
