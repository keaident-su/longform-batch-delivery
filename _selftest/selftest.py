#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py —— LFBD v9 回归测试

验证用户的六步流程是否真的被机器执行：
  ① 轮数 x = 目标 ÷ (单轮上限 × 0.8) 必须先算出来
  ② 字数没到 → 只能继续写（exit 1，GENERATE）
  ③ 多路核字数（count）
  ④ 字数到了但有问题 → 修（exit 2，REPAIR/BLOCKED）
  ⑤ 全过 → 才允许停（exit 0，DONE）
  ⑥ 任何阶段都不许"停下来提问"——非 DONE 必须带 RESUME
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RS = os.path.join(ROOT, "scripts", "run_state.py")
SCN = os.path.join(HERE, "scenes")

SENT = ("他把作业本摊在桌上，屏幕右下角的时间还停在深夜。"
        "远处传来列车经过的声音，窗框跟着轻轻震动。")


def scene(n, day, chars=800, ep=None):
    head = ""
    if ep:
        head = ("═" * 40 + "\n" + ep + "\n"
                "【本集时间线】2028年2月1日 20:00 — 2028年2月9日 22:00\n"
                "本集概要（按作者更正口径）：自测用。\n"
                "本集场次：第%d场—第%d场\n" % (n, n + 1) + "═" * 40 + "\n")
    body = ""
    while len(re.findall(r"[\u4e00-\u9fff]", body)) < chars:
        body += SENT
    return (head + "第%d场\n" % n +
            "大纲锚点（作者口径）：自测锚点。\n"
            "时间：2028年2月%d日 20:00\n" % day +
            "地点：东京都新宿区，自测场景。\n"
            "出场人物：徐萱、苏晚\n" + body + "\n\n")


def run(*args):
    r = subprocess.run([sys.executable, RS] + list(args), cwd=ROOT,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def write_scenes(pairs, ep=None):
    with open(os.path.join(SCN, "act4_01.txt"), "w", encoding="utf-8") as f:
        for i, (n, d) in enumerate(pairs):
            f.write(scene(n, d, ep=ep if i == 0 else None))


def main():
    shutil.rmtree(os.path.join(HERE, "scenes"), ignore_errors=True)
    os.makedirs(SCN, exist_ok=True)
    for f in ("run_state.json", "LEDGER.md"):
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            os.remove(p)

    fails = []

    def expect(name, cond, extra=""):
        print(("  PASS  " if cond else "  FAIL  ") + name + (" " + extra if extra else ""))
        if not cond:
            fails.append(name)

    # ---------------- ① 轮数契约 ----------------
    print("== 1. 轮数契约 x = 目标 ÷ (上限 × 0.8) ==")
    rc, out = run("init", "--target", "20000", "--cap", "5000", "--util", "0.8",
                  "--glob", "_selftest/scenes/*.txt", "--floors", "700,500")
    line = [l for l in out.splitlines() if "轮数 x" in l]
    print("  " + (line[0] if line else out.strip()))
    expect("init 退出码 0", rc == 0)
    expect("x = ceil(20000/4000) = 5", "= 5 轮" in out, "实际: %s" % (line[0] if line else "?"))
    expect("每轮计划产出 = 4000", "4000" in out)
    expect("算出需接续次数 ceil(5/3)=2", "= 2 次" in out, "实际: %s" % [l for l in out.splitlines() if "接续的次数" in l])
    expect("算出 Work Mode 窗口：每 25 步暂停", "25 次工具调用暂停一次" in out)
    expect("给出预计 Continue 次数", "Continue" in out)
    expect("给出 calibrate 提示", "calibrate" in out or "首个作业单" in out)

    # 换个目标，方便后续跑到 DONE
    rc, out = run("init", "--target", "3000", "--cap", "5000", "--util", "0.8",
                  "--glob", "_selftest/scenes/*.txt", "--floors", "700,500")
    expect("重新 init 退出码 0", rc == 0)

    # ---------------- ② 字数没到 → 只能继续写 ----------------
    print("== 2. 字数没到：必须 GENERATE / exit 1 ==")
    write_scenes([(171, 1), (172, 2)], ep="第二季·第4集《回潮》")
    rc, out = run("gate", "--skip-g10")
    print("  " + [l for l in out.splitlines() if l.startswith("状态：")][0])
    expect("gate 未达标 → exit 1", rc == 1, "实际 %s" % rc)
    expect("输出必须带 RESUME", "RESUME" in out)
    expect("输出必须标明阶段 GENERATE", "GENERATE" in out)

    rc, out = run("next", "--skip-g10")
    expect("next 未达标 → exit 1", rc == 1, "实际 %s" % rc)
    expect("next 明说『继续写』", "继续写" in out)
    expect("next 带契约轮次 1/1", "1/1" in out or "第 1 轮" in out)

    # ---------------- ③ 多路核字数 ----------------
    print("== 3. 多路核字数 count ==")
    rc, out = run("count")
    print("  " + [l for l in out.splitlines() if "判定口径" in l][0])
    expect("count 未达标 → exit 1", rc == 1, "实际 %s" % rc)
    expect("至少给出 4 种口径", out.count("源文件·") >= 4)
    expect("给出最严口径说明", "取最严" in out)

    # ---------------- ④ tick 记账 + 升级梯 ----------------
    print("== 4. tick 记账与吞吐升级梯 ==")
    rc, out = run("tick", "--added", "1600", "--units", "2", "--cursor", "172")
    print("  " + out.splitlines()[0])
    expect("tick 退出码 0", rc == 0)
    expect("记录为第 1/1 轮", "1/1" in out)

    # ---------------- ④.5 轮内链式续跑 ----------------
    print("== 4.5 plan --chunks：轮内链式续跑作业单 ==")
    rc, out = run("plan", "--chunks", "3", "--skip-g10")
    print("  " + [l for l in out.splitlines() if "链式续跑" in l][0] if "链式续跑" in out else "  （未命中）")
    expect("plan --chunks 3 退出码 0", rc == 0, "实际 %s" % rc)
    expect("输出含『轮内链式续跑』", "链式续跑" in out)
    expect("输出含『不得收尾』", "不得收尾" in out)
    expect("列出 3 个连续块的轮次", out.count("第 ") >= 3)

    # ---------------- ⑤ 字数达标 → DONE ----------------
    print("== 5. 字数达标且闸门全过 → DONE / exit 0 ==")
    write_scenes([(171, 1), (172, 2), (173, 3), (174, 4)], ep="第二季·第4集《回潮》")
    rc, out = run("gate", "--skip-g10")
    print("  " + [l for l in out.splitlines() if l.startswith("状态：")][0])
    expect("达标全过 → exit 0", rc == 0, "实际 %s" % rc)
    expect("DONE 才允许写『完成』", "允许在回复里写" in out)

    rc, out = run("next", "--skip-g10")
    expect("next 在 DONE 时 exit 0", rc == 0, "实际 %s" % rc)

    # ---------------- ⑥ 字数到了但有问题 → REPAIR ----------------
    print("== 6. 字数达标但时间倒流 → REPAIR / exit 2 ==")
    write_scenes([(171, 9), (172, 2), (173, 3), (174, 4)], ep="第二季·第4集《回潮》")
    rc, out = run("gate", "--skip-g10")
    print("  " + [l for l in out.splitlines() if l.startswith("状态：")][0])
    expect("时间倒流 → exit 2", rc == 2, "实际 %s" % rc)
    expect("REPAIR 阶段仍给 RESUME", "RESUME" in out)
    expect("明确指出哪一场倒流", "时间倒流" in out)

    rc, out = run("next", "--skip-g10")
    expect("next 在 REPAIR 时 exit 2", rc == 2, "实际 %s" % rc)
    expect("next 明说『先修问题』", "先修问题" in out)

    # ---------------- ⑦ 重号 → BLOCKED ----------------
    print("== 7. 重号污染 → BLOCKED / exit 2 ==")
    write_scenes([(171, 1), (172, 2), (173, 3), (174, 4)], ep="第二季·第4集《回潮》")
    with open(os.path.join(SCN, "act4_02.txt"), "w", encoding="utf-8") as f:
        f.write(scene(174, 5))
    rc, out = run("gate", "--skip-g10")
    print("  " + [l for l in out.splitlines() if l.startswith("状态：")][0])
    expect("重号 → exit 2", rc == 2, "实际 %s" % rc)
    expect("点名 BLOCKED", "BLOCKED" in out)
    os.remove(os.path.join(SCN, "act4_02.txt"))

    # ---------------- ⑧ G10 内容一致性 ----------------
    print("== 8. 逐字重复 → G10 命中 / exit 2 ==")
    rc, out = run("gate")
    expect("G10 命中 → exit 2", rc == 2, "实际 %s" % rc)
    expect("G10 提示跑 dedupe_scan", "dedupe_scan" in out)

    # ---------------- ⑨ 报告 ----------------
    print("== 9. report 固定汇报表 ==")
    rc, out = run("report", "--skip-g10")
    expect("report 含『目标』『当前』『还差』『完成度』",
           all(k in out for k in ("目标", "当前", "还差", "完成度")))
    expect("report 含轮次与阶段", "阶段" in out and "轮" in out)

    print("\n" + "=" * 52)
    print("自测结果：%s" % ("全部通过 ✅" if not fails
                          else "失败 %d 项 ❌ %s" % (len(fails), fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
