# multi-ai-sync

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[English](README.md) · **中文**

同时用好几个 AI 的人（Grok Bot + Claude Code、Cursor 云端 + 本机 AI……）：查出哪些 AI 的产出和记忆根本没到你电脑上，再把它们接通。

> 复制给你的 AI：*按照 https://github.com/runesleo/multi-ai-sync/blob/main/install.md 的官方说明，在这台电脑上安装 multi-ai-sync。*

## 作为插件安装

- **Claude Code**（2.1.275 及以上）：`/plugin install multi-ai-sync --marketplace runesleo/x-reader`
- **Codex**：先 `codex plugin marketplace add runesleo/x-reader`，再 `codex plugin add multi-ai-sync@runesleo`

`runesleo` 插件市场里还有 Leo 的其他工具，见 [runesleo/x-reader](https://github.com/runesleo/x-reader)。

## 你会得到

- **`ai_sync_audit.py`**：一条只读命令，逐个 AI 检查三样东西在不在这台电脑上、新不新：对话、结果文件、记忆。有缺的、过期的、读不出时间的，就返回 1。
- **`skills/multi-ai-sync/SKILL.md`**：一套任何 AI 都能照着做的方法——先盘点，再查为什么收不到，把方向反过来让 AI 主动推，最后记忆双向同步。

## 为什么要做

能读到 AI 的对话，不等于收到了它干的活。

我这边的情况：一组跑在云端的盯项目 Bot，把正经结果写在各自云电脑里的文件中。它们一闲下来，云电脑没多久就断网，我从本机定时去拉，次次超时，还不报错，每天大部分结果都没到。改成「让 Bot 自己推回我电脑」之后，当天大部分就到了，剩下的这个自查也标了出来。

## 怎么运作

```text
ai-sync.json（你有哪些 AI、它们的东西应该在哪）
        │
        ▼
ai_sync_audit.py  ──►  表格 / JSON：每层 OK · STALE（过期）· MISSING（没有）· UNREADABLE（读不出时间）
        │
        ▼
有缺口 → 按 skills/multi-ai-sync/SKILL.md：查通路 → 改成 AI 主动推 → 记忆双向同步
```

**输出示例**（数字是示意）：

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

## 安装

```bash
git clone https://github.com/runesleo/multi-ai-sync.git
cd multi-ai-sync
python3 ai_sync_audit.py --init      # Windows 用 py -3 ai_sync_audit.py --init
```

改 `ai-sync.json`：每个 AI 一条，想查哪一层就填路径：

```json
{
  "max_age_hours": 36,
  "agents": [
    {
      "name": "盯项目 Bot",
      "results": "~/ai-mirror/outbox/projects/*/latest.json",
      "results_mode": "every",
      "results_time_field": "observed_at",
      "memory": "~/ai-mirror/memory/trackers.md",
      "max_age_hours": 26
    }
  ]
}
```

| 字段 | 含义 |
|---|---|
| `chat` / `results` / `memory` | 一个通配路径（`*`、`**`）或一组路径。用不到的层不写，表格里显示 `-`。 |
| `<层>_mode` | `newest`（默认）：最新那份是新的就算新。`every`：每一份都要新——像 `*/latest.json` 这种一个 Bot 一份的目录要用它，不然 10 个里只要 1 个是新的就会显示 OK。 |
| `<层>_time_field` | 按 JSON 文件里 AI 自己写的时间（顶层字段）算新旧，不按文件修改时间。同步任务拷过来的 JSON 结果都要配——不然两周前的结果一小时前刚拷过来，看起来也是新的。读不出这个字段就标 `UNREADABLE`。这是我实际踩到的坑。 |
| `max_age_hours` | 多久算过期，可以全局设，也可以每个 AI 单独设。 |

小技巧：AI 是固定那几个的话，把每个的确切路径列出来（`"results": ["…/a/latest.json", "…/b/latest.json"]`），这样从来没写过文件的那个会显示 `MISSING`，而不是悄悄匹配不到。

`*` 只匹配一层、不匹配点号开头的文件，跟 Python 的 `glob` 一样。没写时区的时间按 UTC 算。

**任何 AI 编程助手**：让它读 `skills/multi-ai-sync/SKILL.md` 就行，不绑定框架。

## 环境要求

- Python 3.9+，只用标准库。macOS、Linux、Windows 都行（Windows 用 `py -3`）。
- **隐私**：自查读文件名和修改时间；配了 `*_time_field` 的 JSON 文件会整份解析。不往任何地方发数据。`--json` 的输出和你的配置文件里都有本机路径；`ai-sync.json` 和 `*.local.json` 已写进 `.gitignore`，自己的配置文件请用这两种名字。

## 快速上手

```bash
python3 ai_sync_audit.py              # 表格；0 = 全齐，1 = 有缺口（表格里列出来），2 = 配置或读取错误
python3 ai_sync_audit.py --json       # 给脚本、定时检查用
```

把 `--json` 那条挂成定时任务（cron、launchd、Windows 任务计划程序），下次再悄悄断掉会自己冒出来。

## 实测

| 场景 | 环境 | 结果 |
|------|------|------|
| 单元测试（`python3 -m unittest`） | macOS，Python 3.14 | 11 个测试通过 |
| 真实环境：一组云端 Bot + 本机 AI | macOS Apple Silicon | 抓到一个 Bot：按文件时间看是新的，按它自己写的时间已经一周多没更新 |
| 拉改推 | 同上 | 之前收不到的结果，第一天大部分就到了 |

拉改推只在我这一套环境里观察了一天。还没在 Python 3.9 上实跑（语法和标准库用法兼容 3.9）。你的 AI 产品怎么连你的电脑可能不一样。

## 已知限制（v0.1）

- 只查有没有、新不新，不查结果对不对、下游有没有用上。
- 文件内时间只支持单个 JSON 对象的顶层字段（还不支持 JSONL、Markdown front-matter）。
- 用 git 分支交结果的 AI（比如 Cursor 云端）要看提交时间，自查目前还不读提交时间，做法见 `skills/multi-ai-sync/SKILL.md`。
- 让 AI 推文件回来，前提是你的 AI 产品允许它在你电脑上执行命令；不支持的话，退回「在对话里贴结构化结果」（见 `skills/multi-ai-sync/SKILL.md`）。

## 计划

- 支持按 git 提交时间检查
- 支持 JSONL、front-matter 里的时间
- 可选的「下游用上了没」一层（每个被消费的结果留一份回执）

## 关于作者

*Leo（[@runes_leo](https://x.com/runes_leo)）— AI × Crypto 独立构建者，用 Claude Code、Grok Bot、Cursor 带一支 AI 小团队干活。*

*[leolabs.me](https://leolabs.me) — 写作 · 社群 · 开源工具 · 独立项目*

*[X 订阅](https://x.com/runes_leo/creator-subscriptions/subscribe) — 付费内容周刊*

*Learn in public, Build in public.*

## 许可

[MIT](LICENSE)
