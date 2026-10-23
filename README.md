# multi-ai-sync

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**English** · [中文](README.zh.md)

For people who run more than one AI (Grok Bot + Claude Code, Cursor cloud agents + a local agent, …): find out which agents' results and memory never reached your machine, and fix it so they do.

> Copy into your AI agent: *Set up multi-ai-sync on this computer by following the official instructions at https://github.com/runesleo/multi-ai-sync/blob/main/install.md.*

## What you get

- **`ai_sync_audit.py`** — one read-only command that checks, per agent, whether its chats, result files and memory are on this machine and how fresh they are. Exit code 1 when anything is missing, stale or has no usable timestamp.
- **`SKILL.md`** — the method, written so any AI agent can follow it: audit, find out why results don't arrive, reverse the direction so the agent pushes, and sync memory both ways.

## Why

Being able to read an agent's chat is not the same as receiving its work. In the setup this came from, a team of cloud tracker agents wrote their real results into files inside their own sandboxes. The sandboxes went offline shortly after the agents went idle, so the scheduled pull from the laptop timed out — quietly — and most daily results never arrived. After switching to "the agent pushes to my machine", most of them arrived the same day, and this audit flagged the rest.

## How it works

```text
ai-sync.json (your agents + where their stuff should be)
        │
        ▼
ai_sync_audit.py  ──►  table / JSON: OK · STALE · MISSING · UNREADABLE per layer
        │
        ▼
gaps → SKILL.md: check the transport → agent pushes → memory both ways
```

**Output example** (illustrative numbers):

```text
agent        chat           results         memory
-----------  -------------  --------------  ------------
Cloud main   OK 0.2h (10)   OK 1.5h (50)    OK 1.0h (1)
Trackers     -              STALE 0.5h (5)  OK 1.0h (1)
Local agent  OK 0.0h (100)  -               OK 1.0h (20)

2/3 agents fully synced.
  - Trackers / results: STALE — 3/5 file(s) older than 26h: tracker-e/latest.json, tracker-d/latest.json, tracker-c/latest.json
Cells: status, age of newest file, (file count). '-' = layer not configured.
```

## Setup

```bash
git clone https://github.com/runesleo/multi-ai-sync.git
cd multi-ai-sync
python3 ai_sync_audit.py --init      # Windows: py -3 ai_sync_audit.py --init
```

Edit `ai-sync.json` — one entry per agent, a path pattern for each layer you care about:

```json
{
  "max_age_hours": 36,
  "agents": [
    {
      "name": "Trackers",
      "results": "~/ai-mirror/outbox/projects/*/latest.json",
      "results_mode": "every",
      "results_time_field": "observed_at",
      "memory": "~/ai-mirror/memory/trackers.md",
      "max_age_hours": 26
    }
  ]
}
```

| Key | Meaning |
|---|---|
| `chat` / `results` / `memory` | A glob (`*`, `**`) or a list of them. Leave a layer out if it doesn't apply (shown as `-`). |
| `<layer>_mode` | `newest` (default): the layer is fresh if its newest file is. `every`: every matched file must be fresh — use it for one-file-per-agent folders like `*/latest.json`. |
| `<layer>_time_field` | Read freshness from a top-level timestamp field inside a JSON object file, instead of the file's modified time. Use it for JSON results a sync job copies — a two-week-old result copied an hour ago otherwise looks fresh. If the field can't be read, the layer is `UNREADABLE`. |
| `max_age_hours` | Freshness limit, top-level default or per agent. |

Tip: for a fixed set of agents, list their exact paths (`"results": ["…/a/latest.json", "…/b/latest.json"]`) so an agent that never wrote anything shows as `MISSING` instead of silently not matching.

`*` matches one level and skips dot-files, as in Python's `glob`. Timestamps without a timezone are read as UTC.

**Any AI coding agent:** point it at `SKILL.md`. No framework lock-in.

## Requirements

- Python 3.9+, standard library only. macOS, Linux or Windows (`py -3` on Windows).
- **Privacy:** the audit reads file names and modification times, and fully parses JSON files you give a `*_time_field` for. It sends nothing anywhere. `--json` output contains your local paths; so does your config. `ai-sync.json` and `*.local.json` are git-ignored — keep custom configs under those names.

## Quick start

```bash
python3 ai_sync_audit.py              # table; exit 0 = all synced, 1 = gaps (table shows them), 2 = config/read error
python3 ai_sync_audit.py --json       # for scripts and scheduled checks
```

Put the `--json` run on a schedule (cron, launchd, Windows Task Scheduler) so the next silent break shows up on its own.

## Verified

| Case | Environment | Result |
|------|-------------|--------|
| Unit tests (`python3 -m unittest`) | macOS, Python 3.14 | 11 tests pass |
| Real setup: a cloud agent team + a local agent | macOS Apple Silicon | Caught a tracker whose result looked fresh by file time but was over a week old by its own timestamp |
| Push-instead-of-pull | Same setup | Most tracker results that hadn't been arriving arrived on the first day |

The push fix was observed in one setup over one day. Not run on Python 3.9 yet (syntax and stdlib use are 3.9-compatible). How your agent product connects to your computer may differ.

## Known limitations (v0.1)

- Checks presence and freshness — not whether a result is *correct* or was *used* downstream.
- Content timestamps: top-level field of a single JSON object only (no JSONL, no Markdown front-matter yet).
- Git branches as results (e.g. Cursor cloud agents) need commit time, which the audit doesn't read yet — see `SKILL.md`.
- Pushing files back needs an agent product that can run commands on your computer. Without that, fall back to structured results in chat (`SKILL.md`).

## Roadmap

- Commit-time check for git-based agents
- JSONL and front-matter timestamps
- Optional "used downstream" layer (a receipt per consumed result)

## About the author

*Leo ([@runes_leo](https://x.com/runes_leo)) — AI × Crypto independent builder, running a small team of AI agents with Claude Code, Grok Bot and Cursor.*

*[leolabs.me](https://leolabs.me) — writing · community · open-source tools · indie projects · all platforms.*

*[X Subscription](https://x.com/runes_leo/creator-subscriptions/subscribe) — paid content weekly, or just buy me a coffee 😁*

*Learn in public, Build in public.*

## License

[MIT](LICENSE)
