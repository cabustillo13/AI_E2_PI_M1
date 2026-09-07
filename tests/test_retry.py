import pytest

from ticketflow.pipeline.retry import (
    parse_response,
)


def test_parse_valid_json():
    response = parse_response(
        '{"answer":"ok",'
        '"confidence":0.9,'
        '"category":"other",'
        '"actions":["review"]}'
    )

    assert (
        response.category.value
        == "other"
    )


def test_reject_invalid_json():
    with pytest.raises(
        ValueError
    ):
        parse_response(
            "not json"
        )