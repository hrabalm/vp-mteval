import processors.protocols
import processors.bleu
import processors.chrf
import processors.comet
import processors.metricx24

processors_by_name = {
    "BLEU": processors.bleu.BLEUProcessor,
    "chrF2": processors.chrf.CHRF2Processor,
    "CometKiwi22": processors.comet.CometKiwiProcessor,
    "MetricX24": processors.metricx24.MetricX24Processor,
}


def get_processor_factory(
    name: str,
) -> type[processors.protocols.MetricsProcessorProtocol]:
    """Get the processor class by name."""
    if name not in processors_by_name:
        raise ValueError(f"Unknown processor: {name}")
    return processors_by_name[name]
