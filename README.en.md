# Long-Form Batch Delivery

> A delivery protocol for text that cannot fit in one turn.
> Write 100k+ words of fiction, screenplays, or reports in **verifiable, resumable batches** —
> instead of discovering at the very end that only 30% was produced.

English ｜ [简体中文](README.md)

---

## The problem it solves

LLMs have a hard **output cap per turn**. Ask for a 170,000-character screenplay and it physically
cannot emit it in one response — so it either gets truncated, or it produces a fraction and **tells
you only at the end** that a huge chunk is missing. Meanwhile you have to re-explain the brief every time.

This protocol turns that failure mode into a workflow:

| Pain point | Countermeasure |
|---|---|
| Model promises "one shot" and gets cut off | Measure volume first; state "this takes N rounds" up front |
| You notice the shortfall near the end | Every batch reports `target / current / remaining` |
| New session loses all context | Progress lives in an on-disk ledger; just say "continue" |
| Structure drifts (broken numbering, time reversals) | Skeleton-first + automated gates every batch |
| Verification by hand | One command runs 7 checks |

---

## Quick start

```bash
# 1. Estimate and create the ledger (target 170k chars, 10k per batch -> 17 batches)
python scripts/ledger.py init --target 170000 --budget 10000 --cursor-scene 0

# 2. Register each finished batch (rewrites LEDGER.md automatically)
python scripts/ledger.py add --n 1 --range "scenes 1-40" --added 10400 --verify PASS

# 3. Inspect anytime
python scripts/ledger.py report
python scripts/ledger.py next
```

```bash
# Rebuild + audit (numbering, monotonic time, required fields, degradation, blank lines, structure)
python scripts/build_and_verify.py \
  --src "scenes/part_a_*.txt" --title Volume-A \
  --out merged_a.txt --docx volume_a.docx
```

---

## Core rules (see [SKILL.md](SKILL.md))

1. **Never promise "all in one turn"** — round one is: measure, fix the batch plan, state the round count.
2. **Body text goes to disk, not to chat** — each batch is written as source files; chat only gets the report.
3. **Every batch ends with rebuild + verify + report** — the report always includes `target / current / remaining`.
4. **Skeleton first** — lock numbering and structure before filling prose.
5. **The ledger lives on disk** — sessions die, files don't.

---

## Volume thresholds

| Target size | Must batch? | Suggested batches |
|---|---|---|
| < 10k chars | No | 1 |
| 10k–30k | Yes | 2–4 |
| 30k–100k | Yes | 4–12 |
| > 100k | Yes | 12+, with skeleton-first + ledger |

Budget **8,000–10,000 CJK characters per batch** conservatively.

---

## Layout

```
longform-batch-delivery/
├── SKILL.md                      # The protocol an agent reads
├── README.md / README.en.md      # Docs (zh / en)
├── LICENSE                       # MIT
├── docs/
│   ├── workflow.zh.md            # Full workflow (Chinese)
│   └── workflow.en.md            # Full workflow (English)
├── scripts/
│   ├── ledger.py                 # Progress ledger CLI (zero deps)
│   └── build_and_verify.py       # Generic rebuild + verify template
└── templates/
    ├── ledger.json
    └── batch_plan.md
```

---

## Install as a Chatbox / Claude skill

Drop the directory into your skills folder; `SKILL.md` must expose `name` and `description`.
In Chatbox, point the skill installer at this directory.

---

## License

MIT — see [LICENSE](LICENSE).
