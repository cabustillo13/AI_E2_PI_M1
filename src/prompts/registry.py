from src.prompts.loader import load_prompt


class PromptRegistry:
    def __init__(self, prompts_path: str) -> None:
        self.prompts_path = prompts_path

    def get(self, version: str, kind: str = "triage") -> dict:
        return load_prompt(
            self.prompts_path,
            version,
            kind=kind,
        )