#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_v91.py —— 对 run_state.py 做确定性字符串替换（避免编辑工具的锚点问题）"""
import io
import sys

PATH = r"C:\Users\17400\AppData\Local\Temp\chatbox-sandbox\356fa94a-846a-44d9-9029-4c9450777434\lfbd-v9\scripts\run_state.py"

R = []

R.append((
    '    "rounds_planned": 0,        # x = ceil(target / per_round)\n'
    '    "phase": "GENERATE",',
    '    "rounds_planned": 0,        # x = ceil(target / per_round)\n'
    '    "chunks_per_turn": 3,       # 一个回合里链式跑几块（受 harness 迭代上限约束）\n'
    '    "turns_needed": 0,          # ≈ ceil(rounds_planned / chunks_per_turn)\n'
    '    "phase": "GENERATE",'
))

R.append((
    '    "`python scripts/run_state.py next` 看当前阶段，按作业单把本轮到上限写满，再跑 "\n'
    '    "`python scripts/run_state.py gate`；未 exit 0 不许停、不许提问、不许征求确认。"',
    '    "`python scripts/run_state.py next` 看当前阶段，"\n'
    '    "本轮**链式跑满 chunks_per_turn 块**（块与块之间不要收尾、不要报告），再跑 "\n'
    '    "`python scripts/run_state.py gate`；未 exit 0 不许停、不许提问、不许征求确认。"'
))

R.append((
    'def print_next_plan(d, sc, short, m=None, eff=None):',
    'def print_next_plan(d, sc, short, m=None, eff=None, chunks=1):'
))

R.append((
    '    cur = d["cursor"]\n'
    '    done_rounds = len(d["history"])',
    '    cur = d["cursor"]\n'
    '    done_rounds = len(d["history"])\n'
    '    x = max(1, d["rounds_planned"])\n'
    '    k = max(1, min(chunks, d.get("chunks_per_turn", 1)))'
))

R.append((
    '    print("  · 铁令：**加长单块，不要增加块数**（每单元低于 %d 字即不合格）" % cpu)\n'
    '    print("  · 按当前计划，还需约 %d 轮" % rounds)',
    '    print("  · 铁令：**加长单块，不要增加块数**（每单元低于 %d 字即不合格）" % cpu)\n'
    '    if k > 1:\n'
    '        print("  · **轮内链式续跑**：本回合连跑 %d 块（第 %d—%d 轮），中间**不得收尾、不得报告**"\n'
    '              % (k, done_rounds + 1, min(done_rounds + k, x)))\n'
    '        for i in range(k):\n'
    '            print("      %d) 第 %d 轮：%d 单元 × %d 字 = %d 字"\n'
    '                  % (i + 1, done_rounds + i + 1, units, cpu, planned))\n'
    '        print("  · 本回合合计计划 %d 字；写满后再跑 gate" % (k * planned))\n'
    '    print("  · 按当前计划，还需约 %d 轮" % rounds)'
))

R.append((
    '    d["rounds_planned"] = int(math.ceil(d["target"] / max(1, d["per_round"])))\n'
    '    d["phase"] = "GENERATE"',
    '    d["rounds_planned"] = int(math.ceil(d["target"] / max(1, d["per_round"])))\n'
    '    if a.chunks_per_turn:\n'
    '        d["chunks_per_turn"] = a.chunks_per_turn\n'
    '    d["turns_needed"] = int(math.ceil(d["rounds_planned"] / max(1, d["chunks_per_turn"])))\n'
    '    d["phase"] = "GENERATE"'
))

R.append((
    '    print("  轮数 x          ceil(%d / %d) = %d 轮"\n'
    '          % (d["target"], d["per_round"], d["rounds_planned"]))\n'
    '    print("  扫描范围        %s ｜ 前缀 %r" % (d["glob"], d["prefix"]))',
    '    print("  轮数 x          ceil(%d / %d) = %d 轮"\n'
    '          % (d["target"], d["per_round"], d["rounds_planned"]))\n'
    '    print("  轮内链式块数 k  %d 块/回合（受 harness 迭代上限约束）" % d["chunks_per_turn"])\n'
    '    print("  ────────────────────────────────────────")\n'
    '    print("  需你接续的次数   ceil(%d / %d) = %d 次"\n'
    '          % (d["rounds_planned"], d["chunks_per_turn"], d["turns_needed"]))\n'
    '    print("                  （不链式的话是 %d 次；链式把接续次数压到约 1/k）"\n'
    '          % d["rounds_planned"])\n'
    '    print("  扫描范围        %s ｜ 前缀 %r" % (d["glob"], d["prefix"]))'
))

R.append((
    '    print("  本轮每单元目标  %d 字" % d["target_cpu"])',
    '    print("  本轮每单元目标  %d 字" % d["target_cpu"])\n'
    '    print("  首个作业单      python scripts/run_state.py plan --chunks %d"\n'
    '          % d["chunks_per_turn"])'
))

R.append((
    '    print("轮数契约：x = %d 轮 ｜ 每轮 %d 字（%d × %s）"\n'
    '          % (d["rounds_planned"], d["per_round"], d["cap"], d["util"]))',
    '    print("轮数契约：x = %d 轮 ｜ 每轮 %d 字（%d × %s）"\n'
    '          % (d["rounds_planned"], d["per_round"], d["cap"], d["util"]))\n'
    '    print("轮内链式：k = %d 块/回合 ｜ 需接续约 %d 次"\n'
    '          % (d.get("chunks_per_turn", 1), d.get("turns_needed", 0)))'
))

R.append((
    '    print_next_plan(d, r["sc"], r["short"], r["m"], r["eff"])\n'
    '    return 0\n\n\ndef cmd_tick',
    '    print_next_plan(d, r["sc"], r["short"], r["m"], r["eff"], chunks=a.chunks)\n'
    '    return 0\n\n\ndef cmd_tick'
))

R.append((
    '    p.add_argument("--util", type=float, default=0.8, help="利用率，默认 0.8")',
    '    p.add_argument("--util", type=float, default=0.8, help="利用率，默认 0.8")\n'
    '    p.add_argument("--chunks-per-turn", type=int, default=3, dest="chunks_per_turn",\n'
    '                   help="一个回合里链式跑几块（默认 3）")'
))

R.append((
    '        p = sp.add_parser(name); p.set_defaults(f=fn)\n'
    '        p.add_argument("--skip-g10", action="store_true")',
    '        p = sp.add_parser(name); p.set_defaults(f=fn)\n'
    '        p.add_argument("--skip-g10", action="store_true")\n'
    '        if name == "plan":\n'
    '            p.add_argument("--chunks", type=int, default=1,\n'
    '                           help="打印 N 块的连续作业单（轮内链式续跑）")'
))


def main():
    t = io.open(PATH, encoding="utf-8", newline="").read()
    bad = 0
    for i, (old, new) in enumerate(R, 1):
        n = t.count(old)
        if n != 1:
            print("  [%2d] FAIL  命中 %d 次" % (i, n))
            bad += 1
            continue
        t = t.replace(old, new)
        print("  [%2d] OK" % i)
    io.open(PATH, "w", encoding="utf-8", newline="").write(t)
    print("完成：%d/%d，失败 %d" % (len(R) - bad, len(R), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
