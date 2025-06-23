from collections.abc import AsyncGenerator

from litestar import Litestar
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.exceptions import ClientException
from litestar.status_codes import HTTP_409_CONFLICT
from litestar.template.config import TemplateConfig
from litestar_saq import CronJob, QueueConfig, SAQConfig, SAQPlugin
from litestar_vite import ViteConfig, VitePlugin
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import server.events as events
import server.plugins as plugins
import server.routes as routes
import server.tasks as tasks
import server.hooks as hooks
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


template_config = TemplateConfig(engine=JinjaTemplateEngine(directory="templates/"))
vite_plugin = VitePlugin(
    config=ViteConfig(
        use_server_lifespan=True,
        is_react=True,
    )
)


app = Litestar(
    [
        routes.api_v1_router,
        routes.WebController,
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
        hooks.drop_all_tables_if_requested,
        hooks.initialize_db_extensions,
        hooks.seed_database_with_testing_data,
    ],
    template_config=template_config,
    listeners=events.listeners,
)
