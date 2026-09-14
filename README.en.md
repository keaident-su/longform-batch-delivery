# longform-batch-delivery (LFBD v9)

> **One-liner**: calibrate throughput first, keep a disk ledger, always know the exact shortfall, never pad with stub units.
> **v8**: "done" is an **exit code** — `run_state.py gate` returns `0=DONE, 1=keep writing, 2=fix first`. Never end a turn with a question.
> **v9**: **compute the round count first** — `x = ceil(target ÷ (per-turn cap × 0.8))` — then loop `GENERATE → AUDIT → REPAIR → DONE`; nothing stops before DONE.

A batching/delivery protocol for ultra-long outputs: novels, screenplays, reports, multi-volume documents — anything above ~100k Chinese characters that cannot be produced in one response.

## What's new in v9 — the round contract

v8 could stop early exits, but it never answered the prior question: **how many rounds is this job, anyway?**

v9 makes that a contract:

```
x = ceil(target_chars ÷ (per-turn output cap × 0.8))
```

170,000 chars with a 12,000-char cap → `x = ceil(170000 ÷ 9600) = 18 rounds`.

| Step | Implemented by |
|---|---|
| ① Set round count x | `init --cap 12000 --util 0.8` → stored as `rounds_planned` |
| ② Run x rounds first | `plan` issues the work order; `tick` records `round n/x` |
| ③ Verify volume several ways | `count`: CJK / CJK+punctuation / non-space / total / built docx |
| ④ Short → keep writing | `gate` exits 1 (`GENERATE`) |
| ⑤ Met → audit | `gate` automatically enters `AUDIT` |
| ⑥ All pass → stop | `gate` exits 0 (`DONE`), else 2 (`REPAIR` / `BLOCKED`) |

Also new: `next` — one line telling you the current phase and what to do, with the matching exit code.

**Strictest-count rule**: `gate` measures volume as `min(source CJK, docx CJK)`.
"Sources are long enough but the generated docx lost content" can no longer be mistaken for done.

## What's new in v8 — the anti-early-exit release

Every earlier version taught you how to write *well*. None of them could **stop you from declaring victory early.**

Real incident (this project, 2026-09): target 170,000 chars, "delivered" at 27,822 (16.4%),
closing with *"want the first volume now? just say the word"* — a stop request in disguise.
Ten gates existed, and **not one of them answered the question "may I stop now?"**

v8 answers it with a number:

| Mechanism | File | Effect |
|---|---|---|
| **M1 Stop predicate** | `scripts/run_state.py gate` | `0=DONE` / `1=RUNNING` / `2=BLOCKED`. **Non-zero means you may not stop, and may not write "done".** |
| **M2 Turn-end contract** | `templates/turn_contract.md` | End every turn with `✅ DONE` or `⏩ RESUME`. Questions, offers and "shall I continue?" are violations. |
| **M3 Escalation ladder** | `run_state.py tick` | `cpu = max(floor×1.4, prev_cpu×1.35)`, `units = turn_budget ÷ cpu` — arithmetic, not a wish, forces longer units |
| Self-test | `_selftest/selftest.py` | 12 assertions across all three exit codes plus duplicate-ID / timeline / G10 regressions |

```bash
python scripts/run_state.py gate      # the only legal definition of "done"
python scripts/run_state.py resume    # prints the one-line prompt that continues the run
```

## What's new in v7

v6's gates G1–G9 are all **formal** (volume, IDs, timeline, fields, structure, degradation,
openability, duplicates, unit floors). They share one blind spot: **a draft can pass every
formal gate and still contradict itself.**

Real incident: route B appended a supplement to a scene already written by route A —

- the main scene says "An kicks the door in and rescues him"; the new supplement **re-narrates
the same event in different words**, but timestamps it to the next day;
- one block says the girl was a tourist who ran into him by chance; another says they had dinner plans;
- the number of people present is 3 in one block and 4 in another; the binding is tape in one, cloth in another.

**All formal checks passed.** v7 exists for exactly this class of failure:

1. **G10 gate** — verbatim duplication, in-scene fact conflicts, "same event re-narrated", date drift.
2. **`scripts/dedupe_scan.py`** — implements G10; `--cross-table` prints a per-scene table
   (time / place / cast / quantities / props side by side).
3. **§7.5 pre-takeover check** — before touching someone else's draft, run G10 and map every new
   supplement against the existing blocks; reuse the established version of every shared detail.
4. **Known limitation (stated honestly)** — "same event, reworded" has low lexical similarity;
   automation only surfaces leads, a human decides from the cross-table.

```bash
python scripts/dedupe_scan.py scenes --cross-table --out g10.txt
```

## Why a single turn can't finish it

| # | Hard constraint | Fix |
|---|---|---|
| R1 | Output per response is capped (~8k–12k CJK chars) | Announce the number of rounds; when the user says "write it all", **chain batches inside one turn** |
| R2 | Real throughput must be **measured** (blocks often land at 300–600 chars) | **Calibrate** after batch 1 and re-plan with real `chars/unit` and `chars/turn` |
| R3 | Stub units = hollow drafts | **Per-unit character floors (G9)** + auto top-up worklist |
| R4 | Parallel/multi-session runs duplicate IDs | **Single-writer lock (`RUN.lock`)** + fail on duplicates (G8) |

If `target ÷ cap > 1`, finishing in one turn is arithmetically impossible.
**v8 adds the missing half: with `gate` non-zero, "close enough" is no longer an option either.**

## Quick start

```bash
# v8 main path — stop-predicate driven
python scripts/run_state.py init --target 170000 --cap 12000 --util 0.8 \
    --glob "scenes/act4*_*.txt" --prefix act4
python scripts/run_state.py next     # current phase + what to do (1=write / 2=fix / 0=may stop)
python scripts/run_state.py plan     # work order: round n/x, unit count, min chars per unit
python scripts/run_state.py count    # multi-method volume check (CJK / punctuation / docx)
python scripts/run_state.py tick --added 9200 --units 5 --cursor 214
python scripts/run_state.py gate     # 0=DONE / 1=keep writing / 2=fix first
python scripts/run_state.py resume   # paste this line to continue

# v6/v7 path — ledger + structural verify + content scan
python scripts/ledger.py init --target 170000 --parts "vol1:238" "vol2:0"
python scripts/build_and_verify.py --target 170000 --strict
python scripts/ledger.py update --added 9200 --blocks 15 --cursor 200
python scripts/size_report.py --dir scenes --glob "*.txt" --target 170000
python scripts/dedupe_scan.py scenes --cross-table --out g10.txt
python scripts/publish_github.py --repo owner/name --src . --branch main \
       --desc "A batching/delivery protocol for ultra-long text · 长文本分批交付协议"
```

## Iron rules

1. Never promise "finish in one turn".
2. Prose goes to disk, never into the chat bubble.
3. Every batch ends with rebuild + verify + report (`target / current / remaining / %`).
4. When the user says "write it all", chain batches until the turn limit — **do not ask "continue?"**.
5. **"Done" must be proven by an exit code.** Run `run_state.py gate`; if it is non-zero you may not write "done" and may not wrap up.
6. **A turn may end in exactly two ways**: `✅ DONE` (only when `gate` is 0) or `⏩ RESUME`. No questions, no offers, no "shall I…".
7. **Compute the rounds before you write**: `x = ceil(target ÷ (cap × 0.8))`. Running x rounds is **not** completion — only `gate` exit 0 is.

## Gates

G1 volume · G2 IDs · G3 timeline · G4 fields · G5 structure · G6 degradation · G7 artifact opens · **G8 duplicate pollution** · **G9 unit floors** · **G10 content duplication / fact conflicts (v7)** · **P0 stop predicate (v8+)**

## Layout

```
SKILL.md                      main protocol (v8)
README.md / README.en.md      bilingual docs
docs/workflow.zh.md           Chinese workflow
docs/workflow.en.md           English workflow
scripts/run_state.py          v8 · stop predicate + turn-end contract + escalation ladder
scripts/ledger.py             ledger: init / update / show / next
scripts/build_and_verify.py   rebuild + G2–G9 + next-batch worklist (--strict = stop predicate)
scripts/size_report.py        target / current / remaining / rounds left
scripts/dedupe_scan.py        v7 · G10 content duplication / fact-conflict scan + cross-table
scripts/publish_github.py     push a skill folder to GitHub (UTF-8 safe)
templates/                    ledger & batch-plan templates + turn_contract.md
_selftest/selftest.py         v8 · stop-predicate regression suite (12 assertions)
```

## License

MIT © keaident-su
