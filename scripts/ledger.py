#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ledger.py —— 长文本分批交付：账本初始化 / 更新 / 查询 / 算下一批

零依赖。用法：
  python scripts/ledger.py init --target 170000 --parts "上册:238" "下册:0"
  python scripts/ledger.py update --added 11511 --blocks 28 --cursor 270
  python scripts/ledger.py show
  python scripts/ledger.py next --remaining-round-chars 9200
"""

import os, sys, json, argparse, datetime

LEDGER = "ledger.json"
DEFAULTS = {
    "target": 0,
    "unit": "cjk_chars",
    "current_total": 0,
    "calibrated": {"chars_per_block": 0, "chars_per_round": 9000},
    "cursor": {"chapter": 0, "scene": 0},
    "parts": [],
    "floors": {"main": 700, "sub": 500},
    "batches": [],
    "checks": {},
    "updated_at": "",
}


def load():
    if os.path.exists(LEDGER):
        try:
            d = json.load(open(LEDGER, encoding="utf-8"))
            for k, v in DEFAULTS.items():
                d.setdefault(k, v)
            return d
        except Exception:
            pass
    return dict(DEFAULTS)


def save(d):
    d["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    d["remaining"] = max(0, d.get("target", 0) - d.get("current_total", 0))
    t = d.get("target", 0) or 1
    d["progress_pct"] = round(100.0 * d.get("current_total", 0) / t, 1)
    json.dump(d, open(LEDGER, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    # 同步人读版
    md = [
        "# LEDGER",
        "",
        "| 项目 | 值 |",
        "|---|---|",
        "| 目标 | %d |" % d["target"],
        "| 当前 | %d |" % d["current_total"],
        "| 还差 | %d |" % d["remaining"],
        "| 完成度 | %.1f%% |" % d["progress_pct"],
        "| 实测吞吐 | %d 字/块 ｜ %d 字/轮 |" % (
            d["calibrated"].get("chars_per_block", 0),
            d["calibrated"].get("chars_per_round", 0)),
        "| 游标 | 章 %s ｜ 场 %s |" % (d["cursor"].get("chapter"), d["cursor"].get("scene")),
        "| 更新时间 | %s |" % d["updated_at"],
        "",
        "## 分批记录",
        "",
        "| 批 | 范围 | 新增 | 累计 | 校验 |",
        "|---|---|---|---|---|",
    ]
    for b in d["batches"]:
        md.append("| %s | %s | +%s | %s | %s |" % (
            b.get("n"), b.get("range"), b.get("added"), b.get("total"), b.get("verify")))
    open("LEDGER.md", "w", encoding="utf-8").write("\n".join(md) + "\n")


def cmd_init(a):
    d = load()
    d["target"] = a.target
    d["parts"] = []
    for p in (a.parts or []):
        name, _, mx = p.partition(":")
        d["parts"].append({"name": name, "max_id": int(mx) if mx else 0})
    save(d)
    print("已初始化账本：目标 %d" % a.target)


def cmd_update(a):
    d = load()
    cur = d["current_total"] + a.added
    cpb = int(a.added / a.blocks) if a.blocks else d["calibrated"].get("chars_per_block", 0)
    d["current_total"] = cur
    d["calibrated"] = {"chars_per_block": cpb, "chars_per_round": a.added}
    if a.cursor:
        d["cursor"]["scene"] = a.cursor
    d["batches"].append({
        "n": len(d["batches"]) + 1,
        "range": a.range or "",
        "added": a.added,
        "total": cur,
        "verify": a.verify or "PASS",
    })
    save(d)
    remaining = d["remaining"]
    print("当前 %d ｜ 还差 %d ｜ 完成度 %.1f%% ｜ 实测 %d 字/块" % (
        cur, remaining, d["progress_pct"], cpb))
    if a.added:
        print("按本批吞吐，还需约 %d 轮" % (-(-remaining // a.added)))


def cmd_show(a):
    d = load()
    print("目标 %d ｜ 当前 %d ｜ 还差 %d（%.1f%%）" % (
        d["target"], d["current_total"], d["remaining"], d["progress_pct"]))
    print("实测吞吐：%d 字/块 ｜ %d 字/轮" % (
        d["calibrated"].get("chars_per_block", 0),
        d["calibrated"].get("chars_per_round", 0)))
    print("游标：场 %s ｜ 批次数 %d" % (d["cursor"].get("scene"), len(d["batches"])))


def cmd_next(a):
    d = load()
    r = max(1, a.remaining_round_chars or d["calibrated"].get("chars_per_round", 9000))
    print("下一批：范围由游标（场 %s）向后，计划字数 %d" % (d["cursor"].get("scene"), r))
    print("剩余轮数 ≈ %d" % (-(-d["remaining"] // r)))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("init"); p.add_argument("--target", type=int, required=True)
    p.add_argument("--parts", nargs="*"); p.set_defaults(f=cmd_init)
    p = sp.add_parser("update"); p.add_argument("--added", type=int, required=True)
    p.add_argument("--blocks", type=int, default=0); p.add_argument("--cursor", type=int, default=0)
    p.add_argument("--range", default=""); p.add_argument("--verify", default="")
    p.set_defaults(f=cmd_update)
    p = sp.add_parser("show"); p.set_defaults(f=cmd_show)
    p = sp.add_parser("next"); p.add_argument("--remaining-round-chars", type=int, default=0)
    p.set_defaults(f=cmd_next)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
