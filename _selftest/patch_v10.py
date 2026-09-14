#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_v10.py —— LFBD v10：回合内不许收尾 + 密度度量"""
import io
import sys

BASE = r"C:\Users\17400\AppData\Local\Temp\chatbox-sandbox\356fa94a-846a-44d9-9029-4c9450777434\lfbd-v9"
R = []

# R1 默认值：加 density 阈值
R.append((
    '    "chunks_per_turn": 3,       # 一个回合里链式跑几块（受 harness 迭代上限约束）',
    '    "chunks_per_turn": 8,       # 一个回合里链式跑几块（回合内不许收尾）\n'
    '    "density": {"cjk_per_para": 120, "dialogue_ratio": 0.5},'
))

# R2 密度计算函数 + 命令，插在 cmd_resume 之前
R.append((
    'def cmd_resume(a):',
    'def density_stats(sc):\n'
    '    """统计正文密度：对白段产出率极低，必须能量化地盯住。"""\n'
    '    text = sc["text"]\n'
    '    cjk = len(CJK.findall(text))\n'
    '    paras = [p for p in re.split(r"\\n\\s*\\n", text) if p.strip()]\n'
    '    lines = [l for l in text.split("\\n") if l.strip()]\n'
    '    dlg = [l for l in lines\n'
    '           if l.strip().startswith(("\\u201c", "\\""))\n'
    '           or "\\uff1a\\u201c" in l or \'\\uff1a"\' in l]\n'
    '    return {\n'
    '        "cjk": cjk,\n'
    '        "paras": len(paras),\n'
    '        "lines": len(lines),\n'
    '        "cjk_per_para": round(cjk / max(1, len(paras)), 1),\n'
    '        "cjk_per_line": round(cjk / max(1, len(lines)), 1),\n'
    '        "dialogue_ratio": round(len(dlg) / max(1, len(lines)), 3),\n'
    '    }\n'
    '\n'
    '\n'
    'def cmd_density(a):\n'
    '    d = load()\n'
    '    sc = scan(d)\n'
    '    s = density_stats(sc)\n'
    '    th = d.get("density", {})\n'
    '    pmin = th.get("cjk_per_para", 120)\n'
    '    dmax = th.get("dialogue_ratio", 0.5)\n'
    '    print("=" * 64)\n'
    '    print("正文密度核算（对白段汉字产出率极低，这是最大的隐形浪费）")\n'
    '    print("=" * 64)\n'
    '    print("  汉字总数            %d" % s["cjk"])\n'
    '    print("  段落数 / 行数        %d / %d" % (s["paras"], s["lines"]))\n'
    '    print("  汉字/段            %8.1f   （目标 ≥ %d）%s"\n'
    '          % (s["cjk_per_para"], pmin, "" if s["cjk_per_para"] >= pmin else "  ← 偏低"))\n'
    '    print("  汉字/行            %8.1f" % s["cjk_per_line"])\n'
    '    print("  对白行占比         %7.1f%%  （目标 ≤ %.0f%%）%s"\n'
    '          % (s["dialogue_ratio"] * 100, dmax * 100,\n'
    '             "" if s["dialogue_ratio"] <= dmax else "  ← 偏高，一行一句最费回合预算"))\n'
    '    ok = s["cjk_per_para"] >= pmin and s["dialogue_ratio"] <= dmax\n'
    '    print("  结论：%s" % ("密度达标" if ok else "**密度不合格：下一块请用密集叙述写，不要一句一换行**"))\n'
    '    print("=" * 64)\n'
    '    return 0 if ok else 2\n'
    '\n'
    '\n'
    'def cmd_resume(a):'
))

# R3 plan 里加密度要求
R.append((
    '        print("  · 本回合合计计划 %d 字；写满后再跑 gate" % (k * planned))',
    '        print("  · 本回合合计计划 %d 字；写满后再跑 gate" % (k * planned))\n'
    '        print("  · **回合内不许收尾**：块与块之间不输出任何汇总、表格或结尾语")\n'
    '        print("  · 密度要求：汉字/段 ≥ %d；对白行占比 ≤ %.0f%%（用密集叙述，不要一句一换行）"\n'
    '              % (d.get("density", {}).get("cjk_per_para", 120),\n'
    '                 d.get("density", {}).get("dialogue_ratio", 0.5) * 100))'
))

# R4 注册 density 命令
R.append((
    '                     ("next", cmd_next), ("count", cmd_count)):',
    '                     ("next", cmd_next), ("count", cmd_count),\n'
    '                     ("density", cmd_density)):'
))

# R5 版本号
R.append((
    '    "version": "9.1.0",',
    '    "version": "10.0.0",'
))

# R6 RESUME 指令强化
R.append((
    '"本轮**链式跑满 chunks_per_turn 块**（块与块之间不要收尾、不要报告），再跑 "',
    '"本轮**链式跑满 chunks_per_turn 块**（块与块之间不许输出任何汇总/汇报/结尾语），再跑 "'
))


def main():
    path = BASE + r"\scripts\run_state.py"
    t = io.open(path, encoding="utf-8", newline="").read()
    bad = 0
    for i, (old, new) in enumerate(R, 1):
        n = t.count(old)
        if n != 1:
            print("  [%d] FAIL 命中 %d 次" % (i, n))
            bad += 1
            continue
        t = t.replace(old, new)
        print("  [%d] OK" % i)
    io.open(path, "w", encoding="utf-8", newline="").write(t)
    print("v10 补丁：%d/%d，失败 %d" % (len(R) - bad, len(R), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
