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
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    print(f"Running: {args.script}")
    module = importlib.import_module(args.script)
    sys.exit(module.main() or 0)
