import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _parse_admin_ids(raw: str | None) -> set[int]:
    ids: set[int] = set()
    if not raw:
        return ids
    for part in raw.replace(";", ",").split(","):
        p = part.strip()
        if not p:
            continue
        try:
            ids.add(int(p))
        except ValueError:
            continue
    return ids


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    token: str
    admin_ids: set[int]
    base_dir: Path
    # Logging
    log_file: Path | None = None
    log_level: str = "INFO"
    log_max_bytes: int = 5 * 1024 * 1024
    log_backups: int = 5
    # Shell allowlist
    allowed_shell_prefixes: frozenset[str] = Field(default_factory=frozenset)
    allow_power_cmds: bool = False
    command_timeout_sec: int = 20
    max_text_reply_chars: int = 3500
    max_upload_bytes: int = 45 * 1024 * 1024  # ~45MB safety margin

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_level(cls, v: str) -> str:
        return (v or "INFO").upper()

    @field_validator("base_dir", mode="before")
    @classmethod
    def _ensure_path(cls, v: Path | str) -> Path:
        return Path(v).expanduser().resolve()

    @field_validator("log_file", mode="before")
    @classmethod
    def _ensure_log_path(cls, v: str | Path | None) -> Path | None:
        if not v:
            return None
        return Path(v).expanduser().resolve()

    @field_validator("allowed_shell_prefixes", mode="before")
    @classmethod
    def _normalize_allowlist(cls, v: object) -> frozenset[str]:
        if v in (None, "", set(), frozenset()):
            return frozenset()
        if isinstance(v, (set, frozenset, list, tuple)):
            return frozenset(s.strip().lower() for s in v if str(s).strip())
        s = str(v)
        parts = (p.strip().lower() for p in s.replace(";", ",").split(","))
        return frozenset(p for p in parts if p)


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set. Define it in environment or .env file.")

    admin_ids = _parse_admin_ids(os.getenv("ADMIN_USER_IDS"))
    if not admin_ids:
        raise RuntimeError("ADMIN_USER_IDS is not set. Provide at least one Telegram user ID.")

    allow_power_cmds = os.getenv("ALLOW_POWER_CMDS", "false").lower() in {"1", "true", "yes", "y"}
    timeout = int(os.getenv("COMMAND_TIMEOUT_SEC", "20") or 20)
    max_chars = int(os.getenv("MAX_TEXT_REPLY_CHARS", "3500") or 3500)
    max_upload = int(os.getenv("MAX_UPLOAD_BYTES", str(45 * 1024 * 1024)))

    base_dir_raw = os.getenv("BASE_DIR", ".")
    base_dir = Path(base_dir_raw).expanduser().resolve()

    # Logging
    log_file_raw = os.getenv("LOG_FILE", "").strip()
    log_file = Path(log_file_raw).expanduser().resolve() if log_file_raw else None
    log_level = (os.getenv("LOG_LEVEL", "INFO") or "INFO").upper()
    log_max_bytes = int(os.getenv("LOG_MAX_BYTES", str(5 * 1024 * 1024)))
    log_backups = int(os.getenv("LOG_BACKUPS", "5"))

    # Shell allowlist: normalize here for type-safety
    raw_allow = os.getenv("ALLOWED_SHELL_PREFIXES", "")
    parts = (p.strip().lower() for p in str(raw_allow).replace(";", ",").split(","))
    allowlist = frozenset(p for p in parts if p)

    return Settings(
        token=token,
        admin_ids=admin_ids,
        base_dir=base_dir,
        log_file=log_file,
        log_level=log_level,
        log_max_bytes=log_max_bytes,
        log_backups=log_backups,
        allowed_shell_prefixes=allowlist,
        allow_power_cmds=allow_power_cmds,
        command_timeout_sec=timeout,
        max_text_reply_chars=max_chars,
        max_upload_bytes=max_upload,
    )
