import click
import mteval_upload.lib as lib
import json


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    "--data",
    "-d",
    help="Path to the data file to upload.",
    required=True,
    type=click.Path(exists=True),
)
@click.option(
    "--host",
    "-h",
    help="Host URL for the vp-mteval server. For example: http://localhost:8000",
    required=True,
)
@click.option(
    "--api-key", "-k", required=True, help="API key for the vp-mteval server."
)
@click.option(
    "--keep",
    "-K",
    is_flag=True,
    help="Keep the runs after successful upload. Can be useful for development and debugging.",
)
def upload(data, host, api_key, keep):
    with open(data, "r", encoding="utf-8") as f:
        data_dict = json.load(f)
    lib.upload_run(
        host=host,
        run=data_dict,
        api_key=api_key,
        keep=keep,
        save=True,
    )


@cli.command()
@click.option(
    "--host",
    "-h",
    help="Host URL for the vp-mteval server. For example: http://localhost:8000",
    required=True,
)
@click.option(
    "--api-key", "-k", required=True, help="API key for the vp-mteval server."
)
@click.option(
    "--keep",
    "-K",
    is_flag=True,
    help="Keep the runs after successful upload. Can be useful for development and debugging.",
)
def upload_failed(host, api_key, keep):
    pass


@cli.command()
@click.option(
    "--host",
    "-h",
    help="Host URL for the vp-mteval server. For example: http://localhost:8000",
    required=True,
)
@click.option(
    "--api-key", "-k", required=True, help="API key for the vp-mteval server."
)
@click.option(
    "--keep",
    "-K",
    is_flag=True,
    help="Keep the runs after successful upload. Can be useful for development and debugging.",
)
def upload_successful(host, api_key, keep):
    pass


def main():
    cli()


if __name__ == "__main__":
    main()
