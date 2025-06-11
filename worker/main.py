"""
We handle main async main loop which frequently sends heartbeats to the
server. The actual processing of jobs is done in a synchronous loop and
data is sent to it via a queue. Results are returned through another
queue.

Ideally, I want to prefetch.
"""

# TODO: how do I handle metrics that need references?
#           - I could just give out min or None
#           - or explicitly ignore
# TODO: logging levels per click option
# TODO: loading external python metric definition
# TODO: catch status error exceptions or remove them

import multiprocessing
from typing import Literal, Protocol, ClassVar
import queue
import logging

import anyio
import click
from anyio.to_thread import run_sync
from pydantic import BaseModel
import httpx
from functools import partial

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


class Segment(BaseModel):
    src: str
    tgt: str
    ref: str | None = None


class WorkerExample(BaseModel):
    segments: list[Segment]
    src_lang: str
    tgt_lang: str


class WorkerExampleResult(BaseModel):
    name: str
    segment_scores: list[float] | None
    dataset_score: float | None
    higher_is_better: bool


class WorkerRegistrationResponse(BaseModel):
    worker_id: int
    num_jobs: int


class MetricsProcessorProtocol(Protocol):
    """Synchronous worker that continually processes examples from a queue."""

    name: ClassVar[str]
    requires_references: ClassVar[bool]
    higher_is_better: ClassVar[bool] = True

    def process_example(self, example: WorkerExample) -> WorkerExampleResult: ...


class BLEUProcessor(MetricsProcessorProtocol):
    def __init__(self):
        import sacrebleu

        # FIXME: setup tokenizer correctly for CJK languages
        self.bleu = sacrebleu.BLEU()
        # We need to use effective_order=True for sentences.
        self.bleu_sentence = sacrebleu.BLEU(
            effective_order=True,
        )

    name: ClassVar[str] = "BLEU"
    requires_references: ClassVar[bool] = True
    higher_is_better: ClassVar[bool] = True

    def process_example(self, example: WorkerExample) -> WorkerExampleResult:
        # assert all(x.ref for x in example.segments)  # FIXME: enable
        hypotheses = [seg.tgt for seg in example.segments]
        references = [seg.ref for seg in example.segments]
        references = [
            seg.ref if seg.ref else "" for seg in example.segments
        ]  # FIXME: remove
        # Note: we support only BLEU with a single reference
        # setting trg_lang to "zh", "ja" or "ko" should be sufficient
        # as long as 13a is okay for all other considered languages.
        bleu_score = self.bleu.corpus_score(
            hypotheses=hypotheses,
            references=[references],
        )
        # score_full = bleu_score.format()  # human-readable detailed format
        segment_scores = [
            self.bleu_sentence.sentence_score(hypo, [ref]).score
            for hypo, ref in zip(hypotheses, references)
        ]
        logging.debug(f"Segment scores: {segment_scores}")
        return WorkerExampleResult(
            name=self.name,
            segment_scores=segment_scores,
            dataset_score=bleu_score.score,
            higher_is_better=self.higher_is_better,
        )


class Worker:
    def __init__(self, metrics_processor: MetricsProcessorProtocol):
        self.examples_queue = multiprocessing.Queue()
        self.result_queue = multiprocessing.Queue()
        self.metrics_processor = metrics_processor

    def _main_loop(self):
        while True:
            example = self.examples_queue.get()
            if example is POISON_PILL:
                self.result_queue.put(POISON_PILL)
                break
            result = self.metrics_processor.process_example(example)
            self.result_queue.put(result)

    def start(self):
        """Start the worker in a separate process."""
        self.process = multiprocessing.Process(target=self._main_loop)
        self.process.start()

    def start_thread(self):
        """Start the worker in a separate thread."""
        import threading

        self.thread = threading.Thread(target=self._main_loop)
        self.thread.start()


async def send_heartbeat(host, worker_id: int):
    """Send a heartbeat to the server."""
    async with httpx.AsyncClient() as client:
        response = await client.put(f"{host}/api/v1/workers/{worker_id}/heartbeat")
        response.raise_for_status()
        return response.json()


async def send_heartbeats(
    interval_seconds: int, host: str, worker_id: int, is_fake: bool = False
):
    """Periodically send a heartbeat."""
    while True:
        logging.info("Sending heartbeat...")
        if not is_fake:
            await send_heartbeat(host, worker_id)
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
    namespace: str,
    username: str | None,
) -> WorkerRegistrationResponse:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{host}/api/v1/workers/register",
            headers=create_auth_headers(token),
            json={
                "namespace_name": namespace,
                "metric": metric,
                "metric_requires_references": metric_requires_references,
                "username": username,
            },
        )
        response.raise_for_status()
        return WorkerRegistrationResponse.model_validate(response.json())


async def unregister_worker(
    host: str,
    token: str,
    worker_id: int,
):
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{host}/api/v1/workers/{worker_id}",
            headers=create_auth_headers(token),
        )
        response.raise_for_status()
        return response.json()


async def assign_and_get_job(
    host: str,
    token: str,
    worker_id: int,
) -> list[dict]:
    """Assign a job to the worker and return it."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{host}/api/v1/workers/{worker_id}/jobs/assign",
            headers=create_auth_headers(token),
        )
        response.raise_for_status()
        data = response.json()
        return data


def start_heartbeat_task(tg, interval_seconds: int, host: str, worker_id: int):
    tg.start_soon(
        partial(
            send_heartbeats,
            interval_seconds,
            host=host,
            worker_id=worker_id,
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
    example_result: WorkerExampleResult,
    job_id: int,
    host: str,
    token: str,
    worker_id: int,
):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{host}/api/v1/workers/{worker_id}/jobs/{job_id}/report_result",
            headers=create_auth_headers(token),
            json=JobResultRequest(
                job_id=job_id,
                dataset_level_metrics=[
                    PostDatasetMetric(
                        name=example_result.name,
                        higher_is_better=example_result.higher_is_better,
                        score=example_result.dataset_score,
                    )
                ],
                segment_level_metrics=[
                    PostSegmentMetric(
                        name=example_result.name,
                        higher_is_better=example_result.higher_is_better,
                        scores=[score for score in example_result.segment_scores],
                    ),
                ],
            ).model_dump(),
        )
        response.raise_for_status()
        return response.json()


def job_to_example(job):
    logging.debug(f"Processing job: {job}")
    logging.debug(f"Job segments: {job['segments']}")
    example = WorkerExample(
        segments=[
            Segment(
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
    res = await register_worker(
        host=host,
        token=token,
        metric=metric,
        metric_requires_references=BLEUProcessor.requires_references,
        namespace=namespace,
        username=username,
    )
    logging.info(f"Worker registered: {res}")

    async with anyio.create_task_group() as tg:
        # 2. Start the Worker subprocess and heartbeat task
        start_heartbeat_task(tg, 5, host, worker_id=res.worker_id)  # FIXME

        # 3. Fetch initial NUM_FETCHED_TASKS tasks and add them to the queue
        logging.info("Fetching a single initial task...")
        jobs = await assign_and_get_job(
            host=host,
            token=token,
            worker_id=res.worker_id,
        )
        logging.debug(f"Fetched jobs: {jobs}")
        logging.info("Fetched a single initial task...")

        initial_jobs = jobs

        if len(initial_jobs) > 0:
            worker = Worker(metrics_processor=BLEUProcessor())
            worker.start()
            for job in initial_jobs:
                example = job_to_example(job)
                worker.examples_queue.put(example)

        # 4. Every time a task is finished, push the results to the server and fetch another task. If not available, either wait (persistent mode) or emit POISON_PILL (single shot mode).
        while True:
            try:
                # Get the result from the worker
                example_result = await run_sync(worker.result_queue.get)
                if example_result is POISON_PILL:
                    logging.info("Received POISON_PILL, exiting...")
                    break

                # Report the result to the server
                logging.info("Reporting job results...")
                await report_job_results(
                    example_result=example_result,
                    job_id=initial_jobs[0]["id"],
                    host=host,
                    token=token,
                    worker_id=res.worker_id,
                )
                logging.info("Job results reported successfully.")

                # Fetch a new job
                logging.info("Fetching a new job...")
                jobs = await assign_and_get_job(
                    host=host,
                    token=token,
                    worker_id=res.worker_id,
                )
                if not jobs:
                    logging.info("No more jobs available.")
                    if mode == "one-shot":
                        break  # Exit if in one-shot mode
                    else:
                        logging.info("Waiting for new jobs...")
                        await anyio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                        continue

                # Add the new job to the worker's queue
                for job in jobs:
                    example = job_to_example(job)
                    worker.examples_queue.put(example)

            except queue.Empty:
                logging.info("No results available, waiting...")
                await anyio.sleep(HEARTBEAT_INTERVAL_SECONDS)

    # 5. If we want to end, unregister the worker explicitly and exit.
    # TODO: also call this on signal termination
    logging.info("Unregistering worker...")
    await unregister_worker(
        host=host,
        token=token,
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
@click.option("--metric", type=str, required=True, help="Metric to be used")
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
