from pathlib import Path

import yaml


def load_prompt(
    prompts_path: str,
    version: str,
) -> dict:

    path = Path(prompts_path) / f"triage_{version}.yaml"

    if not path.exists():
        raise ValueError(
            f"Prompt version not found: {version}"
        )

    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if (
        not isinstance(data, dict)
        or "system" not in data
        or "user_template" not in data
    ):
        raise ValueError(
            f"Invalid prompt file: {path}"
        )

    return data