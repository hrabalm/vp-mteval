import logging
from typing import ClassVar

import processors.protocols

logger = logging.getLogger(__name__)

MODEL_NAME_OR_PATH = "google/metricx-24-hybrid-xl-v2p6-bfloat16"
TOKENIZER = "google/mt5-xl"
MAX_INPUT_LENGTH = 1536
MAX_BATCH_SIZE = 32


class MetricX24Processor(processors.protocols.MetricsProcessorProtocol):
    def __init__(self):
        try:
            from processors.metricx24_impl import Model
        except ImportError as e:
            raise ImportError(
                f"unbabel-comet>=2.0 is required for {MetricX24Processor.name} metric."
            )

        self.model = Model(
            model_name_or_path=MODEL_NAME_OR_PATH,
            tokenizer=TOKENIZER,
            batch_size=MAX_BATCH_SIZE,
            max_input_length=MAX_INPUT_LENGTH,
        )

    name: ClassVar[str] = "MetricX24[noref]"
    requires_references: ClassVar[bool] = False
    higher_is_better: ClassVar[bool] = False

    def process_example(
        self, example: processors.protocols.WorkerExample
    ) -> processors.protocols.WorkerExampleResult:
        sources = [seg.src for seg in example.segments]
        hypotheses = [seg.tgt for seg in example.segments]

        segment_scores = None
        for bs in [32, 16, 8, 4, 2, 1]:
            try:
                # Try to use the model with the given batch size
                segment_scores = self.model.predict(
                    sources,
                    hypotheses,
                )
            except Exception as e:
                logger.warning(f"Batch size {bs} failed: {e}")

        if segment_scores is None:
            raise RuntimeError("Failed to compute segment scores with any batch size.")

        system_score = sum(segment_scores) / len(segment_scores)
        logger.debug(f"Segment scores: {segment_scores}")
        return processors.protocols.WorkerExampleResult(
            job_id=example.job_id,
            name=self.name,
            segment_scores=segment_scores,
            dataset_score=system_score,
            higher_is_better=self.higher_is_better,
        )
