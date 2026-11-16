"""Contratos en las fronteras API, corpus y herramientas."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Document(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source: str = Field(min_length=1)
    simulated: Literal[True]
    before_minutes: float = Field(gt=0)
    after_minutes: float = Field(ge=0)
    volume_month: int = Field(gt=0)

    @model_validator(mode='after')
    def consistent(self):
        if self.after_minutes > self.before_minutes:
            raise ValueError('El tiempo posterior supera al inicial')
        return self


class SearchInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=3, ge=1, le=10, strict=True)


class SearchOutput(BaseModel):
    documents: list[Document]


class CalculationInput(BaseModel):
    documents: list[Document] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def unique(self):
        if len({d.id for d in self.documents}) != len(self.documents):
            raise ValueError('Identificadores duplicados')
        return self


class CalculationRow(BaseModel):
    id: str
    source: str
    before_hours: float = Field(gt=0, allow_inf_nan=False)
    after_hours: float = Field(ge=0, allow_inf_nan=False)
    saved_hours: float = Field(ge=0, allow_inf_nan=False)


class CalculationOutput(BaseModel):
    rows: list[CalculationRow]
    before_hours: float = Field(gt=0, allow_inf_nan=False)
    after_hours: float = Field(ge=0, allow_inf_nan=False)
    saved_hours: float = Field(ge=0, allow_inf_nan=False)
    reduction_pct: float = Field(ge=0, le=100, allow_inf_nan=False)
    source_ids: list[str]


Status = Literal['PENDING', 'RUNNING', 'DONE', 'FAILED', 'WAITING_APPROVAL', 'REJECTED']


class Accepted(BaseModel):
    job_id: UUID
    status: Status


class Job(Accepted):
    query: str
    action: Literal['analyze', 'publish_report']
    created_at: str
    updated_at: str
    result: str | None
    error: str | None
    decision: bool | None = None


class Health(BaseModel):
    status: Literal['ok']
