import os
from pathlib import Path
import pytest

from bot.config import _parse_admin_ids, load_settings


def test_parse_admin_ids():
    assert _parse_admin_ids(None) == set()
    assert _parse_admin_ids("") == set()
    assert _parse_admin_ids("123") == {123}
    assert _parse_admin_ids("123, 456 ; 789") == {123, 456, 789}
    # invalid tokens ignored
    assert _parse_admin_ids("12a, 34b, 56") == {56}


def test_load_settings_requires_token_and_admins(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)
    with pytest.raises(RuntimeError):
        load_settings()


def test_load_settings_parses_logging_and_allowlist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv("BOT_TOKEN", "t")
    monkeypatch.setenv("ADMIN_USER_IDS", "1,2")
    monkeypatch.setenv("BASE_DIR", str(tmp_path))

    # logging
    log_file = tmp_path / "logs" / "bot.log"
    monkeypatch.setenv("LOG_FILE", str(log_file))
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("LOG_MAX_BYTES", "1024")
    monkeypatch.setenv("LOG_BACKUPS", "3")

    # allowlist
    monkeypatch.setenv("ALLOWED_SHELL_PREFIXES", "ls, Echo ; UNAME ")

    s = load_settings()
    assert s.token == "t"
    assert s.admin_ids == {1, 2}
    assert s.base_dir == Path(tmp_path).resolve()
    assert s.log_file == log_file.resolve()
    assert s.log_level == "DEBUG"
    assert s.log_max_bytes == 1024
    assert s.log_backups == 3
    assert s.allowed_shell_prefixes == {"ls", "echo", "uname"}
