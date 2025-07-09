from typing import ClassVar
import logging

import processors.protocols

logger = logging.getLogger(__name__)


class CHRF2Processor(processors.protocols.MetricsProcessorProtocol):
    def __init__(self, config: dict | None = None) -> None:
        try:
            import sacrebleu
        except ImportError as e:
            raise ImportError(
                f"sacrebleu>=2.0 is required for {CHRF2Processor.name} metric."
            )

        self.chrf = sacrebleu.CHRF()

    name: ClassVar[str] = "chrF2"
    requires_references: ClassVar[bool] = True
    higher_is_better: ClassVar[bool] = True

    def process_example(
        self, example: processors.protocols.WorkerExample
    ) -> processors.protocols.WorkerExampleResult:
        assert all(x.ref for x in example.segments)
        hypotheses = [seg.tgt for seg in example.segments]
        references = [seg.ref for seg in example.segments]

        # Note: we support only BLEU with a single reference
        # setting trg_lang to "zh", "ja" or "ko" should be sufficient
        # as long as 13a is okay for all other considered languages.
        bleu_score = self.chrf.corpus_score(
            hypotheses=hypotheses,
            references=[references],
        )
        # score_full = bleu_score.format()  # human-readable detailed format
        segment_scores = [
            self.chrf.sentence_score(hypo, [ref]).score
            for hypo, ref in zip(hypotheses, references)
        ]
        logger.debug(f"Segment scores: {segment_scores}")
        return processors.protocols.WorkerExampleResult(
            job_id=example.job_id,
            name=self.name,
            segment_scores=segment_scores,
            dataset_score=bleu_score.score,
            higher_is_better=self.higher_is_better,
        )
