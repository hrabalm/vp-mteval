import json
import pathlib
import uuid as uuid_lib  # we need to rename this to avoid conflict with uuid var in dataclasses
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Optional, cast

import iso639
from advanced_alchemy.config import AsyncSessionConfig, EngineConfig
from litestar import Controller, Litestar, Router, get, post
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.contrib.sqlalchemy.plugins import SQLAlchemyAsyncConfig, SQLAlchemyPlugin
from litestar.exceptions import ClientException, NotFoundException
from litestar.response import Template
from litestar.status_codes import HTTP_200_OK, HTTP_409_CONFLICT
from litestar.template.config import TemplateConfig
from litestar_saq import CronJob, QueueConfig, SAQConfig, SAQPlugin
from litestar_vite import ViteConfig, VitePlugin
from pydantic import BaseModel, ConfigDict
from sqlalchemy import MetaData, select, text
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload

import server.models as m
import server.plugins as plugins
import server.routes.worker as worker_module  # Changed import
import server.tasks as tasks
from server.config import settings


async def provide_transaction(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncSession, None]:
    try:
        async with db_session.begin():
            yield db_session
    except IntegrityError as exc:
        raise ClientException(
            status_code=HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


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
    uuid: Optional[uuid_lib.UUID] = None
    config: dict[str, Any] = {}


def dataset_hash(segments: list[SegmentPostData], source_lang, target_lang) -> str:
    """Calculate the hash of the dataset. We canonicalize the JSON representation.
    Currently use blake2b as the hashing algorithm.

    For canonical JSON, see JCS(RFC8785):
    - https://datatracker.ietf.org/doc/html/rfc8785

    Note that we take only the source and reference segments into
    account as the target segments are linked to a run, not a dataset.
    """
    import hashlib

    from json_canonical import canonicalize

    # make langs iso639-1
    source_lang = iso639.Language.match(source_lang).part1
    target_lang = iso639.Language.match(target_lang).part1

    data = {
        "segments": [
            {
                "src": s.src,
                "ref": s.ref if s.ref is not None else "",
            }
            for s in segments
        ],
        "source_lang": source_lang,
        "target_lang": target_lang,
    }

    canonical_json = cast(bytes, canonicalize(data))
    return hashlib.blake2b(canonical_json).hexdigest()


async def get_or_create_default_namespace(transaction: AsyncSession) -> m.Namespace:
    """Create the default namespace if it does not exist. This is a
    convenience function to allow us to create the default namespace
    in the database."""
    # FIXME: we should move the default namespace creation to DB
    # migration/initialization
    query = select(m.Namespace).where(m.Namespace.id == 1)
    result = await transaction.execute(query)
    try:
        return result.scalar_one()
    except NoResultFound:
        # create the default namespace
        namespace = m.Namespace(id=1, name="default")
        transaction.add(namespace)
        return namespace


async def get_namespace_by_name(
    namespace_name: str, transaction: AsyncSession
) -> m.Namespace:
    """Get the namespace by name."""
    query = select(m.Namespace).where(m.Namespace.name == namespace_name)
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
) -> m.Dataset:
    query = select(m.Dataset).where(
        m.Dataset.data_hash == dataset_hash_value,
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
    uuid: uuid_lib.UUID
    dataset_id: int
    namespace_name: str
    config: dict[str, Any]
    dataset_metrics: list[ReadDatasetMetric]


class ReadTranslationRunDetail(BaseModel):
    id: int
    uuid: uuid_lib.UUID
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
) -> m.Dataset:
    """Get an existing dataset by hash or create a new one."""
    try:
        return await get_dataset_by_hash(dataset_hash_value, transaction)
    except NotFoundException:
        dataset = m.Dataset(
            source_lang=source_lang,
            target_lang=target_lang,
            data_hash=dataset_hash_value,
            has_reference=has_reference,
            namespace_id=namespace_id,
        )
        transaction.add(dataset)
        await transaction.flush()

        dataset_name_obj = m.DatasetName(dataset=dataset, name=dataset_name)
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
        select(m.Segment.id).where(m.Segment.dataset_id == dataset_id).limit(1)
    )
    segments_exist = segment_count_query.scalar() is not None

    # If no segments exist, create them all
    if not segments_exist:
        db_segments = [
            m.Segment(
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
        select(m.Segment)
        .where(m.Segment.dataset_id == dataset_id)
        .order_by(m.Segment.idx)
    )
    db_segments = db_segments_query.scalars().all()

    # Create translations for all segments
    db_translations = [
        m.SegmentTranslation(
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
    transaction: AsyncSession,
) -> ReadTranslationRunDetail:
    """Add a translation run and associated segments to the database. Also creates the dataset and namespace if they don't exist."""

    # Calculate the hash of the dataset
    dataset_hash_value = dataset_hash(
        data.segments, data.dataset_source_lang, data.dataset_target_lang
    )

    # Get or create namespace
    if data.namespace_name == "default":
        namespace = await get_or_create_default_namespace(transaction)
    else:
        namespace = await get_namespace_by_name(data.namespace_name, transaction)

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
        transaction=transaction,
        has_reference=has_reference,
    )

    # Create translation run
    translation_run = m.TranslationRun(
        dataset_id=dataset.id,
        namespace=namespace,
        uuid=data.uuid,
        config=data.config,
    )
    transaction.add(translation_run)
    await transaction.flush()

    # Create segments and translations
    await create_segments_and_translations(
        segments=data.segments,
        dataset_id=dataset.id,
        run_id=translation_run.id,
        transaction=transaction,
    )

    return ReadTranslationRunDetail(
        id=translation_run.id,
        uuid=translation_run.uuid,
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
    transaction: AsyncSession,
) -> ReadTranslationRun:
    """Add a translation run and associated segments to the database. Also creates the dataset and namespace if they don't exist."""
    # Update the namespace_name in the data to ensure it matches the URL parameter
    data.namespace_name = namespace_name
    return await _add_translation_run(
        data=data,
        transaction=transaction,
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
        select(m.TranslationRun)
        .options(
            selectinload(m.TranslationRun.namespace),
            selectinload(m.TranslationRun.segment_metrics),
            selectinload(m.TranslationRun.dataset_metrics),
        )
        .where(m.TranslationRun.namespace_id == namespace.id)
        .order_by(m.TranslationRun.id.desc())
    )
    result = await transaction.execute(query)
    runs = result.scalars().all()

    return [
        ReadTranslationRun(
            id=run.id,
            uuid=run.uuid,
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
        select(m.TranslationRun)
        .options(
            selectinload(m.TranslationRun.namespace),
            selectinload(m.TranslationRun.segment_metrics),
            selectinload(m.TranslationRun.dataset_metrics),
            selectinload(m.TranslationRun.dataset).selectinload(m.Dataset.segments),
            selectinload(m.TranslationRun.translations),
        )
        .where(
            m.TranslationRun.id == run_id, m.TranslationRun.namespace_id == namespace.id
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
            uuid=result1.uuid,
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
        select(m.Dataset)
        .where(m.Dataset.namespace_id == namespace.id)
        .order_by(m.Dataset.id.desc())
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
        select(m.Dataset)
        .where(m.Dataset.id == dataset_id, m.Dataset.namespace_id == namespace.id)
        .options(selectinload(m.Dataset.segments))
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
    query = select(m.Namespace)
    result = await transaction.execute(query)
    namespaces = result.scalars().all()
    return [ReadNamespace.model_validate(namespace) for namespace in namespaces]


class WebController(Controller):
    opt = {"exclude_from_auth": True}
    include_in_schema = False

    @get(["/", "/{path:path}"], status_code=HTTP_200_OK)
    async def index(self) -> Template:
        return Template(template_name="index.html.j2")


async def drop_all_tables_if_requested(app: Litestar) -> None:
    """On startup callback to drop all tables (for testing)
    when configured to do so."""
    if settings.drop_database_on_startup:
        print("Dropping all tables...", flush=True)
        metadata = MetaData()

        # We keep tables managed by plugins such as SAQ
        tables_to_keep = [
            "saq_jobs",
            "saq_stats",
            "saq_versions",
        ]

        # We can't call reflect on AsyncEngine, se we need to wrap it
        def drop_all_tables(engine):
            metadata.reflect(engine)
            # Create a filtered list of tables excluding those we want to keep
            tables_to_drop = [
                table
                for name, table in metadata.tables.items()
                if name not in tables_to_keep
            ]
            # Drop only the filtered tables
            metadata.drop_all(engine, tables=tables_to_drop)

        async with app.state.db_engine.connect() as conn:
            await conn.run_sync(lambda sync_conn: drop_all_tables(sync_conn))
            await conn.commit()
            # Recreate all tables, because this is run after the SQLAlchemyPlugin hooks
            await conn.run_sync(m.Base.metadata.create_all)
            await conn.commit()


async def initialize_db_extensions(app: Litestar):
    """Create required PostgreSQL extensions."""
    async with app.state.db_engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        await conn.commit()


async def seed_database_with_testing_data(app: Litestar):
    """Seed database with initial data if configured."""
    if settings.seed_database_on_startup is False:
        return

    print("Seeding database with initial data...", flush=True)

    async with AsyncSession(app.state.db_engine, expire_on_commit=False) as session:
        async with session.begin():
            data_path = (
                pathlib.Path(__file__).parent.parent / "data/translation_runs.json"
            )
            translation_runs = json.loads(open(data_path).read())
            for run in translation_runs:
                await _add_translation_run(
                    data=TranslationRunPostData(
                        **run,
                    ),
                    transaction=session,
                )

            # Create default namespace if it doesn't exist
            try:
                await get_or_create_default_namespace(session)
            except IntegrityError as e:
                print(f"Error creating default namespace: {e}", flush=True)

            # Create default user if it doesn't exist
            try:
                default_user = m.User(
                    id=1,
                    username="default",
                    email="test@ufal",
                    password_hash="xxxx",
                )
                session.add(default_user)
            except IntegrityError as e:
                print(f"Error creating default user: {e}", flush=True)


template_config = TemplateConfig(engine=JinjaTemplateEngine(directory="templates/"))
vite_plugin = VitePlugin(
    config=ViteConfig(
        use_server_lifespan=True,
        is_react=True,
    )
)

api_v1_router = Router(
    "/api/v1",
    route_handlers=[
        # Namespace-based routes
        add_translation_run,
        get_translation_runs,
        get_translation_run,
        get_namespaces,
        get_datasets,
        get_dataset_by_id,
        # Worker routes
        *worker_module.worker_routes,
    ],
)


app = Litestar(
    [
        api_v1_router,
        WebController,
    ],
    debug=True,
    dependencies={"transaction": provide_transaction},
    plugins=[
        plugins.alchemy_plugin,
        SAQPlugin(
            SAQConfig(
                web_enabled=True,
                use_server_lifespan=True,
                queue_configs=[
                    QueueConfig(
                        dsn=settings.saq_queue_dsn,
                        tasks=[
                            tasks.cleanup_expired_workers_and_jobs_task,
                        ],
                        scheduled_tasks=[
                            CronJob(
                                function=tasks.cleanup_expired_workers_and_jobs_task,
                                cron="* * * * *",
                                timeout=600,
                                ttl=200,
                            )
                        ],
                    ),
                ],
            )
        ),
        vite_plugin,
    ],
    on_startup=[
        drop_all_tables_if_requested,
        initialize_db_extensions,
        seed_database_with_testing_data,
    ],
    template_config=template_config,
)
