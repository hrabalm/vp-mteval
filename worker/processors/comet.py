from typing import ClassVar
import logging

import processors.protocols

logger = logging.getLogger(__name__)


class CometKiwiProcessor(processors.protocols.MetricsProcessorProtocol):
    def __init__(self):
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
        self, example: processors.protocols.WorkerExample
    ) -> processors.protocols.WorkerExampleResult:
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
                model_output = self.model.predict(data, batch_size=bs, gpus=1)
                break
            except Exception as e:
                logger.warning(f"Batch size {bs} failed: {e}")

        if model_output is None:
            raise RuntimeError("Failed to compute model output with any batch size.")

        system_score = model_output.system_score
        segment_scores = model_output.scores
        logger.debug(f"Segment scores: {segment_scores}")
        return processors.protocols.WorkerExampleResult(
            job_id=example.job_id,
            name=self.name,
            segment_scores=segment_scores,
            dataset_score=system_score,
            higher_is_better=self.higher_is_better,
        )
