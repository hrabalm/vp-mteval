from collections.abc import AsyncGenerator

from litestar import Litestar
from litestar.config.compression import CompressionConfig
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.exceptions import ClientException
from litestar.middleware import DefineMiddleware
from litestar.status_codes import HTTP_409_CONFLICT
from litestar.template.config import TemplateConfig
from litestar_saq import CronJob, QueueConfig, SAQConfig, SAQPlugin
from litestar_vite import ViteConfig, VitePlugin
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import server.auth as auth
import server.events as events
import server.hooks as hooks
import server.plugins as plugins
import server.routes as routes
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


template_config = TemplateConfig(engine=JinjaTemplateEngine(directory="templates/"))
vite_plugin = VitePlugin(
    config=ViteConfig(
        use_server_lifespan=True,
        is_react=True,
    )
)
auth_middleware = DefineMiddleware(
    auth.CustomAuthenticationMiddleware,
    exclude="schema",
)

app = Litestar(
    [
        routes.api_v1_router,
        routes.WebController,
    ],
    debug=True,
    dependencies={"transaction": provide_transaction},
    compression_config=CompressionConfig(backend="brotli", brotli_gzip_fallback=True),
    plugins=[
        plugins.alchemy_plugin,
        SAQPlugin(
            SAQConfig(
                web_enabled=True,
                use_server_lifespan=True,
                queue_configs=[
                    QueueConfig(  # n-grams computation
                        name="ngrams",
                        dsn=settings.saq_queue_dsn,
                        tasks=[
                            tasks.compute_ngrams_on_run_created,
                        ],
                    ),
                    QueueConfig(
                        name="default",
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
    middleware=[
        auth_middleware,
    ],
)
