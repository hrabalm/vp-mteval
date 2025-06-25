from typing import ClassVar, Protocol

from pydantic import BaseModel


class Segment(BaseModel):
    src: str
    tgt: str
    ref: str | None = None


class WorkerExample(BaseModel):
    job_id: int
    segments: list[Segment]
    src_lang: str
    tgt_lang: str


class WorkerExampleResult(BaseModel):
    job_id: int
    name: str
    segment_scores: list[float] | None
    dataset_score: float | None
    higher_is_better: bool


class WorkerRegistrationResponse(BaseModel):
    worker_id: int
    num_jobs: int


class MetricsProcessorProtocol(Protocol):
    """Synchronous worker that continually processes examples from a queue."""

    name: ClassVar[str]
    requires_references: ClassVar[bool]
    higher_is_better: ClassVar[bool] = True

    def process_example(self, example: WorkerExample) -> WorkerExampleResult: ...
