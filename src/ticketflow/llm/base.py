from dataclasses import dataclass
from typing import Protocol


@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model: str
    provider: str


class LLMProvider(Protocol):
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMResult:
        ...