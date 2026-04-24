---
{
  "title": "Test Suite: Soul Configuration — OCEAN, Communication, Biorhythms, Persona, and Config Files",
  "summary": "Validates the flexible birth configuration system for `Soul`, covering direct-kwarg birth with OCEAN personality traits, communication style, biorhythms, and persona text, as well as file-based birth from YAML and JSON configs via `Soul.birth_from_config()`. The suite also covers CLI `--config` and `--openness/--neuroticism` flags and verifies that all settings survive export → awaken round-trips.",
  "concepts": [
    "Soul.birth",
    "OCEAN traits",
    "personality at birth",
    "communication style",
    "biorhythms",
    "persona",
    "birth_from_config",
    "YAML config",
    "JSON config",
    "forward compatibility",
    "export round-trip",
    "CLI --config",
    "CliRunner"
  ],
  "categories": [
    "testing",
    "soul configuration",
    "personality",
    "CLI",
    "test"
  ],
  "source_docs": [
    "182ec6716963f1b2"
  ],
  "backlinks": null,
  "word_count": 495,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Before this configuration layer, all souls were born with identical default personalities (0.5 for all OCEAN traits, moderate communication style). Deployers who wanted distinct AI companion personalities had to post-hoc modify soul state, which was fragile. This test file locks the API that lets integrators declare a soul's character at birth, either programmatically or via a config file.

## OCEAN Personality at Birth

```python
soul = await Soul.birth("Aria", ocean={
    "openness": 0.8, "conscientiousness": 0.9,
    "extraversion": 0.3, "agreeableness": 0.7, "neuroticism": 0.2,
})
assert soul.dna.personality.openness == pytest.approx(0.8)
```

Partial OCEAN dicts are supported — unspecified traits default to 0.5. The partial test is important: it prevents the implementation from requiring all five traits, which would break callers who only want to tune one or two dimensions.

## Communication Style and Biorhythms

Communication parameters (`warmth`, `verbosity`, `humor_style`, `emoji_usage`) and biorhythms (`chronotype`, `energy_regen_rate`) follow the same partial-fill pattern. The partial communication test confirms that an unspecified `verbosity` defaults to `"moderate"` rather than `None` or an error.

## Persona vs. Personality Parameter

Two separate parameters address different needs:
- `personality` (legacy): A freeform text string that becomes core memory persona text
- `persona` (new): An explicit persona declaration, takes priority over `personality`

When both are provided, `persona` wins. When only `personality` is provided, it falls back to core memory. This precedence rule prevents silent data loss in deployments that set both.

## Forward Compatibility

```python
async def test_birth_with_kwargs_does_not_crash():
    soul = await Soul.birth("Aria", future_param="some_value")
    assert soul.name == "Aria"
```

Extra keyword arguments must not crash birth. This guards against breakage when a config file contains a field that was added in a newer protocol version but the runtime is slightly older.

## File-Based Birth: birth_from_config()

`Soul.birth_from_config(path)` reads YAML or JSON and births a fully configured soul:

```python
config = {"name": "Aria", "archetype": "The Coding Expert", "ocean": {...}}
yaml_path.write_text(yaml.dump(config))
soul = await Soul.birth_from_config(yaml_path)
```

Error cases are explicitly tested:
- **Unsupported format** (`.txt`): Raises `ValueError("Unsupported config format")`
- **Missing file**: Raises `FileNotFoundError("Config file not found")`

Both `.yaml` and `.yml` extensions are accepted. JSON is also supported. These tests prevent silent failures where a wrong extension causes the config to be ignored.

## Config Round-Trip: Export → Awaken

Custom OCEAN traits, communication style, biorhythms, and persona must survive `export()` → `awaken()`. Without this, a soul would revert to default personality after every session restart — breaking the persistence guarantee.

## CLI Integration

The CLI is tested with `click.testing.CliRunner`:
- `birth --config soul-config.yaml` reads the file and births a soul
- `birth OceanTest --openness 0.9 --neuroticism 0.1` sets traits via flags
- `birth BasicSoul` without `--config` still works (backward compatibility)
- JSON configs work via `--config config.json`

The output assertions (`"Birthed" in result.output`, `"O=0.9" in result.output`) pin the CLI output format, preventing silent formatting changes from breaking scripts that parse the output.

## Known Gaps

No TODO or FIXME markers. There is no test for invalid OCEAN values (e.g., `openness: 1.5`) — it is unclear whether `birth_from_config` validates ranges or silently clamps them.