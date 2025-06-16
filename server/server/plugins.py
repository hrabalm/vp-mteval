from server.config import settings
import server.models as models
from advanced_alchemy.config import AsyncSessionConfig, EngineConfig
from litestar.contrib.sqlalchemy.plugins import SQLAlchemyAsyncConfig, SQLAlchemyPlugin

db_config = SQLAlchemyAsyncConfig(
    connection_string=settings.database_connection_string,
    metadata=models.Base.metadata,
    create_all=True,
    before_send_handler="autocommit",
    session_config=AsyncSessionConfig(expire_on_commit=False),  # keep attributes alive
    engine_config=EngineConfig(
        echo=settings.database_echo,
    ),
)
alchemy_plugin = SQLAlchemyPlugin(config=db_config)
