"""
Business logic services for the application.

This module contains core business logic functions that can be used
across different parts of the application (routes, tasks, etc.).
"""

from sqlalchemy import select, and_
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

import server.models as models


async def find_runs_without_jobs(
    transaction: AsyncSession, namespace_id: int, metric: str
) -> List[models.TranslationRun]:
    """Find translation runs that do not have associated jobs for the given namespace and metric."""
    jobs = aliased(models.Job)

    query = (
        select(models.TranslationRun)
        .outerjoin(
            jobs,
            and_(models.TranslationRun.id == jobs.run_id, jobs.metric == metric),
        )
        .filter(models.TranslationRun.namespace_id == namespace_id, jobs.id.is_(None))
    )

    result = await transaction.execute(query)
    return list(result.scalars().all())


async def create_new_jobs(transaction: AsyncSession, worker: models.Worker) -> List[models.Job]:
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
