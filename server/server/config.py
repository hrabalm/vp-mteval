import typed_settings as ts


@ts.settings
class Settings:
    """Server app configuration."""

    database_connection_string: str | None = None
    drop_database_on_startup: bool = False
    seed_database_on_startup: bool = False

    # Show SQLAlchemy SQL queries in the logs for debugging purposes.
    database_echo: bool = False

    saq_queue_dsn: str


settings = ts.load(Settings, appname="server")
