from anthropic import Anthropic

from ticketflow.llm.base import LLMResult


class AnthropicProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMResult:

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            temperature=0,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        )

        text = "".join(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        )

        return LLMResult(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=(
                response.usage.input_tokens
                + response.usage.output_tokens
            ),
            model=self.model,
            provider="anthropic",
        )