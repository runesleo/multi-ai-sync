# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-10-23

### Added
- `ai_sync_audit.py`: read-only per-agent check of chats, result files and memory (OK / STALE / MISSING / UNREADABLE), table or `--json`, exit codes 0/1/2.
- `<layer>_time_field`: judge JSON freshness by the timestamp inside the file, not the copy time; unreadable timestamps are a gap (`UNREADABLE`), never a silent fallback to mtime. Offset-less times are UTC.
- `<layer>_mode: every`: every matched file must be fresh, and the stale ones are listed. A layer can also be a list of exact paths.
- Config/read errors exit 2 with a message, never a traceback.
- `SKILL.md`: audit → diagnose transport → agent pushes → two-way memory sync; Cursor cloud agent case.
- `install.md` for AI agents; bilingual README.
