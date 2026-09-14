#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LFBD v7 — 账本工具 / ledger tool

用法 / Usage:
  python ledger.py init   --target 170000 --prefix act4_
  python ledger.py update --add 15600 --blocks 12
  python ledger.py show
  python ledger.py next   --chars-per-round 13000

账本文件 / Ledger file: ./ledger.json
"""
import json, os, sys, argparse, datetime

LEDGER = 'ledger.json'


def load():
    if not os.path.exists(LEDGER):
        print('no ledger.json; run: python ledger.py init --target N --prefix PREFIX')
        sys.exit(1)
    return json.load(open(LEDGER, encoding='utf-8'))


def save(d):
    d['remaining'] = max(0, d['target'] - d['current_total'])
    d['progress_pct'] = round(100.0 * d['current_total'] / d['target'], 1) if d['target'] else 0.0
    d['done'] = bool(d['current_total'] >= d['target']) and all(d.get('checks', {}).values()) and bool(d.get('checks'))
    json.dump(d, open(LEDGER, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['init', 'update', 'show', 'next'])
    ap.add_argument('--target', type=int, default=170000)
    ap.add_argument('--prefix', default='')
    ap.add_argument('--add', type=int, default=0)
    ap.add_argument('--blocks', type=int, default=0)
    ap.add_argument('--chars-per-round', type=int, default=9000)
    a = ap.parse_args()

    if a.cmd == 'init':
        d = {
            'target': a.target, 'unit': 'cjk_chars',
            'calibrated': {'chars_per_block': 0, 'chars_per_round': 0},
            'current_total': 0, 'remaining': a.target, 'progress_pct': 0.0,
            'cursor': {'chapter': 0, 'scene': 0},
            'floors': {'main': 700, 'supp': 500},
            'file_prefixes': [a.prefix] if a.prefix else [],
            'done': False,
            'checks': {},
            'updated_at': datetime.datetime.now().isoformat(timespec='seconds'),
        }
        save(d)
        print('ledger initialized:', json.dumps(d, ensure_ascii=False))
        return

    d = load()
    if a.cmd == 'update':
        d['current_total'] += a.add
        if a.blocks:
            d['calibrated']['chars_per_block'] = round(a.add / a.blocks, 1)
        d['calibrated']['chars_per_round'] = a.add
        d['updated_at'] = datetime.datetime.now().isoformat(timespec='seconds')
        save(d)
        print('目标 %d ｜ 当前 %d ｜ 还差 %d（%.1f%%）｜ done=%s'
              % (d['target'], d['current_total'], d['remaining'], d['progress_pct'], d['done']))
        return

    if a.cmd == 'show':
        print('目标 %d ｜ 当前 %d ｜ 还差 %d（%.1f%%）｜ done=%s'
              % (d['target'], d['current_total'], d['remaining'], d['progress_pct'], d['done']))
        print('checks:', d.get('checks'))
        return

    if a.cmd == 'next':
        cpr = d['calibrated'].get('chars_per_round') or a.chars_per_round
        cpr = max(1000, cpr)
        rounds = -(-d['remaining'] // cpr) if d['remaining'] > 0 else 0
        print('还差 %d 字；按实测 %d 字/轮，预计还需 %d 轮' % (d['remaining'], cpr, rounds))
        return


if __name__ == '__main__':
    main()
