import typed_settings as ts


@ts.settings
class Settings:
    """Server app configuration."""

    saq_queue_dsn: str | None = "postgresql://user:password@placeholder/dbname"
    database_connection_string: str | None = (
        "postgresql://user:password@placeholder/dbname"
    )
    drop_database_on_startup: bool = False
    seed_database_on_startup: bool = False

    # Show SQLAlchemy SQL queries in the logs for debugging purposes.
    database_echo: bool = False
    debug: bool = False

    worker_expiration_seconds: int = 60


settings = ts.load(Settings, appname="server")
