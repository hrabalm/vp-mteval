import json
import logging
import pathlib

from litestar import Litestar
from sqlalchemy import MetaData, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import server.models as models
import server.routes as routes
from server.config import settings

logger = logging.getLogger(__name__)


async def seed_database_with_testing_data(app: Litestar):
    """Seed database with initial data if configured."""
    if settings.seed_database_on_startup is False:
        return

    logger.info("Seeding database with initial data...")

    async with AsyncSession(app.state.db_engine, expire_on_commit=False) as session:
        data_path = pathlib.Path(__file__).parent.parent / "data/translation_runs.json"
        translation_runs = json.loads(open(data_path).read())
        for run in translation_runs:
            await routes._add_translation_run(
                data=routes.TranslationRunPostData(
                    **run,
                ),
                db_session=session,
                app=app,
            )

        # Create default namespace if it doesn't exist
        try:
            await routes.get_or_create_default_namespace(session)
        except IntegrityError as e:
            logger.error(f"Error creating default namespace: {e}")

        # Create default user if it doesn't exist
        try:
            logger.info("Creating default user...")
            default_user = models.User(
                id=1,
                username="default",
                password_hash="xxxx",
                api_key="test_user_key",
            )
            session.add(default_user)
            await session.commit()
        except IntegrityError as e:
            logger.error(f"Error creating default user: {e}")


async def drop_all_tables_if_requested(app: Litestar) -> None:
    """On startup callback to drop all tables (for testing)
    when configured to do so."""
    if settings.drop_database_on_startup:
        logger.info("Dropping all tables...")
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
            await conn.run_sync(models.Base.metadata.create_all)
            await conn.commit()


async def initialize_db_extensions(app: Litestar):
    """Create required PostgreSQL extensions."""
    async with app.state.db_engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        await conn.commit()
