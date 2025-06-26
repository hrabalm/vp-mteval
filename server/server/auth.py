import asyncio

import passlib.context
import pydantic
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.handlers import BaseRouteHandler
from litestar.middleware import (
    AbstractAuthenticationMiddleware,
    AuthenticationResult,
)
from sqlalchemy import select

import server.models as models
import server.plugins as plugins

pwd_context = passlib.context.CryptContext(schemes=["argon2"], deprecated="auto")


async def get_password_hash(password: str) -> str:
    return await asyncio.get_running_loop().run_in_executor(
        None, pwd_context.hash, password
    )


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    return await asyncio.get_running_loop().run_in_executor(
        None, pwd_context.verify, plain_password, hashed_password
    )


class User(pydantic.BaseModel):
    id: int
    username: str
    is_admin: bool


class Token(pydantic.BaseModel):
    api_key: str


class CustomAuthenticationMiddleware(AbstractAuthenticationMiddleware):
    async def authenticate_request(
        self, connection: ASGIConnection
    ) -> AuthenticationResult:
        auth_header = connection.headers.get("Authorization")
        if not auth_header:
            raise NotAuthorizedException()

        token = Token(api_key=auth_header.replace("Bearer ", "", 1).strip())
        async with plugins.db_config.get_session() as session:
            query = select(models.User).where(models.User.api_key == token.api_key)
            result = await session.execute(query)
            user = result.scalars().first()
            if not user:
                raise NotAuthorizedException()
        user = User(id=user.id, username=user.username, is_admin=user.is_admin)

        if not user.username:
            raise NotAuthorizedException()

        return AuthenticationResult(
            user=user,
            auth=token,
        )


def admin_user_guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    if not connection.user.is_admin:
        raise NotAuthorizedException()
