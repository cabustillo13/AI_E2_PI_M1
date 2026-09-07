import json

from src.llm.base import LLMResult
from src.pipeline.judge import judge_response
from src.prompts.registry import PromptRegistry


class FakeProvider:
    def __init__(self, text: str) -> None:
        self.text = text

    def generate(self, system_prompt, user_prompt):
        return LLMResult(
            text=self.text,
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            model="fake-model",
            provider="fake",
        )


def test_judge_parses_valid_verdict():
    verdict_json = json.dumps(
        {
            "score": 0.9,
            "verdict": "pass",
            "reasoning": "La respuesta es relevante y las acciones son concretas.",
        }
    )

    verdict = judge_response(
        FakeProvider(verdict_json),
        PromptRegistry("prompts"),
        "v1",
        "No puedo iniciar sesión",
        "account",
        "Te ayudo a recuperar el acceso.",
        ["Verificar identidad", "Guiar recuperación de contraseña"],
    )

    assert verdict.verdict == "pass"
    assert verdict.score == 0.9


def test_judge_falls_back_to_fail_on_invalid_json():
    verdict = judge_response(
        FakeProvider("esto no es json"),
        PromptRegistry("prompts"),
        "v1",
        "No puedo iniciar sesión",
        "account",
        "Te ayudo a recuperar el acceso.",
        ["Verificar identidad"],
    )

    assert verdict.verdict == "fail"
    assert verdict.score == 0.0
