from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Category(str, Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    OTHER = "other"


class TriageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    category: Category
    actions: list[str] = Field(min_length=1)