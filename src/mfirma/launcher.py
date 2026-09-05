from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence

from .ui.single_instance import (
    ForwardStatus,
    RequestError,
    forward_file_request,
    instance_server_name,
    startup_pdf_paths,
)


def launch_or_forward(arguments: Sequence[str] | None = None) -> int:
    raw_arguments = list(arguments or sys.argv)
    try:
        paths = startup_pdf_paths(raw_arguments)
        status = forward_file_request(instance_server_name(), paths)
    except RequestError:
        status = ForwardStatus.REJECTED
    if status is ForwardStatus.DELIVERED:
        return 0

    subprocess.Popen(
        [sys.executable, "-m", "mfirma", *raw_arguments[1:]],
        close_fds=True,
    )
    return 0


def main() -> None:
    raise SystemExit(launch_or_forward())


if __name__ == "__main__":
    main()
