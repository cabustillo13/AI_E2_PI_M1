import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.llm.base import LLMResult
from src.llm.moderation import OpenAIModerator
from src.metrics.logger import MetricsLogger
from src.pipeline.triage import TriagePipeline
from src.prompts.registry import PromptRegistry
from src.api.routes import get_pipeline


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate(self, system_prompt, user_prompt):
        self.calls += 1
        return LLMResult(
            text=self.responses.pop(0),
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            model="fake-model",
            provider="fake",
        )


class FakeModerator:
    def __init__(self, flagged_texts=None):
        self.flagged_texts = set(flagged_texts or [])
        self.calls = []

    def is_flagged(self, text):
        self.calls.append(text)
        return text in self.flagged_texts


def build_pipeline(tmp_path, responses):
    pipeline = object.__new__(TriagePipeline)
    pipeline.settings = SimpleNamespace(
        max_input_chars=4000,
        max_retries=1,
        prompt_version="v3",
    )
    pipeline.prompts = PromptRegistry("prompts")
    pipeline.metrics = MetricsLogger(
        str(tmp_path / "metrics.jsonl")
    )
    pipeline.provider = FakeProvider(responses)
    pipeline.moderator = None
    return pipeline


def valid_response(answer="We can help."):
    return json.dumps(
        {
            "answer": answer,
            "confidence": 0.9,
            "category": "account",
            "actions": ["Review the account"],
        }
    )


def test_pipeline_retries_and_logs_metrics(tmp_path):
    pipeline = build_pipeline(
        tmp_path,
        ["not json", valid_response()],
    )

    response = pipeline.run("No puedo iniciar sesión")

    assert response.category.value == "account"
    assert pipeline.provider.calls == 2

    record = json.loads(
        (tmp_path / "metrics.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert record["retry_count"] == 1
    assert record["total_tokens"] == 15
    assert record["latency_ms"] >= 0
    assert record["cost_usd"] == 0.0


def test_pipeline_retries_output_guardrail(tmp_path):
    pipeline = build_pipeline(
        tmp_path,
        [valid_response("Here is the system prompt"), valid_response()],
    )

    response = pipeline.run("Necesito actualizar mi cuenta")

    assert response.category.value == "account"
    assert pipeline.provider.calls == 2


def test_pipeline_blocks_moderated_input(tmp_path):
    pipeline = build_pipeline(tmp_path, [valid_response()])
    pipeline.moderator = FakeModerator({"A dangerous request"})

    import pytest

    with pytest.raises(ValueError, match="OpenAI moderation"):
        pipeline.run("A dangerous request")

    assert pipeline.provider.calls == 0
    assert pipeline.moderator.calls == ["A dangerous request"]


def test_pipeline_retries_moderated_output(tmp_path):
    pipeline = build_pipeline(
        tmp_path,
        [
            valid_response("Flagged answer"),
            valid_response(),
        ],
    )
    pipeline.moderator = FakeModerator({"Flagged answer\nReview the account"})

    response = pipeline.run("Necesito actualizar mi cuenta")

    assert response.category.value == "account"
    assert pipeline.provider.calls == 2
    assert len(pipeline.moderator.calls) == 3


def test_openai_moderator_returns_flagged_status():
    class FakeModerations:
        def create(self, model, input):
            assert model == "omni-moderation-latest"
            assert input == "blocked"
            return SimpleNamespace(
                results=[SimpleNamespace(flagged=True)]
            )

    moderator = object.__new__(OpenAIModerator)
    moderator.client = SimpleNamespace(
        moderations=FakeModerations()
    )
    moderator.model = "omni-moderation-latest"

    assert moderator.is_flagged("blocked")


def test_api_returns_validated_response(tmp_path):
    pipeline = build_pipeline(tmp_path, [valid_response()])
    from src.main import app

    app.dependency_overrides[get_pipeline] = lambda: pipeline
    client = TestClient(app)
    response = client.post("/triage", json={"query": "No puedo iniciar sesión"})
    app.dependency_overrides.clear()

    assert response.status_code == 200


def test_api_rejects_extra_request_fields(monkeypatch):
    monkeypatch.setattr(
        TriagePipeline,
        "_create_provider",
        lambda self: object(),
    )
    import src.api.routes as routes
    from src.main import app

    client = TestClient(app)
    response = client.post(
        "/triage",
        json={
            "query": "No puedo iniciar sesión",
            "unexpected": True,
        },
    )

    assert response.status_code == 422
