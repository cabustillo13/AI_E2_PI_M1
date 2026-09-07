from ticketflow.prompts.loader import (
    load_prompt,
)


def test_prompt_v3_exists():
    prompt = load_prompt(
        "prompts",
        "v3",
    )

    assert prompt["version"] == "v3"

    assert (
        "{{query}}"
        in prompt["user_template"]
    )