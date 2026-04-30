# runtime/diff.py — Soul-level structured diff (#191).
# Created: feat/soul-diff-cli — Compare two Soul instances and emit a structured
#   `SoulDiff` covering identity, OCEAN, state, core memory, memories per
#   layer/domain, bond, skills, trust chain, self-model, and evolution. Format-
#   agnostic — text/json/markdown rendering lives next door in cli/diff.py.
#
# Compares two Soul instances loaded via Soul.awaken() — works for any
# combination of zip and dir format. Schema-version mismatch raises a clean
# error before any field-level work begins.
#
# Memory diff strategy: by id. Added = in right not left, removed = in left not
# right, modified = same id different fields. By default, superseded memories
# are filtered out of the "removed" diff (they still live in the file). With
# include_superseded=True, the supersession chain is shown explicitly.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from soul_protocol.runtime.soul import Soul


# ---------------------------------------------------------------------------
# Diff models
# ---------------------------------------------------------------------------


class FieldChange(BaseModel):
    """A single before/after pair for a scalar field."""

    field: str
    before: Any = None
    after: Any = None


class IdentityDiff(BaseModel):
    """Changes to the soul's stable identity fields."""

    changes: list[FieldChange] = Field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.changes


class OceanDiff(BaseModel):
    """OCEAN trait deltas + communication / biorhythm field changes."""

    trait_deltas: dict[str, float] = Field(default_factory=dict)
    """Map of trait name -> (after - before). Only present when the delta
    rounds to a non-zero amount at 3 decimals."""

    communication_changes: list[FieldChange] = Field(default_factory=list)
    biorhythm_changes: list[FieldChange] = Field(default_factory=list)

    @property
    def empty(self) -> bool:
        return (
            not self.trait_deltas and not self.communication_changes and not self.biorhythm_changes
        )


class StateDiff(BaseModel):
    """Soul state changes — mood, energy, social_battery, focus."""

    changes: list[FieldChange] = Field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.changes


class CoreMemoryDiff(BaseModel):
    """Core memory (persona + human) changes."""

    persona_changed: bool = False
    human_changed: bool = False
    persona_before: str = ""
    persona_after: str = ""
    human_before: str = ""
    human_after: str = ""

    @property
    def empty(self) -> bool:
        return not self.persona_changed and not self.human_changed


class MemoryEntryAbstract(BaseModel):
    """Compact view of a memory entry for diff lists."""

    id: str
    layer: str
    domain: str = "default"
    type: str = ""
    importance: int = 0
    content: str = ""
    truncated_content: str = ""
    superseded_by: str | None = None


class MemoryEntryChange(BaseModel):
    """A modified memory — same id, different content/importance/etc."""

    id: str
    layer: str
    domain: str = "default"
    field_changes: list[FieldChange] = Field(default_factory=list)
    content_before: str = ""
    content_after: str = ""


class LayerCounts(BaseModel):
    """Per-domain count snapshot inside a layer."""

    layer: str
    before: dict[str, int] = Field(default_factory=dict)
    after: dict[str, int] = Field(default_factory=dict)


class MemoryDiff(BaseModel):
    """Memory layer + domain counts plus per-entry changes."""

    layer_counts: list[LayerCounts] = Field(default_factory=list)
    added: list[MemoryEntryAbstract] = Field(default_factory=list)
    removed: list[MemoryEntryAbstract] = Field(default_factory=list)
    modified: list[MemoryEntryChange] = Field(default_factory=list)
    superseded: list[MemoryEntryAbstract] = Field(default_factory=list)
    """Memories that are present in both files but moved into a superseded
    state on the right. Only populated when include_superseded=True."""

    @property
    def empty(self) -> bool:
        return (
            not self.added
            and not self.removed
            and not self.modified
            and not self.superseded
            and all(c.before == c.after for c in self.layer_counts)
        )


class BondChange(BaseModel):
    """Bond strength change for a single user (or default)."""

    user_id: str | None = None  # None = default bond
    bonded_to: str = ""
    strength_before: float = 0.0
    strength_after: float = 0.0
    interaction_count_before: int = 0
    interaction_count_after: int = 0


class BondDiff(BaseModel):
    """Per-user bond changes."""

    changes: list[BondChange] = Field(default_factory=list)
    added_users: list[str] = Field(default_factory=list)
    removed_users: list[str] = Field(default_factory=list)

    @property
    def empty(self) -> bool:
        return (
            not self.added_users
            and not self.removed_users
            and all(
                c.strength_before == c.strength_after
                and c.interaction_count_before == c.interaction_count_after
                for c in self.changes
            )
        )


class SkillChange(BaseModel):
    """A skill that gained or lost XP / level between snapshots."""

    skill_id: str
    name: str
    level_before: int = 0
    level_after: int = 0
    xp_before: int = 0
    xp_after: int = 0


class SkillDiff(BaseModel):
    """Skill registry changes."""

    added: list[SkillChange] = Field(default_factory=list)
    removed: list[SkillChange] = Field(default_factory=list)
    changed: list[SkillChange] = Field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.added and not self.removed and not self.changed


class TrustChainDiff(BaseModel):
    """Trust chain delta — count + new entries."""

    length_before: int = 0
    length_after: int = 0
    new_actions: list[str] = Field(default_factory=list)
    """Distinct action names that appeared in entries past the left's head."""

    new_entries_sample: list[dict] = Field(default_factory=list)
    """Up to 5 newest entries past the left's head, summarised as
    {seq, timestamp, action, actor_did}."""

    @property
    def empty(self) -> bool:
        return self.length_before == self.length_after


class SelfModelChange(BaseModel):
    domain: str
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    evidence_before: int = 0
    evidence_after: int = 0


class SelfModelDiff(BaseModel):
    added_domains: list[str] = Field(default_factory=list)
    removed_domains: list[str] = Field(default_factory=list)
    changed: list[SelfModelChange] = Field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.added_domains and not self.removed_domains and not self.changed


class EvolutionDiff(BaseModel):
    """Mutations applied between snapshots."""

    new_mutations: list[dict] = Field(default_factory=list)
    """List of mutation dicts from the right's evolution.history that aren't
    in the left's evolution.history (matched by mutation id)."""

    @property
    def empty(self) -> bool:
        return not self.new_mutations


class SoulDiff(BaseModel):
    """Top-level structured diff between two souls.

    All sections are populated even when empty — the consumer reads
    ``section.empty`` to decide whether to render. Schema mismatches are
    raised before construction; once a SoulDiff is built, the two souls
    are guaranteed to share a schema version.
    """

    left_name: str = ""
    right_name: str = ""
    left_did: str = ""
    right_did: str = ""

    identity: IdentityDiff = Field(default_factory=IdentityDiff)
    ocean: OceanDiff = Field(default_factory=OceanDiff)
    state: StateDiff = Field(default_factory=StateDiff)
    core_memory: CoreMemoryDiff = Field(default_factory=CoreMemoryDiff)
    memory: MemoryDiff = Field(default_factory=MemoryDiff)
    bond: BondDiff = Field(default_factory=BondDiff)
    skills: SkillDiff = Field(default_factory=SkillDiff)
    trust_chain: TrustChainDiff = Field(default_factory=TrustChainDiff)
    self_model: SelfModelDiff = Field(default_factory=SelfModelDiff)
    evolution: EvolutionDiff = Field(default_factory=EvolutionDiff)

    def summary(self) -> dict[str, int]:
        """Return per-section change counts."""
        return {
            "identity": len(self.identity.changes),
            "ocean": len(self.ocean.trait_deltas)
            + len(self.ocean.communication_changes)
            + len(self.ocean.biorhythm_changes),
            "state": len(self.state.changes),
            "core_memory": int(self.core_memory.persona_changed)
            + int(self.core_memory.human_changed),
            "memories_added": len(self.memory.added),
            "memories_removed": len(self.memory.removed),
            "memories_modified": len(self.memory.modified),
            "memories_superseded": len(self.memory.superseded),
            "bonds": len(self.bond.changes)
            + len(self.bond.added_users)
            + len(self.bond.removed_users),
            "skills_added": len(self.skills.added),
            "skills_removed": len(self.skills.removed),
            "skills_changed": len(self.skills.changed),
            "trust_chain_delta": self.trust_chain.length_after - self.trust_chain.length_before,
            "self_model": len(self.self_model.added_domains)
            + len(self.self_model.removed_domains)
            + len(self.self_model.changed),
            "evolution": len(self.evolution.new_mutations),
        }

    @property
    def empty(self) -> bool:
        """True when no sections detected any change."""
        return (
            self.identity.empty
            and self.ocean.empty
            and self.state.empty
            and self.core_memory.empty
            and self.memory.empty
            and self.bond.empty
            and self.skills.empty
            and self.trust_chain.empty
            and self.self_model.empty
            and self.evolution.empty
        )


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SchemaMismatchError(ValueError):
    """Raised when the two souls have incompatible schema versions."""


# ---------------------------------------------------------------------------
# Diff implementation
# ---------------------------------------------------------------------------


_TRUNCATE_LEN = 80
"""Content truncation length for added/removed entry abstracts."""

_NEW_ENTRIES_SAMPLE_LIMIT = 5
"""Cap on trust-chain new-entry samples in the diff output."""


def _truncate(text: str, length: int = _TRUNCATE_LEN) -> str:
    """Truncate ``text`` to ``length`` chars with an ellipsis when over."""
    if len(text) <= length:
        return text
    return text[: max(0, length - 3)] + "..."


def _abstract_entry(entry: Any) -> MemoryEntryAbstract:
    """Render a MemoryEntry into a compact MemoryEntryAbstract."""
    return MemoryEntryAbstract(
        id=getattr(entry, "id", "") or "",
        layer=getattr(entry, "layer", "") or getattr(entry.type, "value", str(entry.type)),
        domain=getattr(entry, "domain", "default") or "default",
        type=getattr(entry.type, "value", str(entry.type)) if hasattr(entry, "type") else "",
        importance=getattr(entry, "importance", 0),
        content=getattr(entry, "content", ""),
        truncated_content=_truncate(getattr(entry, "content", "")),
        superseded_by=getattr(entry, "superseded_by", None),
    )


def _all_memories(soul: Soul, *, include_superseded: bool = True) -> list[Any]:
    """Return every MemoryEntry across every layer, including custom layers.

    Episodic / semantic / procedural / social hit their dedicated stores.
    Custom layers (set via Soul.remember(layer=...)) live in
    ``MemoryManager._custom_layers``.

    The semantic store filters superseded facts by default; we always
    request both for diffing — the diff caller decides whether to surface
    them downstream. Defaults to ``include_superseded=True`` so the diff
    sees the full state, and filtering happens at the section level.
    """
    mem = soul._memory
    entries: list[Any] = []
    entries.extend(mem._episodic.entries())
    # Pass include_superseded so we see entries past their supersession line.
    try:
        entries.extend(mem._semantic.facts(include_superseded=include_superseded))
    except TypeError:
        # Older runtimes: facts() takes no flag.
        entries.extend(mem._semantic.facts())
    entries.extend(mem._procedural.entries())
    if hasattr(mem, "_social"):
        entries.extend(mem._social.entries())
    if hasattr(mem, "_custom_layers"):
        for store in mem._custom_layers.values():
            entries.extend(store.values())
    return entries


def _index_memories_by_id(soul: Soul) -> dict[str, Any]:
    """Index every memory entry by id for fast lookups during diff."""
    return {entry.id: entry for entry in _all_memories(soul) if getattr(entry, "id", None)}


def _layer_counts(soul: Soul, *, include_superseded: bool = False) -> dict[str, dict[str, int]]:
    """Per-layer per-domain entry counts.

    Returns ``{layer_name: {domain: count}}`` so the diff can show "memories
    in semantic.finance went from 4 to 6" without flattening. Counts
    exclude superseded entries by default — that matches what the soul
    actually surfaces to recall, so the count delta tells reviewers what
    they'd see in practice.
    """
    counts: dict[str, dict[str, int]] = {}
    for entry in _all_memories(soul, include_superseded=include_superseded):
        if not include_superseded and getattr(entry, "superseded_by", None):
            continue
        layer = getattr(entry, "layer", "") or "unknown"
        domain = getattr(entry, "domain", "default") or "default"
        counts.setdefault(layer, {}).setdefault(domain, 0)
        counts[layer][domain] += 1
    return counts


def _soul_version(soul: Soul) -> str:
    """Resolve the soul's schema version string.

    Soul.serialize() currently hardcodes ``version="1.0.0"`` for every
    runtime, but the underlying ``_config.version`` field is the per-instance
    source of truth — older `.soul` files carry the version they were
    created with even if the runtime has moved on. Prefer ``_config.version``
    when set, falling back to the serialized version. This keeps the diff
    correct when an old soul (e.g. v0.3.x) is compared against a freshly
    awakened one in a newer runtime.
    """
    config_version = getattr(getattr(soul, "_config", None), "version", None)
    if config_version:
        return str(config_version)
    return str(soul.serialize().version)


def _check_schema_compat(left: Soul, right: Soul) -> None:
    """Raise SchemaMismatchError when the two souls have different versions."""
    left_version = _soul_version(left)
    right_version = _soul_version(right)
    if left_version != right_version:
        raise SchemaMismatchError(
            f"Schema version mismatch: left={left_version!r}, right={right_version!r}. "
            f"Soul diff requires both files to share a schema version. "
            f"Migrate the older soul with `soul migrate <path>` first."
        )


# ---------------------------------------------------------------------------
# Section diffs
# ---------------------------------------------------------------------------


def _diff_identity(left: Soul, right: Soul) -> IdentityDiff:
    """Compare identity fields that callers care about for review.

    DID, name, archetype, born, bonded_to, role, core_values are all stable
    enough to be diff-worthy. Volatile fields (incarnation counter, previous
    lives) are skipped — they're more noise than signal in a typical diff.
    """
    diff = IdentityDiff()
    li, ri = left.identity, right.identity
    fields = [
        ("did", li.did, ri.did),
        ("name", li.name, ri.name),
        ("archetype", li.archetype, ri.archetype),
        (
            "born",
            li.born.isoformat() if li.born else None,
            ri.born.isoformat() if ri.born else None,
        ),
        ("bonded_to", li.bonded_to, ri.bonded_to),
        ("role", li.role, ri.role),
        ("core_values", list(li.core_values), list(ri.core_values)),
    ]
    for name, before, after in fields:
        if before != after:
            diff.changes.append(FieldChange(field=name, before=before, after=after))
    return diff


def _diff_ocean(left: Soul, right: Soul) -> OceanDiff:
    """Compare DNA — OCEAN traits, communication style, biorhythms."""
    diff = OceanDiff()
    lp, rp = left.dna.personality, right.dna.personality
    for trait in ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"):
        delta = round(getattr(rp, trait) - getattr(lp, trait), 3)
        if delta != 0.0:
            diff.trait_deltas[trait] = delta

    lc, rc = left.dna.communication, right.dna.communication
    for field in ("warmth", "verbosity", "humor_style", "emoji_usage"):
        before = getattr(lc, field, None)
        after = getattr(rc, field, None)
        if before != after:
            diff.communication_changes.append(FieldChange(field=field, before=before, after=after))

    lb, rb = left.dna.biorhythms, right.dna.biorhythms
    for field in ("chronotype", "social_battery", "energy_regen_rate"):
        before = getattr(lb, field, None)
        after = getattr(rb, field, None)
        if before != after:
            diff.biorhythm_changes.append(FieldChange(field=field, before=before, after=after))
    return diff


def _diff_state(left: Soul, right: Soul) -> StateDiff:
    """Compare current state — mood, energy, social_battery, focus."""
    diff = StateDiff()
    ls, rs = left.state, right.state
    fields = [
        ("mood", getattr(ls.mood, "value", str(ls.mood)), getattr(rs.mood, "value", str(rs.mood))),
        ("energy", round(ls.energy, 2), round(rs.energy, 2)),
        ("social_battery", round(ls.social_battery, 2), round(rs.social_battery, 2)),
        ("focus", ls.focus, rs.focus),
    ]
    for name, before, after in fields:
        if before != after:
            diff.changes.append(FieldChange(field=name, before=before, after=after))
    return diff


def _diff_core_memory(left: Soul, right: Soul) -> CoreMemoryDiff:
    """Compare core memory persona + human profile blocks."""
    lc = left.get_core_memory()
    rc = right.get_core_memory()
    return CoreMemoryDiff(
        persona_changed=lc.persona != rc.persona,
        human_changed=lc.human != rc.human,
        persona_before=lc.persona,
        persona_after=rc.persona,
        human_before=lc.human,
        human_after=rc.human,
    )


def _diff_memory(left: Soul, right: Soul, *, include_superseded: bool) -> MemoryDiff:
    """Compare memories by id across all layers.

    A memory present in both souls but with different content / importance
    / superseded_by is reported as ``modified``. A memory only on the right
    is ``added``; only on the left is ``removed`` (filtered to non-
    superseded by default — the supersession chain stays in the file but
    typically isn't what reviewers want to see).
    """
    diff = MemoryDiff()

    left_idx = _index_memories_by_id(left)
    right_idx = _index_memories_by_id(right)

    left_counts = _layer_counts(left)
    right_counts = _layer_counts(right)
    all_layers = sorted(set(left_counts.keys()) | set(right_counts.keys()))
    for layer in all_layers:
        diff.layer_counts.append(
            LayerCounts(
                layer=layer,
                before=dict(left_counts.get(layer, {})),
                after=dict(right_counts.get(layer, {})),
            )
        )

    # Added — right has it, left doesn't.
    for entry_id, entry in right_idx.items():
        if entry_id not in left_idx:
            diff.added.append(_abstract_entry(entry))

    # Removed — left has it, right doesn't.
    # By default, memories that were superseded on the way out are filtered
    # since they typically still live in the file; with include_superseded
    # they're shown explicitly so the supersession chain is visible.
    for entry_id, entry in left_idx.items():
        if entry_id not in right_idx:
            superseded = getattr(entry, "superseded_by", None)
            if superseded and not include_superseded:
                continue
            diff.removed.append(_abstract_entry(entry))

    # Modified — same id, different content or metadata.
    # Also tracks the case where a memory got marked superseded on the right
    # — surfaces the supersession explicitly in the modified section.
    for entry_id, left_entry in left_idx.items():
        if entry_id not in right_idx:
            continue
        right_entry = right_idx[entry_id]
        field_changes: list[FieldChange] = []
        if getattr(left_entry, "importance", None) != getattr(right_entry, "importance", None):
            field_changes.append(
                FieldChange(
                    field="importance",
                    before=getattr(left_entry, "importance", None),
                    after=getattr(right_entry, "importance", None),
                )
            )
        if getattr(left_entry, "content", None) != getattr(right_entry, "content", None):
            field_changes.append(
                FieldChange(
                    field="content",
                    before=getattr(left_entry, "content", ""),
                    after=getattr(right_entry, "content", ""),
                )
            )
        left_super = getattr(left_entry, "superseded_by", None)
        right_super = getattr(right_entry, "superseded_by", None)
        if left_super != right_super:
            # By default the supersession chain is hidden — superseded
            # entries still live in the file, so reviewers typically don't
            # want them flagged as a "modification". With
            # include_superseded=True we surface both the field change and
            # a dedicated superseded list for the chain visualization.
            if include_superseded:
                field_changes.append(
                    FieldChange(field="superseded_by", before=left_super, after=right_super)
                )
                if right_super and not left_super:
                    diff.superseded.append(_abstract_entry(right_entry))

        if field_changes:
            diff.modified.append(
                MemoryEntryChange(
                    id=entry_id,
                    layer=getattr(right_entry, "layer", "")
                    or getattr(right_entry.type, "value", str(right_entry.type)),
                    domain=getattr(right_entry, "domain", "default") or "default",
                    field_changes=field_changes,
                    content_before=getattr(left_entry, "content", ""),
                    content_after=getattr(right_entry, "content", ""),
                )
            )

    return diff


def _diff_bonds(left: Soul, right: Soul) -> BondDiff:
    """Compare bond strength and per-user bonds."""
    diff = BondDiff()
    lb = left.bond
    rb = right.bond

    # Default bond
    if (
        lb.bond_strength != rb.bond_strength
        or lb.interaction_count != rb.interaction_count
        or lb.bonded_to != rb.bonded_to
    ):
        diff.changes.append(
            BondChange(
                user_id=None,
                bonded_to=rb.bonded_to or lb.bonded_to or "",
                strength_before=lb.bond_strength,
                strength_after=rb.bond_strength,
                interaction_count_before=lb.interaction_count,
                interaction_count_after=rb.interaction_count,
            )
        )

    # Per-user bonds
    left_users = set(lb.users())
    right_users = set(rb.users())
    diff.added_users = sorted(right_users - left_users)
    diff.removed_users = sorted(left_users - right_users)

    for uid in sorted(left_users & right_users):
        lpu = lb.for_user(uid)
        rpu = rb.for_user(uid)
        if lpu.bond_strength != rpu.bond_strength or lpu.interaction_count != rpu.interaction_count:
            diff.changes.append(
                BondChange(
                    user_id=uid,
                    bonded_to=uid,
                    strength_before=lpu.bond_strength,
                    strength_after=rpu.bond_strength,
                    interaction_count_before=lpu.interaction_count,
                    interaction_count_after=rpu.interaction_count,
                )
            )

    return diff


def _diff_skills(left: Soul, right: Soul) -> SkillDiff:
    """Compare skill registries — added / removed / level + xp deltas."""
    diff = SkillDiff()
    left_skills = {s.id: s for s in left.skills.skills}
    right_skills = {s.id: s for s in right.skills.skills}

    for sid, skill in right_skills.items():
        if sid not in left_skills:
            diff.added.append(
                SkillChange(
                    skill_id=sid,
                    name=skill.name,
                    level_after=skill.level,
                    xp_after=skill.xp,
                )
            )

    for sid, skill in left_skills.items():
        if sid not in right_skills:
            diff.removed.append(
                SkillChange(
                    skill_id=sid,
                    name=skill.name,
                    level_before=skill.level,
                    xp_before=skill.xp,
                )
            )

    for sid in set(left_skills) & set(right_skills):
        left_skill = left_skills[sid]
        right_skill = right_skills[sid]
        if left_skill.level != right_skill.level or left_skill.xp != right_skill.xp:
            diff.changed.append(
                SkillChange(
                    skill_id=sid,
                    name=right_skill.name,
                    level_before=left_skill.level,
                    level_after=right_skill.level,
                    xp_before=left_skill.xp,
                    xp_after=right_skill.xp,
                )
            )

    return diff


def _diff_trust_chain(left: Soul, right: Soul) -> TrustChainDiff:
    """Compare trust chains by length and new entries past the left's head."""
    diff = TrustChainDiff()
    le = left.trust_chain.entries
    re = right.trust_chain.entries
    diff.length_before = len(le)
    diff.length_after = len(re)
    if len(re) <= len(le):
        return diff

    new_entries = re[len(le) :]
    actions: list[str] = []
    for entry in new_entries:
        if entry.action not in actions:
            actions.append(entry.action)
    diff.new_actions = actions
    diff.new_entries_sample = [
        {
            "seq": entry.seq,
            "timestamp": entry.timestamp.isoformat(),
            "action": entry.action,
            "actor_did": entry.actor_did,
        }
        for entry in new_entries[:_NEW_ENTRIES_SAMPLE_LIMIT]
    ]
    return diff


def _diff_self_model(left: Soul, right: Soul) -> SelfModelDiff:
    """Compare self-model domain confidence shifts."""
    diff = SelfModelDiff()
    li = left.self_model.self_images if hasattr(left.self_model, "self_images") else {}
    ri = right.self_model.self_images if hasattr(right.self_model, "self_images") else {}

    diff.added_domains = sorted(set(ri) - set(li))
    diff.removed_domains = sorted(set(li) - set(ri))
    for domain in sorted(set(li) & set(ri)):
        l_img = li[domain]
        r_img = ri[domain]
        if l_img.confidence != r_img.confidence or l_img.evidence_count != r_img.evidence_count:
            diff.changed.append(
                SelfModelChange(
                    domain=domain,
                    confidence_before=l_img.confidence,
                    confidence_after=r_img.confidence,
                    evidence_before=l_img.evidence_count,
                    evidence_after=r_img.evidence_count,
                )
            )
    return diff


def _diff_evolution(left: Soul, right: Soul) -> EvolutionDiff:
    """Compare evolution history — mutations applied since left."""
    diff = EvolutionDiff()
    left_history = left.evolution_history if hasattr(left, "evolution_history") else []
    right_history = right.evolution_history if hasattr(right, "evolution_history") else []

    left_ids = {m.id for m in left_history}
    diff.new_mutations = [m.model_dump(mode="json") for m in right_history if m.id not in left_ids]
    return diff


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def diff_souls(
    left: Soul,
    right: Soul,
    *,
    include_superseded: bool = False,
) -> SoulDiff:
    """Compare two souls and return a structured ``SoulDiff``.

    Args:
        left: The "before" soul.
        right: The "after" soul.
        include_superseded: When True, include memories whose
            ``superseded_by`` field changed in the modified section, plus
            populate ``memory.superseded`` with entries that just got
            marked superseded. Default False — superseded memories are
            filtered from the removed list since they still live in the
            file.

    Raises:
        SchemaMismatchError: When ``left.serialize().version`` differs from
            ``right.serialize().version``. Run ``soul migrate <path>`` on
            the older soul first.
    """
    _check_schema_compat(left, right)

    return SoulDiff(
        left_name=left.name,
        right_name=right.name,
        left_did=left.did,
        right_did=right.did,
        identity=_diff_identity(left, right),
        ocean=_diff_ocean(left, right),
        state=_diff_state(left, right),
        core_memory=_diff_core_memory(left, right),
        memory=_diff_memory(left, right, include_superseded=include_superseded),
        bond=_diff_bonds(left, right),
        skills=_diff_skills(left, right),
        trust_chain=_diff_trust_chain(left, right),
        self_model=_diff_self_model(left, right),
        evolution=_diff_evolution(left, right),
    )


__all__ = [
    "SchemaMismatchError",
    "SoulDiff",
    "IdentityDiff",
    "OceanDiff",
    "StateDiff",
    "CoreMemoryDiff",
    "MemoryDiff",
    "BondDiff",
    "SkillDiff",
    "TrustChainDiff",
    "SelfModelDiff",
    "EvolutionDiff",
    "FieldChange",
    "MemoryEntryAbstract",
    "MemoryEntryChange",
    "LayerCounts",
    "BondChange",
    "SkillChange",
    "SelfModelChange",
    "diff_souls",
]
