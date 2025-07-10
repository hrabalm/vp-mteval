# mteval_upload

A Python tool for uploading machine translation evaluation data to the vp-mteval server. Provides both a command-line interface (CLI) and a Python API for seamless integration into your workflow.

## Features

- **Upload translation runs** to vp-mteval server with automatic retry logic
- **Local caching** of runs with success/failure tracking
- **Batch upload** of previously failed or successful runs
- **Exponential backoff retry strategy**
- **CLI and Python API** for flexible usage

## Installation

### From Git Repository (Recommended)

The CLI tool can be used directly using `uv tool`:

```bash
uv tool run "git+https://github.com/hrabalm/vp-mteval.git#subdirectory=mteval_upload"
```

Or install directly from the GitHub repository using uv:

```bash
uv add "git+https://github.com/hrabalm/vp-mteval.git#subdirectory=mteval_upload"
```

or using pip:

```bash
pip install "git+https://github.com/hrabalm/vp-mteval.git#subdirectory=mteval_upload"
```

### Install Specific Version

To install a specific commit or tag, specify it in the URL:

```bash
uv add "git+https://github.com/hrabalm/vp-mteval.git@v1.0.0#subdirectory=mteval_upload"
```

Replace `v1.0.0` with the desired tag or commit hash.

## CLI Usage

### Upload a translation run

```bash
mteval_upload upload -d example.json -h http://localhost:8000 -k your-api-key
```

### Upload failed runs

```bash
mteval_upload upload-failed -h http://localhost:8000 -k your-api-key
```

### Upload successful runs

```bash
mteval_upload upload-successful -h http://localhost:8000 -k your-api-key
```

### Options

- `-d, --data`: Path to the JSON data file to upload
- `-h, --host`: Host URL for the vp-mteval server (e.g., http://localhost:8000)
- `-k, --api-key`: API key for authentication
- `-K, --keep`: Keep runs after successful upload (useful for debugging)

## Data Format

The tool expects JSON files with the following structure:

```json
{
    "namespace_name": "default",
    "dataset_name": "example_dataset",
    "dataset_source_lang": "en",
    "dataset_target_lang": "fr",
    "segments": [
        {
            "src": "Hello, world!",
            "tgt": "Bonjour, le monde!"
        },
        {
            "src": "How are you?",
            "tgt": "Comment ça va?"
        }
    ]
}
```

## Python API

```python
import mteval_upload.lib as mteval

# Upload a single run
run_data = {
    "namespace_name": "default",
    "dataset_name": "my_dataset",
    "dataset_source_lang": "en",
    "dataset_target_lang": "fr",
    "segments": [...]
}

mteval.upload_run(
    host="http://localhost:8000",
    run=run_data,
    api_key="your-api-key",
    keep=False,  # Delete after successful upload
    save=True    # Save locally before upload
)

# Upload all failed runs
mteval.upload_failed_runs(
    host="http://localhost:8000",
    api_key="your-api-key",
    keep=False
)

# Upload all successful runs
mteval.upload_successful_runs(
    host="http://localhost:8000",
    api_key="your-api-key",
    keep=False
)
```

## Local Storage

The tool automatically stores runs locally using platformdirs:
- **Success**: `~/.local/share/vp-mteval/vp-mteval/success/`
- **Failure**: `~/.local/share/vp-mteval/vp-mteval/failure/`

Failed uploads are automatically saved for later retry, while successful uploads are moved to the success directory.
