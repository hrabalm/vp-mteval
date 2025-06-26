from litestar import post
from litestar.exceptions import NotAuthorizedException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import server.auth as auth


class PostLogin(BaseModel):
    username: str
    password: str


class ReadUserLogin(BaseModel):
    id: int
    username: str
    is_admin: bool
    api_key: str


@post("/api/login")
async def login(data: PostLogin, transaction: AsyncSession) -> ReadUserLogin:
    user = await auth.authenticate_user(
        transaction=transaction, username=data.username, password=data.password
    )
    if not user:
        raise NotAuthorizedException(detail="Invalid username or password")
    return ReadUserLogin(
        id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        api_key=user.api_key,
    )


routes = [
    login,
]
