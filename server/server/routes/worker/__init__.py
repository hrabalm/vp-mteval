"""
Process:

1. Worker announces namespace, optionally user and other filters and what metrics it handles.
2. Server creates a list of corresponding jobs and runs and initializes them if they don't already exist. It responds with success.
3. Worker asks for a job, server assigns it or anounces that there are no jobs available.
4. Worker processes the job and reports the result. If the job already exists, error is raised. (concurrency issues)

Other notes:
- Workers and jobs have an assigned uuid.
- Jobs have state and expiration time. It would be ideal to keep track if the worker is alive, but that might be needlessly complicated for now.

For now, we will implement this with HTTP requests, but
perhaps gRPC would be a better fit in the future.
"""

import litestar
import litestar.exceptions
import litestar.status_codes
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.orm import aliased, selectinload
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Optional
import time

import server.models as models

# region Worker Registration and Management


async def find_runs_without_jobs(
    transaction: AsyncSession, namespace_id: int, metric: str
):
    """Find translation runs that do not have associated jobs for the given namespace and metric."""
    jobs = aliased(models.Job)

    query = (
        select(models.TranslationRun)
        .outerjoin(
            jobs,
            and_(models.TranslationRun.id == jobs.run_id, jobs.metric == metric),
        )
        .filter(models.TranslationRun.namespace_id == namespace_id, jobs.id == None)
    )

    result = await transaction.execute(query)
    return result.scalars().all()


async def create_new_jobs(transaction: AsyncSession, worker: models.Worker):
    """Create new jobs for translation runs that don't have associated jobs yet for this worker."""
    # Find runs without jobs for this worker
    runs_without_jobs = await find_runs_without_jobs(
        transaction, worker.namespace_id, worker.metric
    )

    # Create a new job for each run
    jobs = []
    for run in runs_without_jobs:
        job = models.Job(
            namespace_id=worker.namespace_id,
            user_id=worker.user_id,
            run_id=run.id,
            queue="default",  # Default queue, could be customized based on requirements
            priority=1,  # Default priority
            status=models.JobStatus.PENDING,
            metric=worker.metric,
            payload={},  # Empty payload initially
        )
        transaction.add(job)
        jobs.append(job)

    # Only commit if we actually created jobs
    if jobs:
        await transaction.flush()

    return jobs


class WorkerRegistrationData(BaseModel):
    metric: str
    metric_requires_references: bool
    username: str | None = None  # If None, runs of all users are considered.
    queue: str | None = (
        None  # If None, the worker will be assigned to the default queue.
    )


class WorkerRegistrationResponse(BaseModel):
    worker_id: int
    num_jobs: int  # estimated number of remaining jobs at the moment (in case it is zero and the worker is working in one shot mode, it can exit without fully loading expensive libraries/models/etc.)


@litestar.post("/namespaces/{namespace_name:str}/workers/register")
async def register_worker(
    namespace_name: str,
    data: WorkerRegistrationData,
    transaction: AsyncSession,
) -> WorkerRegistrationResponse:
    # Create a worker record
    namespace_query = select(models.Namespace).where(
        models.Namespace.name == namespace_name
    )
    namespace = await transaction.scalar(namespace_query)
    if namespace is None:
        raise litestar.exceptions.NotFoundException(
            f"Namespace with name '{namespace_name}' not found."
        )

    user_query = select(models.User).where(models.User.username == data.username)
    user = await transaction.scalar(user_query)
    if user is None:
        raise litestar.exceptions.NotFoundException(
            f"User with username '{data.username}' not found."
        )
    worker = models.Worker(
        namespace_id=namespace.id,
        user_id=user.id,
        status=models.WorkerStatus.WAITING,
        metric=data.metric,
        metric_requires_references=data.metric_requires_references,
        queue=data.queue or "default",  # Default to "default" queue if not specified
    )
    transaction.add(worker)
    await transaction.flush()

    # Create and assign jobs for the worker
    # note that they are not yet assigned to it yet, because
    # another worker doing the same metric might get to them first.
    jobs = await create_new_jobs(transaction, worker)
    await transaction.flush()

    return WorkerRegistrationResponse(
        worker_id=worker.id,
        num_jobs=len(jobs),
    )


class ReadWorker(BaseModel):
    id: int
    namespace_name: str
    username: str | None
    status: models.WorkerStatus
    metric: str
    metric_requires_references: bool
    last_heartbeat: float


@litestar.get("/namespaces/{namespace_name:str}/workers/{worker_id:int}")
async def get_worker(
    namespace_name: str,
    worker_id: int,
    transaction: AsyncSession,
) -> ReadWorker:
    namespace_query = select(models.Namespace).where(
        models.Namespace.name == namespace_name
    )
    namespace = await transaction.scalar(namespace_query)
    if namespace is None:
        raise litestar.exceptions.NotFoundException(
            f"Namespace with name '{namespace_name}' not found."
        )

    worker = await transaction.get(models.Worker, worker_id)
    if worker is None or worker.namespace_id != namespace.id:
        raise litestar.exceptions.NotFoundException(
            f"Worker with ID '{worker_id}' not found in namespace '{namespace_name}'."
        )
    return ReadWorker(
        id=worker.id,
        namespace_name=worker.namespace.name,
        username=worker.user.username,
        status=worker.status,
        metric=worker.metric,
        metric_requires_references=worker.metric_requires_references,
        last_heartbeat=worker.last_heartbeat,
    )


@litestar.post("/namespaces/{namespace_name:str}/workers/{worker_id:int}/unregister")
async def unregister_worker(
    namespace_name: str,
    worker_id: int,
    transaction: AsyncSession,
) -> None:
    """Explicitly unregister a worker from the server. In case the worker forgets to call this, the cleanup will take place after a timeout."""
    namespace_query = select(models.Namespace).where(
        models.Namespace.name == namespace_name
    )
    namespace = await transaction.scalar(namespace_query)
    if namespace is None:
        raise litestar.exceptions.NotFoundException(
            f"Namespace with name '{namespace_name}' not found."
        )

    try:
        worker = await transaction.get(models.Worker, worker_id)
    except NoResultFound:
        raise litestar.exceptions.NotFoundException(
            f"Worker with ID '{worker_id}' not found."
        )
    if worker is None or worker.namespace_id != namespace.id:
        raise litestar.exceptions.NotFoundException(
            f"Worker with ID '{worker_id}' not found in namespace '{namespace_name}'."
        )
    
    worker.status = models.WorkerStatus.FINISHED

    # TODO: we also have to dissociate the worker from any jobs it was assigned to and were not finished yet.
    query = select(models.Job).where(models.Job.worker_id == worker_id)
    unfinished_jobs = await transaction.scalars(query).all()
    print(
        f"Worker {worker_id} is ending with {len(unfinished_jobs)} unfinished jobs..."
    )
    for job in unfinished_jobs:
        job.worker_id = None
        job.status = models.JobStatus.PENDING

    await transaction.commit()


@litestar.put("/namespaces/{namespace_name:str}/workers/{worker_id:int}/heartbeat")
async def heartbeat_worker(
    namespace_name: str,
    worker_id: int,
    transaction: AsyncSession,
) -> None:
    """Update the worker's last heartbeat time to indicate that it is still alive."""
    namespace_query = select(models.Namespace).where(
        models.Namespace.name == namespace_name
    )
    namespace = await transaction.scalar(namespace_query)
    if namespace is None:
        raise litestar.exceptions.NotFoundException(
            f"Namespace with name '{namespace_name}' not found."
        )

    try:
        worker = await transaction.get(models.Worker, worker_id)
    except NoResultFound:
        raise litestar.exceptions.NotFoundException(
            f"Worker with ID '{worker_id}' not found."
        )
    if worker is None or worker.namespace_id != namespace.id:
        raise litestar.exceptions.NotFoundException(
            f"Worker with ID '{worker_id}' not found in namespace '{namespace_name}'."
        )
        
    worker.last_heartbeat = time.time()
    await transaction.commit()


# endregion

# region Job Management


# FIXME: this type should not be duplicated, move it to a commin place
class ReadSegment(BaseModel):
    src: str
    tgt: str
    ref: Optional[str] = None


class ReadJob(BaseModel):
    id: int
    namespace_id: int
    user_id: int | None
    run_id: int
    queue: str
    priority: int
    status: models.JobStatus
    metric: str
    payload: dict | None
    segments: list[ReadSegment] | None = None
    source_lang: str
    target_lang: str


async def _assign_job_to_worker(
    worker_id: int,
    transaction: AsyncSession,
) -> models.Job | None:
    """Assign a job to a worker if available."""
    # Find a job that is pending and not assigned to any worker
    worker = await transaction.get(models.Worker, worker_id)
    if worker is None:
        raise litestar.exceptions.NotFoundException(
            f"Worker with ID '{worker_id}' not found."
        )

    job_query = (
        select(models.Job)
        .options(
            selectinload(models.Job.run)
            .selectinload(models.TranslationRun.dataset)
            .selectinload(models.Dataset.segments),
            selectinload(models.Job.run).selectinload(
                models.TranslationRun.translations
            ),
        )
        .where(
            models.Job.namespace_id == worker.namespace_id,
            models.Job.status == models.JobStatus.PENDING,
            models.Job.worker_id == None,  # Not assigned to any worker
            # Only add the reference requirement if the metric requires references
            *(
                [
                    models.Job.run.has(
                        models.TranslationRun.dataset.has(
                            models.Dataset.has_reference == True
                        )
                    )
                ]
                if worker.metric_requires_references
                else []
            ),
        )
        .order_by(
            models.Job.priority.desc(),  # Prefer higher priority jobs
            models.Job.created_at.desc(),  # Prefer newer jobs
        )
        .limit(1)
    )
    job = await transaction.scalar(job_query)

    if job:
        job.worker_id = worker_id  # Assign the job to the worker
        job.status = models.JobStatus.RUNNING
        return job


@litestar.post("/namespaces/{namespace_name:str}/workers/{worker_id:int}/jobs/assign")
async def assign_job(
    namespace_name: str,
    worker_id: int,
    transaction: AsyncSession,
) -> list[ReadJob]:
    """Note that this currently returns either [] if no appropriate
    job available or a list of single job if any jobs are available."""
    namespace_query = select(models.Namespace).where(
        models.Namespace.name == namespace_name
    )
    namespace = await transaction.scalar(namespace_query)
    if namespace is None:
        raise litestar.exceptions.NotFoundException(
            f"Namespace with name '{namespace_name}' not found."
        )

    worker = await transaction.get(models.Worker, worker_id)
    if worker is None or worker.namespace_id != namespace.id:
        raise litestar.exceptions.NotFoundException(
            f"Worker with ID '{worker_id}' not found in namespace '{namespace_name}'."
        )
        
    job = await _assign_job_to_worker(worker_id, transaction)
    if job is None:
        return []
    segments = [
        ReadSegment(
            src=ds.src,
            tgt=ts.tgt,
            ref=ds.tgt if ds.tgt is not None else None,
        )
        for ds, ts in zip(job.run.dataset.segments, job.run.translations)
    ]
    return [
        ReadJob(
            id=job.id,
            namespace_id=job.namespace_id,
            user_id=job.user_id,
            run_id=job.run_id,
            queue=job.queue,
            priority=job.priority,
            status=job.status,
            metric=job.metric,
            payload=job.payload or {},
            segments=segments,
            source_lang=job.run.dataset.source_lang,
            target_lang=job.run.dataset.target_lang,
        )
    ]


class PostSegmentMetric(BaseModel):
    name: str
    higher_is_better: bool
    scores: list[float]


class PostDatasetMetric(BaseModel):
    name: str
    higher_is_better: bool
    score: float


class JobResultRequest(BaseModel):
    job_id: int
    dataset_level_metrics: list[PostDatasetMetric]
    segment_level_metrics: list[PostSegmentMetric]


@litestar.post("/namespaces/{namespace_name:str}/workers/{worker_id:int}/jobs/{job_id:int}/report_result")
async def report_job_result(
    namespace_name: str,
    worker_id: int,
    job_id: int,
    data: JobResultRequest,
    transaction: AsyncSession,
) -> None:
    namespace_query = select(models.Namespace).where(
        models.Namespace.name == namespace_name
    )
    namespace = await transaction.scalar(namespace_query)
    if namespace is None:
        raise litestar.exceptions.NotFoundException(
            f"Namespace with name '{namespace_name}' not found."
        )

    worker = await transaction.get(models.Worker, worker_id)
    if worker is None or worker.namespace_id != namespace.id:
        raise litestar.exceptions.NotFoundException(
            f"Worker with ID '{worker_id}' not found in namespace '{namespace_name}'."
        )
        
    job_query = (
        select(models.Job)
        .options(
            selectinload(models.Job.run)
            .selectinload(models.TranslationRun.dataset)
            .selectinload(models.Dataset.segments),
            selectinload(models.Job.run).selectinload(
                models.TranslationRun.translations
            ),
        )
        .where(models.Job.id == job_id)
    )
    job = await transaction.scalar(job_query)
    if job is None:
        raise litestar.exceptions.NotFoundException(
            f"Job with ID '{job_id}' not found."
        )
    if job.worker_id != worker_id:
        raise litestar.exceptions.HTTPException(
            f"Job with ID '{job_id}' is not assigned to worker with ID '{worker_id}'.",
            status_code=litestar.status_codes.HTTP_400_BAD_REQUEST,
        )

    # Save dataset level metrics
    for dataset_metric in data.dataset_level_metrics:
        metric = models.DatasetMetric(
            run_id=job.run_id,
            name=dataset_metric.name,
            higher_is_better=dataset_metric.higher_is_better,
            score=dataset_metric.score,
        )
        transaction.add(metric)
    
    # Save segment level metrics
    for segment_metric in data.segment_level_metrics:
        for idx, score in enumerate(segment_metric.scores):
            metric = models.SegmentMetric(
                run_id=job.run_id,
                name=segment_metric.name,
                higher_is_better=segment_metric.higher_is_better,
                score=score,
                segment_translation_id=job.run.translations[idx].id,
                segment_idx=idx,
            )
            transaction.add(metric)

# @litestar.get()
# async def get_job(
#     request: Any,
#     transaction: AsyncSession,
# ):
#     pass


# endregion

worker_routes = [
    register_worker,
    get_worker,
    unregister_worker,
    heartbeat_worker,
    assign_job,
    report_job_result,
    # get_job,
]
