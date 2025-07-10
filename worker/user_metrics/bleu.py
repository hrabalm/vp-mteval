"""This is the exact same as builtin BLEU metric processor, but it may
be useful for testing purposes as its lightest on resources and
dependencies."""

from typing import ClassVar
import logging

import mteval_worker.processors.protocols

logger = logging.getLogger(__name__)


class BLEUProcessor(mteval_worker.processors.protocols.MetricsProcessorProtocol):
    def __init__(self, config: dict | None = None) -> None:
        try:
            import sacrebleu
        except ImportError as e:
            raise ImportError(
                f"sacrebleu>=2.0 is required for {BLEUProcessor.name} metric."
            )

        # FIXME: setup tokenizer correctly for CJK languages
        self.bleu = sacrebleu.BLEU()
        # We need to use effective_order=True for sentences.
        self.bleu_sentence = sacrebleu.BLEU(
            effective_order=True,
        )

    name: ClassVar[str] = "BLEU"
    requires_references: ClassVar[bool] = True
    higher_is_better: ClassVar[bool] = True

    def process_example(
        self, example: mteval_worker.processors.protocols.WorkerExample
    ) -> mteval_worker.processors.protocols.WorkerExampleResult:
        assert all(x.ref for x in example.segments)
        hypotheses = [seg.tgt for seg in example.segments]
        references = [seg.ref for seg in example.segments]

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
        logger.debug(f"Segment scores: {segment_scores}")
        return mteval_worker.processors.protocols.WorkerExampleResult(
            job_id=example.job_id,
            name=self.name,
            segment_scores=segment_scores,
            dataset_score=bleu_score.score,
            higher_is_better=self.higher_is_better,
        )


# We need to explicitly export the processor type or factory function
processor_factory = BLEUProcessor
