# tests/test_memory_layers/test_layer_strings.py — Open-string layer support.
# Created: 2026-04-29 (#41) — Verifies that the spec MemoryEntry treats
# layer as a free-form string, that the LAYER_* constants match expected
# values, and that runtime MemoryEntry derives layer from type for legacy
# callers while accepting any custom layer string.

from __future__ import annotations

from soul_protocol.runtime.types import MemoryEntry as RuntimeMemoryEntry
from soul_protocol.runtime.types import MemoryType
from soul_protocol.spec.memory import (
    DEFAULT_DOMAIN,
    LAYER_CORE,
    LAYER_EPISODIC,
    LAYER_PROCEDURAL,
    LAYER_SEMANTIC,
    LAYER_SOCIAL,
)
from soul_protocol.spec.memory import MemoryEntry as SpecMemoryEntry


class TestLayerConstants:
    def test_all_constants_have_expected_values(self):
        assert LAYER_CORE == "core"
        assert LAYER_EPISODIC == "episodic"
        assert LAYER_SEMANTIC == "semantic"
        assert LAYER_PROCEDURAL == "procedural"
        assert LAYER_SOCIAL == "social"
        assert DEFAULT_DOMAIN == "default"

    def test_constants_match_runtime_memory_type(self):
        assert LAYER_CORE == MemoryType.CORE.value
        assert LAYER_EPISODIC == MemoryType.EPISODIC.value
        assert LAYER_SEMANTIC == MemoryType.SEMANTIC.value
        assert LAYER_PROCEDURAL == MemoryType.PROCEDURAL.value
        assert LAYER_SOCIAL == MemoryType.SOCIAL.value


class TestSpecMemoryEntryLayerStrings:
    def test_built_in_layer_strings_validate(self):
        for layer in [LAYER_CORE, LAYER_EPISODIC, LAYER_SEMANTIC, LAYER_PROCEDURAL, LAYER_SOCIAL]:
            entry = SpecMemoryEntry(content="x", layer=layer)
            assert entry.layer == layer

    def test_custom_layer_string_validates(self):
        entry = SpecMemoryEntry(content="x", layer="custom_layer")
        assert entry.layer == "custom_layer"

    def test_arbitrary_layer_string_validates(self):
        # Layers are intentionally free-form — anything goes.
        entry = SpecMemoryEntry(content="x", layer="my-business-domain.42")
        assert entry.layer == "my-business-domain.42"

    def test_default_domain_when_unspecified(self):
        entry = SpecMemoryEntry(content="x", layer="custom")
        assert entry.domain == DEFAULT_DOMAIN

    def test_domain_field_is_settable(self):
        entry = SpecMemoryEntry(content="x", layer="semantic", domain="finance")
        assert entry.domain == "finance"


class TestRuntimeMemoryEntryLayerCoercion:
    def test_legacy_call_with_only_type_sets_layer_from_type(self):
        # Existing 0.3.x callers wrote MemoryEntry(type=..., content=...).
        # They should get layer="semantic" automatically.
        entry = RuntimeMemoryEntry(type=MemoryType.SEMANTIC, content="hello")
        assert entry.layer == "semantic"
        assert entry.domain == "default"

    def test_explicit_layer_wins_over_type_default(self):
        entry = RuntimeMemoryEntry(type=MemoryType.SEMANTIC, content="hello", layer="custom")
        assert entry.layer == "custom"

    def test_serialise_then_deserialise_round_trip(self):
        original = RuntimeMemoryEntry(
            type=MemoryType.SEMANTIC, content="hello", layer="finance", domain="legal"
        )
        data = original.model_dump(mode="json")
        # Both fields written
        assert data["layer"] == "finance"
        assert data["domain"] == "legal"
        # Reload preserves both
        reload = RuntimeMemoryEntry.model_validate(data)
        assert reload.layer == "finance"
        assert reload.domain == "legal"

    def test_legacy_dict_without_layer_or_domain_back_fills_defaults(self):
        # Simulate a 0.3.x soul where MemoryEntry was persisted with only
        # `type` (no layer, no domain). The model validator should fill
        # the gaps so the runtime sees a uniform shape.
        legacy_data = {
            "id": "old123",
            "type": "episodic",
            "content": "old memory",
            "importance": 5,
            "created_at": "2026-01-01T00:00:00",
        }
        entry = RuntimeMemoryEntry.model_validate(legacy_data)
        assert entry.layer == "episodic"
        assert entry.domain == "default"
        assert entry.type == MemoryType.EPISODIC

    def test_social_memory_type_resolves_to_social_layer(self):
        entry = RuntimeMemoryEntry(type=MemoryType.SOCIAL, content="alice trusts us")
        assert entry.layer == "social"
        assert entry.domain == "default"
