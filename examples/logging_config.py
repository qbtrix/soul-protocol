# logging_config.py — Example logging configurations for soul-protocol.
# Shows how to set up structured logging for development and production.

"""
Soul Protocol Logging Configuration Examples
=============================================

The runtime uses Python's stdlib logging throughout.
All loggers live under the ``soul_protocol.runtime`` namespace,
so you can control verbosity with a single line.

Quick start (development):

    import logging
    logging.basicConfig(level=logging.DEBUG)

Quick start (production, INFO only):

    import logging
    logging.basicConfig(level=logging.INFO)
"""

import json
import logging
import logging.config


# ---------------------------------------------------------------------------
# 1. Simple development config — see everything
# ---------------------------------------------------------------------------

def configure_dev_logging() -> None:
    """Human-readable console output with DEBUG level for the soul runtime."""
    logging.basicConfig(
        level=logging.WARNING,  # third-party libs stay quiet
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    # Turn on DEBUG for soul-protocol runtime specifically
    logging.getLogger("soul_protocol.runtime").setLevel(logging.DEBUG)


# ---------------------------------------------------------------------------
# 2. Production config — INFO level, JSON format
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def configure_production_logging() -> None:
    """JSON-formatted output at INFO level — suitable for log aggregation."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.WARNING)

    # Soul runtime at INFO — lifecycle events, saves, exports
    logging.getLogger("soul_protocol.runtime").setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# 3. Dict-based config (for YAML/JSON config files)
# ---------------------------------------------------------------------------

LOGGING_DICT_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        },
        "json": {
            "()": f"{__name__}.JSONFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "DEBUG",
        },
    },
    "loggers": {
        "soul_protocol.runtime": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": False,
        },
    },
    "root": {
        "level": "WARNING",
        "handlers": ["console"],
    },
}


def configure_from_dict() -> None:
    """Apply the dict-based config."""
    logging.config.dictConfig(LOGGING_DICT_CONFIG)


# ---------------------------------------------------------------------------
# Usage example
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio

    configure_dev_logging()

    async def demo():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.birth(
            name="Echo",
            personality="A curious explorer.",
            values=["learning", "creativity"],
        )
        print(f"Soul created: {soul.name} ({soul.did})")

    asyncio.run(demo())
