import litestar
import litestar.events
import litestar.exceptions
import pydantic
import server.models as models
import server.plugins as plugins
import sqlalchemy
import logging
import asyncio

logger = logging.getLogger(__name__)

RUN_CREATED = "run_created"


class DatasetCreatedData(pydantic.BaseModel):
    dataset_id: int


class RunCreatedData(pydantic.BaseModel):
    run_id: int


async def compute_ngrams_on_dataset_created():
    pass


@litestar.events.listener(RUN_CREATED)
async def compute_ngrams_on_run_created(data: RunCreatedData):
    await asyncio.sleep(1)
    logger.info(f"Computing n-grams for run {data.run_id}")
    import server.ngrams as ngrams

    tokenizer_name = "v1_case"

    normalizer = ngrams.MTEvalInternationalNormalizer()
    tokenizer = ngrams.Tokenizer(case_sensitive=True)
    ngramizer = ngrams.NGramizer(tokenizer)

    async with plugins.db_config.get_session() as session:
        run = await session.get(
            models.TranslationRun,
            data.run_id,
            options=[
                sqlalchemy.orm.selectinload(models.TranslationRun.dataset).selectinload(
                    models.Dataset.segments
                ),
                sqlalchemy.orm.selectinload(models.TranslationRun.translations),
            ],
        )
        if not run:
            raise litestar.exceptions.NotFoundException(
                f"Run with ID {data.run_id} not found."
            )
        if not run.dataset.has_reference:
            # N-grams are only computed for datasets with reference translations.
            logger.info(
                f"Skipping n-grams computation for run {data.run_id} as the dataset does not have reference translations."
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


listeners = [compute_ngrams_on_run_created]
