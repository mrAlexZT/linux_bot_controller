from __future__ import annotations

import asyncio
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CmdResult:
    returncode: int
    stdout: bytes
    stderr: bytes


async def run_shell(cmd: str, timeout_sec: int = 20) -> CmdResult:
    """Run a shell command with timeout, returning stdout/stderr as bytes.

    Uses bash if available for better compatibility. Falls back to /bin/sh.
    """
    shell = "/bin/bash" if Path("/bin/bash").exists() else "/bin/sh"
    try:
        proc = await asyncio.create_subprocess_exec(
            shell,
            "-lc",
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        # Extremely minimal systems; shell invocation is intended and controlled by admin users.
        # bandit: subprocess with shell is acceptable in this context.
        proc = await asyncio.create_subprocess_shell(  # nosec B602
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await proc.wait()
        except Exception:
            # Ignore wait errors on kill path
            pass
        return CmdResult(
            returncode=124, stdout=b"", stderr=f"Timeout after {timeout_sec}s".encode()
        )

    return CmdResult(returncode=proc.returncode or 0, stdout=stdout or b"", stderr=stderr or b"")


def text_preview_or_file(
    text: str,
    max_chars: int,
    filename_prefix: str = "output",
) -> tuple[str | None, str | None]:
    """Return either a text preview <= max_chars, or create a temp file and return its path.

    Returns (preview_text, file_path). Exactly one of them is non-None unless text is empty.
    """
    if not text:
        return "", None
    if len(text) <= max_chars:
        return text, None

    fd, path = tempfile.mkstemp(prefix=f"{filename_prefix}_", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8", errors="replace") as f:
        f.write(text)
    return None, path


def normalize_path(raw: str) -> Path:
    p = Path(os.path.expanduser(raw.strip())).resolve()
    return p


def human_bytes(n: int) -> str:
    step = 1024.0
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    v = float(n)
    while v >= step and i < len(units) - 1:
        v /= step
        i += 1
    return f"{v:.2f} {units[i]}"
