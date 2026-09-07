from openai import OpenAI


class OpenAIModerator:
    def __init__(
        self,
        api_key: str,
        model: str = "omni-moderation-latest",
    ) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def is_flagged(self, text: str) -> bool:
        response = self.client.moderations.create(
            model=self.model,
            input=text,
        )

        return bool(response.results[0].flagged)
