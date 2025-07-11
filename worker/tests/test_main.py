from functools import partial

import anyio
import mteval_worker.main
import pytest
from anyio.to_thread import run_sync
from mteval_worker.processors.bleu import BLEUProcessor
from mteval_worker.processors.protocols import (
    Segment,
    WorkerExample,
    WorkerExampleResult,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


EXAMPLE_PERFECT_TRANSLATION = WorkerExample(
    job_id=0,
    segments=[
        Segment(src="Hello", tgt="Bonjour", ref="Bonjour"),
        Segment(src="World", tgt="Monde", ref="Monde"),
        Segment(src="This is a test", tgt="Ceci est un test", ref="Ceci est un test"),
        Segment(src="Goodbye", tgt="Au revoir", ref="Au revoir"),
        Segment(src="See you later", tgt="À plus tard", ref="À plus tard"),
        Segment(src="Have a nice day", tgt="Bonne journée", ref="Bonne journée"),
        Segment(src="Thank you", tgt="Merci", ref="Merci"),
        Segment(
            src="I love programming", tgt="J'aime programmer", ref="J'aime programmer"
        ),
    ],
    src_lang="en",
    tgt_lang="fr",
)


EXAMPLE_IMPERFECT_TRANSLATION = WorkerExample(
    job_id=0,
    segments=[
        Segment(src="Hello", tgt="", ref="Bonjour"),  # intentionally wrong example
        Segment(src="World", tgt="Monde", ref="Monde"),
        Segment(src="This is a test", tgt="Ceci est un test", ref="Ceci est un test"),
        Segment(src="Goodbye", tgt="Au revoir", ref="Au revoir"),
        Segment(src="See you later", tgt="À plus tard", ref="À plus tard"),
        Segment(src="Have a nice day", tgt="Bonne journée", ref="Bonne journée"),
        Segment(src="Thank you", tgt="Merci", ref="Merci"),
        Segment(
            src="I love programming", tgt="J'aime programmer", ref="J'aime programmer"
        ),
    ],
    src_lang="en",
    tgt_lang="fr",
)


def test_bleu_processor_perfect():
    bleu_processor = BLEUProcessor()
    result = bleu_processor.process_example(EXAMPLE_PERFECT_TRANSLATION)
    assert result.dataset_score == pytest.approx(100.0), (
        "Dataset should have perfect BLEU score"
    )
    assert result.higher_is_better, "BLEU score should be higher is better"
    assert result.segment_scores is not None
    assert len(result.segment_scores) == len(EXAMPLE_PERFECT_TRANSLATION.segments), (
        "Segment scores should match number of segments"
    )
    for score in result.segment_scores:
        assert score == pytest.approx(100.0)


def test_bleu_processor_imperfect():
    bleu_processor = BLEUProcessor()
    result = bleu_processor.process_example(EXAMPLE_IMPERFECT_TRANSLATION)
    assert result.dataset_score, "BLEU should return dataset level scores"
    assert result.dataset_score < 100.0, "Dataset should not have perfect BLEU score"
    assert result.higher_is_better, "BLEU score should be higher is better"
    assert result.segment_scores is not None
    assert len(result.segment_scores) == len(EXAMPLE_IMPERFECT_TRANSLATION.segments), (
        "Segment scores should match number of segments"
    )
    assert any(score < 100.0 for score in result.segment_scores), (
        "At least one segment should have a non-perfect BLEU score"
    )


async def test_main_mp():
    import queue

    bleu_processor = BLEUProcessor()
    worker_instance = mteval_worker.main.Worker(metrics_processor=bleu_processor)

    print(f"Starting worker with {bleu_processor.name} processor...")

    # Start the worker's main_loop in a subprocess
    worker_instance.start()
    print("Worker main_loop started in a background subprocess.")

    async with anyio.create_task_group() as tg:
        # Start the heartbeat task
        tg.start_soon(
            partial(
                mteval_worker.main.send_heartbeats,
                mteval_worker.main.HEARTBEAT_INTERVAL_SECONDS,
                host="",
                namespace_name="default",
                worker_id=1,
                is_fake=True,
                token="",
            )
        )

        # Prepare an example job
        example_job = EXAMPLE_PERFECT_TRANSLATION

        # Send the job to the worker
        print("Sending job to worker...")
        await run_sync(worker_instance.examples_queue.put, example_job)

        # Send another job
        example_job_2 = EXAMPLE_IMPERFECT_TRANSLATION
        print("Sending another job to worker...")
        await run_sync(worker_instance.examples_queue.put, example_job_2)

        # Signal the worker to exit
        print("Sending POISON_PILL to worker...")
        await run_sync(
            worker_instance.examples_queue.put, mteval_worker.main.POISON_PILL
        )
        print("Worker shutdown signaled.")

        # Process the results
        while True:
            try:
                result = await run_sync(worker_instance.result_queue.get_nowait)
                print(f"Processed result: {result}")
                if result is mteval_worker.main.POISON_PILL:
                    print("Received POISON_PILL, exiting result processing loop.")
                    tg.cancel_scope.cancel()  # stop remaining heartbeat task
                    break
            except queue.Empty:
                await anyio.sleep(1)
    print("Worker has shut down. Main function finished.")


async def test_main_threading():
    import queue

    bleu_processor = BLEUProcessor()
    worker_instance = mteval_worker.main.Worker(metrics_processor=bleu_processor)

    print(f"Starting worker with {bleu_processor.name} processor...")

    # Start the worker's main_loop in a subprocess
    worker_instance.start_thread()
    print("Worker main_loop started in a background subprocess.")

    async with anyio.create_task_group() as tg:
        # Start the heartbeat task
        tg.start_soon(
            partial(
                mteval_worker.main.send_heartbeats,
                mteval_worker.main.HEARTBEAT_INTERVAL_SECONDS,
                host="",
                namespace_name="default",
                worker_id=1,
                is_fake=True,
                token="",
            )
        )

        # Prepare an example job
        example_job = EXAMPLE_PERFECT_TRANSLATION

        # Send the job to the worker
        print("Sending job to worker...")
        await run_sync(worker_instance.examples_queue.put, example_job)

        # Send another job
        example_job_2 = EXAMPLE_IMPERFECT_TRANSLATION
        print("Sending another job to worker...")
        await run_sync(worker_instance.examples_queue.put, example_job_2)

        # Signal the worker to exit
        print("Sending POISON_PILL to worker...")
        await run_sync(
            worker_instance.examples_queue.put, mteval_worker.main.POISON_PILL
        )
        print("Worker shutdown signaled.")

        # Process the results
        while True:
            try:
                result = await run_sync(worker_instance.result_queue.get_nowait)
                print(f"Processed result: {result}")
                if result is mteval_worker.main.POISON_PILL:
                    print("Received POISON_PILL, exiting result processing loop.")
                    tg.cancel_scope.cancel()  # stop remaining heartbeat task
                    break
            except queue.Empty:
                await anyio.sleep(1)
    print("Worker has shut down. Main function finished.")
