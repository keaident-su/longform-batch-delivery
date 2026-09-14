#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_v92.py —— 给 run_state.py 加入 Work Mode 窗口（25 步）估算与 calibrate"""
import io
import sys

PATH = r"C:\Users\17400\AppData\Local\Temp\chatbox-sandbox\356fa94a-846a-44d9-9029-4c9450777434\lfbd-v9\scripts\run_state.py"

R = []

# 1) DEFAULTS 增加窗口参数
R.append((
    '    "turns_needed": 0,          # ≈ ceil(rounds_planned / chunks_per_turn)',
    '    "turns_needed": 0,          # ≈ ceil(rounds_planned / chunks_per_turn)\n'
    '    "steps_per_window": 25,     # Chatbox Work Mode：每 25 次连续工具调用暂停一次\n'
    '    "calls_per_chunk": 2,       # 写一块大约要几次工具调用（write_file + 校验）'
))

# 2) init 计算窗口数
R.append((
    '    d["turns_needed"] = int(math.ceil(d["rounds_planned"] / max(1, d["chunks_per_turn"])))',
    '    d["turns_needed"] = int(math.ceil(d["rounds_planned"] / max(1, d["chunks_per_turn"])))\n'
    '    if a.steps_per_window:\n'
    '        d["steps_per_window"] = a.steps_per_window\n'
    '    if a.calls_per_chunk:\n'
    '        d["calls_per_chunk"] = a.calls_per_chunk\n'
    '    cw = max(1, d["steps_per_window"] // max(1, d["calls_per_chunk"]))\n'
    '    d["chunks_per_window"] = cw\n'
    '    d["windows_needed"] = int(math.ceil(d["rounds_planned"] / cw))'
))

# 3) init 打印窗口信息
R.append((
    '    print("  需你接续的次数   ceil(%d / %d) = %d 次"\n'
    '          % (d["rounds_planned"], d["chunks_per_turn"], d["turns_needed"]))',
    '    print("  需你接续的次数   ceil(%d / %d) = %d 次"\n'
    '          % (d["rounds_planned"], d["chunks_per_turn"], d["turns_needed"]))\n'
    '    print("")\n'
    '    print("  —— Chatbox Work Mode 检查点 ——")\n'
    '    print("  每 %d 次工具调用暂停一次（产品硬护栏，不可配置）" % d["steps_per_window"])\n'
    '    print("  每块约 %d 次调用 → 每个窗口可写 %d 块" % (d["calls_per_chunk"], d["chunks_per_window"]))\n'
    '    print("  **预计只需点 %d 次 Continue**" % d["windows_needed"])'
))

# 4) 新增 --steps-per-window / --calls-per-chunk
R.append((
    '    p.add_argument("--chunks-per-turn", type=int, default=3, dest="chunks_per_turn",\n'
    '                   help="一个回合里链式跑几块（默认 3）")',
    '    p.add_argument("--chunks-per-turn", type=int, default=3, dest="chunks_per_turn",\n'
    '                   help="一个回合里链式跑几块（默认 3）")\n'
    '    p.add_argument("--steps-per-window", type=int, default=25, dest="steps_per_window",\n'
    '                   help="Work Mode 每多少次工具调用暂停一次（默认 25）")\n'
    '    p.add_argument("--calls-per-chunk", type=int, default=2, dest="calls_per_chunk",\n'
    '                   help="写一块大约几次工具调用（默认 2）")'
))

# 5) where 显示窗口信息
R.append((
    '    print("轮内链式：k = %d 块/回合 ｜ 需接续约 %d 次"\n'
    '          % (d.get("chunks_per_turn", 1), d.get("turns_needed", 0)))',
    '    print("轮内链式：k = %d 块/回合 ｜ 需接续约 %d 次"\n'
    '          % (d.get("chunks_per_turn", 1), d.get("turns_needed", 0)))\n'
    '    print("Work Mode：每 %s 次调用暂停 ｜ 每窗口 %s 块 ｜ 预计点 %s 次 Continue"\n'
    '          % (d.get("steps_per_window"), d.get("chunks_per_window", 0),\n'
    '             d.get("windows_needed", 0)))'
))

# 6) 新增 calibrate 命令
R.append((
    'def cmd_resume(a):',
    'def cmd_calibrate(a):\n'
    '    """用实测数据反推 cap：把"单轮输出上限"换成真实观测值，重算 x。"""\n'
    '    d = load()\n'
    '    hist = d.get("history", [])\n'
    '    if not hist:\n'
    '        print("还没有轮次记录，先跑至少一轮 tick 再校准。")\n'
    '        return 2\n'
    '    cpus = [h.get("cpu", 0) for h in hist if h.get("cpu")]\n'
    '    if not cpus:\n'
    '        print("历史记录里没有 chars_per_unit，无法校准。")\n'
    '        return 2\n'
    '    cpus.sort()\n'
    '    med = cpus[len(cpus) // 2]\n'
    '    old_cap = d["cap"]\n'
    '    old_x = d["rounds_planned"]\n'
    '    # 单块实测产出 → 反推单次回复的真实容量（块 = 一次回复的产出）\n'
    '    d["cap"] = max(500, med)\n'
    '    d["per_round"] = int(round(d["cap"] * d["util"]))\n'
    '    d["rounds_planned"] = int(math.ceil(d["target"] / max(1, d["per_round"])))\n'
    '    cw = max(1, d["steps_per_window"] // max(1, d["calls_per_chunk"]))\n'
    '    d["chunks_per_window"] = cw\n'
    '    d["windows_needed"] = int(math.ceil(d["rounds_planned"] / cw))\n'
    '    d["turns_needed"] = int(math.ceil(d["rounds_planned"] / max(1, d["chunks_per_turn"])))\n'
    '    save(d)\n'
    '    print("已按实测校准：")\n'
    '    print("  单块实测中位数   %d 字（样本 %d 块）" % (med, len(cpus)))\n'
    '    print("  单轮上限 cap     %d → %d" % (old_cap, d["cap"]))\n'
    '    print("  轮数 x           %d → %d" % (old_x, d["rounds_planned"]))\n'
    '    print("  **预计点 Continue 次数：%d**" % d["windows_needed"])\n'
    '    return 0\n'
    '\n'
    '\n'
    'def cmd_resume(a):'
))

# 7) 注册 calibrate 子命令
R.append((
    '    for name, fn in (("resume", cmd_resume), ("where", cmd_where)):\n'
    '        p = sp.add_parser(name); p.set_defaults(f=fn)',
    '    for name, fn in (("resume", cmd_resume), ("where", cmd_where),\n'
    '                     ("calibrate", cmd_calibrate)):\n'
    '        p = sp.add_parser(name); p.set_defaults(f=fn)'
))

# 8) 版本号
R.append((
    '    "version": "9.1.0",',
    '    "version": "9.2.0",'
))


def main():
    t = io.open(PATH, encoding="utf-8", newline="").read()
    bad = 0
    for i, (old, new) in enumerate(R, 1):
        n = t.count(old)
        if n != 1:
            print("  [%d] FAIL  命中 %d 次" % (i, n))
            bad += 1
            continue
        t = t.replace(old, new)
        print("  [%d] OK" % i)
    io.open(PATH, "w", encoding="utf-8", newline="").write(t)
    print("完成：%d/%d，失败 %d" % (len(R) - bad, len(R), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
