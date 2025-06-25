import processors.protocols
import processors.bleu
import processors.chrf

processors_by_name = {
    "BLEU": processors.bleu.BLEUProcessor,
    "chrF2": processors.chrf.CHRF2Processor,
}


def get_processor_factory(
    name: str,
) -> type[processors.protocols.MetricsProcessorProtocol]:
    """Get the processor class by name."""
    if name not in processors_by_name:
        raise ValueError(f"Unknown processor: {name}")
    return processors_by_name[name]
