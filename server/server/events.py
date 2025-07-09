import litestar
import litestar.events
import server.tasks as tasks
from server.config import settings

from saq import Queue
import logging


logger = logging.getLogger(__name__)

RUN_CREATED = "run_created"


@litestar.events.listener(RUN_CREATED)
async def compute_ngrams_on_run_created(
    data: tasks.RunCreatedData,
):
    assert settings.saq_queue_dsn, "SAQ queue DSN must be set in settings"
    queue = Queue.from_url(settings.saq_queue_dsn, name="ngrams")
    await queue.connect()
    print(queue.info())

    await queue.enqueue(
        "compute_ngrams_on_run_created", data=data.model_dump_json(), timeout=5 * 60
    )


listeners = [compute_ngrams_on_run_created]
