from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class JudgeVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0, le=1)
    verdict: Literal["pass", "fail"]
    reasoning: str = Field(min_length=1)
