import importlib
import importlib.util


def load_module(filename: str):
    module_name = filename
    spec = importlib.util.spec_from_file_location(module_name, filename)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print("Error")
        print(e)
        pass  # FIXME
    return module


def load_custom_metric(filename: str):
    """Load a custom metric implementation from a Python file."""
    module = load_module(filename)
    print(module)
    return module.processor_factory


if __name__ == "__main__":
    processor = load_custom_metric("/workspace/worker/processors/example_custom.py")
    print(processor)
