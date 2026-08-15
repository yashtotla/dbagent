"""Entry point for the dbagent experiment."""

import argparse
import sys

from src.experiment import main as run_experiment
from src.utils.constants import MODEL_REGISTRY


def parse_args():
    """Parse the command line."""
    parser = argparse.ArgumentParser(description="dbagent experiment runner")
    parser.add_argument("--mode", required=True, choices=["A", "B"],
                        help="A: every statement commits. B: checkpoint and restore available")
    parser.add_argument("--model", required=True, choices=sorted(MODEL_REGISTRY),
                        help="Model alias from the registry")
    parser.add_argument("--limit", type=int, default=3, help="Number of tasks to run")
    parser.add_argument("--offset", type=int, default=0, help="Index of the first task")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(run_experiment(mode=args.mode, model=args.model,
                            limit=args.limit, offset=args.offset))
