# longform-batch-delivery (LFBD v7)

> **One-liner**: calibrate throughput first, keep a disk ledger, always know the exact shortfall, never pad with stub units.

A batching/delivery protocol for ultra-long outputs: novels, screenplays, reports, multi-volume documents — anything above ~100k Chinese characters that cannot be produced in one response.

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

| # | Hard constraint | v6's fix |
|---|---|---|
| R1 | Output per response is capped (~8k–12k CJK chars) | Announce the number of rounds; when the user says "write it all", **chain batches inside one turn** |
| R2 | Real throughput must be **measured** (blocks often land at 300–600 chars) | **Calibrate** after batch 1 and re-plan with real `chars/block` and `chars/round` |
| R3 | Stub units = hollow drafts | **Per-unit character floors (G9)** + auto top-up worklist |
| R4 | Parallel/multi-session runs duplicate IDs | **Single-writer lock (`RUN.lock`)** + fail on duplicates (G8) |

If `target ÷ cap > 1`, finishing in one turn is arithmetically impossible.

## Quick start

```bash
python scripts/ledger.py init --target 170000 --parts "vol1:238" "vol2:0"
python scripts/build_and_verify.py --target 170000     # verify + print next-batch worklist
python scripts/ledger.py update --added 9200 --blocks 15 --cursor 200
python scripts/size_report.py --dir scenes --glob "*.txt" --target 170000
python scripts/publish_github.py --repo owner/name --src . --branch main \
       --desc "A batching/delivery protocol for ultra-long text · 长文本分批交付协议"
```

## Iron rules

1. Never promise "finish in one turn".
2. Prose goes to disk, never into the chat bubble.
3. Every batch ends with rebuild + verify + report (`target / current / remaining / %`).
4. When the user says "write it all", chain batches until the turn limit — **do not ask "continue?"**.

## Gates

G1 volume · G2 IDs · G3 timeline · G4 fields · G5 structure · G6 degradation · G7 artifact opens · **G8 duplicate pollution** · **G9 unit floors** · **G10 content duplication / fact conflicts (v7)**

## Layout

```
SKILL.md                      main protocol (v7)
README.md / README.en.md      bilingual docs
docs/workflow.zh.md           Chinese workflow
docs/workflow.en.md           English workflow
scripts/ledger.py             ledger: init / update / show / next
scripts/build_and_verify.py   rebuild + G2–G10 + next-batch worklist
scripts/size_report.py        target / current / remaining / rounds left
scripts/dedupe_scan.py        v7 · G10 content duplication / fact-conflict scan + cross-table
scripts/publish_github.py     push a skill folder to GitHub (UTF-8 safe)
templates/                    ledger & batch-plan templates
```

## Layout

```
SKILL.md                      main protocol (v6)
README.md / README.en.md      bilingual docs
docs/workflow.zh.md           Chinese workflow
docs/workflow.en.md           English workflow
scripts/ledger.py             ledger: init / update / show / next
scripts/build_and_verify.py   rebuild + G2–G9 + next-batch worklist
scripts/size_report.py        target / current / remaining / rounds left
scripts/publish_github.py     push a skill folder to GitHub (UTF-8 safe)
templates/                    ledger & batch-plan templates
```

## License

MIT © keaident-su
