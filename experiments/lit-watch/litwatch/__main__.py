"""`python -m litwatch ...` entry point (run from experiments/lit-watch/)."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
