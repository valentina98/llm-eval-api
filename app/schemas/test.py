from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class RunTestRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=2000)
    test_type: Literal["length", "keyword", "llm_judge"]


class JudgeScore(BaseModel):
    model: str
    score: float
    reason: str


class TestResultResponse(BaseModel):
    id: int
    input: str
    output: str | None = None
    test_type: str
    result: Literal["pending", "passed", "failed"]
    score: float | None = None
    judge_scores: list[JudgeScore] = []
    judge_agreement: float | None = None
    judge_errors: list[dict] = []

    @field_validator("judge_scores", "judge_errors", mode="before")
    @classmethod
    def coerce_none_to_list(cls, v: object) -> object:
        return v if v is not None else []

    execution_time: float
    llm_source: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class RunTestResponse(BaseModel):
    id: int
    result: Literal["pending", "passed", "failed"]
