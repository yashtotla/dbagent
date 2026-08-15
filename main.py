"""Entry point for all experiment scripts."""

import argparse
import importlib
import sys


def parse_args():
    """Parse the command line."""
    parser = argparse.ArgumentParser(description="dbagent experiment runner")
    parser.add_argument(
        "--script",
        required=True,
        help="Dotted module path to an experiment, e.g. experiments.milestone0",
    )
    parser.add_argument("--limit", type=int, help="Number of tasks to run")
    parser.add_argument("--offset", type=int, help="Index of the first task to run")
    parser.add_argument("--mode", choices=["A", "B"], help="Which agent mode to run")
    parser.add_argument("--model", help="Override the model in config for this run")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    print(f"Running: {args.script}")
    module = importlib.import_module(args.script)

    kwargs = {k: v for k, v in vars(args).items() if k != "script" and v is not None}
    sys.exit(module.main(**kwargs) or 0)
