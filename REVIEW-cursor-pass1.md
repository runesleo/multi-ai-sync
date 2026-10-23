# Independent review — pass 1 (Cursor, read-only)

Reviewed v0.1.0 draft before first publish. All 🔴 blockers were fixed in the following commit; see pass 2.

这份仓库现在按原样公开会把「没同步」报成已经同步。下面按代码和四份说明对照，本机没有 Python 3.9，3.9 的结论来自语法和标准库范围，不是实跑。

## 🔴 Blockers

- `ai_sync_audit.py:62`（退出在 `:149`；承诺在 `README.md:13`、`README.zh.md:13`；示例在 `examples/config.example.json:12`）一层里有多份文件时，OK/STALE 和退出码只看时间最新的那一份。`projects/*/latest.json` 这种 glob 在一组 tracker 里只要有少数是新的，就会显示 OK、退出码 0，其余过期的不会出现；还没生成的文件 glob 也列不出来。页脚 `:118` 写的是 newest file，和 README 第一屏「有缺或过期就返回 1」、以及「剩下的自查会标出来」对不上。修法：任一匹配文件超过 `max_age_hours` 就让该层 STALE；每个 tracker 写具体路径，文件不存在才是 MISSING。

- `ai_sync_audit.py:61`（`tests/test_audit.py:63` 把这个结果写成了期望）配了 `*_time_field` 之后，缺字段、JSON 数组、JSONL（`json.load` 遇到第二行就失败）、以及 3.9 的 `fromisoformat` 不接受的字符串（小写 `z`、无冒号的 `+0000`、超过 6 位小数），都会改用文件 mtime。同步刚拷完时 mtime 是现在，这一层变成 OK；这份文件又常常是最新的，会盖住同目录里已经解析出来的旧时间。修法：配了时间字段却读不出来就记为缺口，mtime 只在没配 `*_time_field` 时使用，并改掉该断言。

- `ai_sync_audit.py:47` 没有偏移的时间会交给 naive datetime 的 `.timestamp()`，按这台电脑的本地时区换算。同一串 `2026-10-23T00:00:00`，在 UTC+8 上年龄多 8 小时，在 UTC-5 上少 5 小时，26 小时门槛两边可以一边 STALE、一边 OK。修法：无偏移的时间固定按 UTC 解析，或者直接当成解析失败走上面的缺口。

- `ai_sync_audit.py:144` 配置根不是对象、`agents` 或 `max_age_hours` 为 null、路径写成数组，以及扫描中途 `getmtime` 抛 `OSError`，都不在捕获列表里。进程以 traceback 退出，退出码仍是 1，和「有缺口」相同。修法：这些情况返回 2，并在 stderr 留一句配置或读取错误。

- `install.md:3`（命令在 `:7`、`:27`）说明要求步骤受阻就停。仓库刚克隆、还没有 `ai-sync.json` 时退出码是 2；有缺口时退出码是 1。按字面执行的 agent 会停在第一次审计，不展示表格，也不去 `--init`。修法：写明 1 表示有缺口、stdout 的表格就是结果，2 才执行 `--init`，这两步都继续。

- `README.md:18`（中文 `README.zh.md:20`；示例 `README.md:39`、`README.zh.md:41`；实测 `README.md:97`、`README.zh.md:99`）稿子里写了这次真实运行的具体规模（tracker 数量、到达数量、小时数、示例表的文件数）。修法：改成标明虚构的整数例子；案例保留「多数结果没到，改成推送后当天大部分到了」。

## 🟡 Warnings

- `README.md:72`（中文 `README.zh.md:74`；限制写在 `README.md:104`）设置段要求凡是同步拷来的文件都配时间字段，限制段写只支持 JSON 顶层字段。示例里的 memory 是 Markdown，对话是 JSONL，配了字段也会掉进 mtime。修法：把第 72 行改成只对单个 JSON 对象的顶层字段有效。

- `README.md:79`（定时在 `:89`）要求写了 Windows，命令全是 `python3`，定时只写了 cron / launchd。修法：Windows 改成 `py -3`，并补上 Task Scheduler（`SKILL.md` 里已经有）。

- `SKILL.md:43`（示例 `examples/config.example.json:24`）用 `.git/refs/...` 的 mtime 当结果时间。`git fetch` 会把旧 commit 刷成刚刚更新；`git gc` 打进 `packed-refs` 后这些文件消失，审计报 MISSING。修法：改用 commit 时间，并写明 pack 之后这条 glob 无效。

- `ai_sync_audit.py:33`（测试 `tests/test_audit.py:68`）`*` 只匹配一层、不匹配点号开头的名字；目录没有权限时 `glob` 得到空列表，这一层变成 MISSING，退出码 1。递归测试只造了 `o/deep/er/r.md`。`**/*.md` 按 `glob` 的分层规则会包含该目录下一层的文件，这里没有 Python 3.9，这条没跑过。修法：文档写明 `*` 与点号文件的范围；目录不可读单独报错；用 3.9 补一个「文件就在 `**` 下一层」的测试。

- `ai_sync_audit.py:53`（汇总在 `:84`、`:111`）层的值是 JSON `null`，或一个 agent 三层都没写，会当成未配置，退出码可以是 0。修法：键不存在才是 SKIPPED；值为 null，或一个 agent 一层都没有，返回 2。

- `ai_sync_audit.py:65`（展示用 `:67` 的 `round`，文案在 `:116`）比较用的是未舍入的小时，打印是一位小数，所以会出现 `26.0h old (limit 26h)` 仍然 STALE。未来时间的年龄是负数，比较同样通过，状态是 OK。修法：用同一套非负年龄做判断，未来时间算缺口。

- `ai_sync_audit.py:46` 秒（约 1e9）和毫秒（约 1e12）的分界是对的。微秒、纳秒只除一次 1000，会落在很远的未来，年龄为负，状态 OK。修法：按数量级连续换算到秒，换不干净就当解析失败。

- `README.md:80`（实现 `ai_sync_audit.py:44`、`:68`；忽略规则 `.gitignore:1`）说明写的是只读文件名、mtime 和可选的一个时间字段。`json.load` 会解析整份 JSON；`--json` 的 `newest` 是展开后的绝对路径，里面有用户名；gitignore 只忽略默认文件名 `ai-sync.json`。修法：写明会整份解析、报告含本机路径、不外发，并把任意 `--config` 文件名也排除出 git。

- `install.md:12`（相对命令在 `:27`；链接在 `README.md:9`）Claude 只要求复制 `SKILL.md`，没写 Claude Code 技能目录下的 `multi-ai-sync/` 文件夹，技能目录里也没有脚本。第 5、7 步是相对路径，换一个 shell 就找不到。链接写死 `blob/main`，当前分支是 `release/v0.1.0`。修法：技能目录同时放脚本，步骤用绝对路径，链接改到 tag `v0.1.0` 或先确认 `main` 上已有这份文件。

- `examples/config.example.json:6` `--init` 放进去的是像某台 Mac 上的真实布局（`sand-client-persistence`、`~/.claude/projects/**/*.jsonl`）。agent 经常照抄，目录一对不上就一直 MISSING。修法：改成明显的占位符，并写上必须对照本机改。

- `README.md:18` 前半把「沙箱闲置几分钟就断网、本机拉取静默超时」写成普遍情况，范围说明在 `:99`，只是一套环境、一天。修法：这两句改成同一次观察里发生的事。

- `SKILL.md:36` 要求按相同相对路径推送，结果文件没有冲突规则（记忆部分 `:49` 才写本机文件优先）。`SKILL.md:54` 把本机 guard 对目录名 `Projects` 的匹配写进了公开说明。修法：结果文件补上同一条冲突规则，删掉 `Projects` 这句。

## 🟢 OK

- `ai_sync_audit.py:12` 有 `from __future__ import annotations`，`float | None` 和 `list[str]` 在 3.9 导入时不会求值。文件里没有 `match`、海象运算符或其他 3.10 才有的语法，标准库即可启动。

- `ai_sync_audit.py:33` 已把 `recursive=True` 传给 `glob.glob`。示例里的 `**/*.md`、`**/*.jsonl` 会匹配这一层和子目录；那条「模式以 `**` 结尾时只匹配目录」的旧限制，示例没有用到。

- `ai_sync_audit.py:47` 把大写 `Z` 换成 `+00:00`。`tests/test_audit.py:58` 那种无小数的 `Z` 属于 3.9 `fromisoformat` 能解析的格式；单文件、字段能解析时，内容时间会压过刚拷贝的 mtime（同测试 `:61`）。`:46` 对当前的秒和毫秒数值也是对的。

- `ai_sync_audit.py:141` 与 `README.md:85` 对齐：全齐是 0，有缺口是 1，文件缺失、坏 JSON、空 `agents`、缺名字、`--init` 拒绝覆盖是 2。错误在 stderr；`--json` 在这条成功路径上 stdout 只有 JSON。人类表格不含路径。

- 全仓库没有用户名、没有 `/Users/...`、没有密钥。`runesleo` 和作者链接是公开身份。具体文件路径不存在时是 MISSING，`install.md:17` 对字面路径是成立的。
