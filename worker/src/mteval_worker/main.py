"""
We handle main async main loop which frequently sends heartbeats to the
server. The actual processing of jobs is done in a synchronous loop and
data is sent to it via a queue. Results are returned through another
queue.
"""

import logging
import multiprocessing
import queue
from functools import partial
import json

import anyio
import click
import httpx
import mteval_worker.processors
import mteval_worker.processors.protocols
import tenacity
from anyio.to_thread import run_sync
from pydantic import BaseModel

multiprocessing.set_start_method("spawn", force=True)

# Sentinel value to signal the worker to exit
POISON_PILL = None
HEARTBEAT_INTERVAL_SECONDS = 5
NUM_FETCHED_TASKS = 2
HTTP_TIMEOUT = 60  # seconds, for HTTP requests


def setup_logging(log_level: str):
    """Configure logging with the specified level."""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


class Worker:
    def __init__(
        self,
        metrics_processor_name: str | None = None,
        metrics_processor_file: str | None = None,
        config: dict | None = None,
    ):
        if config is None:
            config = {}
        if metrics_processor_name is None and metrics_processor_file is None:
            raise ValueError(
                "You must provide either a metrics_processor or a metrics_processor_file."
            )
        self.metrics_processor_name = metrics_processor_name
        self.metrics_processor_file = metrics_processor_file
        self.metrics_processor = None
        self.config = config

        self.process = None
        self.examples_queue = multiprocessing.Queue()
        self.result_queue = multiprocessing.Queue()

    def _main_loop(self):
        if (
            self.metrics_processor_name is None
            and self.metrics_processor_file is not None
        ):
            metrics_processor = mteval_worker.processors.get_processor_from_file(
                self.metrics_processor_file
            )(config=self.config)
        else:
            metrics_processor = mteval_worker.processors.get_processor_factory(
                self.metrics_processor_name
            )(config=self.config)
        self.metrics_processor = metrics_processor
        try:
            while True:
                example = self.examples_queue.get()
                if example is POISON_PILL:
                    logging.info("Worker received POISON_PILL, shutting down...")
                    self.result_queue.put(POISON_PILL)
                    break
                logging.info(f"Worker processing job {example.job_id}...")
                result = self.metrics_processor.process_example(example)
                if result is None:
                    logging.warning(
                        f"Worker skipped processing job {example.job_id} due to None result."
                    )
                    continue
                logging.info(f"Worker finished processing job {example.job_id}")
                self.result_queue.put(result)
        except Exception as e:
            logging.error(f"Error in worker process: {str(e)}")
            # Make sure we communicate back to the main process that an error occurred
            self.result_queue.put(POISON_PILL)

    def start(self):
        """Start the worker in a separate process."""
        if self.process is not None and self.process.is_alive():
            logging.warning("Worker process is already running")
            return

        self.process = multiprocessing.Process(target=self._main_loop)
        self.process.start()

    def restart(self, timeout: float = 10.0):
        """Restart the worker process reliably."""
        logging.info("Restarting worker process...")

        # First, stop the current process if it exists
        self.stop(timeout=timeout)

        # Clear any remaining items in queues to prevent issues
        self._clear_queues()

        # Start a new process
        self.start()
        logging.info("Worker process restarted successfully")

    def stop(self, timeout: float = 10.0):
        """Stop the worker process gracefully, with forceful termination as fallback."""
        if self.process is None:
            return

        if not self.process.is_alive():
            logging.info("Worker process is already stopped")
            return

        logging.info("Stopping worker process...")

        # Try graceful shutdown first by sending POISON_PILL
        try:
            self.examples_queue.put(POISON_PILL)
            logging.debug("Sent POISON_PILL to worker")
        except Exception as e:
            logging.warning(f"Failed to send POISON_PILL: {e}")

        # Wait for graceful shutdown
        self.process.join(timeout=timeout / 2)

        if self.process.is_alive():
            logging.warning("Worker didn't shut down gracefully, terminating...")
            self.process.terminate()

            # Wait a bit for terminate to take effect
            self.process.join(timeout=timeout / 4)

            if self.process.is_alive():
                logging.error("Worker didn't respond to terminate, killing...")
                self.process.kill()

                # Final wait for kill to take effect
                self.process.join(timeout=timeout / 4)

                if self.process.is_alive():
                    logging.error("Failed to kill worker process!")
                else:
                    logging.info("Worker process killed successfully")
            else:
                logging.info("Worker process terminated successfully")
        else:
            logging.info("Worker process shut down gracefully")

    def is_healthy(self) -> bool:
        """Check if the worker process is healthy (alive and responsive)."""
        if self.process is None or not self.process.is_alive():
            return False

        return True

    def _clear_queues(self):
        """Clear any remaining items in the queues."""
        try:
            while not self.examples_queue.empty():
                self.examples_queue.get_nowait()
        except:
            pass

        try:
            while not self.result_queue.empty():
                self.result_queue.get_nowait()
        except:
            pass


@tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
    stop=tenacity.stop_after_attempt(3),
    reraise=True,
)
async def send_heartbeat(host, worker_id: int, namespace_name: str, token: str):
    """Send a heartbeat to the server."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.put(
            f"{host}/api/v1/namespaces/{namespace_name}/workers/{worker_id}/heartbeat",
            headers=create_auth_headers(token),
        )
        response.raise_for_status()
        return response.json()


async def send_heartbeats(
    interval_seconds: int,
    host: str,
    worker_id: int,
    namespace_name: str,
    token: str,
    state: dict,
    is_fake: bool = False,
):
    """Periodically send a heartbeat."""
    while not state.get("finished", False):
        logging.info("Sending heartbeat...")
        if not is_fake:
            try:
                await send_heartbeat(host, worker_id, namespace_name, token)
            except Exception as e:
                logging.error("Error sending heartbeat: %s", e)
                raise e
        await anyio.sleep(interval_seconds)


def create_auth_headers(token: str) -> dict[str, str]:
    """Create headers for authentication."""
    return {
        "Authorization": f"Bearer {token}",
    }


async def register_worker(
    host: str,
    token: str,
    metric: str,
    metric_requires_references: bool,
    namespace_name: str,
    username: str | None,
) -> mteval_worker.processors.protocols.WorkerRegistrationResponse:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.post(
            f"{host}/api/v1/namespaces/{namespace_name}/workers/register",
            headers=create_auth_headers(token),
            json={
                "metric": metric,
                "metric_requires_references": metric_requires_references,
                "username": username,
            },
        )
        response.raise_for_status()
        return mteval_worker.processors.protocols.WorkerRegistrationResponse.model_validate(
            response.json()
        )


async def unregister_worker(
    host: str,
    token: str,
    namespace_name: str,
    worker_id: int,
):
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.post(
            f"{host}/api/v1/namespaces/{namespace_name}/workers/{worker_id}/unregister",
            headers=create_auth_headers(token),
        )
        response.raise_for_status()
        return response.json()


@tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=5),
    stop=tenacity.stop_after_attempt(2),
    reraise=True,
)
async def assign_and_get_job(
    host: str,
    token: str,
    namespace_name: str,
    worker_id: int,
) -> list[dict]:
    """Assign a job to the worker and return it."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.post(
            f"{host}/api/v1/namespaces/{namespace_name}/workers/{worker_id}/jobs/assign",
            headers=create_auth_headers(token),
        )
        response.raise_for_status()
        data = response.json()
        return data


def start_heartbeat_task(
    tg,
    interval_seconds: int,
    host: str,
    namespace_name: str,
    worker_id: int,
    token: str,
    state: dict,
):
    tg.start_soon(
        partial(
            send_heartbeats,
            interval_seconds,
            host=host,
            namespace_name=namespace_name,
            worker_id=worker_id,
            token=token,
            state=state,
        )
    )


async def fetch_jobs(maximum: int) -> list: ...


class PostSegmentMetric(BaseModel):
    name: str
    higher_is_better: bool
    scores: list[float]
    custom: list[dict] | None = None  # Additional data specific to the metric


class PostDatasetMetric(BaseModel):
    name: str
    higher_is_better: bool
    score: float


class JobResultRequest(BaseModel):
    job_id: int
    dataset_level_metrics: list[PostDatasetMetric]
    segment_level_metrics: list[PostSegmentMetric]


@tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
    stop=tenacity.stop_after_attempt(3),
    reraise=True,
)
async def report_job_results(
    example_result: mteval_worker.processors.protocols.WorkerExampleResult,
    job_id: int,
    host: str,
    token: str,
    namespace_name: str,
    worker_id: int,
):
    # Build metrics lists based on available data
    dataset_level_metrics = []
    if example_result.dataset_score is not None:
        dataset_level_metrics.append(
            PostDatasetMetric(
                name=example_result.name,
                higher_is_better=example_result.higher_is_better,
                score=float(example_result.dataset_score),
            )
        )

    segment_level_metrics = []
    if example_result.segment_scores is not None:
        segment_level_metrics.append(
            PostSegmentMetric(
                name=example_result.name,
                higher_is_better=example_result.higher_is_better,
                scores=[float(score) for score in example_result.segment_scores],
                custom=example_result.segment_custom or None,
            ),
        )

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.post(
            f"{host}/api/v1/namespaces/{namespace_name}/workers/{worker_id}/jobs/{job_id}/report_result",
            headers=create_auth_headers(token),
            json=JobResultRequest(
                job_id=job_id,
                dataset_level_metrics=dataset_level_metrics,
                segment_level_metrics=segment_level_metrics,
            ).model_dump(),
        )
        response.raise_for_status()
        return response.json()


def job_to_example(job):
    logging.debug(f"Processing job: {job}")
    logging.debug(f"Job segments: {job['segments']}")
    example = mteval_worker.processors.protocols.WorkerExample(
        job_id=job["id"],
        segments=[
            mteval_worker.processors.protocols.Segment(
                src=seg["src"],
                tgt=seg["tgt"],
                ref=seg.get("ref"),
            )
            for seg in job["segments"]
        ],
        src_lang="English",  # FIXME
        tgt_lang="Czech",
    )
    logging.debug(f"Created example: {example}")
    return example


async def _main(
    host, token, username, namespace, metric, mode, log_level, config, metric_file
):
    # Setup logging with the specified level
    setup_logging(log_level)

    # 1. Register the worker and announce what metric and what data, if in
    #    single shot mode, we can leave if no data is provided before loading
    if metric:
        processor = mteval_worker.processors.get_processor_factory(metric)
    else:
        processor = mteval_worker.processors.get_processor_from_file(metric_file)
    res = await register_worker(
        host=host,
        token=token,
        metric=processor.name,
        metric_requires_references=processor.requires_references,
        namespace_name=namespace,
        username=username,
    )
    logging.info(f"Worker registered: {res}")

    state = {"finished": False}
    worker = None
    try:
        async with anyio.create_task_group() as tg:
            # 2. Start the Worker subprocess and heartbeat task
            start_heartbeat_task(
                tg,
                5,
                host,
                namespace_name=namespace,
                worker_id=res.worker_id,
                token=token,
                state=state,
            )

            # 3. Fetch initial tasks
            logging.info("Fetching initial tasks...")
            jobs = await assign_and_get_job(
                host=host,
                token=token,
                namespace_name=namespace,
                worker_id=res.worker_id,
            )
            logging.debug(f"Fetched jobs: {jobs}")

            initial_jobs = jobs

            if len(initial_jobs) == 0 and mode == "one-shot":
                logging.info("No initial jobs and in one-shot mode. Exiting.")
                state["finished"] = True
                return

            if metric_file is not None:
                worker = Worker(metrics_processor_file=metric_file, config=config)
            else:
                worker = Worker(
                    metrics_processor_name=metric,
                    config=config,
                )
            worker.start()

            # Track consecutive failures for restart logic
            consecutive_failures = 0
            max_consecutive_failures = 3

            jobs_in_flight = 0
            for job in initial_jobs:
                example = job_to_example(job)
                worker.examples_queue.put(example)
                jobs_in_flight += 1
            logging.info(f"Started with {jobs_in_flight} initial jobs.")

            # 4. Main processing loop
            while True:
                if mode == "persistent" and jobs_in_flight == 0:
                    logging.info(
                        "Persistent mode: No jobs in flight, checking for new jobs."
                    )
                    new_jobs = await assign_and_get_job(
                        host=host,
                        token=token,
                        namespace_name=namespace,
                        worker_id=res.worker_id,
                    )
                    if new_jobs:
                        logging.info(f"Found {len(new_jobs)} new jobs.")
                        for job in new_jobs:
                            example = job_to_example(job)
                            worker.examples_queue.put(example)
                            jobs_in_flight += 1
                    else:
                        logging.info("No new jobs found, waiting.")
                        await anyio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                        continue

                if mode == "one-shot" and jobs_in_flight == 0:
                    logging.info("One-shot mode: All jobs processed.")
                    worker.examples_queue.put(POISON_PILL)
                    state["finished"] = True
                    break

                try:
                    # Check worker health before processing
                    if not worker.is_healthy():
                        logging.error("Worker process is unhealthy, restarting...")
                        worker.restart()
                        consecutive_failures = 0
                        continue
                    # Wait for a result from the worker
                    example_result = await run_sync(
                        lambda: worker.result_queue.get(timeout=1)
                    )
                    if example_result is POISON_PILL:
                        logging.error(
                            "Worker sent unexpected POISON_PILL. Shutting down."
                        )
                        break

                    # Reset failure counter on successful processing
                    consecutive_failures = 0

                    jobs_in_flight -= 1
                    logging.info(
                        f"Result received for job {example_result.job_id}. Jobs in flight: {jobs_in_flight}"
                    )

                    # Report the result to the server
                    await report_job_results(
                        example_result=example_result,
                        job_id=example_result.job_id,
                        host=host,
                        token=token,
                        namespace_name=namespace,
                        worker_id=res.worker_id,
                    )
                    logging.info(
                        f"Job {example_result.job_id} results reported successfully."
                    )

                except queue.Empty:
                    if not worker.process.is_alive():
                        consecutive_failures += 1
                        logging.error(
                            f"Worker process has terminated unexpectedly. "
                            f"Failure {consecutive_failures}/{max_consecutive_failures}"
                        )

                        if consecutive_failures >= max_consecutive_failures:
                            logging.error(
                                "Too many consecutive worker failures. Exiting."
                            )
                            state["finished"] = True
                            break

                        # Restart the worker
                        worker.restart()
                    logging.debug("Result queue empty, continuing to wait.")
                    continue
                except httpx.HTTPStatusError as e:
                    logging.error(f"HTTP error occurred: {e}, skipping this job")
                    continue
                except Exception as e:
                    consecutive_failures += 1
                    logging.error(f"Unexpected error in main loop: {e}")

                    if consecutive_failures >= max_consecutive_failures:
                        logging.error("Too many consecutive failures. Exiting.")
                        state["finished"] = True
                        break

                    # Restart worker on unexpected errors
                    worker.restart()
                    continue

    finally:
        if worker:
            # Wait for the final POISON_PILL from the result queue to confirm shutdown
            try:
                final_pill = await run_sync(lambda: worker.result_queue.get(timeout=5))
                if final_pill is not POISON_PILL:
                    logging.warning(
                        "Expected POISON_PILL at the end, but got something else."
                    )
            except queue.Empty:
                logging.warning("Timeout waiting for final POISON_PILL from worker.")

            # 5. If we want to end, unregister the worker explicitly and exit.
            logging.info("Unregistering worker...")
            await unregister_worker(
                host=host,
                token=token,
                namespace_name=namespace,
                worker_id=res.worker_id,
            )
            logging.info("Worker unregistered successfully.")
            state["finished"] = True


@click.command()
@click.option("--host", type=str, required=True, help="Server host URL")
@click.option("--token", type=str, required=True, help="Authentication token")
@click.option("--username", type=str, required=True, help="Username for the worker")
@click.option(
    "--namespace",
    type=str,
    required=True,
    help="Namespace for the worker",
    default="default",
    show_default=True,
)
@click.option(
    "--metric",
    type=click.Choice(
        [name for name in mteval_worker.processors.processors_by_name.keys()]
    ),
    help="Metric to be used",
)
@click.option(
    "--metric-file",
    type=str,
    default=None,
    help="Path to a custom metric Python file.",
)
@click.option(
    "--mode",
    type=click.Choice(["persistent", "one-shot"]),
    default="persistent",
    show_default=True,
    help="Mode of operation. If one-shot, the worker will exit after processing all available runs. If persisent, it will keep running and processing runs until explicitly stopped.",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    show_default=True,
    help="Set the logging level",
)
@click.option(
    "--config",
    type=str,
    default="{}",
    help="JSON string with additional configuration for the metric processor, if needed.",
)
def cli(host, token, username, namespace, metric, mode, log_level, metric_file, config):
    if not metric and not metric_file:
        raise click.UsageError(
            "You must specify either a metric or a metric file to use."
        )
    anyio.run(
        partial(
            _main,
            host=host,
            token=token,
            username=username,
            namespace=namespace,
            metric=metric,
            mode=mode,
            log_level=log_level,
            config=json.loads(config),
            metric_file=metric_file,
        )
    )


def main():
    cli()


if __name__ == "__main__":
    main()
