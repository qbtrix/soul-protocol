# eval/schema.py — Pydantic schema for soul-aware eval YAML format.
# Created: 2026-04-29 (#160) — Defines EvalSpec and the discriminated Scoring
#   union (keyword | regex | semantic | judge | structural). Evals are written
#   in YAML; this module parses and validates them. The runner consumes the
#   resulting Pydantic models and drives Soul.observe/recall/respond.
#
# Design note: we keep the schema deliberately small. Anything the soul
# already exposes (Personality, Mood, MemoryType) is referenced directly so
# YAML authors can use the same names that show up in soul-protocol code.
# When we need a YAML-friendly subset (e.g. memory entries), we wrap with a
# *Seed model that maps cleanly to the runtime type at apply time.

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from soul_protocol.runtime.types import Mood


class SchemaValidationError(ValueError):
    """Raised when a YAML eval spec fails Pydantic validation.

    Wraps Pydantic's ``ValidationError`` so callers can catch a single
    eval-specific exception without depending on Pydantic internals.
    """

    def __init__(self, message: str, source: str | None = None) -> None:
        self.source = source
        super().__init__(message)


# ---------------------------------------------------------------------------
# Soul + state seed
# ---------------------------------------------------------------------------


class OceanSeed(BaseModel):
    """OCEAN trait values for the seeded soul. Each trait 0.0 - 1.0."""

    model_config = ConfigDict(extra="forbid")

    openness: float = Field(default=0.5, ge=0.0, le=1.0)
    conscientiousness: float = Field(default=0.5, ge=0.0, le=1.0)
    extraversion: float = Field(default=0.5, ge=0.0, le=1.0)
    agreeableness: float = Field(default=0.5, ge=0.0, le=1.0)
    neuroticism: float = Field(default=0.5, ge=0.0, le=1.0)


class SoulSeed(BaseModel):
    """How to birth the soul before running cases.

    Mirrors the inputs ``Soul.birth()`` already accepts. ``bonded_to`` is
    optional — pass a user_id string to seed a default bond. For multi-user
    setups, leave ``bonded_to`` unset and use the top-level ``bond_strength``
    map to wire per-user bonds.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = "EvalSoul"
    archetype: str = ""
    persona: str = ""
    values: list[str] = Field(default_factory=list)
    ocean: OceanSeed = Field(default_factory=OceanSeed)
    bonded_to: str | None = None


class StateSeed(BaseModel):
    """Initial mood / energy / focus for the soul before cases run.

    Each field is optional; missing fields keep ``Soul.birth`` defaults.
    Energy and social_battery are absolute targets (0-100), not deltas —
    the runner overrides whatever ``Soul.birth`` produced.
    """

    model_config = ConfigDict(extra="forbid")

    mood: Mood | None = None
    energy: float | None = Field(default=None, ge=0.0, le=100.0)
    social_battery: float | None = Field(default=None, ge=0.0, le=100.0)
    focus: str | None = None  # "low" | "medium" | "high" | "max" | "auto"


class MemorySeed(BaseModel):
    """A pre-seeded memory entry to install before any case runs.

    Maps to ``Soul.remember(...)`` plus the optional layer/domain/user_id
    namespacing introduced in v0.4.0. The ``layer`` field accepts either a
    built-in :class:`MemoryType` value (``"semantic"``, ``"episodic"``,
    etc.) or any custom string for user-defined layers.
    """

    model_config = ConfigDict(extra="forbid")

    content: str
    layer: str = "semantic"
    importance: int = Field(default=5, ge=1, le=10)
    domain: str = "default"
    user_id: str | None = None
    emotion: str | None = None
    entities: list[str] = Field(default_factory=list)


class BondSeed(BaseModel):
    """Per-user bond strengths to apply post-birth.

    Each entry is ``user_id -> strength`` (0-100). Entries here are
    written via :class:`BondRegistry.for_user` so they round-trip through
    ``Soul.observe(user_id=...)`` and ``Soul.recall(user_id=...)``.
    """

    model_config = ConfigDict(extra="forbid")

    strengths: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_strengths(self) -> BondSeed:
        for uid, strength in self.strengths.items():
            if not 0.0 <= strength <= 100.0:
                raise ValueError(f"bond_strength[{uid!r}]={strength} must be between 0 and 100")
        return self


# Top-level seed bundle (referenced from EvalSpec.seed)
class Seed(BaseModel):
    """Everything the runner needs to set up the soul before running cases."""

    model_config = ConfigDict(extra="forbid")

    soul: SoulSeed = Field(default_factory=SoulSeed)
    state: StateSeed = Field(default_factory=StateSeed)
    memories: list[MemorySeed] = Field(default_factory=list)
    bond_strength: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Scoring — discriminated union by `kind`
# ---------------------------------------------------------------------------


class _ScoringBase(BaseModel):
    """Shared fields for every scoring kind.

    ``threshold`` is the minimum normalized score (0-1) that counts as a
    pass. Default 0.5 — individual kinds may override (e.g. keyword
    scoring is binary so threshold is effectively 1.0).
    """

    model_config = ConfigDict(extra="forbid")

    threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class KeywordScoring(_ScoringBase):
    """Pass when the soul's output contains every required keyword.

    Case-insensitive substring match. ``mode="all"`` (default) requires
    every keyword; ``mode="any"`` passes when at least one matches.
    Default threshold 1.0 — keyword scoring is binary unless the caller
    overrides.
    """

    kind: Literal["keyword"] = "keyword"
    expected: list[str]
    mode: Literal["all", "any"] = "all"
    threshold: float = Field(default=1.0, ge=0.0, le=1.0)


class RegexScoring(_ScoringBase):
    """Pass when the output matches a Python regex.

    The pattern is compiled with ``re.MULTILINE | re.DOTALL`` so authors
    don't have to remember those flags. Score is 1.0 on match, 0.0
    otherwise; threshold defaults to 1.0.
    """

    kind: Literal["regex"] = "regex"
    pattern: str
    threshold: float = Field(default=1.0, ge=0.0, le=1.0)


class SemanticScoring(_ScoringBase):
    """Token-overlap similarity (Jaccard-with-containment) against expected text.

    Reuses :func:`soul_protocol.runtime.memory.dedup._jaccard_similarity`
    so we get the same scoring behaviour as the soul's memory dedup.
    Score is the similarity in [0, 1]; pass when >= ``threshold``
    (default 0.5).
    """

    kind: Literal["semantic"] = "semantic"
    expected: str


class JudgeScoring(_ScoringBase):
    """LLM-as-judge scoring against free-form criteria.

    Calls the configured :class:`CognitiveEngine` with a prompt that asks
    for a 0-1 score. When no engine is available the case is marked
    ``skipped`` instead of ``failed``. Default threshold 0.7.
    """

    kind: Literal["judge"] = "judge"
    criteria: str
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class StructuralScoring(_ScoringBase):
    """Programmatic checks on soul state / output without LLM input.

    ``expected`` accepts a small dict of supported keys:

    - ``output_contains_bonded_user`` (bool): true when at least one
      bonded user_id appears in the output text.
    - ``output_contains_user_id`` (str): the output must mention this
      specific user_id.
    - ``mood_after`` (str): the soul's mood after the case must equal
      this :class:`Mood` value.
    - ``min_energy_after`` / ``max_energy_after`` (float): bounds on
      ``soul.state.energy`` after the case runs.
    - ``recall_min_results`` (int): when the case used recall mode,
      number of returned memories must be >= this.
    - ``recall_expected_substring`` (str): the recall result list must
      contain at least one entry whose content includes this substring.

    Each present key contributes to the score; missing keys are skipped.
    Score is the fraction of present keys that passed; pass when score
    >= threshold (default 1.0 — every check must pass).
    """

    kind: Literal["structural"] = "structural"
    expected: dict[str, Any] = Field(default_factory=dict)
    threshold: float = Field(default=1.0, ge=0.0, le=1.0)


# Discriminated union — Pydantic resolves on the ``kind`` field
Scoring = KeywordScoring | RegexScoring | SemanticScoring | JudgeScoring | StructuralScoring


# ---------------------------------------------------------------------------
# Cases + top-level spec
# ---------------------------------------------------------------------------


class CaseInputs(BaseModel):
    """Input for a single case.

    Two modes:

    - ``mode="respond"`` (default) — runner builds a system prompt + context
      block from the soul, asks the engine for a reply to ``message``, and
      hands the reply to the scorer.
    - ``mode="recall"`` — runner calls ``Soul.recall(query=message, ...)``
      and hands the result list to the scorer (rendered as one entry per
      line for keyword/semantic/judge; full list for structural).

    ``observe`` (default false) — when true, the runner additionally calls
    ``Soul.observe()`` after generating the response, so subsequent cases
    in the same spec see the updated state. Defaults to false because evals
    should be deterministic and memory mutations between cases make that
    harder.
    """

    model_config = ConfigDict(extra="forbid")

    message: str
    user_id: str | None = None
    domain: str | None = None
    mode: Literal["respond", "recall"] = "respond"
    observe: bool = False
    # recall-mode specific knobs
    recall_limit: int = 5
    recall_layer: str | None = None


class EvalCase(BaseModel):
    """A single eval case inside a spec."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    inputs: CaseInputs
    scoring: Scoring = Field(discriminator="kind")


class EvalSpec(BaseModel):
    """Top-level YAML eval spec.

    A spec has one seeded soul and N cases run against that soul. Cases
    by default do not mutate state (see ``CaseInputs.observe``) so the
    seed remains the source of truth across the case list.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    seed: Seed = Field(default_factory=Seed)
    cases: list[EvalCase]


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def parse_eval_spec(data: dict[str, Any], *, source: str | None = None) -> EvalSpec:
    """Validate a raw dict against the EvalSpec schema.

    Args:
        data: Parsed YAML / JSON dict.
        source: Optional path string used in error messages.

    Returns:
        A validated :class:`EvalSpec`.

    Raises:
        SchemaValidationError: When validation fails.
    """
    try:
        return EvalSpec.model_validate(data)
    except ValidationError as e:  # re-wrap so callers get a clean exception
        raise SchemaValidationError(str(e), source=source) from e


def load_eval_spec(path: str | Path) -> EvalSpec:
    """Load and validate a YAML eval spec from disk.

    Args:
        path: Path to a ``.yaml`` / ``.yml`` file.

    Returns:
        A validated :class:`EvalSpec`.

    Raises:
        FileNotFoundError: When the file does not exist.
        SchemaValidationError: When validation fails.
    """
    import yaml

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Eval spec not found: {p}")
    text = p.read_text()
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise SchemaValidationError(
            f"Eval spec must be a YAML mapping, got {type(data).__name__}",
            source=str(p),
        )
    return parse_eval_spec(data, source=str(p))
