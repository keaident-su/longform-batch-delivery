# longform-batch-delivery · 长文本分批交付协议 (LFBD v9)

> **一句话**：先测产出、再排期；每轮都有账本；差多少永远秒答；不许用短段落注水。
> **v8 一句话**：**"完成"不是你说了算，是退出码说了算**（`run_state.py gate` exit 0）。
> **v9 一句话**：**先把轮数算出来**（x = 目标 ÷ 上限×0.8），再按 GENERATE→AUDIT→REPAIR→DONE 转，非 DONE 不停。
> **One-liner**: calibrate throughput first, keep a disk ledger, always know the exact shortfall, never pad with stub units.
> **v8**: "done" is an **exit code** — `0=DONE, 1=keep writing, 2=fix first`. Never end a turn with a question.

[简体中文](#为什么你用了技能还是没写完) ｜ [English](#why-it-still-didnt-finish)

---

## 为什么你用了技能还是没写完

v5 收到最多的抱怨是："我用了这个技能，怎么还是没写完？"

根因不在技能"没生效"，而在四个**真实约束**：

| 编号 | 约束 | v5 的病 | v6 的药 |
|---|---|---|---|
| **R1** | 单轮输出有硬上限（约 8,000–12,000 中文字符），提示词改不掉 | 用户以为"分批＝每轮会自己接着写" | 明确宣布轮数；用户说"全部写完"时，**一轮内连续跑批**，不问"继续吗" |
| **R2** | **真实吞吐必须实测**：实测常出现单块只有 300–600 字，而不是你以为的 1,500 字 | 用"每轮一万字"估值排期，严重乐观 | 第 1 批结束立刻标定 `字/块`、`字/轮`，用实测值重排 |
| **R3** | 用"补充场/附录"堆量会做出**空心稿**：块多、字少、主线没走 | 只统计总字数，不查单块体量 | **单元字数地板（G9）**：低于地板即失败，并自动生成补写清单 |
| **R4** | 多轮/并行运行会把同一编号写两遍 | 无写者约束、无重号检测 | **单写者锁** + 构建前**重号即失败（G8）** |

**记住 R1：只要 目标字数 ÷ 单轮上限 > 1，"一轮写完"在数学上就不成立。** 这不是能力问题，是算数问题。

---

## 30 秒上手

```bash
# 0) 放好你的源目录，比如 scenes/
# ---- 【v8 主路线】停止谓词驱动：跑到 exit 0 为止，中途不问不倚 ----
python scripts/run_state.py init --target 170000 --cap 12000 --util 0.8 \
    --glob "scenes/act4*_*.txt" --prefix act4
python scripts/run_state.py next     # 当前阶段 + 该干什么（exit 1=继续写 / 2=先修 / 0=可停）
python scripts/run_state.py plan     # 作业单：轮次 n/x、单元数、每单元最少多少字
python scripts/run_state.py count    # 多路核字数（汉字/含标点/去空白/docx）
#   ……写正文，落盘（正文不进聊天）……
python scripts/run_state.py tick --added 9200 --units 5 --cursor 214
python scripts/run_state.py gate     # 退出码 0=DONE ／ 1=继续写 ／ 2=先修问题
python scripts/run_state.py resume   # 需要续跑时，把这一行贴回对话框

# ---- 【v6/v7 路线】账本 + 结构校验 + 内容扫描（保留） ----
# 1) 初始化账本（目标 17 万中文字符）
python scripts/ledger.py init --target 170000 --parts "上册:238" "下册:0"

# 2) 写第 1 批，然后校验 + 拿到"下一批作业单"（--strict 可作停止谓词用于 CI）
python scripts/build_and_verify.py --target 170000 --strict

# 3) 记录本批实测吞吐（这一步会算出"还需几轮"）
python scripts/ledger.py update --added 9200 --blocks 15 --cursor 200

# 4) 任何时候问"还差多少"
python scripts/size_report.py --dir scenes --glob "*.txt" --target 170000

# 5) 【v7】内容级检查：重复/事实冲突/跨来源拼接（带逐场对照表）
python scripts/dedupe_scan.py scenes --cross-table --out g10.txt
```

---

## v9 相对 v8 新增了什么（把"跑几轮"先算出来）

v8 能拦住"提前收工"，但它没回答一个前置问题：**这活儿一共要跑几轮？**

v9 把它变成契约：

```
x = ceil(目标字数 ÷ (单轮输出上限 × 0.8))
```

目标 17 万字、单轮上限 12,000 字 → `x = ceil(170000 ÷ 9600) = 18 轮`。

| 步骤 | 机器实现 |
|---|---|
| ① 设轮数 x | `init --cap 12000 --util 0.8` → 写入 `rounds_planned` |
| ② 先跑满 x 轮 | `plan` 给作业单；`tick` 记 `轮 n/x` |
| ③ 多方式查字数 | `count`：汉字／含全角标点／去空白／总字符／交付 docx |
| ④ 不够就补 | `gate` exit 1（GENERATE）→ 继续写 |
| ⑤ 够了再排查 | `gate` 自动进入 AUDIT |
| ⑥ 全过才停 | `gate` exit 0（DONE），否则 exit 2（REPAIR / BLOCKED） |

新增 `next`：一句话告诉你现在是哪个阶段、该干什么。

### v9.1：把接续次数再砍一截

一个回合里可以塞进多次模型输出——只要中间夹着工具调用（这一条在 Chatbox 里成立：
助手的单次回复可以包含十几次工具调用）。所以 v9.1 规定：**块与块之间不得收尾**。

```bash
python scripts/run_state.py init --target 170000 --cap 12000 --util 0.8 --chunks-per-turn 3
# → 轮数 x = 18 轮
# → 需你接续的次数 ceil(18 / 3) = 6 次
```

`plan --chunks 3` 一次给出连续 3 块的作业单；`init` 直接把“需你接续的次数”打印出来。

| 量 | 含义 |
|---|---|
| `x` | 需要多少次模型输出（语义上的“轮”） |
| `k` | 一个回合里链式跑几块 |
| `turns_needed ≈ ceil(x / k)` | **你实际需要接续的次数** |

> 诚实说明：k 受 harness 迭代上限约束，不是无限大，所以这个数是“约”；
> 而 **x（总输出量）根本不可压缩**——能压的只是接续次数。

### v9.2：把真正的边界核实完了

Chatbox 官方文档写明：**Work Mode 本身就是循环**（think → call tool → read result → repeat until done），
唯一的硬边界是——

> it automatically pauses after **25 consecutive tool calls** so you can check it is on track, then continue.

这条**不可配置**。于是 v9.2 做了三件事：

1. **铁律 8 收紧**：块与块之间不得输出任何消息；**正文一律通过 `write_file` 落盘**
   （每次写入都算一步工具调用，循环继续）。
2. **强制 Work Mode**：Chat Mode 不注入任何工具，根本没有循环。
3. **把“点几次 Continue”算出来**：`init` 直接打印「预计只需点 N 次 Continue」；
   实测偏了就跑 `calibrate` 用真实数据重算 x 与窗口数。

| 问题 | 能否修复 |
|---|---|
| 块之间不该停 | ✅ 铁律 8（块间不得输出消息） |
| 不该在 Chat Mode 跑长文 | ✅ 强制 Work Mode |
| 每 25 步暂停 | ❌ 产品护栏，只能点 Continue |
| 总输出量 x | ❌ 内容量，不可压缩 |

**最严口径**：`gate` 判字数时取 `min(源文件汉字, docx 汉字)`——
"源文件够、生成的 docx 却漏内容"不会再被误判成达标。

---

## v8 相对 v7 新增了什么（解决"用了技能还是停"）

前面所有版本都在教你**怎么写好**。没有任何一版能**阻止**你提前宣布完成。
真实事故：目标 170,000 字，写到 27,822 字（16.4%）就"交付"，末尾还附一句
"要不要先出上册，回我一句"——那只是变相的"停下来问"。

v8 就干一件事：**把"完成"变成退出码。**

| 机制 | 文件 | 说明 |
|---|---|---|
| **M1 停止谓词** | `scripts/run_state.py gate` | 退出码 `0=DONE / 1=RUNNING / 2=BLOCKED`。**非 0 一律不许停。** |
| **M2 轮末契约** | `templates/turn_contract.md` | 每轮只许以 `✅ DONE` 或 `⏩ RESUME` 结尾，禁止任何提问/征询/提议 |
| **M3 吞吐升级梯** | `run_state.py tick` | `cpu = max(地板×1.4, 上轮cpu×1.35)`，`units = 预算÷cpu`——靠算术逼单块变长 |
| 自测 | `_selftest/selftest.py` | 12 项断言，覆盖三种退出码 + 重号/时间倒流/G10 反向用例 |

以前你遇到的那种结尾（"如果你希望现在就先拿一份……回我一句"）在 v8 下属于**违规**：
它既不是 `✅ DONE`，也不是 `⏩ RESUME`。

---

## v7 相对 v6 新增了什么（必须知道）

v6 的 G1–G9 全部是**形式**闸门（字数/编号/时间/字段/结构/退化/可打开/重号/地板）。
它们有一个共同盲点：**一份"看起来完全合规"的稿子，内容可以是互相打架的。**

真实事故：底稿是 A 路写的，B 路后来往同一场次下面追加了一条补充场——

- 主场次写"安撞门救人"，新补充场把**同一件事换词又写了一遍**，时间戳却标成第二天；
- 小晚的来因一处写"跟妈妈来旅游偶遇"、一处写"跟他约好吃饭"；
- 到场人数一处三人、一处四人；绑具一处布条、一处胶带。

**编号/时间/字段/字数全对，G2~G9 一个都没拦住。** v7 就是为这一类事故而加。

1. **G10 内容重复/事实冲突闸门**（四路判据）：逐字重复、同场事实冲突、"换词重写主场次"、正文日期错位。
2. **`scripts/dedupe_scan.py`**：实现 G10，并可用 `--cross-table` 输出**逐场对照表**（时间/地点/人物/量词/道具 并排）。
3. **§7.5 跨来源接管前置检查**：接手别人底稿/更早批次时，**动笔前**先跑 G10，逐场对位；同一事件的细节一律沿用底稿已立的那一版。
4. **已知局限（诚实说明）**：语义级"换词重写"字面相似度很低，自动化只给线索，最终裁定靠人看对照表。

---

## v6 相对 v5 新增了什么

1. **吞吐标定**：不再用估值排期，用第 1 批实测值重排剩余轮数。
2. **G9 单元字数地板 + 自动作业单**：把"还差多少"变成一张可以直接照着写的清单；明确告诉你**要加长单块，而不是增加块数**。
3. **G8 重号/污染检测 + RUN.lock 单写者锁**：并行运行或换会话时，不会再把同一编号写两遍。
4. **`publish_github.py`**：把技能整体推送到 GitHub，**全程 UTF-8 + base64**，中文描述不再变成 `????`。
5. **第 4 条铁律**：用户说"全部写完"时，必须一轮内链式跑批，不许中途问"要继续吗"。
6. **排障表**：症状 → 原因 → 动作，直接对着你踩过的坑。

---

## 验收闸门

| 闸门 | 判据 |
|---|---|
| G1 字数 | 累计字数单调增长且 ≥ 本批承诺 |
| G2 编号 | 主编号无跳号、无重号 |
| G3 时间线 | 时间戳严格递增、零倒流 |
| G4 字段 | 每单元必填字段齐全 |
| G5 结构 | 集/卷/章标题齐全 |
| G6 退化 | 无碎片断句、无连续空行 ≥3 |
| G7 交付 | docx/pdf 可打开 |
| **G8 重号污染** | 同编号不出现在两个文件；扫描范围外文件=污染 |
| **G9 单元地板** | 每单元字数 ≥ 地板，并输出补写清单 |
| **G10 内容重复/事实冲突** | 无逐字重复段落；同场各块事实不打架；补充场不换词重写主场次；正文日期不与时间字段脱节（`dedupe_scan.py`） |
| **P0 停止谓词（v8+）** | `run_state.py gate` 退出码 `0=DONE / 1=GENERATE / 2=REPAIR｜BLOCKED`；**非 0 即不许停、不许写"完成"** |

---

## 目录结构

```
SKILL.md                      主协议（v8）
README.md / README.en.md      中英文说明
docs/workflow.zh.md           中文工作流
docs/workflow.en.md           English workflow
scripts/ledger.py             账本：init / update / show / next
scripts/run_state.py          【v9】轮数契约 + 四阶段 + 停止谓词 + 轮末契约 + 吞吐升级梯
scripts/build_and_verify.py   重建 + G2–G9 + 下一批作业单（`--strict` 可作停止谓词）
scripts/size_report.py        目标/当前/还差/完成度/还需几轮
scripts/publish_github.py     推送技能到 GitHub（UTF-8 安全）
scripts/dedupe_scan.py        【v7】G10：内容重复/事实冲突/跨来源拼接冲突 + 逐场对照表
templates/                    账本、分批计划、**轮末契约卡片**（turn_contract.md）
_selftest/selftest.py         【v8】停止谓词回归测试（12 项断言）
```

---

## 协议要点（SKILL.md 摘录）

- **铁律 1**：不许承诺"一轮写完"。
- **铁律 2**：正文只落盘，不进聊天。
- **铁律 3**：每批结束必须重建＋校验＋汇报，汇报必含 `目标/当前/还差/完成度`。
- **铁律 4**：用户说"全部写完"时，一轮内连续跑批，不问"要继续吗"。
- **铁律 5**：**"完成"必须由退出码证明**——`run_state.py gate` 非 0 不得收工。
- **铁律 6**：**轮末只许两种结尾**——`✅ DONE` 或 `⏩ RESUME`，禁止任何提问。
- **铁律 7**：**先算轮数再开写**——`x = ceil(目标 ÷ (单轮上限×0.8))`；但跑满 x 轮 ≠ 完成，验收只看 `gate`。
- **骨架先行**：先出全量骨架（编号＋一句锚点＋计划字数），再逐段填正文，填的时候不许改编号。
- **断点续写**：用户只说"继续"时，读账本 → 取游标 → 按实测吞吐算范围 → 直接写，不重问需求。

---

## License

MIT © keaident-su

---

## English

### Why it still didn't finish

v5's most common complaint: *"I used the skill, so why does it still fall short?"*

Four hard constraints, not a prompt problem:

1. **R1 — Per-response output cap** (~8k–12k CJK chars). If `target ÷ cap > 1`, a single turn *cannot* finish it. Only arithmetic.
2. **R2 — Throughput must be measured, not guessed.** In practice a "block" often comes out at 300–600 chars, not the 1,500 you assumed.
3. **R3 — Padding with stub units produces hollow drafts.** v6 adds a **per-unit character floor (G9)** and an auto-generated top-up worklist.
4. **R4 — Parallel/multi-session runs duplicate IDs.** v6 adds a **single-writer lock (`RUN.lock`)** and fails the build on duplicates **(G8)**.

### What's new in v8

Every earlier version taught you how to write *well*. None could **stop you from declaring victory early**.
Real incident: target 170,000 chars, "delivered" at 27,822 (16.4%), ending with
*"want a first volume now? just say the word"* — a question in disguise.

v8 does one thing: **turns "done" into an exit code.**

| Mechanism | File | What it does |
|---|---|---|
| **M1 Stop predicate** | `scripts/run_state.py gate` | `0=DONE / 1=RUNNING / 2=BLOCKED`; **non-zero means you may not stop** |
| **M2 Turn-end contract** | `templates/turn_contract.md` | End every turn with `✅ DONE` or `⏩ RESUME` — never a question |
| **M3 Escalation ladder** | `run_state.py tick` | `cpu = max(floor×1.4, prev_cpu×1.35)`, `units = budget÷cpu` — forces longer units |
| Self-test | `_selftest/selftest.py` | 12 assertions across all three exit codes plus duplicate/timeline/G10 regressions |

### Quick start

```bash
# v8 main path — stop-predicate driven
python scripts/run_state.py init --target 170000 --glob "scenes/act4*_*.txt" --prefix act4
python scripts/run_state.py plan     # work order: N units × M chars each
python scripts/run_state.py tick --added 9200 --units 5 --cursor 214
python scripts/run_state.py gate     # 0=DONE / 1=keep writing / 2=fix first
python scripts/run_state.py resume   # paste this line to continue

# v6/v7 path — ledger + structural verify + content scan
python scripts/ledger.py init --target 170000 --parts "vol1:238" "vol2:0"
python scripts/build_and_verify.py --target 170000 --strict
python scripts/dedupe_scan.py scenes --cross-table --out g10.txt
```

### What's new in v6

- Throughput **calibration** after batch 1 (re-plan with real numbers)
- **G9 character floors** + an actionable next-batch worklist ("lengthen blocks, don't add more blocks")
- **G8 duplicate/pollution detection** + `RUN.lock` single-writer rule
- `publish_github.py` — pushes a skill folder to GitHub with **UTF-8 + base64** (no more `????` descriptions)
- 4th iron rule: when the user says "write it all", **chain batches inside one turn** — never stop to ask "continue?"

### Gates

G1 volume · G2 IDs · G3 timeline · G4 fields · G5 structure · G6 degradation · G7 artifact opens · **G8 duplicate pollution** · **G9 unit floors** · **G10 content duplication / fact conflicts (v7)** · **P0 stop predicate (v8)**
