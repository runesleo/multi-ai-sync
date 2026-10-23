#!/usr/bin/env python3
"""ai-sync-audit: check whether every AI agent's chats, result files and memory
actually reached this machine — and how fresh they are.

Read-only. Python 3.9+ standard library only.

    python3 ai_sync_audit.py --init            # write ai-sync.json from the example
    python3 ai_sync_audit.py                   # human table
    python3 ai_sync_audit.py --json            # machine-readable report on stdout
    python3 ai_sync_audit.py --config other.json

Exit codes: 0 all synced · 1 gaps found (the table is the result) · 2 config/read error.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

LAYERS = ("chat", "results", "memory")
MODES = ("newest", "every")
DEFAULT_CONFIG = "ai-sync.json"
EXAMPLE_CONFIG = Path(__file__).resolve().parent / "examples" / "config.example.json"
DEFAULT_MAX_AGE_HOURS = 36
FUTURE_TOLERANCE_HOURS = 0.1

OK, STALE, MISSING, UNREADABLE, SKIPPED = "OK", "STALE", "MISSING", "UNREADABLE", "-"
GAP_STATUSES = (STALE, MISSING, UNREADABLE)
SEVERITY = {OK: 0, STALE: 1, UNREADABLE: 2, MISSING: 3}


class ConfigError(ValueError):
    pass


def expand(pattern: str) -> list[str]:
    files = glob.glob(os.path.expanduser(os.path.expandvars(pattern)), recursive=True)
    return [f for f in files if os.path.isfile(f)]


def parse_time(value) -> float | None:
    """Epoch seconds from an ISO-8601 string or an epoch number (s/ms/µs/ns).
    Strings without a UTC offset are read as UTC, never as this machine's local time."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        while v > 1e11:  # ms, µs, ns → s
            v /= 1000
        return v if v > 0 else None
    if not isinstance(value, str) or not value.strip():
        return None
    s = value.strip()
    s = re.sub(r"[zZ]$", "+00:00", s)
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)            # +0800 → +08:00
    s = re.sub(r"(\.\d{6})\d+", r"\1", s)                      # >6 fractional digits
    s = s.replace(" ", "T", 1) if re.match(r"^\d{4}-\d{2}-\d{2} \d", s) else s
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def content_time(path: str, field: str) -> float | None:
    """Timestamp the agent wrote inside a JSON object file, e.g. "observed_at".
    A sync job rewrites files, so mtime only says when it was copied."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return parse_time(data.get(field)) if isinstance(data, dict) else None


def file_age(path: str, time_field: str | None, now: float) -> tuple[float | None, str]:
    """(age in hours, source). Age None means unreadable."""
    if time_field:
        t = content_time(path, time_field)
        source = "content"
    else:
        t = os.path.getmtime(path)
        source = "mtime"
    if t is None:
        return None, source
    age = round((now - t) / 3600, 1)
    if age < -FUTURE_TOLERANCE_HOURS:  # a timestamp from the future is not trustworthy
        return None, source
    return max(age, 0.0), source


def check_pattern(pattern: str, max_age: float, now: float, time_field: str | None, mode: str) -> dict:
    files = expand(pattern)
    if not files:
        return {"pattern": pattern, "status": MISSING, "files": 0, "newest_age_hours": None,
                "oldest_age_hours": None, "stale": [], "unreadable": []}
    ages, unreadable, source = {}, [], "mtime"
    for f in files:
        age, source = file_age(f, time_field, now)
        if age is None:
            unreadable.append(f)
        else:
            ages[f] = age
    stale = sorted((f for f, a in ages.items() if a > max_age), key=lambda f: -ages[f])
    newest = min(ages.values()) if ages else None
    if mode == "every":
        status = UNREADABLE if unreadable else (STALE if stale else OK)
    elif newest is None:
        status = UNREADABLE
    else:
        status = OK if newest <= max_age else STALE
    return {
        "pattern": pattern,
        "status": status,
        "files": len(files),
        "newest_age_hours": newest,
        "oldest_age_hours": max(ages.values()) if ages else None,
        "stale": stale if mode == "every" else [],
        "unreadable": unreadable,
        "time_source": source,
    }


def check_layer(spec, max_age: float, now: float, time_field: str | None, mode: str) -> dict:
    patterns = [spec] if isinstance(spec, str) else spec
    parts = [check_pattern(p, max_age, now, time_field, mode) for p in patterns]
    status = max((p["status"] for p in parts), key=lambda s: SEVERITY[s])
    ages = [p["newest_age_hours"] for p in parts if p["newest_age_hours"] is not None]
    return {
        "status": status,
        "mode": mode,
        "files": sum(p["files"] for p in parts),
        "newest_age_hours": min(ages) if ages else None,
        "patterns": parts,
    }


def _number(value, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ConfigError(f"{what} must be a positive number")
    return float(value)


def audit(config, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    if not isinstance(config, dict):
        raise ConfigError("config must be a JSON object")
    agents = config.get("agents")
    if not isinstance(agents, list) or not agents:
        raise ConfigError("config needs a non-empty \"agents\" list")
    default_age = _number(config.get("max_age_hours", DEFAULT_MAX_AGE_HOURS), "max_age_hours")
    rows = []
    for i, agent in enumerate(agents):
        if not isinstance(agent, dict) or not isinstance(agent.get("name"), str) or not agent["name"]:
            raise ConfigError(f"agents[{i}] needs a name")
        name = agent["name"]
        max_age = _number(agent.get("max_age_hours", default_age), f"{name}: max_age_hours")
        row = {"name": name, "max_age_hours": max_age}
        configured = 0
        for layer in LAYERS:
            if layer not in agent:
                row[layer] = {"status": SKIPPED, "files": 0, "newest_age_hours": None, "patterns": []}
                continue
            spec = agent[layer]
            if isinstance(spec, str):
                ok = bool(spec)
            else:
                ok = isinstance(spec, list) and bool(spec) and all(isinstance(p, str) and p for p in spec)
            if not ok:
                raise ConfigError(f"{name}: \"{layer}\" must be a path pattern or a list of them")
            mode = agent.get(f"{layer}_mode", "newest")
            if mode not in MODES:
                raise ConfigError(f"{name}: {layer}_mode must be one of {MODES}")
            time_field = agent.get(f"{layer}_time_field")
            if time_field is not None and (not isinstance(time_field, str) or not time_field):
                raise ConfigError(f"{name}: {layer}_time_field must be a field name")
            row[layer] = check_layer(spec, max_age, now, time_field, mode)
            configured += 1
        if not configured:
            raise ConfigError(f"{name}: configure at least one of {LAYERS}")
        row["gaps"] = [layer for layer in LAYERS if row[layer]["status"] in GAP_STATUSES]
        rows.append(row)
    return {
        "checked_at": datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds"),
        "agents": rows,
        "agents_with_gaps": sum(1 for r in rows if r["gaps"]),
        "ok": all(not r["gaps"] for r in rows),
    }


def cell(layer: dict) -> str:
    status = layer["status"]
    if status in (SKIPPED, MISSING, UNREADABLE):
        return status
    return f'{status} {layer["newest_age_hours"]}h ({layer["files"]})'


def short_list(files: list[str], limit: int = 5) -> str:
    names = ", ".join(os.path.basename(os.path.dirname(f)) + "/" + os.path.basename(f) for f in files[:limit])
    return names + (f" (+{len(files) - limit} more)" if len(files) > limit else "")


def gap_lines(r: dict) -> list[str]:
    out = []
    for layer in r["gaps"]:
        for p in r[layer]["patterns"]:
            st, where = p["status"], f"{r['name']} / {layer}"
            if st == MISSING:
                out.append(f"  - {where}: MISSING — nothing matches {p['pattern']}")
                continue
            if p["unreadable"]:
                out.append(f"  - {where}: UNREADABLE — {len(p['unreadable'])}/{p['files']} file(s) without a usable"
                           f" timestamp: {short_list(p['unreadable'])}")
            if p["stale"]:
                out.append(f"  - {where}: STALE — {len(p['stale'])}/{p['files']} file(s) older than"
                           f" {r['max_age_hours']:g}h: {short_list(p['stale'])}")
            elif st == STALE:
                out.append(f"  - {where}: STALE — newest file is {p['newest_age_hours']}h old"
                           f" (limit {r['max_age_hours']:g}h)")
    return out


def render(report: dict) -> str:
    header = ["agent", "chat", "results", "memory"]
    table = [header] + [[r["name"]] + [cell(r[l]) for l in LAYERS] for r in report["agents"]]
    widths = [max(len(row[i]) for row in table) for i in range(len(header))]
    lines = ["  ".join(v.ljust(widths[i]) for i, v in enumerate(row)).rstrip() for row in table]
    lines.insert(1, "  ".join("-" * w for w in widths))
    total, gaps = len(report["agents"]), report["agents_with_gaps"]
    lines.append("")
    lines.append(f"{total - gaps}/{total} agents fully synced." if gaps else f"All {total} agents fully synced.")
    for r in report["agents"]:
        lines.extend(gap_lines(r))
    lines.append("Cells: status, age of newest file, (file count). '-' = layer not configured.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check that every AI agent's chats, results and memory reached this machine.")
    ap.add_argument("--config", default=DEFAULT_CONFIG, help=f"config file (default: {DEFAULT_CONFIG})")
    ap.add_argument("--json", action="store_true", help="print the report as JSON (contains local paths)")
    ap.add_argument("--init", action="store_true", help="copy the example config to --config and exit")
    args = ap.parse_args(argv)

    if args.init:
        if os.path.exists(args.config):
            print(f"{args.config} already exists; not overwriting.", file=sys.stderr)
            return 2
        shutil.copyfile(EXAMPLE_CONFIG, args.config)
        print(f"Wrote {args.config}. Replace the placeholder paths with where each agent's files live on this computer.")
        return 0

    try:
        with open(args.config, encoding="utf-8") as fh:
            config = json.load(fh)
        report = audit(config)
    except FileNotFoundError:
        print(f"No config at {args.config}. Run with --init first.", file=sys.stderr)
        return 2
    except ValueError as exc:  # ConfigError and JSONDecodeError
        print(f"Config error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Read error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
