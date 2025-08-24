from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shlex
from datetime import datetime, timedelta
from pathlib import Path

import psutil
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.types.input_file import FSInputFile

from .config import Settings
from .utils import human_bytes, run_shell, text_preview_or_file

router = Router(name="core")


HELP = (
    "Remote control commands:\n"
    "/start – show this message\n"
    "/help – show this message\n"
    "/sh <cmd> – run shell command\n"
    "!<cmd> – quick shell (prefix with exclamation)\n"
    "/ls [path] – list directory (within BASE_DIR)\n"
    "/cat <path> – show small file content\n"
    "/download <path> – download a file\n"
    "/upload <path> – send a file with this caption to upload\n"
    "/sysinfo – system info\n"
    "/power <reboot|shutdown> – power control (if enabled)\n"
)


def _ensure_inside(base_dir: Path, path: Path) -> None:
    try:
        base = base_dir.resolve()
        target = path.resolve()
    except FileNotFoundError:
        # resolve will fail on missing parts; fall back to strict commonpath check on parent
        base = base_dir.resolve()
        target = path.parent.resolve()
    if os.path.commonpath([str(base)]) != os.path.commonpath([str(base), str(target)]):
        raise PermissionError("Path escapes BASE_DIR")


def _get_args(message: Message) -> str:
    text = message.text or message.caption or ""
    if not text:
        return ""
    parts = text.split(maxsplit=1)
    if len(parts) == 1:
        return ""
    return parts[1].strip()


def _resolve_under(base_dir: Path, raw: str) -> Path:
    raw = (raw or "").strip()
    if not raw or raw == ".":
        return base_dir.resolve()
    if raw.startswith("/") or raw.startswith("~"):
        return Path(os.path.expanduser(raw)).resolve()
    # relative to base_dir
    return (base_dir / raw).resolve()


async def _send_text_or_file(message: Message, text: str, max_chars: int, prefix: str) -> None:
    preview, file_path = text_preview_or_file(text, max_chars, filename_prefix=prefix)
    if preview is not None:
        await message.answer(preview)
    else:
        try:
            await message.answer_document(FSInputFile(file_path))
        finally:
            with contextlib.suppress(Exception):
                os.remove(file_path)


def _is_cmd_allowed(cmd: str, settings: Settings) -> bool:
    """Return True if the command is allowed based on allowed_shell_prefixes.

    Semantics: If allowed set is empty, all commands are allowed. Otherwise, we parse the
    first executable token (handling optional leading 'sudo' and absolute paths) and require
    that token to be exactly in the allowed set (case-insensitive, basename match).
    """
    allowed = settings.allowed_shell_prefixes
    if not allowed:
        return True
    try:
        parts = shlex.split(cmd or "", posix=True)
    except Exception:
        parts = (cmd or "").strip().split()
    if not parts:
        return False
    idx = 0
    if parts[0].lower() == "sudo" and len(parts) > 1:
        idx = 1
    first = parts[idx]
    base = os.path.basename(first).lower()
    allow_norm = {a.strip().lower() for a in allowed}
    return base in allow_norm


@router.message(Command("start"))
@router.message(Command("help"))
async def cmd_help(message: Message, settings: Settings) -> None:
    lines = [HELP, f"BASE_DIR: <code>{settings.base_dir}</code>"]
    await message.answer("\n".join(lines))


@router.message(Command("sh"))
async def cmd_sh(message: Message, settings: Settings) -> None:
    args = _get_args(message)
    if not args:
        await message.answer("Usage: /sh <command>")
        return
    if not _is_cmd_allowed(args, settings):
        logging.warning("Command not allowed: %s", args)
        await message.answer("Command not allowed by policy.")
        return
    res = await run_shell(args, timeout_sec=settings.command_timeout_sec)
    combined = []
    combined.append(f"$ <code>{args}</code>\n")
    if res.stdout:
        try:
            combined.append(res.stdout.decode("utf-8", errors="replace"))
        except Exception:
            combined.append("<binary stdout>\n")
    if res.stderr:
        try:
            err = res.stderr.decode("utf-8", errors="replace")
        except Exception:
            err = "<binary stderr>\n"
        if res.stdout:
            combined.append("\n[stderr]\n")
        combined.append(err)
    combined.append(f"\n[exit {res.returncode}]")

    text = "".join(combined).strip()
    await _send_text_or_file(message, text, settings.max_text_reply_chars, prefix="cmd")


@router.message(F.text.startswith("!"))
async def bang_shell(message: Message, settings: Settings) -> None:
    cmd = (message.text or "")[1:].strip()
    if not cmd:
        return
    if not _is_cmd_allowed(cmd, settings):
        logging.warning("Command not allowed: %s", cmd)
        await message.answer("Command not allowed by policy.")
        return
    res = await run_shell(cmd, timeout_sec=settings.command_timeout_sec)
    combined = []
    combined.append(f"$ <code>{cmd}</code>\n")
    if res.stdout:
        try:
            combined.append(res.stdout.decode("utf-8", errors="replace"))
        except Exception:
            combined.append("<binary stdout>\n")
    if res.stderr:
        try:
            err = res.stderr.decode("utf-8", errors="replace")
        except Exception:
            err = "<binary stderr>\n"
        if res.stdout:
            combined.append("\n[stderr]\n")
        combined.append(err)
    combined.append(f"\n[exit {res.returncode}]")
    text = "".join(combined).strip()
    await _send_text_or_file(message, text, settings.max_text_reply_chars, prefix="cmd")


@router.message(Command("ls"))
async def cmd_ls(message: Message, settings: Settings) -> None:
    arg = _get_args(message) or "."
    path = _resolve_under(settings.base_dir, arg)
    try:
        _ensure_inside(settings.base_dir, path)
    except PermissionError:
        await message.answer("Path not allowed")
        return

    if not path.exists():
        await message.answer("Not found")
        return

    if path.is_file():
        info = path.stat()
        await message.answer(
            f"FILE {path.relative_to(settings.base_dir)} ({human_bytes(info.st_size)})"
        )
        return

    entries = []
    for entry in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        try:
            if entry.is_dir():
                entries.append(f"[D] {entry.name}/")
            else:
                sz = human_bytes(entry.stat().st_size)
                entries.append(f"[F] {entry.name} ({sz})")
        except PermissionError:
            entries.append(f"[?] {entry.name} <perm denied>")
    text = f"Listing {path.relative_to(settings.base_dir)}:\n" + "\n".join(entries)
    await _send_text_or_file(message, text, settings.max_text_reply_chars, prefix="ls")


@router.message(Command("cat"))
async def cmd_cat(message: Message, settings: Settings) -> None:
    arg = _get_args(message)
    if not arg:
        await message.answer("Usage: /cat <path>")
        return
    path = _resolve_under(settings.base_dir, arg)
    try:
        _ensure_inside(settings.base_dir, path)
    except PermissionError:
        await message.answer("Path not allowed")
        return

    if not path.exists() or not path.is_file():
        await message.answer("File not found")
        return

    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        await message.answer(f"Read error: {e}")
        return

    await _send_text_or_file(message, data, settings.max_text_reply_chars, prefix="cat")


@router.message(Command("download"))
async def cmd_download(message: Message, settings: Settings) -> None:
    arg = _get_args(message)
    if not arg:
        await message.answer("Usage: /download <path>")
        return
    path = _resolve_under(settings.base_dir, arg)
    try:
        _ensure_inside(settings.base_dir, path)
    except PermissionError:
        await message.answer("Path not allowed")
        return

    if not path.exists() or not path.is_file():
        await message.answer("File not found")
        return

    size = path.stat().st_size
    if size > settings.max_upload_bytes:
        await message.answer(
            f"File too large to upload: {human_bytes(size)} > {human_bytes(settings.max_upload_bytes)}"
        )
        return

    await message.answer_document(FSInputFile(path))


@router.message(Command("upload"))
async def cmd_upload(message: Message, settings: Settings) -> None:
    if not message.document:
        await message.answer("Attach a file and use caption: /upload <target_path>")
        return
    arg = _get_args(message)
    if not arg:
        await message.answer("Usage: attach file with caption '/upload <target_path>'")
        return

    target = _resolve_under(settings.base_dir, arg)
    try:
        _ensure_inside(settings.base_dir, target)
    except PermissionError:
        await message.answer("Path not allowed")
        return

    size = message.document.file_size or 0
    if size > settings.max_upload_bytes:
        await message.answer(
            f"File too large: {human_bytes(size)} > {human_bytes(settings.max_upload_bytes)}"
        )
        return

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        await message.bot.download(message.document, destination=target)
    except Exception as e:
        logging.exception("Upload failed")
        await message.answer(f"Upload failed: {e}")
        return
    await message.answer(
        f"Saved to {target.relative_to(settings.base_dir)} ({human_bytes(target.stat().st_size)})"
    )


@router.message(Command("sysinfo"))
async def cmd_sysinfo(message: Message) -> None:
    boot = datetime.fromtimestamp(psutil.boot_time())
    up = datetime.now() - boot
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    loadavg = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)

    text = (
        f"Uptime: {str(timedelta(seconds=int(up.total_seconds())))}\n"
        f"CPU: {cpu}%\n"
        f"RAM: {mem.percent}% ({human_bytes(mem.used)}/{human_bytes(mem.total)})\n"
        f"Disk: {disk.percent}% ({human_bytes(disk.used)}/{human_bytes(disk.total)})\n"
        f"Load avg: {loadavg[0]:.2f} {loadavg[1]:.2f} {loadavg[2]:.2f}\n"
    )
    await message.answer(text)


@router.message(Command("power"))
async def cmd_power(message: Message, settings: Settings) -> None:
    if not settings.allow_power_cmds:
        await message.answer("Power commands disabled.")
        return
    arg = _get_args(message).lower()
    if arg not in {"reboot", "shutdown"}:
        await message.answer("Usage: /power <reboot|shutdown>")
        return

    if arg == "reboot":
        cmd = "sudo /sbin/shutdown -r now || sudo /usr/sbin/reboot || sudo reboot"
        msg = "Rebooting..."
    else:
        cmd = "sudo /sbin/shutdown -h now || sudo /usr/sbin/poweroff || sudo poweroff"
        msg = "Shutting down..."

    await message.answer(msg)
    # Fire-and-forget a short delay to let the message send before shutdown
    asyncio.create_task(run_shell(cmd, timeout_sec=5))
