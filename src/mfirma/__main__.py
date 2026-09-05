from __future__ import annotations

import sys


def main() -> None:
    if "--qt-dashboard" in sys.argv[1:]:
        from .ui.application import run_qt_dashboard

        raise SystemExit(run_qt_dashboard(sys.argv))

    from .app import main as run_tk_app

    run_tk_app()

if __name__ == "__main__":
    main()
