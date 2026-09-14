# Workflow (English)

[中文](workflow.zh.md) ｜ [Back to README](../README.md)

---

## 1. Kick-off: three things

1. **Write `RUN.lock`** (single-writer lock)

```json
{ "run_id": "2026-09-14T18:20", "file_prefixes": ["act4_"], "owner": "session-A" }
```

The build script only scans files matching `file_prefixes`; anything else with the same prefix is treated as pollution.
When several sessions or parallel runs share a directory, **exactly one owner** is allowed.

2. **Initialise the ledger**

```bash
python scripts/ledger.py init --target 170000 --prefix act4_
```

3. **Estimate rounds**: `rounds = ceil(target / 9000)`, and tell the user that number up front.

---

## 2. Skeleton first

Write only "ID + one-line anchor + planned length" first. After it is confirmed, fill the prose batch by batch.
**Never change IDs or order while filling.**

---

## 3. Per-batch SOP

```
1. read LEDGER.md -> take cursor and the next range
2. write only this batch (target = measured chars/turn)
3. save to disk (ordered filenames, matching RUN.lock prefixes)
4. python scripts/build_and_verify.py --dir scenes --mode scene --target 170000
5. short of the word count -> top up inside this batch
6. python scripts/ledger.py update --add <chars> --blocks <blocks>
7. report using the fixed table (SKILL.md §8)
8. continuous mode -> back to step 1
```

---

## 4. Continuous mode (the v7 default)

Trigger phrases: **"write it all" / "don't stop" / "keep going until it's done"**.

Once triggered:

- Keep batching **inside the same turn**: save → verify → update ledger → save → verify ...
- **Never** stop mid-way to ask "shall I continue?".
- Stop only when either:
  1. `done = true` (target reached AND G1–G10 all pass), or
  2. this turn's output ceiling is reached.
- When stopping for reason 2, end with: the progress table + "the first thing next turn".

---

## 5. Troubleshooting

| Symptom | Cause | Action |
|---|---|---|
| Writes one batch then stops | not in continuous mode | see SKILL.md §1 rule 4 |
| Many blocks, few words | blocks too short | read `WORKLIST.md`, **lengthen blocks** |
| Timestamp regression | new unit earlier than the last sibling | run `slot_allocator.py` first |
| Two drafts with the same IDs | multiple writers | G8 fails → decide by hand, **never auto-merge** |
| Progress resets on a new session | progress only lived in chat | the ledger must be on disk |

---

## 6. Definition of finished

```bash
python scripts/size_report.py --dir scenes --target 170000
```

must print:

```
target 170000 | current 170xxx | remaining 0 (100.0%) | done=True
```

and `build_and_verify.py` must show G1–G10 all OK. **Only then may you declare completion.**
