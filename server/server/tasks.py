import datetime
import logging

import litestar
import litestar.exceptions
import pydantic
from sqlalchemy import select

import server.models as models
import server.plugins as plugins
from server.config import settings
from saq.types import Context

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
        expired_worker_ids = [worker.id for worker in expired_workers]
        # deactivate expired workers
        for worker in expired_workers:
            worker.status = models.WorkerStatus.TIMED_OUT

        # fail jobs assigned to expired workers
        job_query = select(models.Job).filter(
            models.Job.worker_id.in_(expired_worker_ids),
            models.Job.status == models.JobStatus.RUNNING,
        )
        job_result = await transaction.execute(job_query)
        expired_jobs = job_result.scalars().all()
        for job in expired_jobs:
            job.status = models.JobStatus.PENDING
            job.worker_id = None  # Unassign the job from the expired worker
        await transaction.flush()


async def cleanup_expired_workers_and_jobs_task(_):
    logger.info("Starting cleanup of expired workers and jobs...")
    async with plugins.db_config.get_session() as session:
        async with session.begin():
            await _cleanup_expired_workers_and_jobs(session)


class RunCreatedData(pydantic.BaseModel):
    run_id: int


async def compute_ngrams_on_run_created(_: Context, *, data: str):
    parsed_data = RunCreatedData.model_validate_json(data)
    import sqlalchemy

    import server.ngrams as ngrams

    logger.info(f"Computing n-grams for run {parsed_data.run_id}")

    tokenizer_name = "v1_case"

    normalizer = ngrams.MTEvalInternationalNormalizer()
    tokenizer = ngrams.Tokenizer(case_sensitive=True)
    ngramizer = ngrams.NGramizer(tokenizer)

    async with plugins.db_config.get_session() as session:
        run = await session.get(
            models.TranslationRun,
            parsed_data.run_id,
            options=[
                sqlalchemy.orm.selectinload(models.TranslationRun.dataset).selectinload(
                    models.Dataset.segments
                ),
                sqlalchemy.orm.selectinload(models.TranslationRun.translations),
            ],
        )
        if not run:
            raise litestar.exceptions.NotFoundException(
                f"Run with ID {parsed_data.run_id} not found."
            )
        if not run.dataset.has_reference:
            # N-grams are only computed for datasets with reference translations.
            logger.info(
                f"Skipping n-grams computation for run {parsed_data.run_id} as the dataset does not have reference translations."
            )
            return
        reference_segments = run.dataset.segments
        target_segments = run.translations

        for tgt, ref in zip(target_segments, reference_segments, strict=True):
            tgt_norm = normalizer.normalize(tgt.tgt)
            ref_norm = normalizer.normalize(ref.tgt)

            tgt_ngrams = ngramizer.get_ngrams(tgt_norm)
            ref_ngrams = ngramizer.get_ngrams(ref_norm)

            for n in tgt_ngrams.keys():
                segment_translation_ngrams = models.SegmentTranslationNGrams(
                    run_id=run.id,
                    segment_translation=tgt,
                    tokenizer=tokenizer_name,
                    n=n,
                    ngrams=tgt_ngrams[n],
                    ngrams_ref=ref_ngrams[n],
                )
                session.add(segment_translation_ngrams)
        await session.commit()
