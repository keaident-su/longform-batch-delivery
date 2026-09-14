#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
restore_enabled.py —— 把 longform-batch-delivery 重新写回 Chatbox 的 enabledSkillNames

背景：description 超过 1024 字符导致 skills:parser 解析失败，
应用随即把该技能从 settings.skills.enabledSkillNames 中摘掉（=“技能不见了”）。
修好 description 后，这里再把名字补回去。

做法：纯文本补丁，保留原文件的缩进与格式，只动数组那一处；写入走“临时文件 + 替换”，避免读到半截文件。
"""
import io
import json
import os
import re
import shutil
import sys

NAME = "longform-batch-delivery"


def main(cfg_path):
    raw = io.open(cfg_path, encoding="utf-8", newline="").read()

    m = re.search(r'"enabledSkillNames"\s*:\s*\[(.*?)\]', raw, re.S)
    if not m:
        print("ERROR: config.json 里找不到 enabledSkillNames")
        return 2

    inner = m.group(1)
    names = re.findall(r'"([^"]+)"', inner)
    print("当前 enabledSkillNames: %s" % names)

    if NAME in names:
        print("已经在了，无需修改。")
        return 0

    # 找出数组元素的缩进
    lines = [l for l in inner.split("\n") if l.strip()]
    indent = "				"
    if lines:
        indent = re.match(r"[ \t]*", lines[-1]).group(0)

    stripped = inner.rstrip()
    new_inner = stripped + ",\n" + indent + '"%s"\n' % NAME
    if inner.endswith("\n"):
        new_inner += inner[len(stripped) + 1:]

    new_raw = raw[:m.start(1)] + new_inner + raw[m.end(1):]

    # 校验仍是合法 JSON
    try:
        obj = json.loads(new_raw)
    except Exception as e:
        print("ERROR: 修改后不是合法 JSON：%s" % e)
        return 3
    got = obj["settings"]["skills"]["enabledSkillNames"]
    if NAME not in got:
        print("ERROR: 写入校验失败")
        return 4

    bak = cfg_path + ".bak-lfbd"
    shutil.copy2(cfg_path, bak)
    tmp = cfg_path + ".tmp-lfbd"
    io.open(tmp, "w", encoding="utf-8", newline="").write(new_raw)
    os.replace(tmp, cfg_path)

    print("已写回：%s" % got)
    print("备份：%s" % bak)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
