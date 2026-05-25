"""Entry point: python -m praxis"""

from __future__ import annotations

import sys

import anthropic

from .config import Config
from .orchestrator import Orchestrator


def main() -> None:
    config = Config.from_env()
    client = anthropic.Anthropic()
    orch = Orchestrator(client, config)

    if len(sys.argv) > 1:
        message = " ".join(sys.argv[1:])
    else:
        message = sys.stdin.read()

    result = orch.run(message)
    print(result)


if __name__ == "__main__":
    main()
