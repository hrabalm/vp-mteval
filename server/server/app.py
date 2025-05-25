import os
import uuid as uuid_lib  # we need to rename this to avoid conflict with uuid var in dataclasses
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Optional, cast

import iso639
from advanced_alchemy.config import AsyncSessionConfig
from litestar import Controller, Litestar, Router, get, post
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.contrib.sqlalchemy.plugins import SQLAlchemyAsyncConfig, SQLAlchemyPlugin
from litestar.exceptions import ClientException, NotFoundException
from litestar.response import Template
from litestar.status_codes import HTTP_200_OK, HTTP_409_CONFLICT
from litestar.template.config import TemplateConfig
from litestar_vite import ViteConfig, VitePlugin
from pydantic import BaseModel
from sqlalchemy import MetaData, select, text
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload

import server.models as m


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
    """
    import hashlib

    from json_canonical import canonicalize

    # make langs iso639-1
    source_lang = iso639.Language.match(source_lang).part1
    target_lang = iso639.Language.match(target_lang).part1

    data = {
        "segments": [s.model_dump() for s in segments],
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


class ReadTranslationRun(BaseModel):
    id: int
    uuid: uuid_lib.UUID
    dataset_id: int
    namespace_id: int
    namespace_name: str
    config: dict[str, Any]


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
    for segment in segments:
        db_segment = m.Segment(
            src=segment.src,
            dataset_id=dataset_id,
        )
        transaction.add(db_segment)

        # We need to flush to get the segment ID
        await transaction.flush()

        db_translation = m.SegmentTranslation(
            run_id=run_id,
            tgt=segment.tgt,
            segment=db_segment,
        )
        transaction.add(db_translation)

    # Final flush after adding all segments and translations
    await transaction.flush()


@post("/translations-runs/")
async def add_translation_run(
    data: TranslationRunPostData,
    transaction: AsyncSession,
) -> ReadTranslationRun:
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

    return ReadTranslationRun(
        id=translation_run.id,
        uuid=translation_run.uuid,
        dataset_id=dataset.id,
        namespace_id=namespace.id,
        namespace_name=namespace.name,
        config=translation_run.config,
    )


@get("/translations-runs/{run_id:int}")
async def get_translation_run(
    run_id: int,
    transaction: AsyncSession,
) -> ReadTranslationRun:
    """Get a translation run by ID."""
    query = (
        select(m.TranslationRun)
        .options(selectinload(m.TranslationRun.namespace))
        .where(m.TranslationRun.id == run_id)
    )
    result = await transaction.execute(query)
    try:
        result1 = result.scalar_one()
        return ReadTranslationRun(
            id=result1.id,
            uuid=result1.uuid,
            dataset_id=result1.dataset_id,
            namespace_id=result1.namespace_id,
            namespace_name=result1.namespace.name,
            config=result1.config,
        )
    except NoResultFound as e:
        raise NotFoundException(detail=f"Translation run {run_id} not found")


class WebController(Controller):
    opt = {"exclude_from_auth": True}
    include_in_schema = False

    @get(["/", "/{path:path}"], status_code=HTTP_200_OK)
    async def index(self) -> Template:
        return Template(template_name="index.html.j2")


async def drop_all_tables_if_requested(app: Litestar) -> None:
    if os.environ.get("DATABASE_DROP", "").lower() == "true":
        print("Dropping all tables...", flush=True)
        metadata = MetaData()

        # We can't call reflect on AsyncEngine, se we need to wrap it
        def drop_all_tables(engine):
            metadata.reflect(engine)
            metadata.drop_all(engine)

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


db_config = SQLAlchemyAsyncConfig(
    connection_string=os.environ["DATABASE_URL"],
    metadata=m.Base.metadata,
    create_all=True,
    before_send_handler="autocommit",
    session_config=AsyncSessionConfig(expire_on_commit=False),  # keep attributes alive
)

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
        add_translation_run,
        get_translation_run,
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
        SQLAlchemyPlugin(db_config),
        vite_plugin,
    ],
    on_startup=[
        drop_all_tables_if_requested,
        initialize_db_extensions,
    ],
    template_config=template_config,
)
