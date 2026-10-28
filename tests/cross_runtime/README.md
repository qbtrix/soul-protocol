# Cross-Runtime Test Suite

This directory contains round-trip tests that verify `.soul` files work
across multiple AI agent runtimes.

## Runtimes Tested

| Runtime    | Tests | What it tests                          | Memory types         |
|------------|-------|----------------------------------------|----------------------|
| PocketPaw  | 6     | Soul import/export round-trip          | semantic + episodic  |
| LangChain  | 3     | Memory format + identity compatibility | semantic             |
| CrewAI     | 3     | Memory format + identity compatibility | semantic             |

## Setup

### Prerequisites

The cross-runtime tests are **optional** — they require external packages
that are not part of soul-protocol's core dependencies.

```bash
# Install soul-protocol with dev extras (if not already done)
pip install -e ".[dev]"

# Install runtime-specific packages (only the ones you want to test)
pip install langchain langchain-core         # For LangChain tests
pip install crewai                            # For CrewAI tests
# PocketPaw tests use subprocess — no extra install needed
```

### Running

```bash
# Run ALL cross-runtime tests (skips missing runtimes automatically)
pytest tests/cross_runtime/ -v

# Run only a specific runtime
pytest tests/cross_runtime/test_langchain.py -v
pytest tests/cross_runtime/test_crewai.py -v
pytest tests/cross_runtime/test_pocketpaw.py -v
```

### CI Behavior

All tests are marked with `@pytest.mark.cross_runtime`. CI skips them
unless the marker is explicitly selected. This ensures contributors
without all three runtimes installed do not see spurious failures.

## Architecture

```
tests/cross_runtime/
├── README.md          ← This file
├── conftest.py        ← Shared fixtures (populated soul, tmp paths)
├── test_pocketpaw.py  ← PocketPaw subprocess round-trip
├── test_langchain.py  ← LangChain memory adapter round-trip
└── test_crewai.py     ← CrewAI memory adapter round-trip
```

## What "Round-Trip" Means

1. **Create** a soul with known memories using Soul Protocol
2. **Export** it to a `.soul` file
3. **Import** it into the target runtime
4. **Read back** the memories
5. **Assert** the memories survived the hop

The bar is **data survival** — not behavioral equivalence across runtimes.
