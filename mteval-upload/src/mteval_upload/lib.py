import pathlib
import platformdirs
import httpx
import tenacity
import uuid
import shutil
import logging
import json

logger = logging.getLogger(__name__)


def _get_runs_path():
    path = platformdirs.user_data_path("vp-mteval", "vp-mteval", ensure_exists=True)
    success = path / "success"
    failure = path / "failure"
    success.mkdir(parents=True, exist_ok=True)
    failure.mkdir(parents=True, exist_ok=True)
    return success, failure


def _get_run_path(uuid: str, success: bool) -> pathlib.Path:
    """Get the path to a specific run."""
    success_path, failure_path = _get_runs_path()
    run_path = (
        pathlib.Path(failure_path if not success else success_path) / f"{uuid}.json"
    )
    return run_path


def _create_auth_headers(token: str) -> dict[str, str]:
    """Create headers for authentication."""
    return {
        "Authorization": f"Bearer {token}",
    }


def _upload_run(host: str, run: dict, api_key: str):
    namespace_name = run["namespace_name"]

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            f"{host}/api/v1/namespaces/{namespace_name}/translations-runs",
            headers=_create_auth_headers(api_key),
            json=run,
        )
        response.raise_for_status()
        return response.json()


def _upload_run_wrapped(host: str, run: dict, api_key: str):
    """Upload a run to the server with retry logic."""

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def upload():
        return _upload_run(host, run, api_key)

    try:
        upload()
        return True
    except Exception as e:
        logger.error(f"Error uploading run: {e}")
        return False


def _move_to_success(run: dict):
    """Move the run to the success directory."""
    run_path = _get_run_path(run["uuid"], success=False)
    if not run_path.exists():
        raise FileNotFoundError(f"Run file {run_path} does not exist.")

    success_path = _get_run_path(run["uuid"], success=True)
    run_path.rename(success_path)
    return success_path


def _save_run(run: dict):
    """Save the run to the local filesystem."""
    run_path = _get_run_path(run["uuid"], success=False)
    with open(run_path, "w", encoding="utf-8") as f:
        json.dump(run, f, indent=4, ensure_ascii=False)
    return run_path


def _delete_run(run: dict):
    """Delete the run from the local filesystem."""
    run_path = _get_run_path(run["uuid"], success=True)
    if run_path.exists():
        shutil.rmtree(run_path)
    else:
        raise FileNotFoundError(f"Run file {run_path} does not exist.")
    return run_path


def upload_run(
    host: str, run: dict, api_key: str, keep: bool = False, save: bool = True
):
    if "uuid" not in run:
        run["uuid"] = uuid.uuid4().hex
    if save:
        _save_run(run)
    success = _upload_run_wrapped(host, run, api_key)
    if success and save:
        _move_to_success(run)
        if not keep:
            _delete_run(run)


def upload_failed_runs(host: str, api_key: str, keep: bool = False):
    """Upload all failed runs to the server."""
    success_path, failure_path = _get_runs_path()
    for run_file in failure_path.glob("*.json"):
        with open(run_file, "r", encoding="utf-8") as f:
            run = json.load(f)
        try:
            upload_run(host, run, api_key, keep=keep, save=False)
            if not keep:
                _delete_run(run)
        except Exception as e:
            logger.error(f"Failed to upload run {run_file}: {e}")


def upload_successful_runs(host: str, api_key: str, keep: bool = False):
    """Upload all successful runs to the server."""
    success_path, _ = _get_runs_path()
    for run_file in success_path.glob("*.json"):
        with open(run_file, "r", encoding="utf-8") as f:
            run = json.load(f)
        try:
            upload_run(host, run, api_key, keep=keep, save=False)
            if not keep:
                _delete_run(run)
        except Exception as e:
            logger.error(f"Failed to upload run {run_file}: {e}")
