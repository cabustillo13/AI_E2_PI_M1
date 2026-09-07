import json

from pydantic import ValidationError

from ticketflow.models.response import TriageResponse


def parse_response(text: str) -> TriageResponse:
    try:
        data = json.loads(text)

        return TriageResponse.model_validate(data)

    except (
        json.JSONDecodeError,
        ValidationError,
    ) as exc:

        raise ValueError(
            "LLM returned an invalid TicketFlow response"
        ) from exc