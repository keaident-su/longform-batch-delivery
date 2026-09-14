#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py —— 证明 v8 的停止谓词真的会"拒绝提前收工"

模拟场景：目标 2000 字，先只写 2 个单元（1600 字）→ 必须判 RUNNING(exit 1)；
补齐到 ≥2000 字且闸门全过 → 才允许 DONE(exit 0)。
"""
import os, re, subprocess, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RS = os.path.join(ROOT, "scripts", "run_state.py")
SCN = os.path.join(HERE, "scenes")

BODY = ("他把作业本摊在桌上，屏幕右下角的时间还停在深夜。"
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
        body += BODY
    return (head +
            "第%d场\n" % n +
            "大纲锚点（作者口径）：自测锚点。\n"
            "时间：2028年2月%d日 20:00\n" % day +
            "地点：东京都新宿区，自测场景。\n"
            "出场人物：徐萱、苏晚\n" + body + "\n\n")


def run(*args):
    r = subprocess.run([sys.executable, RS] + list(args), cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def write_upto(nums_days):
    with open(os.path.join(SCN, "act4_01.txt"), "w", encoding="utf-8") as f:
        f.write(scene(171, 1, ep="第二季·第4集《回潮》"))
        for i, (n, d) in enumerate(nums_days):
            if i == 0:
                continue
            f.write(scene(n, d))


def main():
    if os.path.isdir(HERE):
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

    print("== 1. init ==")
    rc, out = run("init", "--target", "2000",
                  "--glob", "_selftest/scenes/*.txt",
                  "--turn-budget", "10000", "--floors", "700,500")
    print(out.strip())
    expect("init 退出码 0", rc == 0, str(rc))

    print("== 2. 只写 2 个单元（1600 字）→ 必须拒绝收工 ==")
    write_upto([(171, 1), (172, 2)])
    rc, out = run("gate", "--skip-g10")
    print(out.strip())
    expect("未达标必须 exit 1（RUNNING）", rc == 1, "实际 %s" % rc)
    expect("输出里必须带 RESUME 指令", "RESUME" in out)

    print("== 3. tick 记账（吞吐升级梯应顶高每单元目标） ==")
    rc, out = run("tick", "--added", "1600", "--units", "2", "--cursor", "172")
    print(out.strip())
    expect("tick 退出码 0", rc == 0)
    expect("每单元目标被抬高到 >=1300", "每单元 ≥" in out)

    print("== 4. plan 出作业单 ==")
    rc, out = run("plan")
    print(out.strip())
    expect("作业单含'加长单块'铁令", "加长单块" in out)
    expect("作业单含单元数", "单元数" in out)

    print("== 5. 补到 4 个单元（>2000 字）→ 允许 DONE ==")
    write_upto([(171, 1), (172, 2), (173, 3), (174, 4)])
    rc, out = run("gate", "--skip-g10")
    print(out.strip())
    expect("达标且闸门全过必须 exit 0（DONE）", rc == 0, "实际 %s" % rc)
    expect("DONE 输出含'允许在回复里写'", "允许在回复里写" in out)

    print("== 5b. 同一批底稿打开 G10 → 必顶必须 BLOCKED 且仍给 RESUME ==")
    rc, out = run("gate")
    print("\n".join(out.strip().splitlines()[:8]))
    expect("G10 命中 → exit 2", rc == 2, "实际 %s" % rc)
    expect("BLOCKED 也必须给 RESUME（不许停下提问）", "RESUME" in out)

    print("== 6. 注入重号污染 → 必须 BLOCKED(exit 2) ==")
    with open(os.path.join(SCN, "act4_02.txt"), "w", encoding="utf-8") as f:
        f.write(scene(174, 5))
    rc, out = run("gate", "--skip-g10")
    print("\n".join(out.strip().splitlines()[:6]))
    expect("重号必须 exit 2（BLOCKED）", rc == 2, "实际 %s" % rc)
    os.remove(os.path.join(SCN, "act4_02.txt"))

    print("== 7. 时间倒流 → 达标后必须 BLOCKED ==")
    with open(os.path.join(SCN, "act4_01.txt"), "w", encoding="utf-8") as f:
        f.write(scene(171, 9, ep="第二季·第4集《回潮》"))
        f.write(scene(172, 2))
        f.write(scene(173, 3))
        f.write(scene(174, 4))
    rc, out = run("gate", "--skip-g10")
    print("\n".join(out.strip().splitlines()[:6]))
    expect("时间倒流必须拦在 exit 2", rc == 2, "实际 %s" % rc)

    print("\n" + ("=" * 50))
    print("自测结果：%s" % ("全部通过 ✅" if not fails else "失败 %d 项 ❌ %s" % (len(fails), fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
