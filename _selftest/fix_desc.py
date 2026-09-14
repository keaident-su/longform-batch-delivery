#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_desc.py —— 把 SKILL.md 的 frontmatter description 压回 1024 字符以内

背景：Chatbox 的 skills:parser 有一条硬限制——
    [warn] [skills:parser] Skill file description exceeds 1024 characters
超限后技能会被摘出 enabledSkillNames，表现为"技能不见了"。
v8 把 description 写成 1341 字符，触发了这条限制。

本脚本只改 frontmatter 里的 description，正文一字不动。
"""
import io
import re
import sys

DESC = """  长文本分批交付协议（LFBD）。用于任何"一次性写不完"的超长产出（十几万字的小说/剧本/报告/多卷文档）。
  v8 核心：把"完成"变成退出码——scripts/run_state.py gate 返回 0=DONE／1=继续写／2=先修问题，
  非 0 一律不许停、不许写"完成"；配合轮末契约（每轮只许以 DONE 或 RESUME 结尾，禁止任何提问）
  与吞吐升级梯（强制单块变长，而非块数变多）。
  v6/v7 能力全部保留：吞吐标定、单元字数地板、单写者锁、G10 内容一致性闸门。
  触发场景：目标字数远超单轮上限（约 8,000–12,000 中文字符）；分卷/分册交付；跨多轮续写不丢进度；
  用户抱怨"又没写够""每次都要重新说一遍要求""写完才发现差一大截"。
  English: LFBD — a batching/delivery protocol for ultra-long outputs (100k+ CJK chars)
  that cannot be produced in one response. v8 turns "done" into an exit code:
  run_state.py gate -> 0=DONE / 1=keep writing / 2=fix first; non-zero means you may not stop
  and may not claim completion. Adds a turn-end contract (every turn ends with a DONE
  certificate or a RESUME line, never a question) and a throughput escalation ladder.
  Keeps throughput calibration, per-unit character floors, single-writer lock and G10."""


def main(path):
    text = io.open(path, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in text else "\n"

    m = re.search(r"(?m)^description: \|.*?(?=^allowed-tools:)", text, re.S)
    if not m:
        print("ERROR: 未找到 description 段")
        return 2

    old_block = m.group(0)
    new_block = "description: |" + nl + DESC.replace("\n", nl) + nl
    text = text[:m.start()] + new_block + text[m.end():]

    net = len(re.sub(r"\s", "", DESC))
    raw = len(DESC)

    io.open(path, "w", encoding="utf-8", newline="").write(text)
    print("已替换 description 段：旧 %d 字符 → 新 %d 字符（净 %d 字符，上限 1024）"
          % (len(old_block), raw, net))
    print("是否超限：%s" % ("是 ✗" if net > 1024 else "否 ✓"))
    return 0 if net <= 1024 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
