# longform-batch-delivery · 长文本分批交付协议 (LFBD v6)

> **一句话**：先测产出、再排期；每轮都有账本；差多少永远秒答；不许用短段落注水。
> **One-liner**: calibrate throughput first, keep a disk ledger, always know the exact shortfall, never pad with stub units.

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
# 1) 初始化账本（目标 17 万中文字符）
python scripts/ledger.py init --target 170000 --parts "上册:238" "下册:0"

# 2) 写第 1 批，然后校验 + 拿到"下一批作业单"
python scripts/build_and_verify.py --target 170000

# 3) 记录本批实测吞吐（这一步会算出"还需几轮"）
python scripts/ledger.py update --added 9200 --blocks 15 --cursor 200

# 4) 任何时候问"还差多少"
python scripts/size_report.py --dir scenes --glob "*.txt" --target 170000
```

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

---

## 目录结构

```
SKILL.md                      主协议（v6）
README.md / README.en.md      中英文说明
docs/workflow.zh.md           中文工作流
docs/workflow.en.md           English workflow
scripts/ledger.py             账本：init / update / show / next
scripts/build_and_verify.py   重建 + G2–G9 + 下一批作业单
scripts/size_report.py        目标/当前/还差/完成度/还需几轮
scripts/publish_github.py     推送技能到 GitHub（UTF-8 安全）
templates/                    账本与分批计划模板
```

---

## 协议要点（SKILL.md 摘录）

- **铁律 1**：不许承诺"一轮写完"。
- **铁律 2**：正文只落盘，不进聊天。
- **铁律 3**：每批结束必须重建＋校验＋汇报，汇报必含 `目标/当前/还差/完成度`。
- **铁律 4**：用户说"全部写完"时，一轮内连续跑批，不问"要继续吗"。
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

### Quick start

```bash
python scripts/ledger.py init --target 170000 --parts "vol1:238" "vol2:0"
python scripts/build_and_verify.py --target 170000
python scripts/ledger.py update --added 9200 --blocks 15 --cursor 200
python scripts/size_report.py --dir scenes --glob "*.txt" --target 170000
```

### What's new in v6

- Throughput **calibration** after batch 1 (re-plan with real numbers)
- **G9 character floors** + an actionable next-batch worklist ("lengthen blocks, don't add more blocks")
- **G8 duplicate/pollution detection** + `RUN.lock` single-writer rule
- `publish_github.py` — pushes a skill folder to GitHub with **UTF-8 + base64** (no more `????` descriptions)
- 4th iron rule: when the user says "write it all", **chain batches inside one turn** — never stop to ask "continue?"

### Gates

G1 volume · G2 IDs · G3 timeline · G4 fields · G5 structure · G6 degradation · G7 artifact opens · **G8 duplicate pollution** · **G9 unit floors**
