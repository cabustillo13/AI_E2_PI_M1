import pytest
from pydantic import ValidationError

from ticketflow.models.response import (
    TriageResponse,
)


def test_valid_response():
    response = TriageResponse(
        answer="We can help.",
        confidence=0.9,
        category="billing",
        actions=["Review invoice"],
    )

    assert (
        response.category.value
        == "billing"
    )


def test_invalid_category():
    with pytest.raises(
        ValidationError
    ):
        TriageResponse(
            answer="x",
            confidence=0.9,
            category="invalid",
            actions=["x"],
        )


def test_invalid_confidence():
    with pytest.raises(
        ValidationError
    ):
        TriageResponse(
            answer="x",
            confidence=1.1,
            category="other",
            actions=["x"],
        )