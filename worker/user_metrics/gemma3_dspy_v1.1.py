from typing import ClassVar
import logging
import processors.protocols

METRIC_NAME = "Gemma3_DSPy_v1"

try:
    import dspy
except ImportError as e:
    raise ImportError(f"dspy is required for {METRIC_NAME} metric.")

try:
    import iso639
except ImportError as e:
    raise ImportError(f"iso639 is required for {METRIC_NAME} metric.")

logger = logging.getLogger(__name__)


class TranslationQualityEstimation(dspy.Signature):
    """Assign a score (integer 0-100) to the following translation.

    100 - perfect translation - The meaning and grammar of the translation is completely consistent with the source.
    66 - most meaning preserved and few grammar mistakes - The translation retains most of the meaning. It may have some grammar mistakes or minor inconsistencies.
    33 - some meaning preserved - Some of the meaning is preserved but significant parts are missing. The narrative is hard to follow due to errors. Grammar may be poor.
    0 - no meaning preserved - Nearly all information is lost in the translation.
    """

    source_language: str = dspy.InputField()
    translation_language: str = dspy.InputField()
    source_text: str = dspy.InputField()
    translation: str = dspy.InputField()

    score: int = dspy.OutputField(desc="Score (0-100) assigned to the translation.")


class Gemma3_DSPy_v1(processors.protocols.MetricsProcessorProtocol):
    def __init__(self, config: dict):
        api_base = config["api_base"]
        api_key = config["api_key"]
        program_path = config["program_path"]

        self.lm = dspy.LM(
            model="openai/google/gemma-3-27b-it",
            api_base=api_base,
            api_key=api_key,
            max_tokens=8000,
        )

        dspy.configure(lm=self.lm)
        self.cof_qe = dspy.ChainOfThought(TranslationQualityEstimation)
        self.cof_qe.load(program_path)

    name: ClassVar[str] = METRIC_NAME
    requires_references: ClassVar[bool] = False
    higher_is_better: ClassVar[bool] = True

    def process_example(
        self, example: processors.protocols.WorkerExample
    ) -> processors.protocols.WorkerExampleResult:
        sources = [seg.src for seg in example.segments]
        hypotheses = [seg.tgt for seg in example.segments]
        src_lang = example.src_lang
        tgt_lang = example.tgt_lang

        examples = [
            dspy.Example(
                source_language=src_lang,
                translation_language=tgt_lang,
                source_text=src,
                translation=tgt,
            ).with_inputs(
                "source_language",
                "translation_language",
                "source_text",
                "translation",
            )
            for src, tgt in zip(sources, hypotheses)
        ]

        predictions = self.cof_qe.batch(examples, num_threads=64, max_errors=100_000)
        segment_scores = [pred.score for pred in predictions]
        reasonings = [pred.reasoning for pred in predictions]
        system_score = sum(segment_scores) / len(segment_scores)
        logger.debug(f"Segment scores: {segment_scores}")
        return processors.protocols.WorkerExampleResult(
            job_id=example.job_id,
            name=self.name,
            segment_scores=segment_scores,
            segment_custom=[
                {
                    "reasoning": reasoning,
                }
                for reasoning in reasonings
            ],
            dataset_score=system_score,
            higher_is_better=self.higher_is_better,
        )


# We need to explicitly export the processor type or factory function
processor_factory = Gemma3_DSPy_v1
