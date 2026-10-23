# Independent review — pass 2 (Cursor, read-only)

## Pass-1 blockers

| # | Pass-1 要点 | 结论 | 证据 |
|---|-------------|------|------|
| 1 | 一层多文件时默认只看 newest，易误报 OK；`*/latest.json` 场景 | **FIXED** | `every` 模式：`ai_sync_audit.py:115-120`（任一过龄即 STALE 并列出 `stale`）；层内多 pattern 取最严重：`ai_sync_audit.py:136`；文档与示例：`README.md:75-79`、`README.zh.md:77-81`、`examples/config.example.json:14-15`；测试：`tests/test_audit.py:51-60`。glob 仍无法匹配「从未建目录」的 agent，靠 `README.md:79` 明示路径列表——属 glob 局限，非 pass-1 主路径误报 OK。 |
| 2 | 配了 `*_time_field` 却读不出时间时静默回退 mtime | **FIXED** | `ai_sync_audit.py:87-94`（`time_field` 时 `t is None` → 年龄不可用，不走 mtime）；`ai_sync_audit.py:74-82`；`tests/test_audit.py:73-79`；`tests/test_audit.py:67-71`（内容时间压过新 mtime）。 |
| 3 | 无时区 ISO 按本机本地时区算年龄 | **FIXED** | `ai_sync_audit.py:48-71`（无 offset 视为 UTC）；`ai_sync_audit.py:69-70`；`tests/test_audit.py:81-86`；`README.md:81`、`README.zh.md:83`。 |
| 4 | 坏配置 / 扫描期 `OSError`  traceback，退出码与缺口同为 1 | **FIXED** | `ConfigError`：`ai_sync_audit.py:39-40`、`147-189`；`main` 捕获：`ai_sync_audit.py:262-274`（`FileNotFoundError` / `ValueError` / `OSError` → stderr 一句 + **2**）；`tests/test_audit.py:102-109`、`111-133`（含无 traceback）。扫描中 `getmtime` 的 `OSError` 会冒泡到 `except OSError`（`ai_sync_audit.py:91` → `:272-274`）。 |
| 5 | `install.md` 遇阻即停，与退出码 1/2 及 `--init` 流程矛盾 | **FIXED** | `install.md:5-7`（1=正常缺口、表格在 stdout；2=配置/读错、无 config 则 `--init`）；`install.md:33`（0/1 均算成功并展示表格）；`ai_sync_audit.py:12` 与 docstring 一致。 |
| 6 | README 写真实规模数字，应改为虚构示例 | **FIXED** | `README.md:32-44`、`README.zh.md:34-46`（标明示意数字）；`README.md:99-107`、`README.zh.md:101-109`（实测表无 tracker 计数/小时数堆砌，并限定观察范围）。 |

---

## New 🔴

本轮只读对照与 `python3 -m unittest tests.test_audit`（11 passed）下，**未发现**新的发布级 🔴（正确性误报已同步、文档与实现严重冲突、仓库内隐私泄漏）。

说明（不构成 🔴，但未达 pass-1 全部 🟡 收口）：

- 默认 `newest` 仍可能掩盖同层其他过期文件；依赖用户为 `*/latest.json` 配 `every` 或读文档——与 pass-1 采用的修法一致，示例已带 `every`。
- `CHANGELOG.md:8` 仍写 OK/STALE/MISSING，未写 `UNREADABLE`，与实现略不一致（文档瑕疵，非运行时错误）。

---

## 🟡

（延续 pass-1 或第二轮仍可见；不挡发布，但 worth 跟）

| 项 | 位置 | 说明 |
|----|------|------|
| `newest` 默认语义 | `ai_sync_audit.py:115-120`、`tests/test_audit.py:56` | 未配 `every` 时「多数过期、一个最新」仍为 OK；文档已强调，代码默认未改。 |
| glob 无法代表「应有但未建目录」的 agent | `README.md:79`、`examples/config.example.json:13` | 示例仍用 `projects/*/latest.json`；缺目录不会单独 MISSING，需显式路径列表。 |
| 不可读目录 vs MISSING | `ai_sync_audit.py:43-45`、`102-105` | 权限等问题常变成 MISSING（退出 1），非配置类 2。 |
| Git 结果层 | `SKILL.md:46`、`README.md:113-114` | 仍建议手工 `git log` 看 commit 时间，审计未实现 commit-time。 |
| `--config` 非默认文件名 | `.gitignore:1-2`、`README.md:88` | 仅忽略 `ai-sync.json` / `*.local.json`；自定义 config 名仍可能被误 commit。 |
| 安装链接固定 `main` | `README.md:9`、`README.zh.md:9`、`install.md:15` | 当前分支为 `release/v0.1.0`；若 `main` 尚未含 v0.1.0，链可能超前或滞后。 |
| `install.md:3` vs `:5-7` | `install.md:3` | 仍写「步骤受阻就停」，与「退出 1 不是失败」并存；靠后文消歧，粗心 agent 可能误停。 |
| `CHANGELOG` 与能力表 | `CHANGELOG.md:8` | 未列出 `UNREADABLE` / `every` 在首条 bullet 的完整状态集。 |
| `every` + STALE 的单元格文案 | `ai_sync_audit.py:204`、`243` | 表头仍写 newest file 年龄；`every` 下可为 `STALE 0.5h (13)` 而 gap 行才列 11/13——略绕。 |

---

VERDICT: READY
