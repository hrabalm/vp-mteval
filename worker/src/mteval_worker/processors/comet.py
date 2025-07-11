from typing import ClassVar
import logging

from . import protocols

logger = logging.getLogger(__name__)


class CometKiwiProcessor(protocols.MetricsProcessorProtocol):
    def __init__(self, config: dict | None = None) -> None:
        try:
            import comet
        except ImportError as e:
            raise ImportError(
                f"unbabel-comet>=2.0 is required for {CometKiwiProcessor.name} metric."
            )

        model_path = comet.download_model("Unbabel/wmt22-cometkiwi-da")
        self.model = comet.load_from_checkpoint(model_path)

    name: ClassVar[str] = "CometKiwi22"
    requires_references: ClassVar[bool] = False
    higher_is_better: ClassVar[bool] = True

    def process_example(
        self, example: protocols.WorkerExample
    ) -> protocols.WorkerExampleResult | None:
        data = [
            {
                "src": seg.src,
                "mt": seg.tgt,
            }
            for seg in example.segments
        ]

        model_output = None
        for bs in [32, 16, 8, 4, 2, 1]:
            try:
                # Try to use the model with the given batch size
                model_output = self.model.predict(
                    data, batch_size=bs, gpus=1, num_workers=0
                )
                break
            except Exception as e:
                logger.warning(f"Batch size {bs} failed: {e}")
                import torch
                import time
                import gc

                gc.collect()
                with torch.no_grad():
                    torch.cuda.empty_cache()
                time.sleep(1)
                logger.info(
                    f"Reserved: {torch.cuda.memory_reserved()} | Allocated: {torch.cuda.memory_allocated()}"
                )

        # If we still failed, we will truncate the output to 6144 chars and try
        # again
        if model_output is None:
            logger.warning(
                "Failed to compute model output with any batch size, truncating input data to 6144 characters."
            )
            data = [
                {
                    "src": seg.src[:6144],  # Truncate source text
                    "mt": seg.tgt[:6144],  # Truncate target text
                }
                for seg in example.segments
            ]
            for bs in [32, 16, 8, 4, 2, 1]:
                try:
                    # Try to use the model with the given batch size
                    model_output = self.model.predict(data, batch_size=bs, gpus=1)
                    break
                except Exception as e:
                    logger.warning(f"Batch size {bs} failed: {e}")
                    import torch
                    import time
                    import gc

                    gc.collect()
                    with torch.no_grad():
                        torch.cuda.empty_cache()
                    time.sleep(1)
                    logger.info(
                        f"Reserved: {torch.cuda.memory_reserved()} | Allocated: {torch.cuda.memory_allocated()}"
                    )

        if model_output is None:
            logger.error(
                "Failed to compute model output with any batch size, even after truncation. Skipping this job."
            )
            return None

        system_score = model_output.system_score
        segment_scores = model_output.scores
        logger.debug(f"Segment scores: {segment_scores}")
        return protocols.WorkerExampleResult(
            job_id=example.job_id,
            name=self.name,
            segment_scores=segment_scores,
            dataset_score=system_score,
            higher_is_better=self.higher_is_better,
        )
