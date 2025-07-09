import processors.protocols
import processors.bleu
import processors.chrf
import processors.comet
import processors.metricx24
import processors.custom

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


def get_processor_from_file(filename):
    """Load a custom metric implementation from a Python file."""
    try:
        module = processors.custom.load_custom_metric(filename)
        return module
    except Exception as e:
        raise RuntimeError(f"Failed to load custom metric from {filename}: {e}")
