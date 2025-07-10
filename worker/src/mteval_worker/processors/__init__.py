from . import protocols
from . import bleu
from . import chrf
from . import comet
from . import metricx24
from . import custom

processors_by_name = {
    "BLEU": bleu.BLEUProcessor,
    "chrF2": chrf.CHRF2Processor,
    "CometKiwi22": comet.CometKiwiProcessor,
    "MetricX24": metricx24.MetricX24Processor,
}


def get_processor_factory(
    name: str,
) -> type[protocols.MetricsProcessorProtocol]:
    """Get the processor class by name."""
    if name not in processors_by_name:
        raise ValueError(f"Unknown processor: {name}")
    return processors_by_name[name]


def get_processor_from_file(filename):
    """Load a custom metric implementation from a Python file."""
    try:
        module = custom.load_custom_metric(filename)
        return module
    except Exception as e:
        raise RuntimeError(f"Failed to load custom metric from {filename}: {e}")
