#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LFBD v7 — 一行回答"目标/当前/还差/完成度/还需几轮/done"

用法 / Usage:
  python size_report.py --dir scenes --target 170000
  python size_report.py --dir scenes --target 170000 --prefix act4_
"""
import re, os, glob, json, argparse


def cc(t):
    return sum(1 for c in t if '\u4e00' <= c <= '\u9fff')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='scenes')
    ap.add_argument('--target', type=int, required=True)
    ap.add_argument('--prefix', default='')
    a = ap.parse_args()

    files = [f for f in sorted(glob.glob(os.path.join(a.dir, '*.*')))
             if not os.path.basename(f).startswith('_') and not f.endswith(('.py', '.md', '.json'))]
    if a.prefix:
        files = [f for f in files if os.path.basename(f).startswith(a.prefix)]
    total = sum(cc(open(f, encoding='utf-8').read()) for f in files)
    remain = max(0, a.target - total)
    pct = 100.0 * total / a.target if a.target else 0

    cpr = 9000
    if os.path.exists('ledger.json'):
        d = json.load(open('ledger.json', encoding='utf-8'))
        cpr = d.get('calibrated', {}).get('chars_per_round') or cpr
        done = d.get('done')
    else:
        done = None
    rounds = -(-remain // cpr) if remain > 0 else 0
    print('目标 %d ｜ 当前 %d ｜ 还差 %d（%.1f%%）｜ done=%s ｜ 预计还需 %d 轮（按 %d 字/轮）'
          % (a.target, total, remain, pct, done, rounds, cpr))
    if remain > 0:
        print('注意：未达标。按铁律 §1.5，不得宣布完成，继续跑批。')
    else:
        print('字数已达标；请确认 G1–G10 全部通过后再宣布完成。')


if __name__ == '__main__':
    main()
