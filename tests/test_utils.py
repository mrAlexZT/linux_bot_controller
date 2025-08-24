from pathlib import Path

import pytest

from bot.utils import human_bytes, run_shell, text_preview_or_file


@pytest.mark.asyncio
async def test_run_shell_echo():
    res = await run_shell("echo hello")
    assert res.returncode == 0
    assert res.stdout.decode("utf-8").strip() == "hello"


@pytest.mark.asyncio
async def test_run_shell_timeout():
    # sleep should exist on Linux/macOS
    res = await run_shell("sleep 2", timeout_sec=0.3)
    assert res.returncode == 124
    assert b"Timeout after" in res.stderr


def test_text_preview_or_file_preview():
    text = "abc" * 10
    preview, path = text_preview_or_file(text, max_chars=len(text))
    assert preview == text
    assert path is None


def test_text_preview_or_file_file(tmp_path: Path):
    text = "x" * 5000
    preview, path = text_preview_or_file(text, max_chars=100, filename_prefix="tst")
    assert preview is None and path
    p = Path(path)
    assert p.exists()
    assert p.name.startswith("tst_") and p.suffix == ".txt"
    assert p.read_text(encoding="utf-8") == text
    p.unlink()


def test_human_bytes():
    assert human_bytes(0) == "0.00 B"
    assert human_bytes(1023).endswith("B")
    assert human_bytes(1024).endswith("KB")
    assert human_bytes(1024 * 1024).endswith("MB")
