# Usage examples

This page shows practical, copyable examples for interacting with the bot after it’s running and you are listed in ADMIN_USER_IDS.

Assumptions
- You started the bot (locally or via Docker) and see it online in Telegram.
- BASE_DIR is set (default is the working directory when launched). All file ops are confined to BASE_DIR.
- Messages use HTML parse mode; code is rendered with <code>…</code>.

General help
- /start or /help
  - Shows available commands and the configured BASE_DIR.

Run shell commands
- Full shell via /sh
  - /sh echo "Hello from bot"
  - /sh uname -a
  - /sh df -h / | sed -n '1,5p'
- Quick shell via leading bang
  - !echo quick run
  - !uptime
Notes
- If ALLOWED_SHELL_PREFIXES is set, only commands whose first token matches the allowlist are permitted.
  - Example allowlist: ALLOWED_SHELL_PREFIXES="ls, echo, df, uname"
  - Allowed: /sh ls -la; Blocked: /sh lsof -i
- Outputs longer than MAX_TEXT_REPLY_CHARS are sent as a file attachment automatically.
- Commands are terminated after COMMAND_TIMEOUT_SEC seconds.

List files and directories
- List BASE_DIR
  - /ls
- List a subdirectory (relative to BASE_DIR)
  - /ls projects
- List with absolute path (must still be inside BASE_DIR)
  - /ls /data/logs
Behavior
- Directories are shown with [D] and a trailing slash; files with [F] and size.
- If the path escapes BASE_DIR, the bot replies: "Path not allowed".

View small files
- /cat README.md
- /cat logs/bot.log
Notes
- If the file is large, content may be sent as a file instead of inline text.
- Binary files will be shown with replacement characters; prefer /download for binaries.

Download a file
- /download logs/bot.log
- /download projects/report.pdf
Notes
- Files larger than MAX_UPLOAD_BYTES are refused with a helpful message.

Upload a file
- Send a file with caption specifying the target path:
  - [attach file] with caption: /upload uploads/new.txt
- The target path must be inside BASE_DIR; parent directories are created as needed.
- On success, the bot replies with the saved relative path and size.

System info
- /sysinfo
  - Returns uptime, CPU, RAM, disk usage, and load average.

Power control (optional)
- Disabled by default. Enable by setting ALLOW_POWER_CMDS=true and configuring sudoers for passwordless shutdown/reboot.
- Commands
  - /power reboot
  - /power shutdown
- Safety
  - The bot replies (e.g., "Rebooting…") and then triggers the action.

Examples of allowlist behavior
- ALLOWED_SHELL_PREFIXES="ls, echo, df, uname"
  - Allowed
    - /sh ls -la /         → directory listing
    - /sh echo "hi"       → prints hi
    - !df -h               → disk usage
  - Blocked
    - /sh lsof -i          → "Command not allowed by policy."
    - !bash -c 'id'        → unless "bash" is in the allowlist

Troubleshooting
- "Command not allowed by policy."
  - Add the command name to ALLOWED_SHELL_PREFIXES (comma/semicolon separated), or clear it to allow any.
- "Path not allowed"
  - The requested path resolves outside BASE_DIR. Use a path within BASE_DIR.
- "File too large"
  - Adjust MAX_UPLOAD_BYTES or choose a smaller file.
- No response to commands
  - Verify you’re included in ADMIN_USER_IDS and the bot token is valid. Check LOG_FILE (if configured) and console logs.
- Power commands have no effect
  - Ensure ALLOW_POWER_CMDS=true and sudoers allow passwordless shutdown/reboot for the bot user.

Environment quick reference
- See README.md for full environment variable documentation and Docker usage.
