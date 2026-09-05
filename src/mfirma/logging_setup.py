from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


_LOGGER_NAME = "mfirma"
_HANDLER_MARKER = "_mfirma_rotating_file_handler"


def default_log_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "mFirma" / "logs" / "mfirma.log"


def configure_logging(path: Path | None = None) -> Path | None:
    """Configure the application logger and return the active log path."""
    destination = (path or default_log_path()).expanduser().resolve()
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in tuple(logger.handlers):
        if not getattr(handler, _HANDLER_MARKER, False):
            continue
        if Path(handler.baseFilename) == destination:  # type: ignore[attr-defined]
            return destination
        logger.removeHandler(handler)
        handler.close()

    try:
        handler = RotatingFileHandler(
            destination,
            maxBytes=1_048_576,
            backupCount=5,
            encoding="utf-8",
        )
    except OSError:
        return None
    setattr(handler, _HANDLER_MARKER, True)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    logger.addHandler(handler)
    logger.info("Log applicativo inizializzato")
    return destination


def shutdown_logging() -> None:
    """Close only handlers installed by :func:`configure_logging`."""
    logger = logging.getLogger(_LOGGER_NAME)
    for handler in tuple(logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)
            handler.close()
