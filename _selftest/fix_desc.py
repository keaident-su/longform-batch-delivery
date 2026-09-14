#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_desc.py —— 校正 SKILL.md 的 frontmatter description 并**双口径校验**

为什么存在：Chatbox 的 skills:parser 有硬限制——
    [warn] [skills:parser] Skill file description exceeds 1024 characters
超限后技能会被摘出 enabledSkillNames，表现为"技能从列表里消失了"。

我们无法确定解析器计的是"净字符"还是"含缩进换行的原始长度"，
所以**两个口径都必须 ≤ 1024**，并且留足余量（目标：原始长度 ≤ 950）。

用法：  python _selftest/fix_desc.py <SKILL.md 路径>
"""
import io
import re
import sys

DESC = """  长文本分批交付协议（LFBD）。用于一次性写不完的超长产出（十几万字的小说/剧本/报告）。
  v10 核心：先把“跑几轮”算出来，再把“完成”变成退出码——
  轮数契约 x = ceil(目标 ÷ (单轮上限 × 0.8))；先跑满 x 轮，
  再用多种口径核字数（汉字/含全角标点/去空白/交付 docx），不够就补；
  够了才排查（编号/时间/字段/内容一致性），问题全过才允许停。
  scripts/run_state.py 四阶段 GENERATE/AUDIT/REPAIR/DONE；
  gate 返回 0=DONE、1=继续写、2=先修问题——非 0 一律不许停、不许提问。
  回合只在输出无工具调用的消息时结束，所以回合内不得收尾；
  一回合链式连跑 k 块，把 N 次接续压成 N/k 次；密度优先（汉字/段 ≥ 120）。
  English: LFBD for ultra-long outputs. Pre-compute x = target ÷ (cap × 0.8), then loop
  GENERATE / AUDIT / REPAIR / DONE. Check volume by several methods; if short keep writing,
  once met run all gates, stop only if all pass. gate: 0=DONE / 1=write more / 2=fix first.
  Never wrap up mid-turn (a turn ends only when a message has no tool call); chain k chunks
  per turn; density metrics included."""

LIMIT = 1024
SAFE = 950


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
    raw = len(DESC)

    print("description：旧 %d → 新 %d" % (len(old_block), raw))
    print("  净字符（去空白）  %4d  / %d" % (net, LIMIT))
    print("  原始长度（含缩进换行）%4d  / %d" % (raw, LIMIT))
    ok = net <= LIMIT and raw <= LIMIT
    if not ok:
        print("!! 超限，必须再删 !!")
        return 1
    if raw > SAFE:
        print("⚠ 原始长度 %d > 安全线 %d，建议再删一点" % (raw, SAFE))
        return 0
    print("✓ 双口径安全（余量 %d）" % (SAFE - raw))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
