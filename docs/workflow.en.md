# Workflow (English)

## 0. Kick-off: three things

1. **Size it**: `N0 = ceil(target ÷ 9000)`; tell the user N0.
2. **Freeze a batch plan**: table of `batch / range / planned chars / cumulative`.
3. **Create the ledger**: `python scripts/ledger.py init --target 170000 --parts "vol1:238" "vol2:0"`

## 0.5 Stop predicate & turn-end contract (v8, highest priority)

### The stop predicate: the only legal definition of "done"

```bash
python scripts/run_state.py gate
```

| Exit code | State | What you do |
|---|---|---|
| **0** | `DONE` | Volume target met + all gates pass + artifacts exist → **you may stop** |
| **1** | `RUNNING` | Not enough volume → **keep writing**; never write "done", never ask |
| **2** | `BLOCKED` | Must-fix items → **fix, then keep going** — not stop and ask |

### Turn-end contract: exactly two legal endings

- `✅ DONE` (only when `gate` returns 0)
- `⏩ RESUME` + the line printed by `run_state.py resume` (every other case)

Forbidden: `shall I…` / `do you want me to continue?` / `just say the word and I'll…`.

### One standard turn

```bash
python scripts/run_state.py where    # see the current contract first
python scripts/run_state.py plan     # work order: N units × at least M chars each
#   … write prose, dump to disk …
python scripts/run_state.py tick --added 9200 --units 5 --cursor 214   # runs the escalation ladder
python scripts/run_state.py gate     # exit code decides your ending
python scripts/run_state.py resume   # prints the continuation line
```

---

## 0.6 Round contract & four phases (v9)

### The round contract

```bash
python scripts/run_state.py init --target 170000 --cap 12000 --util 0.8
```

```
x = ceil(170000 ÷ (12000 × 0.8)) = ceil(170000 ÷ 9600) = 18 rounds
```

`--cap` = the per-turn output cap (CJK chars, default 12000); `--util` defaults to 0.8.
x is stored as `rounds_planned` and every round shows `round n/x`.
**Running x rounds is not completion** — only `gate` exit 0 is.

### The four phases

| Phase | Trigger | exit | Action |
|---|---|---|---|
| `GENERATE` | Below target | 1 | Keep writing; never claim done |
| `AUDIT` | Target just met | — | Run all gates (`gate` does this) |
| `REPAIR` | Formal issues | 2 | Fix from the list; write no new content |
| `BLOCKED` | Duplicate ID / G10 / broken artifact | 2 | Fix first, then re-run |
| `DONE` | All clear | 0 | You may stop |

### Multi-method volume check (strictest wins)

```bash
python scripts/run_state.py count
```

Five measurements: CJK / CJK+punctuation / non-space / total / built docx.
`gate` uses **`min(source CJK, docx CJK)`**, so "sources long enough but the docx lost content"
cannot be mistaken for done.

---

## 0.7 How to run it: Work Mode required (v9.2)

Chatbox's Work Mode is itself a loop (think → call tool → read result → repeat until done).
Its only hard boundary is a pause **every 25 consecutive tool calls**.

- Long-form writing **must** run in Work Mode; Chat Mode injects no tools, so there is no loop.
- Write all prose to disk with `write_file`; **emit no message between chunks**.
- `init` prints "expected Continue clicks: N"; if reality differs, run `calibrate`.

---

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
8. python scripts/run_state.py gate
9. exit 0 → end with ✅ DONE; otherwise → back to step 1 and end with ⏩ RESUME
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
Ending: ✅ DONE (only if gate exits 0) or ⏩ RESUME (every other case)
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

Run `python scripts/run_state.py where` and `plan` first; read `run_state.json` / `LEDGER.md`, take the cursor, compute the range from measured throughput, and write. **Do not re-ask requirements.**


---

## v11.0.0 (latest) · M0 "NO-STOP"

**One line: until `python scripts/run_state.py gate` exits `0`, never emit a message without a tool call.**

Work Mode is a loop: think → call a tool → read the result → decide again. A message with **no tool call ends the
turn** and hands control back to the user. So the real reason "the skill ran one round and stopped" is **not** the
25-step pause (that is an in-turn checkpoint, and it is already disabled under Full Access) — it is the model
writing a summary.

### During a turn, only one action is allowed

✅ Call a tool: `write_file` (prose) / `edit_file` (edits) / `run_command` (checks, ledger).

### Forbidden endings (any one of them breaks the protocol)

| Forbidden | Example |
|---|---|
| Progress table | "## Batch N delivered … target / current / remaining" |
| Soliciting | "Shall I continue?" "Pick one of the following" |
| Question tail | any sentence ending in "?" that waits for input |
| Wrap-up | "That's it for this round", "to summarize" |
| Prose in chat | prose must go to disk via `write_file` |

### The only allowed ending

```
✅ DONE — gate exit 0 | target <X> | current <Y> | artifacts: <file>
```

If `gate` is non-zero: **do not report, do not ask, do not summarize — just issue the next tool call.**
Only on a hard boundary (context exhausted / per-response output cap) write one `⏩ RESUME` line, then stop.

### Self-check

```bash
python _selftest/loop_guard.py     # exit 0 = ready / 2 = not ready
```

It verifies: SKILL.md contains M0, `gate exit 0` is the only legal stop, the description is within 1024 chars on
both measures, and the client's `pauseOnToolCallLimit` is `false`.
