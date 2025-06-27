import wandb
from toolz import take

# Replace with your actual entity and project
ENTITY = "hrabalm"
PROJECT = "llm-translation"

api = wandb.Api()
runs = api.runs(f"{ENTITY}/{PROJECT}")

for run in take(500, runs):
    print(f"\n🔍 Run: {run.name} ({run.id})")

    # Go through the history keys to find tables
    for key, value in run.summary.items():
        print(key, value)

    for key, value in run.config.items():
        print(key, value)
