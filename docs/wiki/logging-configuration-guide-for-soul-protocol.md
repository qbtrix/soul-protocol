---
{
  "title": "Logging Configuration Guide for Soul Protocol",
  "summary": "Provides three ready-to-use logging configurations for the soul-protocol runtime — a human-readable development setup, a structured JSON production setup, and a dict-based config compatible with YAML/JSON config files. All configurations target the `soul_protocol.runtime` logger namespace to give operators precise control over verbosity without silencing third-party libraries.",
  "concepts": [
    "Python logging",
    "stdlib logging",
    "JSONFormatter",
    "soul_protocol.runtime",
    "log aggregation",
    "dictConfig",
    "DEBUG level",
    "INFO level",
    "structured logging",
    "production logging",
    "development logging",
    "namespace logging",
    "log handler"
  ],
  "categories": [
    "configuration",
    "observability",
    "examples",
    "logging"
  ],
  "source_docs": [
    "992c55e295abbf7d"
  ],
  "backlinks": null,
  "word_count": 542,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`logging_config.py` solves a practical integration problem: the soul-protocol runtime emits structured diagnostic events through Python's stdlib `logging`, but callers need different verbosity and formatting depending on their environment. A developer tracing a memory extraction bug wants colored, timestamped DEBUG lines in a terminal. A production deployment needs machine-parseable JSON that flows into Datadog, Splunk, or CloudWatch without format surprises.

This file is a reference, not a required import — consumers copy the pattern that fits their stack.

## Logger Namespace Design

All soul-protocol runtime loggers live under `soul_protocol.runtime.*`. This deliberate namespacing means operators can target exactly the runtime without enabling DEBUG on every third-party library the process imports:

```python
logging.getLogger("soul_protocol.runtime").setLevel(logging.DEBUG)
```

The root logger stays at WARNING, so libraries like `httpx`, `anthropic`, or `openai` remain quiet. This avoids the common failure mode where enabling DEBUG floods the console with irrelevant HTTP traces.

## Development Config (`configure_dev_logging`)

Sets the root logger to WARNING and raises `soul_protocol.runtime` to DEBUG. Output format includes timestamp, level, logger name, and message — enough to trace the observe → extraction → storage → recall pipeline without parsing JSON.

```python
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("soul_protocol.runtime").setLevel(logging.DEBUG)
```

The two-level setup (WARNING for root, DEBUG for runtime) prevents a common rookie mistake: calling `basicConfig(level=logging.DEBUG)` globally and then being overwhelmed by thousands of lines from httpx connection pooling.

## Production Config and JSONFormatter

`configure_production_logging` attaches a custom `JSONFormatter` that serializes every log record as a single-line JSON object:

```python
{
  "ts": "12:34:56,789",
  "level": "INFO",
  "logger": "soul_protocol.runtime.soul",
  "msg": "Soul saved: aria.soul (47 memories)"
}
```

Single-line JSON is critical for log aggregators — multi-line output breaks line-based parsers and corrupts structured log entries. The `JSONFormatter.format()` method also captures `exc_info` as a formatted exception string under the `exception` key, so stack traces don't get lost when errors bubble up through async handlers.

The runtime logger is set to INFO rather than DEBUG in production: lifecycle events (birth, save, export, recall) are emitted at INFO, while internal pipeline steps (entity extraction, significance scoring) are DEBUG-only.

## Dict Config (`configure_from_dict` + `LOGGING_DICT_CONFIG`)

The third pattern targets deployments that configure logging via a YAML or JSON file loaded at startup. `logging.config.dictConfig()` accepts the same structure as the dict literal:

```python
LOGGING_DICT_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    ...
}
```

The `disable_existing_loggers: False` flag is a defensive choice. When `True` (Python's default), calling `dictConfig` after any logger has been created silently disables those existing loggers — a confusing failure mode where log output vanishes after a config reload. Setting it to `False` preserves any loggers already instantiated before the config was applied.

## Data Flow

```
Soul runtime emits → soul_protocol.runtime.* loggers
  ↓
Handler (console StreamHandler)
  ↓
Formatter (standard text OR JSONFormatter)
  ↓
stdout / log aggregator
```

## Known Gaps

- File handler support is absent — production deployments that write to rotating log files would need to add their own `RotatingFileHandler` to the dict config.
- The JSONFormatter does not include a `trace_id` or `correlation_id` field, making it harder to trace a single user request across async soul operations in distributed setups.
- No async-safe log handler is included; very high throughput scenarios could see log calls block the event loop if the StreamHandler's underlying write is slow.