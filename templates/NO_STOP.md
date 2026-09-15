# 不许停（NO-STOP）· 贴在项目根

> 在 `python scripts/run_state.py gate` 退出码 = 0 之前：
> **只发工具调用，不发消息。** 一条不含工具调用的消息 = 回合结束 = 停。

- ❌ 不汇报、不总结、不问"要不要继续"、不写"下一步"。
- ✅ 写完一块 → 立刻写下一块（`write_file`）→ 校验（`run_command`）→ 继续。
- ✅ 唯一收尾：`gate` exit 0，写一行 `✅ DONE — gate exit 0`。
- ✅ 撞硬边界：写一行 `⏩ RESUME`，立即结束。

自查：`python _selftest/loop_guard.py`
