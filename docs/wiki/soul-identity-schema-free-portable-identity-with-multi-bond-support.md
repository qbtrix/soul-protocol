---
{
  "title": "Soul Identity — Schema-Free Portable Identity with Multi-Bond Support",
  "summary": "`Identity` is the portable identity primitive at the core of Soul Protocol. It carries a soul's name, creation timestamp, and an open `traits` dict that runtimes can populate with OCEAN scores, Myers-Briggs types, or any custom dimensions. The `feat/spec-multi-participant` update added `BondTarget` and a `bonds` list so a single soul can maintain relationships with multiple humans, agents, groups, and services.",
  "concepts": [
    "Identity",
    "BondTarget",
    "bonds",
    "bonded_to",
    "traits",
    "OCEAN",
    "soul identity",
    "multi-bond",
    "DID",
    "portable identity",
    "schema-free",
    "backward compatibility"
  ],
  "categories": [
    "identity",
    "spec layer",
    "soul format",
    "relationships"
  ],
  "source_docs": [
    "463b08b443a88116"
  ],
  "backlinks": null,
  "word_count": 455,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

A soul's identity needs to survive platform migrations. If the `Identity` model were tightly coupled to a specific personality framework (like OCEAN), migrating to a platform that doesn't support that framework would require schema translation. By keeping `traits` as an open `dict[str, Any]`, the protocol stays neutral — runtimes layer their own semantics on top.

This is a deliberate contrast to PocketPaw's runtime layer, which does have opinions about OCEAN. The spec layer refuses to codify those opinions so that any runtime — a Discord bot, a healthcare companion, a customer service agent — can use Soul Protocol without mapping to a personality model they don't need.

## `Identity` Model

```python
class Identity(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    created_at: datetime
    traits: dict[str, Any] = Field(default_factory=dict)
    bonded_to: str | None = None  # DEPRECATED
    bonds: list[BondTarget] = Field(default_factory=list)
```

### `id`
A 12-character hex string derived from a UUID. Short enough to embed in filenames and log lines, unique enough for practical use. Full UUID4 uniqueness is not needed because soul IDs are typically combined with a DID (Decentralized Identifier) at the platform layer.

### `traits`
Purposely schema-free. A PocketPaw runtime populates this with `{"openness": 0.8, "conscientiousness": 0.6, ...}`. A custom runtime might store `{"communication_style": "formal", "language": "en"}`. Neither is wrong. The protocol treats it as opaque.

### `bonded_to` (deprecated) vs `bonds`
The original design assumed a soul bonds to exactly one entity — typically the human who owns it. `bonded_to` stored that entity's DID as a string. The multi-participant update recognized that real companions bond to multiple people, groups, and other agents. `bonds` replaces `bonded_to` with a typed list:

```python
class BondTarget(BaseModel):
    id: str        # DID or identifier
    label: str     # Human-readable name
    bond_type: str # "human", "soul", "agent", "group", "service"
```

`bonded_to` is preserved for backward compatibility — older `.soul` files that set `bonded_to` still load correctly. New code should use `bonds`.

## Why Bond Targets Are Portable

Bond targets travel with the soul across platforms. When a soul migrates from one platform to another, the new runtime can inspect `bonds` to reconnect the soul to known entities (if they exist on the new platform) or display the relationship history. Without portability, a soul on Platform A would lose all its relationship context when imported to Platform B.

## Data Flow

```
Soul creation
  └─ Identity(name="Aria", traits={"openness": 0.8})
       └─ bonds.append(BondTarget(id="did:soul:user123", bond_type="human"))
            └─ pack_soul(identity, memory_store) -> .soul bytes
                 └─ EternalStorageProvider.archive() -> permanent storage
```

## Known Gaps

- `bonded_to` is documented as deprecated but no migration path or removal timeline is specified.
- The `traits` dict has no schema validation — a runtime storing malformed data (e.g., `{"openness": "high"}` instead of a float) will not be caught at the spec layer.