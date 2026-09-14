#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ledger.py —— 长文本分批交付协议的进度账本（无第三方依赖）

用法：
  python ledger.py init   --target 170000 --budget 10000 --cursor-chapter 9 --cursor-scene 242
  python ledger.py add    --n 1 --range "第171-200场" --added 10400 --verify PASS
  python ledger.py report
  python ledger.py next   --plan 2

账本文件默认 ./ledger.json。所有写操作会同时刷新 LEDGER.md（人读版）。
"""
import argparse
import json
import math
import os
from datetime import datetime

LEDGER = "ledger.json"
LEDGER_MD = "LEDGER.md"


def _now():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def load(path=LEDGER):
    if not os.path.exists(path):
        return {
            "target": 0, "unit": "cjk_chars", "per_batch_budget": 10000,
            "batches_planned": 0, "batches_done": 0, "current_total": 0,
            "cursor": {"chapter": 0, "scene": 0},
            "updated_at": _now(), "batches": [], "checks": {},
        }
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(d, path=LEDGER):
    d["updated_at"] = _now()
    d["batches_done"] = len(d.get("batches", []))
    d["current_total"] = sum(b.get("added", 0) for b in d.get("batches", []))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    with open(LEDGER_MD, "w", encoding="utf-8") as f:
        f.write(render_md(d))


def render_md(d):
    tgt = d.get("target", 0)
    cur = d.get("current_total", 0)
    left = max(tgt - cur, 0)
    pct = (cur / tgt * 100) if tgt else 0
    lines = []
    lines.append("# LEDGER —— 长文本交付进度账本\n")
    lines.append("| 项目 | 值 |\n|---|---|")
    lines.append("| 目标字数 | %d |" % tgt)
    lines.append("| 当前字数 | %d |" % cur)
    lines.append("| 还差 | **%d** |" % left)
    lines.append("| 完成度 | %.1f%% |" % pct)
    lines.append("| 单批预算 | %d |" % d.get("per_batch_budget", 0))
    lines.append("| 计划批数 / 已完成 | %d / %d |" % (d.get("batches_planned", 0), d.get("batches_done", 0)))
    c = d.get("cursor", {})
    lines.append("| 续写游标 | 第%s章 / 第%s单元 |" % (c.get("chapter", 0), c.get("scene", 0)))
    lines.append("| 更新时间 | %s |" % d.get("updated_at", ""))
    lines.append("\n## 分批记录\n")
    lines.append("| 批 | 范围 | 本批增量 | 累计 | 校验 |\n|---|---|---|---|---|")
    acc = 0
    for b in d.get("batches", []):
        acc += b.get("added", 0)
        lines.append("| %s | %s | +%d | %d | %s |" % (
            b.get("n"), b.get("range", ""), b.get("added", 0), acc, b.get("verify", "-")))
    lines.append("\n## 校验闸门\n")
    for k, v in (d.get("checks") or {}).items():
        lines.append("- %s: %s" % (k, v))
    lines.append("\n> 下一批：读 `cursor`，按单批预算写，写完跑 build_and_verify，再 `ledger.py add`。\n")
    return "\n".join(lines)


def cmd_init(a):
    d = {
        "target": a.target, "unit": a.unit, "per_batch_budget": a.budget,
        "batches_planned": math.ceil(a.target / a.budget) if a.budget else 0,
        "batches_done": 0, "current_total": a.start,
        "cursor": {"chapter": a.cursor_chapter, "scene": a.cursor_scene},
        "updated_at": _now(), "batches": [], "checks": {},
    }
    save(d)
    print("已初始化账本：目标 %d，单批预算 %d，计划 %d 批，起点 %d"
          % (d["target"], d["per_batch_budget"], d["batches_planned"], d["current_total"]))


def cmd_add(a):
    d = load()
    d.setdefault("batches", []).append({
        "n": a.n, "range": a.range, "added": a.added, "verify": a.verify, "at": _now(),
    })
    if a.cursor_chapter is not None:
        d.setdefault("cursor", {})["chapter"] = a.cursor_chapter
    if a.cursor_scene is not None:
        d.setdefault("cursor", {})["scene"] = a.cursor_scene
    if a.set_check:
        for kv in a.set_check:
            k, _, v = kv.partition("=")
            d.setdefault("checks", {})[k] = v
    save(d)
    cmd_report(a)


def cmd_report(a=None):
    d = load()
    tgt, cur = d.get("target", 0), d.get("current_total", 0)
    left = max(tgt - cur, 0)
    print("目标 %d ｜ 当前 %d ｜ 还差 %d（%.1f%%）｜ 已完成 %d/%d 批" % (
        tgt, cur, left, (cur / tgt * 100) if tgt else 0,
        d.get("batches_done", 0), d.get("batches_planned", 0)))


def cmd_next(a):
    d = load()
    tgt, cur = d.get("target", 0), d.get("current_total", 0)
    left = max(tgt - cur, 0)
    budget = d.get("per_batch_budget", 10000)
    n_done = d.get("batches_done", 0)
    print("下一批：第 %d 批，计划 %d 字，还差 %d 字，预计还需 %d 批"
          % (n_done + 1, min(budget, left), left, math.ceil(left / budget) if budget else 0))
    print("游标：", json.dumps(d.get("cursor", {}), ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description="长文本分批交付账本")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init")
    pi.add_argument("--target", type=int, required=True)
    pi.add_argument("--budget", type=int, default=10000)
    pi.add_argument("--start", type=int, default=0)
    pi.add_argument("--unit", default="cjk_chars")
    pi.add_argument("--cursor-chapter", type=int, default=0)
    pi.add_argument("--cursor-scene", type=int, default=0)
    pi.set_defaults(func=cmd_init)

    pa = sub.add_parser("add")
    pa.add_argument("--n", type=int, required=True)
    pa.add_argument("--range", required=True)
    pa.add_argument("--added", type=int, required=True)
    pa.add_argument("--verify", default="PASS")
    pa.add_argument("--cursor-chapter", type=int, default=None)
    pa.add_argument("--cursor-scene", type=int, default=None)
    pa.add_argument("--set-check", action="append", default=[])
    pa.set_defaults(func=cmd_add)

    sub.add_parser("report").set_defaults(func=cmd_report)

    pn = sub.add_parser("next")
    pn.add_argument("--plan", type=int, default=1)
    pn.set_defaults(func=cmd_next)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
