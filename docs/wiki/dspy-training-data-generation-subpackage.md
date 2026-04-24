---
{
  "title": "DSPy Training Data Generation Subpackage",
  "summary": "The `dspy_training/` subpackage provides training data generation for optimizing Soul Protocol's DSPy modules — the LLM-powered components used for memory extraction, significance scoring, and entity recognition. Created under the `feat/dspy-integration` branch, it is a nascent subpackage with the actual generation logic in sibling modules.",
  "concepts": [
    "DSPy",
    "training data generation",
    "LLM optimization",
    "memory extraction",
    "significance scoring",
    "entity recognition",
    "MIPRO",
    "BootstrapFewShot",
    "compiled prompts",
    "feat/dspy-integration",
    "pipeline optimization",
    "soul-protocol runtime"
  ],
  "categories": [
    "research",
    "DSPy",
    "ML-optimization",
    "soul-protocol"
  ],
  "source_docs": [
    "db9cd87104940786"
  ],
  "backlinks": null,
  "word_count": 432,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`research/dspy_training/__init__.py` is a package marker for the `dspy_training` subpackage nested inside `research/`. The file itself is minimal — a header comment identifying the package's purpose and origin branch — but it signals an important architectural direction: Soul Protocol's LLM-powered pipelines are being moved to DSPy for optimization.

## What DSPy Training Data Means in This Context

Soul Protocol uses LLMs in several internal pipeline steps:
- **Memory extraction**: given a conversation turn, which facts are worth storing?
- **Significance scoring**: how important is a given fact relative to the soul's values?
- **Entity recognition**: which named entities appear in the interaction?
- **Emotional inference**: what emotional state does the interaction reflect?

Currently, these modules are prompted with hand-crafted instructions. DSPy replaces hand-crafted prompts with *compiled* prompts — automatically optimized against a labeled dataset using algorithms like MIPRO or BootstrapFewShot.

The `dspy_training/` subpackage generates the labeled datasets required for this optimization. A dataset entry might be:
- **Input**: a conversation turn + soul's current values
- **Label**: the extracted facts, their importance scores, and identified entities

## Why This Lives in `research/`

The training data generator sits inside `research/` rather than the main SDK because it depends on the research simulation infrastructure — specifically, the 1,000 simulated agent runs provide a source of diverse, labeled interaction scenarios. Running the full experiment generates thousands of `(interaction, extraction_result)` pairs that can directly train the DSPy modules.

This creates a virtuous loop:
1. Run experiment with current Soul Protocol (produces labeled data)
2. Train DSPy modules on labeled data (improves extraction quality)
3. Re-run experiment with improved Soul Protocol (produces better labels)
4. Repeat

## Package Structure Inference

Based on the package comment, the actual modules inside `dspy_training/` likely include:
- A dataset builder that converts `ObserveResult` records into DSPy training examples
- A DSPy module definition for each pipeline step (memory extraction, significance, entities)
- A training runner that applies a DSPy optimizer (MIPRO, BootstrapFewShot, etc.)
- Evaluation metrics comparing optimized vs. baseline prompt quality

## Known Gaps

- This is an early-stage subpackage created on a feature branch (`feat/dspy-integration`). The `__init__.py` is empty, meaning no public API is yet defined — all actual content lives in files not captured in this snapshot.
- The connection between the research experiment's `ObserveResult` data and the DSPy training format is not documented — the data transformation pipeline (experiment output → DSPy example) is an implicit gap.
- No DSPy version pin or dependency declaration is visible here — DSPy has had significant API changes across versions, and version mismatches could silently produce wrong training runs.