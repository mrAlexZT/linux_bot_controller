from pathlib import Path

import pytest

from bot.config import Settings
from bot.handlers import _ensure_inside, _is_cmd_allowed, _resolve_under


def mk_settings(tmp_path: Path, allowed: set[str] | None = None) -> Settings:
    return Settings(
        token='t', admin_ids={1}, base_dir=tmp_path, allowed_shell_prefixes=allowed or set()
    )


def test_is_cmd_allowed_empty_allows_any(tmp_path: Path):
    s = mk_settings(tmp_path)
    assert _is_cmd_allowed('uname -a', s)
    assert _is_cmd_allowed('  LS -la', s)


def test_is_cmd_allowed_exact_name_and_sudo_absolute(tmp_path: Path):
    s = mk_settings(tmp_path, {'ls', 'echo'})
    assert _is_cmd_allowed('ls -la', s)
    assert _is_cmd_allowed('sudo /bin/ls -la', s)
    assert _is_cmd_allowed('ECHO hi', s)
    assert not _is_cmd_allowed('lsof -i', s)
    assert not _is_cmd_allowed('bash -lc "id"', s)


def test_resolve_under_builds_paths(tmp_path: Path):
    base = tmp_path
    assert _resolve_under(base, '.') == base.resolve()
    p = _resolve_under(base, 'sub/dir/file.txt')
    assert str(p).startswith(str(base.resolve()))
    assert p.parts[-3:] == ('sub', 'dir', 'file.txt')
    abs_p = _resolve_under(base, '/tmp')
    assert abs_p.is_absolute()


def test_ensure_inside_blocks_escape(tmp_path: Path):
    base = tmp_path
    inside = base / 'a' / 'b.txt'
    inside.parent.mkdir(parents=True, exist_ok=True)
    inside.write_text('x')
    # Should not raise
    _ensure_inside(base, inside)

    # Absolute outside
    etc = Path('/etc')
    with pytest.raises(PermissionError):
        _ensure_inside(base, etc)
