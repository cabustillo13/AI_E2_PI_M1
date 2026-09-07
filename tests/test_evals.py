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

    # Los 10 casos originales (sin "expected_layer") coinciden con los
    # patrones conocidos y deben ser detectados por el filtro de entrada.
    # Los casos con "expected_layer" (sea "output" o "input_or_output") son
    # variantes deliberadamente diseñadas para NO depender del filtro de
    # entrada: prueban que la segunda capa (validate_output sobre la
    # respuesta del LLM) es la que realmente los frena, no el regex.
    input_layer_cases = [
        case
        for case in cases
        if "expected_layer" not in case
    ]

    assert input_layer_cases

    assert all(
        detect_prompt_injection(case["query"])
        for case in input_layer_cases
    )


def test_output_layer_cases_bypass_input_filter():
    """Documenta, en vez de esconder, el límite conocido del filtro de
    entrada: estos casos existen justamente porque el regex no los agarra."""
    cases = load_jsonl(ROOT / "evals" / "adversarial.jsonl")

    output_layer_cases = [
        case
        for case in cases
        if "expected_layer" in case
    ]

    assert output_layer_cases

    assert not any(
        detect_prompt_injection(case["query"])
        for case in output_layer_cases
    )
