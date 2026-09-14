# longform-batch-delivery (LFBD v6)

> **One-liner**: calibrate throughput first, keep a disk ledger, always know the exact shortfall, never pad with stub units.

A batching/delivery protocol for ultra-long outputs: novels, screenplays, reports, multi-volume documents — anything above ~100k Chinese characters that cannot be produced in one response.

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

G1 volume · G2 IDs · G3 timeline · G4 fields · G5 structure · G6 degradation · G7 artifact opens · **G8 duplicate pollution** · **G9 unit floors**

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
