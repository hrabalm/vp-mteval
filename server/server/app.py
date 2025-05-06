import os
from collections.abc import AsyncGenerator
from typing import cast

import iso639
from litestar import Litestar, get, post, put
from litestar.contrib.sqlalchemy.plugins import SQLAlchemyAsyncConfig, SQLAlchemyPlugin
from litestar.exceptions import ClientException, NotFoundException
from litestar.status_codes import HTTP_409_CONFLICT
from pydantic import BaseModel
from sqlalchemy import MetaData, create_engine, select, text
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from starlette_admin.contrib.sqla import ModelView
from starlette_admin_litestar_plugin import (
    StarlettAdminPluginConfig,
    StarletteAdminPlugin,
)

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


async def get_todo_by_title(todo_name, session: AsyncSession) -> m.TodoItem:
    query = select(m.TodoItem).where(m.TodoItem.title == todo_name)
    result = await session.execute(query)
    try:
        return result.scalar_one()
    except NoResultFound as e:
        raise NotFoundException(detail=f"TODO {todo_name!r} not found") from e


async def get_todo_list(done: bool | None, session: AsyncSession) -> list[m.TodoItem]:
    query = select(m.TodoItem)
    if done is not None:
        query = query.where(m.TodoItem.done.is_(done))

    result = await session.execute(query)
    return result.scalars().all()


@get("/")
async def get_list(
    transaction: AsyncSession, done: bool | None = None
) -> list[m.TodoItem]:
    return await get_todo_list(done, transaction)


@post("/")
async def add_item(data: m.TodoItem, transaction: AsyncSession) -> m.TodoItem:
    transaction.add(data)
    return data


@put("/{item_title:str}")
async def update_item(
    item_title: str, data: m.TodoItem, transaction: AsyncSession
) -> m.TodoItem:
    todo_item = await get_todo_by_title(item_title, transaction)
    todo_item.title = data.title
    todo_item.done = data.done
    return todo_item


class SegmentPostData(BaseModel):
    src: str
    tgt: str


class TranslationRunPostData(BaseModel):
    """Complex data structure that also contains a list of segments and allows
    us to either find or create the related dataset."""

    namespace_name: str
    dataset_name: str
    dataset_source_lang: str
    dataset_target_lang: str
    segments: list[SegmentPostData]


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


@post("/translations-runs/")
async def add_translation_run(
    data: TranslationRunPostData, transaction: AsyncSession
) -> m.TranslationRun:
    # TODO: this should be a more complex POST request which creates missing entities

    # Calculate the hash of the dataset (we canonicalize the JSON represenation)
    dataset_hash_value = dataset_hash(
        data.segments, data.dataset_source_lang, data.dataset_target_lang
    )

    async def get_dataset_by_hash(dataset_hash_value: str) -> m.Dataset:
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

    try:
        dataset = await get_dataset_by_hash(dataset_hash_value)
    except NotFoundException:
        dataset = m.Dataset(
            source_lang=data.dataset_source_lang,
            target_lang=data.dataset_target_lang,
            data_hash=dataset_hash_value,
        )
        transaction.add(dataset)
        dataset_name = m.DatasetName(dataset=dataset, name=data.dataset_name)
        transaction.add(dataset_name)
        # create segments
        for segment in data.segments:
            db_segment = m.Segment(
                src=segment.src,
                dataset=dataset,
            )
            transaction.add(db_segment)
            # create translations
            db_translation = m.SegmentTranslation(
                tgt=segment.tgt,
                segment=db_segment,
            )
            transaction.add(db_translation)

    if data.namespace_name == "default":
        namespace = await get_or_create_default_namespace(transaction)
    else:
        namespace = await get_namespace_by_name(data.namespace_name, transaction)

    db_data = m.TranslationRun(
        dataset_id=dataset.id,
        namespace_id=namespace.id,
    )
    transaction.add(db_data)
    await transaction.commit()
    return db_data


engine = create_async_engine(os.environ["DATABASE_URL"])

# for testing: drop all tables if the environment variable DATABASE_DROP is set
if os.environ.get("DATABASE_DROP", "").lower() == "true":
    sync_engine = create_engine(os.environ["DATABASE_URL"])

    metadata = MetaData()
    metadata.reflect(sync_engine)
    metadata.drop_all(sync_engine)


db_config = SQLAlchemyAsyncConfig(
    metadata=m.Base.metadata,
    create_all=True,
    before_send_handler="autocommit",
    engine_instance=engine,
)

# Configure admin
admin_config = StarlettAdminPluginConfig(
    views=[
        ModelView(m.TodoItem),
        ModelView(m.Dataset),
        ModelView(m.DatasetName),
        ModelView(m.Segment),
        ModelView(m.TranslationRun),
        ModelView(m.SegmentTranslation),
        ModelView(m.SegmentMetric),
        ModelView(m.DatasetMetric),
        ModelView(m.Namespace),
        ModelView(m.NamespaceUser),
        ModelView(m.User),
    ],
    engine=engine,
    title="My Admin",
)

app = Litestar(
    [get_list, add_item, update_item, add_translation_run],
    debug=True,
    dependencies={"transaction": provide_transaction},
    plugins=[
        SQLAlchemyPlugin(db_config),
        StarletteAdminPlugin(starlette_admin_config=admin_config),
    ],
)
