# Running unattended (finish while you sleep)

## Bottom line

Chatbox has **no** "auto-open the next turn" switch. A turn ends only when the assistant emits a message
**without a tool call** — and that hands control back to you. So there are only two ways to keep going
without you:

1. **Never end the turn** (LFBD v11, rule M0): the model never emits a tool-free message, so one turn writes
   as many chunks as possible.
2. **Use the message queue as auto-continue**: Chatbox lets you queue messages, and **the next queued message
   is sent automatically when the current reply finishes**.

## Three steps before bed

1. Make sure: Work Mode + Full Access + "Pause after every 25 steps" = **off**.
2. Open `templates/queue_resume.txt` and paste its **20 lines** into the input box, one Enter each (they queue).
   The queue caps at 20.
3. Go to sleep. The client sends them one after another automatically.

## How much one night yields

```
per-night output ~= queue size N x chunks per turn k x chars per chunk c
```

| N | k | c | per night |
|---|---|---|---|
| 20 | 6 | 1,800 | 216,000 chars |

> Enough for a 200k-char Act 5 in one night.

## Hard limits (no switch can remove them)

* **Per-response output cap** — a single reply has a ceiling.
* **Context window** — long sessions get tight; `autoCompaction` helps but is not infinite.
* **Total output x** — content volume cannot be compressed.

When a limit is hit the model writes one `⏩ RESUME` line and stops — just queue another batch and it resumes,
no need to restate the task.

## Truly hands-off (optional)

With an LLM API key, `scripts/overnight_driver.py` runs the loop **outside** the chat: read skeleton ->
generate chunk -> write to disk -> `run_state.py gate` -> keep going until 0. Not bound by turns or the queue.
See the script header for usage.
