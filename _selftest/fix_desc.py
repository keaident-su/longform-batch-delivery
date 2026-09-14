#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_desc.py —— 校正 SKILL.md 的 frontmatter description

为什么存在：Chatbox 的 skills:parser 有硬限制——
    [warn] [skills:parser] Skill file description exceeds 1024 characters
超过 1024 字符后技能会被摘出 enabledSkillNames，表现为"技能从列表里消失了"。
本脚本负责把 description 换成标准文本并**当场校验长度**。

用法：  python _selftest/fix_desc.py <SKILL.md 路径>
"""
import io
import re
import sys

DESC = """  长文本分批交付协议（LFBD）。用于任何"一次性写不完"的超长产出（十几万字的小说/剧本/报告/多卷文档）。
  v9 核心：先把"要跑几轮"算出来，再把"完成"变成退出码——
  轮数契约 x = 目标字数 ÷（单轮输出上限 × 0.8）；先跑满 x 轮，
  再用多种口径核字数（源文件汉字／含全角标点／去空白／交付 docx），不够就补；
  够了才进入排查，问题全过才允许停。
  scripts/run_state.py 四阶段：GENERATE / AUDIT / REPAIR / DONE；
  gate 返回 0=DONE／1=继续写／2=先修问题，非 0 一律不许停、不许提问。
  配套轮末契约（每轮只许以 DONE 或 RESUME 结尾）与吞吐升级梯（逼单块变长而非块数变多）。
  并把 N 次接续压成 N/k 次：一个回合内链式连跑 k 块，块与块之间不收尾。
  触发场景：目标字数远超单轮上限；分卷/分册交付；跨多轮续写不丢进度；
  用户抱怨"又没写够""每次都要重新说一遍要求""写完才发现差一大截"。
  English: LFBD — batching/delivery for ultra-long outputs (100k+ CJK chars).
  v9 pre-computes the round count x = target ÷ (per-turn cap × 0.8), then loops
  through four phases: GENERATE / AUDIT / REPAIR / DONE. Volume is checked by
  several methods (CJK, CJK+punctuation, non-space, built docx); if short, keep
  writing; once met, run all gates; only if everything passes may you stop.
  gate returns 0=DONE / 1=write more / 2=fix first — never end a turn with a question.
  Chaining k chunks inside one turn (no wrap-up between chunks) cuts hand-offs to about 1/k."""

LIMIT = 1024


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
    io.open(path, "w", encoding="utf-8", newline="").write(text)

    net = len(re.sub(r"\s", "", DESC))
    print("description：旧 %d 字符 → 新 %d 字符（净 %d，上限 %d）"
          % (len(old_block), len(DESC), net, LIMIT))
    if net > LIMIT:
        print("!! 仍然超限，必须再删 !!" % ())
        return 1
    print("余量 %d 字符 ✓" % (LIMIT - net))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
