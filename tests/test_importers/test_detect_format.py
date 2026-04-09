# test_detect_format.py — Tests for format auto-detection
# Created: 2026-03-23 — Tests covering detection of SoulSpec directories,
#   TavernAI JSON/PNG, Soul Protocol native formats, and unknown formats.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from soul_protocol.runtime.importers import detect_format


def test_detect_soulspec_directory_with_soul_md(tmp_path: Path):
    """Directory with SOUL.md should be detected as soulspec."""
    d = tmp_path / "spec"
    d.mkdir()
    (d / "SOUL.md").write_text("# Test\n")

    assert detect_format(d) == "soulspec"


def test_detect_soulspec_directory_with_identity_md(tmp_path: Path):
    """Directory with IDENTITY.md should be detected as soulspec."""
    d = tmp_path / "spec2"
    d.mkdir()
    (d / "IDENTITY.md").write_text("# Test\n")

    assert detect_format(d) == "soulspec"


def test_detect_soulspec_directory_with_style_md(tmp_path: Path):
    """Directory with STYLE.md should be detected as soulspec."""
    d = tmp_path / "spec3"
    d.mkdir()
    (d / "STYLE.md").write_text("Warmth: high\n")

    assert detect_format(d) == "soulspec"


def test_detect_soulspec_json_file(tmp_path: Path):
    """JSON file with name + traits should be detected as soulspec."""
    f = tmp_path / "soul.json"
    f.write_text(json.dumps({"name": "Test", "traits": {"openness": 0.8}}))

    assert detect_format(f) == "soulspec"


def test_detect_tavernai_json(tmp_path: Path):
    """JSON file with chara_card_v2 spec should be detected as tavernai."""
    f = tmp_path / "card.json"
    f.write_text(
        json.dumps(
            {
                "spec": "chara_card_v2",
                "data": {"name": "Test"},
            }
        )
    )

    assert detect_format(f) == "tavernai"


def test_detect_tavernai_png(tmp_path: Path):
    """PNG file should be detected as tavernai_png."""
    from soul_protocol.runtime.importers.tavernai import _minimal_png

    f = tmp_path / "avatar.png"
    f.write_bytes(_minimal_png())

    assert detect_format(f) == "tavernai_png"


def test_detect_soul_protocol_soul_file(tmp_path: Path):
    """File with .soul extension should be detected as soul_protocol."""
    f = tmp_path / "test.soul"
    f.write_bytes(b"PK\x03\x04")  # ZIP magic

    assert detect_format(f) == "soul_protocol"


def test_detect_soul_protocol_json(tmp_path: Path):
    """JSON file with identity/dna structure should be detected as soul_protocol."""
    f = tmp_path / "dsp.json"
    f.write_text(json.dumps({"identity": {"name": "Test"}, "dna": {}}))

    assert detect_format(f) == "soul_protocol"


def test_detect_soul_protocol_directory(tmp_path: Path):
    """Directory with DSP-formatted soul.json should be detected as soul_protocol."""
    d = tmp_path / "dsp_dir"
    d.mkdir()
    (d / "soul.json").write_text(
        json.dumps(
            {
                "identity": {"name": "Test"},
                "dna": {},
            }
        )
    )

    assert detect_format(d) == "soul_protocol"


def test_detect_unknown_empty_dir(tmp_path: Path):
    """Empty directory should be detected as unknown."""
    d = tmp_path / "empty"
    d.mkdir()

    assert detect_format(d) == "unknown"


def test_detect_unknown_file(tmp_path: Path):
    """Random file type should be detected as unknown."""
    f = tmp_path / "random.txt"
    f.write_text("just some text")

    assert detect_format(f) == "unknown"


def test_detect_nonexistent_path(tmp_path: Path):
    """Non-existent path should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        detect_format(tmp_path / "nope")


def test_detect_yaml_as_soul_protocol(tmp_path: Path):
    """YAML files should be detected as soul_protocol."""
    f = tmp_path / "soul.yaml"
    f.write_text("name: Test\n")

    assert detect_format(f) == "soul_protocol"


def test_detect_soulspec_directory_with_soul_json_name_desc(tmp_path: Path):
    """Directory with soul.json containing name+description (no identity/dna) -> soulspec."""
    d = tmp_path / "soulspec_dir"
    d.mkdir()
    (d / "soul.json").write_text(
        json.dumps(
            {
                "name": "Test",
                "description": "A test soul",
            }
        )
    )

    assert detect_format(d) == "soulspec"
