import typed_settings as ts


@ts.settings
class Settings:
    """Server app configuration."""

    database_connection_string: str | None = None
    drop_database_on_startup: bool = False
    seed_database_on_startup: bool = False


settings = ts.load(Settings, appname="server")
