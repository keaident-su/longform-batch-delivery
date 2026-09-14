# Full Workflow (English)

This is the operating manual for [SKILL.md](../SKILL.md).

---

## Step 0 — Decide whether batching is required

```
batching required  ⟺  target size > safe single-turn output (8,000–10,000 CJK chars)
```

As soon as batching is required, stop "writing while thinking" and follow the loop below.

---

## Step 1 — Measure and state the round count

```
P = safe single-turn output     (conservative 8,000; generous 10,000)
N = ceil(target / P)
```

Then, **in your very first reply**, state:

- target size
- per-batch budget P
- planned number of batches N
- the range each batch covers
- one explicit sentence: "this takes N rounds, not one"

> The point: surface the round count immediately, so the user never feels a sudden shortfall later.

---

## Step 2 — Create the ledger

```bash
python scripts/ledger.py init --target 170000 --budget 10000
```

This produces `ledger.json` (machine-readable) and `LEDGER.md` (human-readable).
The two fields that matter most:

- `current_total` — cumulative characters so far
- `cursor` — where the next batch starts

---

## Step 3 — Skeleton first

**Outline before prose.** Each unit in the skeleton carries only three things:

```
Scene 171
anchor: <one sentence>
planned chars: 900
```

Deliver the skeleton once for confirmation. It is cheap and prevents all downstream rework.
**Lock two things**: unit numbering and time order. Every later batch must stay inside them.

---

## Step 4 — The per-batch loop

```
┌─ read LEDGER.md, confirm this batch's range
│
├─ write prose (target = per_batch_budget; prefer under, never over)
│     └─ dump to source files: src/part_01.txt, src/part_02.txt ...
│
├─ audit: python scripts/build_and_verify.py --src "src/*.txt" ...
│
├─ register: python scripts/ledger.py add --n K --range "..." --added <chars> --verify PASS
│
├─ report (fixed template below)
│
└─ stop. wait for "continue".
```

**Fixed report template:**

```
## Batch K delivered
| | previous | this batch | delta |
|---|---|---|---|
| total | … | … | … |

target X | current Y | remaining Z (P% done)
added: <what this batch contained>
checks: G1✓ G2✓ G3✓ G4✓ G5✓ G6✓ G7✓
next batch: <range + planned chars>
```

---

## Step 5 — Resume

When the user says "continue":

1. `python scripts/ledger.py next` → get the next range and budget;
2. write it — **do not re-ask for requirements**;
3. go back to Step 4.

Because the ledger is on disk, this survives new sessions, context compression, and multi-day gaps.

---

## The gates

| Gate | Checks | On failure |
|---|---|---|
| G1 | char count grows monotonically, on target | fill the gap now, not next batch |
| G2 | unit numbering continuous; sub-units follow their parent | reorder + global rewrite |
| G3 | timestamps strictly increasing | adjust timestamps |
| G4 | required fields present | fill them |
| G5 | volume/episode/chapter titles complete | add them |
| G6 | degradation (fragmented clauses / blank-line padding / high similarity) | rewrite |
| G7 | deliverable opens in target software | regenerate |

`build_and_verify.py` covers G2–G6; G1 comes from the ledger; G7 is verified by the target app.

---

## Common pitfalls

1. **Editing already-verified chapters inside a new batch** → invalidates the baseline. Make it a separate batch and re-run everything.
2. **Pasting prose into chat** → burns context and loses content. Always dump to disk.
3. **Padding with "supplementary scenes"** → if the main line doesn't advance, it's filler. Supplements must add other viewpoints, causality, or interiority.
4. **Keeping progress only in the conversation** → resets on a new session. Persist it.
5. **Reporting a shortfall only at the end** → the worst outcome for the user. Report every batch; keep the gap visible.
