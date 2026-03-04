# test_error_handling.py — Tests for proper error handling in awaken(), export(), retire().
# Created: v0.3.2 — Covers SoulFileNotFoundError, SoulCorruptError,
#   SoulExportError, SoulRetireError.
# Updated: fix Windows compatibility — NamedTemporaryFile handle management,
#   skip chmod-based tests on Windows (no Unix-style permissions).

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from soul_protocol import Soul
from soul_protocol.exceptions import (
    SoulCorruptError,
    SoulExportError,
    SoulFileNotFoundError,
    SoulRetireError,
)

_IS_WINDOWS = sys.platform == "win32"


# ============ awaken() error handling ============


class TestAwakenErrors:
    """Test that awaken() raises descriptive errors instead of raw exceptions."""

    @pytest.mark.asyncio
    async def test_awaken_nonexistent_file_raises_soul_file_not_found(self):
        with pytest.raises(SoulFileNotFoundError, match="No soul file at"):
            await Soul.awaken("/tmp/does_not_exist_12345.soul")

    @pytest.mark.asyncio
    async def test_awaken_nonexistent_json_raises_soul_file_not_found(self):
        with pytest.raises(SoulFileNotFoundError, match="No soul file at"):
            await Soul.awaken("/tmp/does_not_exist_12345.json")

    @pytest.mark.asyncio
    async def test_awaken_corrupt_soul_file_raises_soul_corrupt(self):
        """A .soul file with invalid content should raise SoulCorruptError."""
        tmp = tempfile.NamedTemporaryFile(suffix=".soul", delete=False)
        tmp.write(b"this is not a zip archive")
        tmp.flush()
        tmp.close()
        try:
            with pytest.raises(SoulCorruptError, match="Invalid .soul archive"):
                await Soul.awaken(tmp.name)
        finally:
            os.unlink(tmp.name)

    @pytest.mark.asyncio
    async def test_awaken_corrupt_bytes_raises_soul_corrupt(self):
        """Raw bytes that aren't a valid .soul archive should raise SoulCorruptError."""
        with pytest.raises(SoulCorruptError):
            await Soul.awaken(b"not a valid archive")

    @pytest.mark.asyncio
    async def test_awaken_error_includes_path(self):
        """Error message should include the file path for debugging."""
        path = os.path.join(tempfile.gettempdir(), "nonexistent_soul_test.soul")
        with pytest.raises(SoulFileNotFoundError) as exc_info:
            await Soul.awaken(path)
        assert "nonexistent_soul_test.soul" in str(exc_info.value)
        assert exc_info.value.path == path

    @pytest.mark.asyncio
    async def test_awaken_unknown_format_still_raises_value_error(self):
        """Unknown file extensions should still raise ValueError."""
        tmp = tempfile.NamedTemporaryFile(suffix=".xyz", delete=False)
        tmp.write(b"data")
        tmp.flush()
        tmp.close()
        try:
            with pytest.raises(ValueError, match="Unknown soul format"):
                await Soul.awaken(tmp.name)
        finally:
            os.unlink(tmp.name)


# ============ export() error handling ============


class TestExportErrors:
    """Test that export() raises SoulExportError on I/O failures."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(_IS_WINDOWS, reason="chmod 0o444 doesn't restrict writes on Windows")
    async def test_export_to_readonly_dir_raises_soul_export_error(self):
        """Exporting to a read-only directory should raise SoulExportError."""
        soul = await Soul.birth(name="ExportTest")

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chmod(tmpdir, 0o444)
            try:
                export_path = os.path.join(tmpdir, "test.soul")
                with pytest.raises(SoulExportError, match="permission denied"):
                    await soul.export(export_path)
            finally:
                os.chmod(tmpdir, 0o755)

    @pytest.mark.asyncio
    @pytest.mark.skipif(_IS_WINDOWS, reason="chmod 0o444 doesn't restrict writes on Windows")
    async def test_export_error_includes_path(self):
        """SoulExportError should include the target path."""
        soul = await Soul.birth(name="ExportTest")

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chmod(tmpdir, 0o444)
            try:
                export_path = os.path.join(tmpdir, "test.soul")
                with pytest.raises(SoulExportError) as exc_info:
                    await soul.export(export_path)
                assert export_path in str(exc_info.value)
                assert exc_info.value.path == export_path
            finally:
                os.chmod(tmpdir, 0o755)

    @pytest.mark.asyncio
    async def test_export_success_still_works(self):
        """Normal export should still work without errors."""
        soul = await Soul.birth(name="ExportTest")
        tmp = tempfile.NamedTemporaryFile(suffix=".soul", delete=False)
        tmp.close()
        try:
            await soul.export(tmp.name)
            assert os.path.getsize(tmp.name) > 0
        finally:
            os.unlink(tmp.name)


# ============ retire() error handling ============


class TestRetireErrors:
    """Test that retire() fails before lifecycle change if save fails."""

    @pytest.mark.asyncio
    async def test_retire_raises_if_save_fails(self):
        """retire(preserve_memories=True) should raise SoulRetireError if save fails."""
        soul = await Soul.birth(name="RetireTest")

        with patch.object(soul, "save", new_callable=AsyncMock) as mock_save:
            mock_save.side_effect = OSError("disk full")
            with pytest.raises(SoulRetireError, match="disk full"):
                await soul.retire(preserve_memories=True)

    @pytest.mark.asyncio
    async def test_retire_keeps_lifecycle_on_save_failure(self):
        """If save fails, the soul should stay ACTIVE, not become RETIRED."""
        soul = await Soul.birth(name="RetireTest")
        from soul_protocol.types import LifecycleState

        assert soul.lifecycle == LifecycleState.ACTIVE

        with patch.object(soul, "save", new_callable=AsyncMock) as mock_save:
            mock_save.side_effect = OSError("disk full")
            with pytest.raises(SoulRetireError):
                await soul.retire(preserve_memories=True)

        # Soul should still be ACTIVE
        assert soul.lifecycle == LifecycleState.ACTIVE

    @pytest.mark.asyncio
    async def test_retire_without_preserve_skips_save(self):
        """retire(preserve_memories=False) should not attempt save."""
        soul = await Soul.birth(name="RetireTest")
        from soul_protocol.types import LifecycleState

        with patch.object(soul, "save", new_callable=AsyncMock) as mock_save:
            await soul.retire(preserve_memories=False)
            mock_save.assert_not_called()

        assert soul.lifecycle == LifecycleState.RETIRED

    @pytest.mark.asyncio
    async def test_retire_success_still_works(self):
        """Normal retire with save should work."""
        soul = await Soul.birth(name="RetireTest")
        from soul_protocol.types import LifecycleState

        with patch.object(soul, "save", new_callable=AsyncMock) as mock_save:
            await soul.retire(preserve_memories=True)
            mock_save.assert_called_once()

        assert soul.lifecycle == LifecycleState.RETIRED


# ============ Exception class tests ============


class TestExceptionClasses:
    """Test exception class attributes and inheritance."""

    def test_soul_file_not_found_has_path(self):
        e = SoulFileNotFoundError("/tmp/test.soul")
        assert e.path == "/tmp/test.soul"
        assert "No soul file" in str(e)

    def test_soul_corrupt_has_path_and_reason(self):
        e = SoulCorruptError("/tmp/test.soul", "missing soul.json")
        assert e.path == "/tmp/test.soul"
        assert e.reason == "missing soul.json"
        assert "missing soul.json" in str(e)

    def test_soul_export_has_path_and_reason(self):
        e = SoulExportError("/tmp/test.soul", "permission denied")
        assert e.path == "/tmp/test.soul"
        assert "permission denied" in str(e)

    def test_soul_retire_has_reason(self):
        e = SoulRetireError("disk full")
        assert e.reason == "disk full"
        assert "disk full" in str(e)

    def test_all_exceptions_inherit_from_base(self):
        from soul_protocol.exceptions import SoulProtocolError

        assert issubclass(SoulFileNotFoundError, SoulProtocolError)
        assert issubclass(SoulCorruptError, SoulProtocolError)
        assert issubclass(SoulExportError, SoulProtocolError)
        assert issubclass(SoulRetireError, SoulProtocolError)
