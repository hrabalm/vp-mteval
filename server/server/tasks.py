import server.models as models
import server.plugins as plugins
from server.config import settings
import datetime
from sqlalchemy import select
import logging

logger = logging.getLogger("server.tasks")


async def _cleanup_expired_workers_and_jobs(transaction):
    now = datetime.datetime.now(datetime.timezone.utc)
    expiration_datetime = now - datetime.timedelta(
        seconds=settings.worker_expiration_seconds
    )
    expiration_timestamp = expiration_datetime.timestamp()

    # select expired workers
    query = select(models.Worker).filter(
        models.Worker.last_heartbeat < expiration_timestamp,
        models.Worker.status == models.WorkerStatus.WORKING,
    )
    result = await transaction.execute(query)
    expired_workers = result.scalars().all()
    if expired_workers:
        # deactivate expired workers
        for worker in expired_workers:
            worker.status = models.WorkerStatus.TIMED_OUT
        await transaction.flush()


async def cleanup_expired_workers_and_jobs_task(_):
    logger.info("Starting cleanup of expired workers and jobs...")
    async with plugins.db_config.get_session() as session:
        async with session.begin():
            await _cleanup_expired_workers_and_jobs(session)
