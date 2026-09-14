#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_config.py —— 关闭 Chatbox 的"工具调用次数上限暂停"（pauseOnToolCallLimit）"""
import io
import json
import os
import shutil
import sys

CFG = os.path.join(os.environ["APPDATA"], "xyz.chatboxapp.app", "config.json")


def main():
    raw = io.open(CFG, encoding="utf-8", newline="").read()
    old = '"pauseOnToolCallLimit": true'
    alt = '"pauseOnToolCallLimit":true'
    if old in raw:
        new_raw = raw.replace(old, '"pauseOnToolCallLimit": false')
    elif alt in raw:
        new_raw = raw.replace(alt, '"pauseOnToolCallLimit":false')
    else:
        print("未找到 pauseOnToolCallLimit: true（可能已经是 false）")
        return 0

    obj = json.loads(new_raw)
    if obj["settings"]["pauseOnToolCallLimit"] is not False:
        print("ERROR: 写入校验失败")
        return 2

    bak = CFG + ".bak-pause"
    shutil.copy2(CFG, bak)
    tmp = CFG + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="").write(new_raw)
    os.replace(tmp, CFG)

    print("已关闭 pauseOnToolCallLimit（原 true → false）")
    print("备份：%s" % bak)
    return 0


if __name__ == "__main__":
    sys.exit(main())
