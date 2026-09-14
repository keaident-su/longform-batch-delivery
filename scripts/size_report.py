#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
size_report.py —— 一行命令回答："目标多少、现在多少、还差多少、还要几轮"

用法：
  python scripts/size_report.py --dir scenes --glob "*.txt" --target 170000
  python scripts/size_report.py --target 170000 --per-round 9200 --floors 700,500
"""
import os, re, sys, glob, argparse, json

CJK = re.compile(r"[\u4e00-\u9fff]")


def cjk_len(s):
    return len(CJK.findall(s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    ap.add_argument("--glob", default="*.txt")
    ap.add_argument("--prefix", default="", help="只统计此前缀的文件（配合 RUN.lock）")
    ap.add_argument("--target", type=int, default=0)
    ap.add_argument("--per-round", type=int, default=9000)
    ap.add_argument("--floors", default="700,500", help="主单元地板,从单元地板")
    ap.add_argument("--ledger", default="ledger.json")
    a = ap.parse_args()

    files = sorted(set(glob.glob(os.path.join(a.dir, a.glob))))
    if a.prefix:
        files = [f for f in files if os.path.basename(f).startswith(a.prefix)]

    total, blocks, sizes = 0, 0, []
    unit_re = re.compile(r"^第(\d+)(?:场|章)$")
    for f in files:
        for line in open(f, encoding="utf-8"):
            if unit_re.match(line.strip()):
                blocks += 1
        t = open(f, encoding="utf-8").read()
        total += cjk_len(t)

    unit_texts = []
    for f in files:
        t = open(f, encoding="utf-8").read()
        parts = re.split(r"(?m)^(?=第\d+(?:场|章))", t)
        for p in parts:
            n = cjk_len(p)
            if n:
                unit_texts.append(n)

    target = a.target
    if not target and os.path.exists(a.ledger):
        try:
            target = json.load(open(a.ledger, encoding="utf-8")).get("target", 0)
        except Exception:
            target = 0

    floors = [int(x) for x in a.floors.split(",")]
    main_floor, sub_floor = (floors + [700, 500])[:2]
    short = [n for n in unit_texts if n < sub_floor]

    print("=" * 62)
    print("文件数 %d ｜ 单元数 %d ｜ 中文字符 %d" % (len(files), blocks, total))
    if target:
        remain = max(0, target - total)
        print("目标 %d ｜ 当前 %d ｜ 还差 %d ｜ 完成度 %.1f%%"
              % (target, total, remain, 100.0 * total / target))
        print("按 %d 字/轮，还需约 %d 轮" % (a.per_round, -(-remain // a.per_round)))
    avg = int(total / max(1, len(unit_texts))) if unit_texts else 0
    print("平均单元字数 %d（主单元地板 %d，从单元地板 %d）" % (avg, main_floor, sub_floor))
    if short:
        print("低于从单元地板的单元：%d 个 → 建议【加长单块】而不是【增加块数】" % len(short))
    else:
        print("所有单元均达标。")
    print("=" * 62)


if __name__ == "__main__":
    sys.exit(main())
