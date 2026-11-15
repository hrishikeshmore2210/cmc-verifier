"""Entrypoint shim. Run from the repo root:  python run.py --help

All logic lives in cmc_verifier/cli.py (also installed as the `cmc-verify` command).
"""

import sys

from cmc_verifier.cli import main

if __name__ == "__main__":
    sys.exit(main())
