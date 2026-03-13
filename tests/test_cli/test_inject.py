# tests/test_cli/test_inject.py — Comprehensive tests for the `soul inject` CLI command.
# Created: 2026-03-13 — Covers helper unit tests, idempotency, CLI integration via
#   CliRunner, and E2E roundtrip scenarios (birth → remember → inject → verify).

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from soul_protocol.cli.inject import (
    SOUL_CONTEXT_END,
    SOUL_CONTEXT_START,
    TARGET_FILES,
    find_soul,
    inject_context_block,
    resolve_target_path,
)
from soul_protocol.cli.main import cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_soul_dir(tmp_path: Path, name: str = "Aria") -> Path:
    """Birth a soul and save it as a directory under tmp_path. Returns the soul dir path."""
    from soul_protocol.runtime.soul import Soul

    soul_dir = tmp_path / "soul_store" / name.lower()

    async def _setup():
        soul = await Soul.birth(name=name, archetype="The Companion")
        await soul.save_local(str(soul_dir))
        return soul

    asyncio.run(_setup())
    return soul_dir


def _make_soul_dir_with_memories(tmp_path: Path, name: str = "Aria", memories: list[str] | None = None) -> Path:
    """Birth a soul, add episodic memories, save as directory, return path.

    Uses _memory.add_episodic() directly to bypass significance gating so memories
    reliably appear in the injected context block during tests.
    """
    from soul_protocol.runtime.soul import Soul
    from soul_protocol.runtime.types import Interaction

    soul_dir = tmp_path / "soul_store" / name.lower()

    async def _setup():
        soul = await Soul.birth(name=name, archetype="The Companion")
        for mem in (memories or []):
            await soul._memory.add_episodic(Interaction(
                user_input=mem,
                agent_output="Acknowledged.",
            ))
        await soul.save_local(str(soul_dir))

    asyncio.run(_setup())
    return soul_dir


# ---------------------------------------------------------------------------
# Unit tests: resolve_target_path
# ---------------------------------------------------------------------------

def test_resolve_target_path_claude_code(tmp_path):
    """claude-code target maps to .claude/CLAUDE.md."""
    result = resolve_target_path("claude-code", tmp_path)
    assert result == tmp_path / ".claude" / "CLAUDE.md"


def test_resolve_target_path_cursor(tmp_path):
    """cursor target maps to .cursorrules."""
    result = resolve_target_path("cursor", tmp_path)
    assert result == tmp_path / ".cursorrules"


def test_resolve_target_path_vscode(tmp_path):
    """vscode target maps to .github/copilot-instructions.md."""
    result = resolve_target_path("vscode", tmp_path)
    assert result == tmp_path / ".github" / "copilot-instructions.md"


def test_resolve_target_path_windsurf(tmp_path):
    """windsurf target maps to .windsurfrules."""
    result = resolve_target_path("windsurf", tmp_path)
    assert result == tmp_path / ".windsurfrules"


def test_resolve_target_path_cline(tmp_path):
    """cline target maps to .clinerules."""
    result = resolve_target_path("cline", tmp_path)
    assert result == tmp_path / ".clinerules"


def test_resolve_target_path_continue(tmp_path):
    """continue target maps to .continuerules."""
    result = resolve_target_path("continue", tmp_path)
    assert result == tmp_path / ".continuerules"


def test_resolve_target_path_invalid(tmp_path):
    """Unknown target raises ValueError with a helpful message."""
    with pytest.raises(ValueError, match="Unknown target"):
        resolve_target_path("unknown-ide", tmp_path)


def test_resolve_target_path_invalid_message_includes_supported(tmp_path):
    """ValueError message lists supported targets."""
    with pytest.raises(ValueError) as exc_info:
        resolve_target_path("bad-target", tmp_path)
    msg = str(exc_info.value)
    for target in TARGET_FILES:
        assert target in msg


# ---------------------------------------------------------------------------
# Unit tests: inject_context_block (pure file I/O, no Soul loading)
# ---------------------------------------------------------------------------

def test_inject_creates_file_if_missing(tmp_path):
    """inject_context_block creates the config file and parent dirs when they don't exist."""
    target = tmp_path / ".claude" / "CLAUDE.md"
    block = f"{SOUL_CONTEXT_START}\n## Soul: Test\n{SOUL_CONTEXT_END}"

    assert not target.exists()
    inject_context_block(target, block)

    assert target.exists()
    content = target.read_text()
    assert SOUL_CONTEXT_START in content
    assert SOUL_CONTEXT_END in content


def test_inject_replaces_existing_section(tmp_path):
    """Running inject twice replaces the section rather than duplicating it."""
    target = tmp_path / ".cursorrules"
    block1 = f"{SOUL_CONTEXT_START}\n## Soul: Aria v1\n{SOUL_CONTEXT_END}"
    block2 = f"{SOUL_CONTEXT_START}\n## Soul: Aria v2\n{SOUL_CONTEXT_END}"

    inject_context_block(target, block1)
    inject_context_block(target, block2)

    content = target.read_text()
    assert content.count(SOUL_CONTEXT_START) == 1
    assert "v1" not in content
    assert "v2" in content


def test_inject_preserves_surrounding_content(tmp_path):
    """Existing file content outside the markers is preserved."""
    target = tmp_path / ".cursorrules"
    preamble = "# My cursor rules\nDo not use tabs.\n\n"
    postamble = "\n\n# End of rules\n"
    initial = preamble + f"{SOUL_CONTEXT_START}\nOld block\n{SOUL_CONTEXT_END}" + postamble
    target.write_text(initial)

    new_block = f"{SOUL_CONTEXT_START}\nNew block\n{SOUL_CONTEXT_END}"
    inject_context_block(target, new_block)

    content = target.read_text()
    assert "# My cursor rules" in content
    assert "Do not use tabs." in content
    assert "# End of rules" in content
    assert "Old block" not in content
    assert "New block" in content


def test_inject_appends_to_existing_file_without_markers(tmp_path):
    """If the target file exists but has no markers, block is appended."""
    target = tmp_path / ".clinerules"
    target.write_text("Existing project rules here.\n")

    block = f"{SOUL_CONTEXT_START}\n## Soul: Test\n{SOUL_CONTEXT_END}"
    inject_context_block(target, block)

    content = target.read_text()
    assert "Existing project rules here." in content
    assert SOUL_CONTEXT_START in content


def test_inject_creates_nested_parent_dirs(tmp_path):
    """Parent directories are created automatically (e.g. .github/ for vscode)."""
    target = tmp_path / ".github" / "copilot-instructions.md"
    block = f"{SOUL_CONTEXT_START}\n## Soul: Test\n{SOUL_CONTEXT_END}"

    assert not (tmp_path / ".github").exists()
    inject_context_block(target, block)

    assert target.exists()


# ---------------------------------------------------------------------------
# Unit tests: build_context_block (requires live Soul)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_format_soul_context(tmp_path):
    """build_context_block generates markdown with identity, state, and core memory sections."""
    from soul_protocol.cli.inject import build_context_block
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth(name="Aria", archetype="The Companion")
    soul_dir = tmp_path / "aria"
    await soul.save_local(str(soul_dir))

    block = await build_context_block(soul_dir)

    assert SOUL_CONTEXT_START in block
    assert SOUL_CONTEXT_END in block
    assert "## Soul: Aria" in block
    assert "The Companion" in block
    assert "did:soul:" in block
    assert "### Core Memory" in block
    assert "### Recent Context" in block


@pytest.mark.asyncio
async def test_format_soul_context_no_memories(tmp_path):
    """build_context_block handles a soul with zero memories gracefully."""
    from soul_protocol.cli.inject import build_context_block
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth(name="EmptySoul", archetype="The Companion")
    soul_dir = tmp_path / "empty_soul"
    await soul.save_local(str(soul_dir))

    block = await build_context_block(soul_dir)

    assert "(no memories yet)" in block
    assert "### Recent Context (0 memories)" in block


@pytest.mark.asyncio
async def test_format_soul_context_with_memories(tmp_path):
    """build_context_block includes episodic memories in the output."""
    from soul_protocol.cli.inject import build_context_block
    from soul_protocol.runtime.soul import Soul
    from soul_protocol.runtime.types import Interaction

    soul = await Soul.birth(name="MemSoul", archetype="The Companion")
    # Use add_episodic directly to bypass significance gating in tests
    interaction = Interaction(
        user_input="User prefers Python over JavaScript",
        agent_output="Noted, will use Python.",
    )
    await soul._memory.add_episodic(interaction)
    soul_dir = tmp_path / "mem_soul"
    await soul.save_local(str(soul_dir))

    block = await build_context_block(soul_dir)

    # Episodic entry content is "User: ...\nAgent: ..." format
    assert "Python" in block


@pytest.mark.asyncio
async def test_format_soul_context_custom_limit(tmp_path):
    """build_context_block respects the memory_limit parameter."""
    from soul_protocol.cli.inject import build_context_block
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth(name="LimitSoul", archetype="The Companion")
    # Add 5 memories
    for i in range(5):
        await soul.remember(f"Memory item {i}", importance=5)
    soul_dir = tmp_path / "limit_soul"
    await soul.save_local(str(soul_dir))

    block_2 = await build_context_block(soul_dir, memory_limit=2)
    block_5 = await build_context_block(soul_dir, memory_limit=5)

    # The count in the section header should reflect the limit
    match_2 = re.search(r"### Recent Context \((\d+) memories\)", block_2)
    match_5 = re.search(r"### Recent Context \((\d+) memories\)", block_5)

    assert match_2 is not None
    assert match_5 is not None
    assert int(match_2.group(1)) <= 2
    assert int(match_5.group(1)) <= 5


@pytest.mark.asyncio
async def test_format_soul_context_long_memory_truncated(tmp_path):
    """build_context_block truncates episodic memory content longer than 120 characters."""
    from soul_protocol.cli.inject import build_context_block
    from soul_protocol.runtime.soul import Soul
    from soul_protocol.runtime.types import Interaction

    soul = await Soul.birth(name="LongMem", archetype="The Companion")
    # The episodic entry content is "User: ...\nAgent: ..." — make user_input very long
    long_input = "A" * 200
    interaction = Interaction(
        user_input=long_input,
        agent_output="Response.",
    )
    await soul._memory.add_episodic(interaction)
    soul_dir = tmp_path / "long_mem_soul"
    await soul.save_local(str(soul_dir))

    block = await build_context_block(soul_dir)

    # The combined content will be >120 chars and should be truncated with "..."
    assert "..." in block
    # The full repeated-A string should not appear verbatim in the block
    assert long_input not in block


# ---------------------------------------------------------------------------
# Unit tests: find_soul
# ---------------------------------------------------------------------------

def test_find_soul_returns_dir_with_soul_json(tmp_path):
    """find_soul returns the soul dir itself when soul.json exists inside it."""
    soul_dir = _make_soul_dir(tmp_path, name="Finder")
    result = find_soul(soul_dir)
    assert result == soul_dir


def test_find_soul_searches_subdirectories(tmp_path):
    """find_soul finds a soul subdirectory inside the given dir."""
    soul_dir = _make_soul_dir(tmp_path, name="Sub")
    parent = soul_dir.parent

    result = find_soul(parent)
    assert (result / "soul.json").exists()


def test_find_soul_by_name(tmp_path):
    """find_soul finds a named soul subdirectory."""
    soul_dir = _make_soul_dir(tmp_path, name="NamedSoul")
    parent = soul_dir.parent

    result = find_soul(parent, soul_name="namedsoul")
    assert result == soul_dir


def test_find_soul_raises_for_missing_dir(tmp_path):
    """find_soul raises FileNotFoundError when the directory doesn't exist."""
    missing = tmp_path / "nonexistent"
    with pytest.raises(FileNotFoundError, match="not found"):
        find_soul(missing)


def test_find_soul_raises_when_no_soul_found(tmp_path):
    """find_soul raises FileNotFoundError when no soul exists in an empty dir."""
    empty_dir = tmp_path / "empty_souls"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        find_soul(empty_dir)


def test_find_soul_raises_for_named_soul_not_found(tmp_path):
    """find_soul raises FileNotFoundError when requested soul name doesn't exist."""
    soul_dir = _make_soul_dir(tmp_path, name="Real")
    parent = soul_dir.parent
    with pytest.raises(FileNotFoundError, match="GhostSoul"):
        find_soul(parent, soul_name="GhostSoul")


# ---------------------------------------------------------------------------
# CLI integration tests (via CliRunner)
# ---------------------------------------------------------------------------

def test_inject_claude_code_creates_file(tmp_path, monkeypatch):
    """soul inject claude-code creates .claude/CLAUDE.md in the cwd."""
    monkeypatch.chdir(tmp_path)
    soul_dir = _make_soul_dir(tmp_path, name="Aria")

    runner = CliRunner()
    result = runner.invoke(
        cli, ["inject", "claude-code", "--dir", str(soul_dir)]
    )

    assert result.exit_code == 0, result.output
    target = tmp_path / ".claude" / "CLAUDE.md"
    assert target.exists()
    content = target.read_text()
    assert SOUL_CONTEXT_START in content
    assert "Aria" in content


def test_inject_cursor_creates_cursorrules(tmp_path, monkeypatch):
    """soul inject cursor creates .cursorrules."""
    monkeypatch.chdir(tmp_path)
    soul_dir = _make_soul_dir(tmp_path, name="Cursor")

    runner = CliRunner()
    result = runner.invoke(cli, ["inject", "cursor", "--dir", str(soul_dir)])

    assert result.exit_code == 0, result.output
    assert (tmp_path / ".cursorrules").exists()


def test_inject_with_soul_option(tmp_path, monkeypatch):
    """--soul option selects a specific soul by name."""
    monkeypatch.chdir(tmp_path)
    soul_dir = _make_soul_dir(tmp_path, name="Named")
    parent = soul_dir.parent

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["inject", "cursor", "--dir", str(parent), "--soul", "named"],
    )

    assert result.exit_code == 0, result.output
    content = (tmp_path / ".cursorrules").read_text()
    assert "Named" in content


def test_inject_with_dir_option(tmp_path, monkeypatch):
    """--dir option specifies the soul directory."""
    monkeypatch.chdir(tmp_path)
    custom_dir = tmp_path / "custom_souls"
    soul_dir = tmp_path / "custom_souls" / "aria"

    from soul_protocol.runtime.soul import Soul

    async def _setup():
        soul = await Soul.birth(name="Aria", archetype="The Companion")
        await soul.save_local(str(soul_dir))

    asyncio.run(_setup())

    runner = CliRunner()
    result = runner.invoke(
        cli, ["inject", "windsurf", "--dir", str(custom_dir)]
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / ".windsurfrules").exists()


def test_inject_with_memories_limit(tmp_path, monkeypatch):
    """--memories 3 includes at most 3 memories even when the soul has 10."""
    monkeypatch.chdir(tmp_path)
    soul_dir = _make_soul_dir_with_memories(
        tmp_path,
        name="MemLim",
        memories=[f"Memory item {i}" for i in range(10)],
    )

    runner = CliRunner()
    result = runner.invoke(
        cli, ["inject", "cline", "--dir", str(soul_dir), "--memories", "3"]
    )

    assert result.exit_code == 0, result.output
    content = (tmp_path / ".clinerules").read_text()
    match = re.search(r"### Recent Context \((\d+) memories\)", content)
    assert match is not None
    count = int(match.group(1))
    assert count <= 3, f"Expected at most 3 memories, got {count}"
    assert count > 0, "Should include some memories (soul has 10 episodic entries)"


def test_inject_quiet_mode(tmp_path, monkeypatch):
    """--quiet flag suppresses console output."""
    monkeypatch.chdir(tmp_path)
    soul_dir = _make_soul_dir(tmp_path, name="Quiet")

    runner = CliRunner()
    result = runner.invoke(
        cli, ["inject", "cursor", "--dir", str(soul_dir), "--quiet"]
    )

    assert result.exit_code == 0
    # Output should be empty (or near-empty) in quiet mode
    assert "Injected" not in result.output


def test_inject_non_quiet_mode_prints_confirmation(tmp_path, monkeypatch):
    """Without --quiet, inject prints a confirmation message."""
    monkeypatch.chdir(tmp_path)
    soul_dir = _make_soul_dir(tmp_path, name="Noisy")

    runner = CliRunner()
    result = runner.invoke(
        cli, ["inject", "cursor", "--dir", str(soul_dir)]
    )

    assert result.exit_code == 0
    assert "Injected" in result.output


def test_inject_missing_soul_dir(tmp_path, monkeypatch):
    """Clear error when soul directory does not exist."""
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["inject", "cursor", "--dir", str(tmp_path / "ghost_souls")]
    )

    assert result.exit_code != 0
    assert "Error" in result.output or "not found" in result.output.lower()


def test_inject_no_soul_in_dir(tmp_path, monkeypatch):
    """Clear error when soul directory exists but contains no soul."""
    monkeypatch.chdir(tmp_path)
    empty_soul_dir = tmp_path / ".soul"
    empty_soul_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        cli, ["inject", "cursor", "--dir", str(empty_soul_dir)]
    )

    assert result.exit_code != 0


@pytest.mark.parametrize("target,expected_rel_path", [
    ("claude-code", ".claude/CLAUDE.md"),
    ("cursor", ".cursorrules"),
    ("vscode", ".github/copilot-instructions.md"),
    ("windsurf", ".windsurfrules"),
    ("cline", ".clinerules"),
    ("continue", ".continuerules"),
])
def test_inject_all_targets(tmp_path, monkeypatch, target, expected_rel_path):
    """Each target creates its corresponding config file."""
    monkeypatch.chdir(tmp_path)
    soul_dir = _make_soul_dir(tmp_path / f"souls_{target}", name="Aria")

    runner = CliRunner()
    result = runner.invoke(cli, ["inject", target, "--dir", str(soul_dir)])

    assert result.exit_code == 0, f"inject {target} failed: {result.output}"
    config_file = tmp_path / expected_rel_path
    assert config_file.exists(), f"Expected {expected_rel_path} to exist after inject {target}"
    assert SOUL_CONTEXT_START in config_file.read_text()


def test_inject_invalid_target_is_rejected(tmp_path, monkeypatch):
    """An invalid target name is rejected by Click's Choice validation."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["inject", "jetbrains"])

    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# E2E-style tests
# ---------------------------------------------------------------------------

def test_inject_roundtrip(tmp_path, monkeypatch):
    """birth soul, add episodic memories, inject, verify file contains soul identity and memories."""
    monkeypatch.chdir(tmp_path)
    from soul_protocol.runtime.soul import Soul
    from soul_protocol.runtime.types import Interaction

    soul_dir = tmp_path / ".soul" / "roundtrip"

    async def _setup():
        soul = await Soul.birth(name="RoundTrip", archetype="The Companion")
        # Use add_episodic directly to bypass significance gating in tests
        await soul._memory.add_episodic(Interaction(
            user_input="User loves async Python",
            agent_output="Great, will use async Python.",
        ))
        await soul._memory.add_episodic(Interaction(
            user_input="Prefers dark mode in all editors",
            agent_output="Understood, dark mode noted.",
        ))
        await soul.save_local(str(soul_dir))

    asyncio.run(_setup())

    runner = CliRunner()
    result = runner.invoke(cli, ["inject", "cursor", "--dir", str(soul_dir)])

    assert result.exit_code == 0, result.output
    content = (tmp_path / ".cursorrules").read_text()

    assert "RoundTrip" in content
    assert "did:soul:" in content
    assert SOUL_CONTEXT_START in content
    assert SOUL_CONTEXT_END in content
    # At least one memory should appear
    assert "async Python" in content or "dark mode" in content


def test_inject_idempotent_e2e(tmp_path, monkeypatch):
    """inject → modify soul → re-inject → verify content is updated, not duplicated."""
    monkeypatch.chdir(tmp_path)
    from soul_protocol.runtime.soul import Soul

    soul_dir = tmp_path / ".soul" / "idempotent"

    async def _setup():
        from soul_protocol.runtime.types import Interaction
        soul = await Soul.birth(name="Idempotent", archetype="The Companion")
        await soul._memory.add_episodic(Interaction(
            user_input="First memory",
            agent_output="Noted.",
        ))
        await soul.save_local(str(soul_dir))

    async def _update():
        from soul_protocol.runtime.types import Interaction
        soul = await Soul.awaken(str(soul_dir))
        await soul._memory.add_episodic(Interaction(
            user_input="Second memory added later",
            agent_output="Also noted.",
        ))
        await soul.save_local(str(soul_dir))

    asyncio.run(_setup())

    runner = CliRunner()
    # First inject
    result1 = runner.invoke(cli, ["inject", "windsurf", "--dir", str(soul_dir)])
    assert result1.exit_code == 0, result1.output

    asyncio.run(_update())

    # Second inject — should replace, not append a second section
    result2 = runner.invoke(cli, ["inject", "windsurf", "--dir", str(soul_dir)])
    assert result2.exit_code == 0, result2.output

    content = (tmp_path / ".windsurfrules").read_text()
    assert content.count(SOUL_CONTEXT_START) == 1, "Marker should appear exactly once"
    assert content.count(SOUL_CONTEXT_END) == 1, "End marker should appear exactly once"


def test_inject_multiple_targets(tmp_path, monkeypatch):
    """Inject same soul into multiple targets; all files contain the soul context."""
    monkeypatch.chdir(tmp_path)
    soul_dir = _make_soul_dir(tmp_path, name="Multi")

    runner = CliRunner()
    targets_and_paths = [
        ("claude-code", tmp_path / ".claude" / "CLAUDE.md"),
        ("cursor", tmp_path / ".cursorrules"),
        ("vscode", tmp_path / ".github" / "copilot-instructions.md"),
    ]

    for target, _ in targets_and_paths:
        result = runner.invoke(cli, ["inject", target, "--dir", str(soul_dir)])
        assert result.exit_code == 0, f"inject {target} failed: {result.output}"

    for target, config_path in targets_and_paths:
        assert config_path.exists(), f"{target} config file missing"
        content = config_path.read_text()
        assert "Multi" in content, f"{target} config does not contain soul name"
        assert SOUL_CONTEXT_START in content, f"{target} config missing start marker"


def test_inject_roundtrip_did_is_present(tmp_path, monkeypatch):
    """The injected block contains a valid DID pattern."""
    monkeypatch.chdir(tmp_path)
    soul_dir = _make_soul_dir(tmp_path, name="DIDCheck")

    runner = CliRunner()
    result = runner.invoke(cli, ["inject", "cline", "--dir", str(soul_dir)])

    assert result.exit_code == 0, result.output
    content = (tmp_path / ".clinerules").read_text()
    assert re.search(r"did:soul:[a-f0-9\-]+", content), "DID not found in injected content"


def test_inject_roundtrip_timestamp_is_present(tmp_path, monkeypatch):
    """The injected block contains a timestamp from soul inject."""
    monkeypatch.chdir(tmp_path)
    soul_dir = _make_soul_dir(tmp_path, name="Timestamp")

    runner = CliRunner()
    result = runner.invoke(cli, ["inject", "continue", "--dir", str(soul_dir)])

    assert result.exit_code == 0, result.output
    content = (tmp_path / ".continuerules").read_text()
    # Timestamp format: 2026-03-13T...Z
    assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", content)
