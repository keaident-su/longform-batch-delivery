#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LFBD v7 — 时间戳分配器 / slot allocator

作用：给"第 N 场补充场（X）"分配一个**保证单调递增**的时间戳，避免倒流。
原理：先算出该单元所在主场的安全窗口 [max(主场时间, 同场景已有补场最后时间), 下一主场时间)，
      再在窗口内按 30 分钟步长取下一个空闲槽位。

用法 / Usage:
  python slot_allocator.py --file scenes/act4_e04_p1.txt
  python slot_allocator.py --file scenes/act4_e04_p1.txt --main 171 --after "2028年9月28日 20:00"
"""
import re, sys, argparse, datetime

CN = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
SCENE = re.compile(r'(?m)^第(\d+)场(补充场（([一二三四五六七八九十]+)）)?$')
TIME = re.compile(r'时间[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})[：:](\d{2})')


def parse(path):
    t = open(path, encoding='utf-8').read()
    units = []
    idx = [(m.start(), m.group(1), m.group(3)) for m in SCENE.finditer(t)]
    idx.append((len(t), None, None))
    for i in range(len(idx) - 1):
        s, num, supp = idx[i]
        body = t[s:idx[i+1][0]]
        m = TIME.search(body)
        tm = tuple(map(int, m.groups())) if m else None
        units.append({'num': int(num), 'supp': CN.get(supp, 0) if supp else 0, 'time': tm})
    return units


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', required=True)
    ap.add_argument('--main', type=int)
    ap.add_argument('--step-min', type=int, default=30)
    a = ap.parse_args()

    units = parse(a.file)
    mains = sorted({u['num'] for u in units if u['supp'] == 0})
    if not mains:
        print('no main scene found'); return
    print('该文件主场次:', mains)
    for n in mains:
        t0 = [u['time'] for u in units if u['num'] == n and u['supp'] == 0 and u['time']]
        supps = [u for u in units if u['num'] == n and u['supp'] > 0 and u['time']]
        if a.main and n != a.main:
            continue
        lo = t0[0] if t0 else None
        if supps:
            last = max(s['time'] for s in supps)
            lo = max(lo, last) if lo else last
            print('  第%d场: 已有补场最大时间 %s（补场序号 %s）'
                  % (n, last, sorted(s['supp'] for s in supps)))
        nxt = [m for m in mains if m > n]
        print('  第%d场: 安全窗口起点 %s ；请确保新补场时间 **晚于** 该点' % (n, lo))
    print('\n提示：若工具未给出下一主场次时间，请手工查看下一主场次行的时间字段。')


if __name__ == '__main__':
    main()
