import time
import uuid

from src.config import get_settings
from src.metrics.logger import MetricsLogger
from src.pipeline.guardrails import (
    detect_prompt_injection,
    validate_output,
)
from src.pipeline.retry import parse_response
from src.prompts.registry import PromptRegistry


class TriagePipeline:
    def __init__(self) -> None:
        settings = get_settings()

        self.settings = settings
        self.prompts = PromptRegistry(
            settings.prompts_path
        )
        self.metrics = MetricsLogger(
            settings.metrics_path
        )
        self.provider = self._create_provider()
        self.moderator = self._create_moderator()

    def _create_moderator(self):
        if not self.settings.moderation_enabled:
            return None

        if not self.settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when moderation is enabled"
            )

        from src.llm.moderation import OpenAIModerator

        return OpenAIModerator(
            self.settings.openai_api_key,
            self.settings.moderation_model,
        )

    def _create_provider(self):
        if self.settings.llm_provider == "openai":

            from src.llm.openai import OpenAIProvider

            if not self.settings.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY is not configured"
                )

            return OpenAIProvider(
                self.settings.openai_api_key,
                self.settings.llm_model,
            )

        if self.settings.llm_provider == "anthropic":

            from src.llm.anthropic import AnthropicProvider

            if not self.settings.anthropic_api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY is not configured"
                )

            return AnthropicProvider(
                self.settings.anthropic_api_key,
                self.settings.llm_model,
            )

        raise ValueError(
            "LLM_PROVIDER must be 'openai' or 'anthropic'"
        )

    def run(self, query: str):

        if detect_prompt_injection(query):
            raise ValueError(
                "Request blocked by input security guardrail"
            )

        if len(query) > self.settings.max_input_chars:
            raise ValueError(
                "Query is too long"
            )

        self._moderate_input(query)

        prompt = self.prompts.get(
            self.settings.prompt_version
        )

        user_prompt = prompt["user_template"].replace(
            "{{query}}",
            query,
        )

        request_id = str(uuid.uuid4())

        started = time.perf_counter()

        retries = 0
        result = None

        for attempt in range(
            self.settings.max_retries + 1
        ):

            result = self.provider.generate(
                prompt["system"],
                user_prompt,
            )

            try:
                response = parse_response(
                    result.text
                )

                validate_output(
                    response.answer
                )

                self._moderate_output(response)

                break

            except ValueError:

                retries = attempt + 1

                if attempt >= self.settings.max_retries:
                    raise

        else:
            raise ValueError(
                "Unable to obtain a valid response"
            )

        latency_ms = round(
            (time.perf_counter() - started) * 1000,
            2,
        )

        self.metrics.log(
            request_id=request_id,
            provider=result.provider,
            model=result.model,
            prompt_version=self.settings.prompt_version,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            latency_ms=latency_ms,
            retry_count=retries,
            cost_usd=estimate_cost(
                result.provider,
                result.model,
                result.input_tokens,
                result.output_tokens,
            ),
        )

        return response

    def _moderate_input(self, query: str) -> None:
        if self.moderator and self.moderator.is_flagged(query):
            raise ValueError(
                "Request blocked by OpenAI moderation"
            )

    def _moderate_output(self, response) -> None:
        if not self.moderator:
            return

        content = "\n".join(
            [
                response.answer,
                *response.actions,
            ]
        )

        if self.moderator.is_flagged(content):
            raise ValueError(
                "Response blocked by OpenAI moderation"
            )


def estimate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:

    prices = {
        "openai": {
            "gpt-5-mini": (
                0.25,
                2.00,
            ),
        },
        "anthropic": {
            "claude-3-5-haiku-latest": (
                0.80,
                4.00,
            ),
        },
    }

    input_price, output_price = prices.get(
        provider,
        {},
    ).get(
        model,
        (0.0, 0.0),
    )

    return round(
        (
            input_tokens * input_price
            + output_tokens * output_price
        )
        / 1_000_000,
        8,
    )