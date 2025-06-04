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
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any
import time

import server.models as models

# region Worker Registration and Management

async def assign_new_jobs():
    pass

class WorkerRegistrationData(BaseModel):
    namespace_name: str
    username: str | None  # If None, runs of all users are considered.
    metric: str


class WorkerRegistrationResponse(BaseModel):
    worker_id: int
    num_jobs: int  # estimated number of remaining jobs at the moment (in case it is zero and the worker is working in one shot mode, it can exit without fully loading expensive libraries/models/etc.)


@litestar.post("/workers/register")
async def register_worker(
    data: WorkerRegistrationData,
    transaction: AsyncSession,
) -> WorkerRegistrationResponse:
    # Create a worker record
    namespace_query = select(models.Namespace).where(
        models.Namespace.name == data.namespace_name
    )
    namespace = await transaction.scalar(namespace_query)
    if namespace is None:
        raise litestar.exceptions.NotFoundException(
            f"Namespace with name '{data.namespace_name}' not found."
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
    )
    transaction.add(worker)
    await transaction.flush()
    # TODO: Create a list of affected runs and corresponding jobs. Count only those that are not finished yet.
    return WorkerRegistrationResponse(
        worker_id=worker.id,
        num_jobs=0,  # Replace with the actual number of jobs
    )


class ReadWorker(BaseModel):
    id: int
    namespace_name: str
    username: str | None
    status: models.WorkerStatus
    last_heartbeat: float


@litestar.get("/workers/{worker_id:int}")
async def get_worker(
    worker_id: int,
    transaction: AsyncSession,
) -> ReadWorker:
    worker = await transaction.get(models.Worker, worker_id)
    if worker is None:
        raise litestar.exceptions.NotFoundException(
            f"Worker with ID '{worker_id}' not found."
        )
    return ReadWorker(
        id=worker.id,
        namespace_name=worker.namespace.name,
        username=worker.user.username,
        status=worker.status,
        last_heartbeat=worker.last_heartbeat,
    )


@litestar.post("/workers/{worker_id:int}/unregister")
async def unregister_worker(
    worker_id: int,
    transaction: AsyncSession,
) -> None:
    """Explicitly unregister a worker from the server. In case the worker forgets to call this, the cleanup will take place after a timeout."""
    try:
        worker = await transaction.get(models.Worker, worker_id)
    except NoResultFound:
        raise litestar.exceptions.NotFoundException(
            f"Worker with ID '{worker_id}' not found."
        )
    assert worker is not None
    worker.status = models.WorkerStatus.FINISHED

    # TODO: we also have to dissociate the worker from any jobs it was assigned to and were not finished yet.

    await transaction.commit()


@litestar.put("/workers/{worker_id:int}/heartbeat")
async def heartbeat_worker(
    worker_id: int,
    transaction: AsyncSession,
) -> None:
    """Update the worker's last heartbeat time to indicate that it is still alive."""
    try:
        worker = await transaction.get(models.Worker, worker_id)
    except NoResultFound:
        raise litestar.exceptions.NotFoundException(
            f"Worker with ID '{worker_id}' not found."
        )
    assert worker is not None
    worker.last_heartbeat = time.time()
    await transaction.commit()


# endregion

# region Job Management


# @litestar.post()
# async def assign_job(
#     request: Any,
#     transaction: AsyncSession,
# ):
#     pass


# @litestar.post()
# async def report_job_result(
#     request: Any,
#     transaction: AsyncSession,
# ):
#     pass


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
    # assign_job,
    # report_job_result,
    # get_job,
]
