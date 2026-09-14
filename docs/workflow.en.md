# Workflow (English)

## 0. Kick-off: three things

1. **Size it**: `N0 = ceil(target ÷ 9000)`; tell the user N0.
2. **Freeze a batch plan**: table of `batch / range / planned chars / cumulative`.
3. **Create the ledger**: `python scripts/ledger.py init --target 170000 --parts "vol1:238" "vol2:0"`

## 1. Skeleton first

Write only the skeleton: one line per unit — `ID + one-sentence anchor + planned chars`. Get it confirmed, then fill prose only. **Never change IDs or order while filling.**

## 2. Single-writer lock

Drop `RUN.lock` at the project root:

```json
{ "run_id": "2026-09-14T18:20", "file_prefixes": ["act4_"], "owner": "session-A" }
```

The build only scans `file_prefixes`; any other file with a similar name is treated as pollution and **G8 fails**.

## 3. Per-batch SOP

```
1. Read LEDGER.md → take cursor + next range
2. Write this batch only (target = last measured chars/round)
3. Dump to disk (numbered filenames)
4. python scripts/build_and_verify.py --target 170000
5. Short → top up INSIDE this batch; never defer the gap
6. python scripts/ledger.py update --added <n> --blocks <k> --cursor <last id>
7. Report (fixed table)
8. If the user said "write it all" → go to step 1 and keep going until the turn cap
```

## 4. Report template

```
## Batch N delivered
| | prev | now | delta |
|---|---|---|---|
| vol1 | … | … | … |
| vol2 | … | … | … |
| total | … | … | … |

Target X | Current Y | Remaining Z (P%)
Measured: a chars/block | b chars/round | ~r rounds left

Added: <what this batch covered>
Gates: G1✓ … G10✓
Next: <range + planned chars>
```

## 5. "Many blocks, little volume"

Look at the G9 short-list. **Lengthen blocks; do not add more blocks.** A 300-char stub and an 800-char unit cost about the same to write, but only the latter is real output.

## 5.5 Cross-source splicing (v7, mandatory)

If the draft is not yours from scratch (written by someone else, an earlier batch, or a parallel run), do this **before writing a single new block**:

```bash
python scripts/dedupe_scan.py scenes --cross-table --out g10.txt
```

1. Read the "must fix" section of `g10.txt`; clear ERRORs first, then review WARNs.
2. Locate every new supplement in the **per-scene cross-table**: if its time is after the main scene, it must not replay actions the main scene already completed.
3. For any shared detail (how many people, which prop, what reason), **reuse the version already established in the draft**. Never start a second version.

> G1–G9 keep it *formally correct*; G10 keeps it *internally consistent*. Both must pass.

### Reading the G10 output

| Level | Meaning | Action |
|---|---|---|
| G10a verbatim | Two blocks share ≥30 identical chars | Must fix: rewrite or delete one |
| G10b fact conflict | Mutually exclusive props / quantities clash inside one scene | Must fix: unify to the draft's version, rebuild |
| G10c suspected re-narration | A later supplement shares ≥3 closing-action verbs with its main scene | Must fix: rewrite from another angle |
| G10d date drift | Body date is >30 days earlier than the time field | Confirm: keep if it is a retrospective reference |

## 6. "Duplicate IDs appeared"

G8 fails first. **Do not auto-merge.** Decide by hand which file survives, delete the other, rebuild.

## 7. Resuming in a new session

Read `LEDGER.md` / `ledger.json`, take the cursor, compute the range from measured throughput, and write. **Do not re-ask requirements.**
