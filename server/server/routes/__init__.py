from typing import Any, Optional

import litestar
from litestar import Controller, Litestar, Router, get, post
from litestar.exceptions import ClientException, NotFoundException
from litestar.response import Template
from litestar.status_codes import HTTP_200_OK, HTTP_409_CONFLICT
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import server.events as events
import server.models as models
import server.routes.worker as worker_module  # Changed import
import server.utils as utils


class SegmentPostData(BaseModel):
    src: str
    tgt: str
    ref: str | None = None


class TranslationRunPostData(BaseModel):
    """Complex data structure that also contains a list of segments and allows
    us to either find or create the related dataset."""

    namespace_name: str
    dataset_name: str
    dataset_source_lang: str
    dataset_target_lang: str
    segments: list[SegmentPostData]
    uuid: Optional[str] = None
    config: dict[str, Any] = {}


async def get_or_create_default_namespace(
    transaction: AsyncSession,
) -> models.Namespace:
    """Create the default namespace if it does not exist. This is a
    convenience function to allow us to create the default namespace
    in the database."""
    # FIXME: we should move the default namespace creation to DB
    # migration/initialization
    query = select(models.Namespace).where(models.Namespace.id == 1)
    result = await transaction.execute(query)
    try:
        return result.scalar_one()
    except NoResultFound:
        # create the default namespace
        namespace = models.Namespace(id=1, name="default")
        transaction.add(namespace)
        return namespace


async def get_namespace_by_name(
    namespace_name: str, transaction: AsyncSession
) -> models.Namespace:
    """Get the namespace by name."""
    query = select(models.Namespace).where(models.Namespace.name == namespace_name)
    result = await transaction.execute(query)
    try:
        return result.scalar_one()
    except NoResultFound as e:
        raise NotFoundException(detail=f"Namespace {namespace_name!r} not found") from e
    except MultipleResultsFound as e:
        raise ClientException(
            status_code=HTTP_409_CONFLICT,
            detail=f"Namespace {namespace_name!r} not unique",
        ) from e


async def get_dataset_by_hash(
    dataset_hash_value: str, transaction: AsyncSession
) -> models.Dataset:
    query = select(models.Dataset).where(
        models.Dataset.data_hash == dataset_hash_value,
    )
    result = await transaction.execute(query)
    try:
        return result.scalar_one()
    except NoResultFound as e:
        raise NotFoundException(
            detail=f"Dataset {dataset_hash_value!r} not found"
        ) from e
    except MultipleResultsFound as e:
        raise ClientException(
            status_code=HTTP_409_CONFLICT,
            detail=f"Dataset {dataset_hash_value!r} not unique",
        ) from e


class ReadSegment(BaseModel):
    idx: int
    src: str
    tgt: str
    ref: Optional[str] = None


class ReadSegmentMetric(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    segment_idx: int
    name: str
    score: float
    higher_is_better: bool = True

    run_id: int
    segment_translation_id: int


class ReadDatasetMetric(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    score: float
    higher_is_better: bool = True

    run_id: int


class ReadGenericMetric(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    pass


class ReadTranslationRun(BaseModel):
    id: int
    uuid: str
    dataset_id: int
    namespace_name: str
    config: dict[str, Any]
    dataset_metrics: list[ReadDatasetMetric]


class ReadTranslationRunDetail(BaseModel):
    id: int
    uuid: str
    dataset_id: int
    namespace_name: str
    config: dict[str, Any]
    segments: list[ReadSegment] | None = None
    segment_metrics: list[ReadSegmentMetric]
    dataset_metrics: list[ReadDatasetMetric]


class ReadNamespace(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


async def get_or_create_dataset(
    dataset_hash_value: str,
    namespace_id: int,
    dataset_name: str,
    source_lang: str,
    target_lang: str,
    has_reference: bool,
    transaction: AsyncSession,
) -> models.Dataset:
    """Get an existing dataset by hash or create a new one."""
    try:
        return await get_dataset_by_hash(dataset_hash_value, transaction)
    except NotFoundException:
        dataset = models.Dataset(
            source_lang=source_lang,
            target_lang=target_lang,
            data_hash=dataset_hash_value,
            has_reference=has_reference,
            namespace_id=namespace_id,
        )
        transaction.add(dataset)
        await transaction.flush()

        dataset_name_obj = models.DatasetName(dataset=dataset, name=dataset_name)
        transaction.add(dataset_name_obj)
        await transaction.flush()

        return dataset


async def create_segments_and_translations(
    segments: list[SegmentPostData],
    dataset_id: int,
    run_id: int,
    transaction: AsyncSession,
) -> None:
    """Create segment and translation records in bulk."""
    # Check if any segments exist for this dataset
    segment_count_query = await transaction.execute(
        select(models.Segment.id)
        .where(models.Segment.dataset_id == dataset_id)
        .limit(1)
    )
    segments_exist = segment_count_query.scalar() is not None

    # If no segments exist, create them all
    if not segments_exist:
        db_segments = [
            models.Segment(
                idx=idx,
                src=segment.src,
                tgt=segment.ref,
                dataset_id=dataset_id,
            )
            for idx, segment in enumerate(segments)
        ]
        transaction.add_all(db_segments)
        await transaction.flush()

    # Now get all segments (either existing or newly created)
    db_segments_query = await transaction.execute(
        select(models.Segment)
        .where(models.Segment.dataset_id == dataset_id)
        .order_by(models.Segment.idx)
    )
    db_segments = db_segments_query.scalars().all()

    # Create translations for all segments
    db_translations = [
        models.SegmentTranslation(
            run_id=run_id,
            tgt=segment.tgt,
            segment=db_segment,
            segment_idx=db_segment.idx,
        )
        for segment, db_segment in zip(segments, db_segments)
    ]
    transaction.add_all(db_translations)
    await transaction.flush()


async def _add_translation_run(
    data: TranslationRunPostData,
    db_session: AsyncSession,
    app: Litestar,
) -> ReadTranslationRunDetail:
    """Add a translation run and associated segments to the database. Also creates the dataset and namespace if they don't exist."""
    async with db_session.begin():
        # Calculate the hash of the dataset
        dataset_hash_value = utils.dataset_hash(
            data.segments, data.dataset_source_lang, data.dataset_target_lang
        )

        # Get or create namespace
        if data.namespace_name == "default":
            namespace = await get_or_create_default_namespace(db_session)
        else:
            namespace = await get_namespace_by_name(data.namespace_name, db_session)

        # check if the dataset has references
        has_reference = False
        for segment in data.segments:
            if segment.ref is not None:
                has_reference = True
                break

        # Get or create dataset
        dataset = await get_or_create_dataset(
            dataset_hash_value=dataset_hash_value,
            namespace_id=namespace.id,
            dataset_name=data.dataset_name,
            source_lang=data.dataset_source_lang,
            target_lang=data.dataset_target_lang,
            transaction=db_session,
            has_reference=has_reference,
        )

        # Create translation run
        translation_run = models.TranslationRun(
            dataset_id=dataset.id,
            namespace=namespace,
            uuid=data.uuid,
            config=data.config,
        )
        db_session.add(translation_run)
        await db_session.flush()

        # Create segments and translations
        await create_segments_and_translations(
            segments=data.segments,
            dataset_id=dataset.id,
            run_id=translation_run.id,
            transaction=db_session,
        )

    app.emit(events.RUN_CREATED, events.RunCreatedData(run_id=translation_run.id))

    return ReadTranslationRunDetail(
        id=translation_run.id,
        uuid=str(translation_run.uuid),
        dataset_id=dataset.id,
        namespace_name=namespace.name,
        config=translation_run.config,
        dataset_metrics=[],
        segment_metrics=[],
        segments=None,
    )


@post("/namespaces/{namespace_name:str}/translations-runs/")
async def add_translation_run(
    namespace_name: str,
    data: TranslationRunPostData,
    db_session: AsyncSession,
    request: litestar.Request,
) -> litestar.Response[ReadTranslationRunDetail]:
    """Add a translation run and associated segments to the database. Also creates the dataset and namespace if they don't exist.

    Note that we use db_session as a dependency directly
    to commit the transaction before emitting the event.
    """
    # Update the namespace_name in the data to ensure it matches the URL parameter
    data.namespace_name = namespace_name
    run = await _add_translation_run(
        data=data,
        db_session=db_session,
        app=request.app,
    )
    return litestar.Response(
        run,
    )


@get("/namespaces/{namespace_name:str}/translations-runs/")
async def get_translation_runs(
    namespace_name: str,
    transaction: AsyncSession,
) -> list[ReadTranslationRun]:
    """Get all translation runs for a specific namespace."""
    # Get namespace by name
    namespace = await get_namespace_by_name(namespace_name, transaction)

    query = (
        select(models.TranslationRun)
        .options(
            selectinload(models.TranslationRun.namespace),
            selectinload(models.TranslationRun.segment_metrics),
            selectinload(models.TranslationRun.dataset_metrics),
        )
        .where(models.TranslationRun.namespace_id == namespace.id)
        .order_by(models.TranslationRun.id.desc())
    )
    result = await transaction.execute(query)
    runs = result.scalars().all()

    return [
        ReadTranslationRun(
            id=run.id,
            uuid=str(run.uuid),
            dataset_id=run.dataset_id,
            namespace_name=run.namespace.name,
            config=run.config,
            dataset_metrics=[
                ReadDatasetMetric.model_validate(dm) for dm in run.dataset_metrics
            ],
        )
        for run in runs
    ]


@get("/namespaces/{namespace_name:str}/translations-runs/{run_id:int}")
async def get_translation_run(
    namespace_name: str,
    run_id: int,
    transaction: AsyncSession,
) -> ReadTranslationRunDetail:
    """Get a translation run by ID within a specific namespace."""
    # Get namespace by name
    namespace = await get_namespace_by_name(namespace_name, transaction)

    query = (
        select(models.TranslationRun)
        .options(
            selectinload(models.TranslationRun.namespace),
            selectinload(models.TranslationRun.segment_metrics),
            selectinload(models.TranslationRun.dataset_metrics),
            selectinload(models.TranslationRun.dataset).selectinload(
                models.Dataset.segments
            ),
            selectinload(models.TranslationRun.translations),
        )
        .where(
            models.TranslationRun.id == run_id,
            models.TranslationRun.namespace_id == namespace.id,
        )
    )
    result = await transaction.execute(query)
    try:
        result1 = result.scalar_one()
        dataset_segments = sorted(result1.dataset.segments, key=lambda x: x.idx)
        translation_segments = sorted(result1.translations, key=lambda x: x.segment.idx)
        segments = [
            ReadSegment(
                idx=ds.idx,
                src=ds.src,
                tgt=ts.tgt,
                ref=ds.tgt if ds.tgt is not None else None,
            )
            for ds, ts in zip(dataset_segments, translation_segments)
        ]
        return ReadTranslationRunDetail(
            id=result1.id,
            uuid=str(result1.uuid),
            dataset_id=result1.dataset_id,
            namespace_name=result1.namespace.name,
            config=result1.config,
            segment_metrics=[
                ReadSegmentMetric.model_validate(sm) for sm in result1.segment_metrics
            ],
            dataset_metrics=[
                ReadDatasetMetric.model_validate(dm) for dm in result1.dataset_metrics
            ],
            segments=segments,
        )
    except NoResultFound:
        raise NotFoundException(
            detail=f"Translation run {run_id} not found in namespace '{namespace_name}'"
        )


class ReadDataset(BaseModel):
    id: int
    names: list[str]
    source_lang: str
    target_lang: str
    has_reference: bool


@get("/namespaces/{namespace_name:str}/datasets/")
async def get_datasets(
    namespace_name: str,
    transaction: AsyncSession,
) -> list[ReadDataset]:
    """Get all datasets within a specific namespace."""
    # Get namespace by name
    namespace = await get_namespace_by_name(namespace_name, transaction)

    query = (
        select(models.Dataset)
        .where(models.Dataset.namespace_id == namespace.id)
        .order_by(models.Dataset.id.desc())
    )
    result = await transaction.execute(query)
    datasets = result.scalars().all()
    return [
        ReadDataset(
            id=dataset.id,
            names=[name.name for name in dataset.names],
            source_lang=dataset.source_lang,
            target_lang=dataset.target_lang,
            has_reference=dataset.has_reference,
        )
        for dataset in datasets
    ]


@get("/namespaces/{namespace_name:str}/datasets/{dataset_id:int}")
async def get_dataset_by_id(
    namespace_name: str,
    dataset_id: int,
    transaction: AsyncSession,
) -> ReadDataset:
    """Get a dataset by ID within a specific namespace."""
    # Get namespace by name
    namespace = await get_namespace_by_name(namespace_name, transaction)

    query = (
        select(models.Dataset)
        .where(
            models.Dataset.id == dataset_id, models.Dataset.namespace_id == namespace.id
        )
        .options(selectinload(models.Dataset.segments))
    )
    result = await transaction.execute(query)
    try:
        dataset = result.scalar_one()
        return ReadDataset(
            id=dataset.id,
            names=[name.name for name in dataset.names],
            source_lang=dataset.source_lang,
            target_lang=dataset.target_lang,
            has_reference=dataset.has_reference,
        )
    except NoResultFound as e:
        raise NotFoundException(
            detail=f"Dataset {dataset_id} not found in namespace '{namespace_name}'"
        ) from e


@get("/namespaces/")
async def get_namespaces(
    transaction: AsyncSession,
) -> list[ReadNamespace]:
    """Get all namespaces."""
    query = select(models.Namespace)
    result = await transaction.execute(query)
    namespaces = result.scalars().all()
    return [ReadNamespace.model_validate(namespace) for namespace in namespaces]


class WebController(Controller):
    opt = {"exclude_from_auth": True}
    include_in_schema = False

    @get(["/", "/{path:path}"], status_code=HTTP_200_OK)
    async def index(self) -> Template:
        return Template(template_name="index.html.j2")


routes = [
    add_translation_run,
    get_translation_runs,
    get_translation_run,
    get_namespaces,
    get_datasets,
    get_dataset_by_id,
]

api_v1_router = Router(
    "/api/v1",
    route_handlers=[
        # Namespace-based routes
        *routes,
        # Worker routes
        *worker_module.worker_routes,
    ],
)
