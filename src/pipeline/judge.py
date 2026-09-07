import json

from pydantic import ValidationError

from src.llm.base import LLMProvider
from src.models.judge import JudgeVerdict
from src.prompts.registry import PromptRegistry


def judge_response(
    provider: LLMProvider,
    prompts: PromptRegistry,
    judge_prompt_version: str,
    query: str,
    category: str,
    answer: str,
    actions: list[str],
) -> JudgeVerdict:
    prompt = prompts.get(judge_prompt_version, kind="judge")

    user_prompt = (
        prompt["user_template"]
        .replace("{{query}}", query)
        .replace("{{category}}", category)
        .replace("{{answer}}", answer)
        .replace("{{actions}}", "; ".join(actions))
    )

    result = provider.generate(prompt["system"], user_prompt)

    try:
        data = json.loads(result.text)
        return JudgeVerdict.model_validate(data)

    except (json.JSONDecodeError, ValidationError):
        return JudgeVerdict(
            score=0.0,
            verdict="fail",
            reasoning="El juez no devolvió un veredicto JSON válido.",
        )
