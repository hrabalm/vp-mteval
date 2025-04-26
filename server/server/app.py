import os
from collections.abc import AsyncGenerator

from litestar import Litestar, get, post, put
from litestar.contrib.sqlalchemy.plugins import SQLAlchemyAsyncConfig, SQLAlchemyPlugin
from litestar.exceptions import ClientException, NotFoundException
from litestar.status_codes import HTTP_409_CONFLICT
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

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


db_config = SQLAlchemyAsyncConfig(
    connection_string=os.environ["DATABASE_URL"],
    metadata=m.Base.metadata,
    create_all=True,
    before_send_handler="autocommit",
)

app = Litestar(
    [get_list, add_item, update_item],
    dependencies={"transaction": provide_transaction},
    plugins=[SQLAlchemyPlugin(db_config)],
)
