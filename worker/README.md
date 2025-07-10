# Worker

Workers take care of providing metrics for translation runs.

## Installation

The CLI tool can be used installed using uv to the current project:

```bash
uv add "git+https://github.com/hrabalm/vp-mteval.git#subdirectory=worker"
```

or using pip:

```bash
pip install "git+https://github.com/hrabalm/vp-mteval.git#subdirectory=worker"
```

Note that depending on which metrics you want to use, you may want to specify
dependecy one of the dependency groups or install custom dependencies to a given
Python environment.

## Example usage

Running builtin metric:

```bash
mteval-worker --host https://mteval2.hrabal.eu --token YOUR_API_TOKEN --metric BLEU --username YOUR_USERNAME
```

```bash
uv run mteval-worker --host https://mteval2.hrabal.eu --token YOUR_API_TOKEN --metric-file user_metrics/bleu.py --username YOUR_USERNAME
```