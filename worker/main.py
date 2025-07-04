"""
We handle main async main loop which frequently sends heartbeats to the
server. The actual processing of jobs is done in a synchronous loop and
data is sent to it via a queue. Results are returned through another
queue.

Ideally, I want to prefetch.
"""

# TODO: logging levels per click option
# TODO: loading external python metric definition
# TODO: catch status error exceptions or remove them

import multiprocessing
import queue
import logging

import anyio
import click
from anyio.to_thread import run_sync
from pydantic import BaseModel
import httpx
from functools import partial

import processors
import processors.protocols

# Sentinel value to signal the worker to exit
POISON_PILL = None
HEARTBEAT_INTERVAL_SECONDS = 5
NUM_FETCHED_TASKS = 2


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
        self, metrics_processor: processors.protocols.MetricsProcessorProtocol
    ):
        self.examples_queue = multiprocessing.Queue()
        self.result_queue = multiprocessing.Queue()
        self.metrics_processor = metrics_processor

    def _main_loop(self):
        try:
            while True:
                example = self.examples_queue.get()
                if example is POISON_PILL:
                    logging.info("Worker received POISON_PILL, shutting down...")
                    self.result_queue.put(POISON_PILL)
                    break
                logging.info(f"Worker processing job {example.job_id}...")
                result = self.metrics_processor.process_example(example)
                logging.info(f"Worker finished processing job {example.job_id}")
                self.result_queue.put(result)
        except Exception as e:
            logging.error(f"Error in worker process: {str(e)}")
            # Make sure we communicate back to the main process that an error occurred
            self.result_queue.put(POISON_PILL)

    def start(self):
        """Start the worker in a separate process."""
        self.process = multiprocessing.Process(target=self._main_loop)
        self.process.start()

    def start_thread(self):
        """Start the worker in a separate thread."""
        import threading

        self.thread = threading.Thread(target=self._main_loop)
        self.thread.start()


async def send_heartbeat(host, worker_id: int, namespace_name: str, token: str):
    """Send a heartbeat to the server."""
    async with httpx.AsyncClient() as client:
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
            await send_heartbeat(host, worker_id, namespace_name, token)
        await anyio.sleep(interval_seconds)


async def fetch_task():
    # TODO: Depending on whether to process only current or indefinitely wait
    # for new tasks, we either wait or emit POISON_PILL.
    pass


async def process_result():
    pass


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
) -> processors.protocols.WorkerRegistrationResponse:
    async with httpx.AsyncClient() as client:
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
        return processors.protocols.WorkerRegistrationResponse.model_validate(
            response.json()
        )


async def unregister_worker(
    host: str,
    token: str,
    namespace_name: str,
    worker_id: int,
):
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{host}/api/v1/namespaces/{namespace_name}/workers/{worker_id}",
            headers=create_auth_headers(token),
        )
        response.raise_for_status()
        return response.json()


async def assign_and_get_job(
    host: str,
    token: str,
    namespace_name: str,
    worker_id: int,
) -> list[dict]:
    """Assign a job to the worker and return it."""
    async with httpx.AsyncClient() as client:
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


class PostDatasetMetric(BaseModel):
    name: str
    higher_is_better: bool
    score: float


class JobResultRequest(BaseModel):
    job_id: int
    dataset_level_metrics: list[PostDatasetMetric]
    segment_level_metrics: list[PostSegmentMetric]


async def report_job_results(
    example_result: processors.protocols.WorkerExampleResult,
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
            ),
        )

    async with httpx.AsyncClient() as client:
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
    example = processors.protocols.WorkerExample(
        job_id=job["id"],
        segments=[
            processors.protocols.Segment(
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


async def main(host, token, username, namespace, metric, mode, log_level):
    # Setup logging with the specified level
    setup_logging(log_level)

    # 1. Register the worker and announce what metric and what data, if in
    #    single shot mode, we can leave if no data is provided before loading
    processor = processors.get_processor_factory(metric)
    res = await register_worker(
        host=host,
        token=token,
        metric=metric,
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

            worker = Worker(metrics_processor=processor())
            worker.start()

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
                    state = {"finished": True}
                    break

                try:
                    # Wait for a result from the worker
                    example_result = await run_sync(
                        lambda: worker.result_queue.get(timeout=1)
                    )
                    if example_result is POISON_PILL:
                        logging.error(
                            "Worker sent unexpected POISON_PILL. Shutting down."
                        )
                        break

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
                    logging.debug("Result queue empty, continuing to wait.")
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
    type=click.Choice([name for name in processors.processors_by_name.keys()]),
    required=True,
    help="Metric to be used",
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
def cli(host, token, username, namespace, metric, mode, log_level):
    anyio.run(
        partial(
            main,
            host=host,
            token=token,
            username=username,
            namespace=namespace,
            metric=metric,
            mode=mode,
            log_level=log_level,
        )
    )


if __name__ == "__main__":
    cli()
