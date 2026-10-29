# test_unicode_encoding.py — Regression test for issue #267.
# Ensures CLI commands don't crash when stdout uses a non-UTF-8 encoding
# (e.g. cp1252 on Windows, C/POSIX locale on Linux).
#
# The test runs `soul status` in a subprocess with PYTHONIOENCODING=cp1252
# to simulate a legacy console. The fix in main.py reconfigures the stream
# to UTF-8 before Rich writes any Unicode characters.

from __future__ import annotations

import json
import subprocess
import sys


class TestUnicodeEncoding:
    """Regression tests for Unicode encoding issues (#267)."""

    def test_status_does_not_crash_with_cp1252(self, tmp_path):
        """soul status must not crash when stdout is cp1252 (#267).

        Simulates a legacy Windows console (or any non-UTF-8 locale) by
        setting PYTHONIOENCODING=cp1252. The CLI should reconfigure the
        stream to UTF-8 and render without a UnicodeEncodeError.
        """
        import os

        soul_path = str(tmp_path / "test.soul")

        # Create a minimal soul to inspect
        setup_script = tmp_path / "setup.py"
        setup_script.write_text(
            "import asyncio\n"
            "from soul_protocol.runtime.soul import Soul\n"
            "\n"
            "async def main():\n"
            f"    soul = await Soul.birth('Test267')\n"
            f"    await soul.export({json.dumps(soul_path)})\n"
            "\n"
            "asyncio.run(main())\n"
        )
        subprocess.run(
            [sys.executable, str(setup_script)],
            check=True,
            capture_output=True,
        )

        assert os.path.exists(soul_path), "Soul file was not created"

        # Run `soul status` with cp1252 encoding to trigger the bug
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "cp1252"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "soul_protocol.cli.main",
                "status",
                soul_path,
            ],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        # Before the fix, this would crash with:
        #   UnicodeEncodeError: 'charmap' codec can't encode character
        assert result.returncode == 0, (
            f"soul status crashed with cp1252 encoding:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_ensure_utf8_reconfigures_non_utf8_stream(self):
        """_ensure_utf8 reconfigures streams with non-UTF-8 encoding."""
        import io

        from soul_protocol.cli.main import _ensure_utf8

        # Create a stream with latin-1 encoding
        stream = io.TextIOWrapper(io.BytesIO(), encoding="latin-1")
        assert stream.encoding == "latin-1"

        _ensure_utf8(stream)

        assert stream.encoding == "utf-8"

    def test_ensure_utf8_skips_utf8_stream(self):
        """_ensure_utf8 does not reconfigure streams already in UTF-8."""
        import io

        from soul_protocol.cli.main import _ensure_utf8

        stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        _ensure_utf8(stream)

        assert stream.encoding == "utf-8"
