from __future__ import annotations

import sys


def main() -> None:
    from .ui.application import run_application

    raise SystemExit(run_application(sys.argv))

if __name__ == "__main__":
    main()
