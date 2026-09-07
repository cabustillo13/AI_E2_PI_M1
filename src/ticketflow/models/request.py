from pydantic import BaseModel, ConfigDict, Field


class TriageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=1,
        max_length=4000,
    )