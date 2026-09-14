# Long-Form Batch Delivery (LFBD) v7

> An engineering protocol that lets an AI agent actually *finish* a 100k+ character deliverable.
> **v7 fixes one thing: make it keep going until the target is met — and stop asking "shall I continue?"**

[中文](README.zh.md) ｜ [Workflow](docs/workflow.md)

---

## The problem

Asking an LLM to write 100,000 Chinese characters in one shot is physically impossible: a single turn tops out around 6,000–12,000 CJK characters.
So you must batch. But batching usually fails in four known ways — v7 blocks each one:

| # | Real constraint | Typical failure | v7 fix |
|---|---|---|---|
| R1 | Per-turn output is hard-capped; no prompt changes that | **Agent writes one batch, then stops and asks "continue?"** | "Keep batching within the same turn until the output ceiling" becomes the **default behaviour**; stopping to ask is the #1 anti-pattern |
| R2 | Real throughput must be measured (often only 300–600 chars/block) | Scheduling from a guessed "10k/turn" | After batch 1, **calibrate** `chars/block` and `chars/turn`; re-plan with measured values |
| R3 | Padding with short "supplementary" units produces a hollow draft | Many blocks, few words, main line stalls | **Unit floors** + under-floor worklist + "lengthen blocks, don't add blocks" |
| R4 | Multi-run / parallel runs duplicate IDs | Two drafts pollute each other | **Single-writer lock** + **fail on duplicate IDs** before build |
| R5 | "Done" is vague and models love saying it | User thinks it's finished; it's half done | **Completion as a decidable predicate** (below) |

---

## The core of v7: completion as a predicate

```
done = (current_chars >= target_chars) AND (gates G1..G10 all pass)
```

- While `done = false`, wording like "finished" or "complete" is a **violation**.
- `done` lives in `ledger.json`, so it survives session changes.
- On resume, read that field first: keep writing while it is `false`; stop only when it is `true`.

---

## Four commands you will actually use

```bash
# 1) initialise the ledger
python scripts/ledger.py init --target 170000 --prefix act4_

# 2) after every batch: rebuild + run G1..G10 + emit the next worklist
python scripts/build_and_verify.py --dir scenes --mode scene --target 170000

# 3) ask anytime: how far, how many rounds left, are we done
python scripts/size_report.py --dir scenes --target 170000

# 4) before writing a new unit: find a timestamp that cannot go backwards
python scripts/slot_allocator.py --file scenes/act4_e04_p1.txt --main 211
```

---

## The ten gates

| Gate | Criterion |
|---|---|
| G1 length | Monotonically increasing and ≥ this batch's promise |
| G2 IDs | No gaps, no duplicates in main IDs |
| G3 time | Timestamps strictly increasing, zero regressions |
| G4 fields | Every required field present per unit |
| G5 structure | Season/volume/chapter headings present |
| G6 degradation | No "subject, verb" fragmentation, no ≥3 blank lines |
| G7 deliverable | Output opens correctly |
| G8 pollution | Same ID never in two files; **fail then decide by hand** |
| G9 floors | Every unit ≥ its floor |
| **G10 completion** | Whether `done` holds |

---

## Layout

```
longform-batch-delivery/
├── SKILL.md                  # full agent instructions (incl. continuous mode)
├── README.md                 # English (this file)
├── README.zh.md              # 中文
├── docs/
│   ├── workflow.md
│   └── workflow.zh.md
├── scripts/
│   ├── ledger.py
│   ├── build_and_verify.py
│   ├── size_report.py
│   ├── slot_allocator.py
│   └── publish_github.py
└── LICENSE
```

## Quick start

1. Drop this folder into your agent's skills directory (or just read `SKILL.md`).
2. Write `RUN.lock` in the project root declaring the file prefixes this run may scan.
3. Follow `docs/workflow.md`: skeleton first → continuous batching → verify each batch → update the ledger.
4. Trigger phrase for continuous mode: **"write it all" / "don't stop" / "keep going until it's done"**.
   After that, the agent must submit multiple batches inside one turn up to the output ceiling.

## License

MIT — see [LICENSE](LICENSE).
