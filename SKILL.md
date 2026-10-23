---
name: multi-ai-sync
description: Use when someone runs several AI agents (e.g. Grok Bot + Claude Code, Cursor cloud agents + a local agent) and needs every agent's results and memory to actually reach one machine. Trigger on "can I see everything my bots produced", "results from the other AI are missing", "sync memory between my AIs", or when a scheduled pull from a cloud sandbox keeps timing out.
---

# Multi-AI Output & Memory Sync

Pick one machine (usually your laptop) as the place where facts live. Every other agent's **result files** and **memory** must land there, and your rules must flow back out. Chat transcripts alone are not enough.

## 1. Audit first — "readable" is not "received"

Check three layers separately, with numbers, before claiming coverage. `ai_sync_audit.py` in this repo does it from a small JSON config (see README for keys):

| Layer | Question |
|---|---|
| chat | Is there a local copy of every agent's conversation? |
| results | Did each agent's latest result file arrive, and is it fresh? |
| memory | Does each agent's memory exist locally, and is it fresh? |

Then ask a fourth question by hand: did anything downstream *use* the result, or was it left unparsed / rejected by a validator?

Typical finding: the chat shows a short summary, the full result sits in a file inside the agent's cloud sandbox, and nothing ever brought that file home.

**Judge freshness by the time the agent wrote inside the result, not the file's modified time.** A sync job rewrites files, so a two-week-old result copied an hour ago looks fresh. Use `results_time_field` (e.g. `observed_at`).

**Check every file, not just the newest.** In a folder with one result per agent, "the newest file is fresh" says nothing about the others. Use `results_mode: "every"`, or list each agent's exact path so one that never wrote anything shows as MISSING.

## 2. Diagnose the transport

Cloud agent sandboxes usually **sleep or drop off the network minutes after the agent goes idle**. A laptop-side schedule that pulls from the sandbox (SSH / VPN / tunnel) then fails most of the time — as timeouts, with no error anyone sees.

Signs: every remote node shows offline; pulls time out for all agents at once; the agents themselves are clearly working (fresh chat messages).

## 3. Fix — reverse the direction, let the agent push

Many agent products let the agent run commands on a connected computer. Use that:

1. Ask the main agent once to push its outbox to your machine at **the same relative paths**, keeping modification times and skipping very large files. Verify on disk (file count, one known file, today's timestamps), not from the agent's reply.
2. Make it incremental and scheduled **from your own machine's scheduler** (cron / launchd / Task Scheduler) — a small job that sends the agent a fixed "push files changed in the last N hours" message. Don't make the AI product's built-in scheduler the only clock.
3. Point your local consumers at the mirror as a fallback when the direct pull fails, and record which source served each result.
4. When the pushed copy and an older local copy differ, the newer agent-written timestamp wins; never let the copy time decide.
5. Don't loosen validators to let malformed results through. If an agent drifts from the schema (its own enum values, a missing field), tell that agent to fix its own routine and rewrite the result.

### Same pattern, other products

- **Cursor cloud agents**: the dashboard shows a title, last update and an opening snippet; the full transcript isn't readable from outside. The durable result is what the agent commits. Judge it by commit time (`git log -1 --format=%ct origin/<agent-branch>` after `git fetch`), not by ref-file mtime — `git fetch` touches refs and `git gc` packs them away. Ask the agent to commit a small receipt file (what it did, when, which checks passed) with each result.
- **Any agent without a computer connector**: have it paste the full structured result in chat inside a fixed marker block, and parse that. Accept that long results may be truncated; ask for a pointer to the full file.

## 4. Memory — sync both ways

- **Agent → local**: an agent's private memory is usually readable only by that agent. The main agent can't export its teammates' memory, so have it relay to each one: "export your own memory to `<mirror>/memory/<name>.md`, and rewrite it daily in your routine." Keep an `_index.md` with OK / UNREADABLE / NO_ROUTINE per agent.
- **Local → agent**: extend an existing daily routine (don't create a parallel one) to read files changed since the last run in your local memory folder, write the relevant rules into the agent's memory, and pass them to the team. Conflict rule: **the local file wins.**
- Never sync credentials, wallet addresses, amounts or client data into any memory. Scan exported files before trusting them.

## 5. Gotchas

- Your own safety guards may misread a harmless instruction (e.g. a read-only path that looks like a repo write). Rephrase it accurately; don't disable the guard.
- An agent replying "done" is not proof. Re-read the files.
- Some agents (inbox / notification roles) have no tools and can't export. Mark them; don't fake them.
- One run proves the path works. Keep the audit on a schedule so the next silent break shows up.

## Done when

- Every agent appears in the audit with a fresh result or an explained gap.
- Results arrive on your machine with no manual step, on your own scheduler.
- Memory exists locally per agent, and your rules show up in the agents' memory the next day.
