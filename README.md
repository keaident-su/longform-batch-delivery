# 长文本分批交付协议（Long-Form Batch Delivery）

> 一个专治「一次性写不完」的写作交付协议。
> 让十几万字的小说 / 剧本 / 报告，可以**分批、可续写、每批可见进度**地产出——而不是写到最后才发现只完成 30%。

[English](README.en.md) ｜ 简体中文

---

## 它解决什么问题

大模型单轮回复有**输出上限**。当你要求"写 17 万字"，它物理上吐不出来，
于是要么被截断，要么写了几成却**到最后才告诉你差一大截**。

你已经把要求讲了三遍，它每次都要重新解释一遍背景。这很烦。

本协议把这件事变成流程：

| 痛点 | 对策 |
|---|---|
| 单轮写不完却被承诺"一次搞定" | 开工先测算，直接告诉你"需要 N 轮" |
| 写到一半发现差一大截 | 每批必报 `目标 / 当前 / 还差` |
| 换会话后就归零、要重讲需求 | 进度写进磁盘账本 `LEDGER.md`，只说"继续"即可续写 |
| 结构越写越乱（编号跳号、时间倒流） | 骨架先行 + 每批自动校验闸门 |
| 校验靠肉眼看 | 一条命令跑完 7 项体检 |

---

## 三步上手

```bash
# 1. 估算并建立账本（目标 17 万字，单批预算 1 万字 → 17 批）
python scripts/ledger.py init --target 170000 --budget 10000 --cursor-scene 0

# 2. 每写完一批，登记一次（会自动刷新 LEDGER.md）
python scripts/ledger.py add --n 1 --range "第1-40场" --added 10400 --verify PASS

# 3. 随时查看进度 / 问下一批该写多少
python scripts/ledger.py report
python scripts/ledger.py next
```

```bash
# 重建 + 体检（编号连续性 / 时间单调 / 字段齐全 / 退化扫描 / 空行 / 结构）
python scripts/build_and_verify.py \
  --src "scenes/part_a_*.txt" --title 上册 \
  --out merged_a.txt --docx 上册.docx
```

---

## 核心规则（详见 [SKILL.md](SKILL.md)）

1. **不许承诺"一次性写完"** —— 第一轮只做：测算、写死分批计划、告知轮数。
2. **正文只落盘，不进聊天** —— 每批产物写成源文件；聊天里只报进展表。
3. **每批结束必须重建 + 校验 + 汇报** —— 汇报固定包含 `目标/当前/还差`。
4. **骨架先行** —— 先锁定编号与结构，再逐段填正文。
5. **账本在磁盘上** —— 会话会丢，文件不会。

---

## 体量红线

| 目标体量 | 是否必须分批 | 建议批数 |
|---|---|---|
| < 1 万字 | 否 | 1 |
| 1—3 万字 | 是 | 2—4 |
| 3—10 万字 | 是 | 4—12 |
| > 10 万字 | 是 | 12+，且必须"骨架先行 + 账本" |

单批安全产出按 **8,000—10,000 中文字符** 保守估算。

---

## 目录结构

```
longform-batch-delivery/
├── SKILL.md                      # 技能本体（给 agent 读的协议）
├── README.md / README.en.md      # 项目说明（中/英）
├── LICENSE                       # MIT
├── docs/
│   ├── workflow.zh.md            # 完整工作流（中文）
│   └── workflow.en.md            # Full workflow (English)
├── scripts/
│   ├── ledger.py                 # 进度账本 CLI（零依赖）
│   └── build_and_verify.py       # 通用"重建 + 校验"模板
└── templates/
    ├── ledger.json               # 账本模板
    └── batch_plan.md             # 分批计划模板
```

---

## 作为 Chatbox / Claude 技能安装

把整个目录放进技能目录，确保 `SKILL.md` 带 `name` 与 `description` 字段即可。
在 Chatbox 里可以直接用技能安装入口指向本目录。

---

## 许可

MIT，见 [LICENSE](LICENSE)。
