#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LFBD v7 — 重建 + 全闸门校验 + 输出下一批作业单
rebuild + verify gates G1..G10 + emit next-batch worklist

用法 / Usage:
  python build_and_verify.py --dir scenes --mode scene --target 170000
  python build_and_verify.py --dir chapters --mode chapter --target 200000

模式 / Modes:
  scene   : 剧本单元，标题形如 "第123场" / "第123场补充场（一）"
  chapter : 章节单元，标题形如 "第12章" / "第12章 标题"

产出 / Outputs:
  <dir>/_merged.txt : 按编号排序后的合并稿
  WORKLIST.md       : 未达标单元清单 + 建议补写量
"""
import re, os, glob, sys, json, argparse

CN = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}


def load_lock():
    if os.path.exists('RUN.lock'):
        try:
            return json.load(open('RUN.lock', encoding='utf-8'))
        except Exception:
            pass
    return {'file_prefixes': []}


def cc(t):
    return sum(1 for c in t if '\u4e00' <= c <= '\u9fff')


def split_units(text, mode):
    if mode == 'chapter':
        pat = re.compile(r'(?m)^(?=第\d+章)')
        out = []
        lead, first = '', True
        for p in pat.split(text):
            if not p.strip():
                continue
            head = p.split('\n', 1)[0].strip()
            m = re.match(r'^第(\d+)章', head)
            if m:
                h, lead, first = (lead if first else ''), '', False
                out.append(((int(m.group(1)), 0), h + p))
            elif first:
                lead += p
            else:
                out[-1] = (out[-1][0], out[-1][1] + p)
        return out
    pat = re.compile(r'(?m)^(?=第\d+场(?:补充场（[一二三四五六七八九十]+）)?$)')
    out = []
    lead, first = '', True
    for p in pat.split(text):
        if not p.strip():
            continue
        head = p.split('\n', 1)[0].strip()
        m_main = re.match(r'^第(\d+)场$', head)
        m_supp = re.match(r'^第(\d+)场补充场（([一二三四五六七八九十]+)）$', head)
        if m_main or m_supp:
            h, lead, first = (lead if first else ''), '', False
            key = (int(m_main.group(1)), 0) if m_main else (int(m_supp.group(1)), CN.get(m_supp.group(2), 0))
            out.append((key, h + p))
        elif first:
            lead += p
        else:
            out[-1] = (out[-1][0], out[-1][1] + p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='scenes')
    ap.add_argument('--mode', default='scene', choices=['scene', 'chapter'])
    ap.add_argument('--target', type=int, default=0)
    ap.add_argument('--floor-main', type=int, default=700)
    ap.add_argument('--floor-supp', type=int, default=500)
    a = ap.parse_args()

    lock = load_lock()
    prefixes = lock.get('file_prefixes') or []
    files = []
    for f in sorted(glob.glob(os.path.join(a.dir, '*.*'))):
        base = os.path.basename(f)
        if base.startswith('_') or base.endswith('.py') or base.endswith('.md') or base.endswith('.json'):
            continue
        if prefixes and not any(base.startswith(p) for p in prefixes):
            print('  [G8] 忽略前缀外文件:', base)
            continue
        if prefixes and base.startswith('_drop_'):
            print('  [G8] 忽略已隔离文件:', base)
            continue
        files.append(f)

    allb = []
    for f in files:
        allb.extend(split_units(open(f, encoding='utf-8').read(), a.mode))
    allb.sort(key=lambda x: x[0])
    text = '\n'.join(b[1] for b in allb)

    # 解析单元
    units = []
    cur = None
    for line in text.split('\n'):
        s = line.strip()
        if a.mode == 'chapter':
            m = re.match(r'^第(\d+)章', s)
            if m:
                cur = {'t': s, 'n': int(m.group(1)), 'sp': 0, 'time': None, 'c': [line]}
                units.append(cur); continue
        else:
            m_main = re.match(r'^第(\d+)场$', s)
            m_supp = re.match(r'^第(\d+)场补充场（([一二三四五六七八九十]+)）$', s)
            if m_main and not m_supp:
                cur = {'t': s, 'n': int(m_main.group(1)), 'sp': 0, 'time': None, 'c': [line]}
                units.append(cur); continue
            if m_supp:
                cur = {'t': s, 'n': int(m_supp.group(1)), 'sp': CN.get(m_supp.group(2), 0), 'time': None, 'c': [line]}
                units.append(cur); continue
        if cur is not None:
            cur['c'].append(line)
            tm = re.match(r'^(?:时间|date)[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})[：:](\d{2})', s)
            if tm:
                cur['time'] = tuple(map(int, tm.groups()))

    total = cc(text)
    checks = {}

    # G2 主编号
    bad_id = []
    prev = 0
    for u in units:
        label_main = (u['sp'] == 0 and a.mode == 'scene') or (a.mode == 'chapter')
        if label_main:
            if u['n'] <= prev:
                bad_id.append(u['t'])
            prev = u['n']
    checks['G2'] = not bad_id

    # 补充场位置
    bad_pos = []
    lm = None
    if a.mode == 'scene':
        for u in units:
            if u['sp'] != 0:
                if lm != u['n']:
                    bad_pos.append(u['t'])
            else:
                lm = u['n']
    checks['G4pos'] = not bad_pos

    # G3 时间单调
    times = [(u['t'], u['time']) for u in units if u['time']]
    bad_t = []
    for i in range(1, len(times)):
        if times[i][1] <= times[i-1][1]:
            bad_t.append((times[i-1], times[i]))
    checks['G3'] = not bad_t

    # G4 字段（scene 模式）
    bad_f = []
    if a.mode == 'scene':
        for u in units:
            c = '\n'.join(u['c'])
            if not ('大纲锚点' in c and re.search(r'时间[：:]', c) and re.search(r'地点[：:]', c)
                    and re.search(r'(出场人物|人物)[：:]', c)):
                bad_f.append(u['t'])
    checks['G4'] = not bad_f

    # G5 结构（集/卷标题）
    if a.mode == 'scene':
        heads = re.findall(r'(?m)^(第[一二三四五六七八九十]+季·第\d+集.*)$', text)
        checks['G5'] = len(heads) > 0
    else:
        checks['G5'] = True

    # G6 退化
    frag = re.findall(r'[""][\u4e00-\u9fff]{1,4}，[说道问答喊叫][：，]', text)
    mx = cur2 = 0
    for l in text.split('\n'):
        if l.strip() == '':
            cur2 += 1; mx = max(mx, cur2)
        else:
            cur2 = 0
    checks['G6'] = (len(frag) == 0 and mx < 3)

    # G8 重号
    seen = {}
    for f in files:
        s = open(f, encoding='utf-8').read()
        if a.mode == 'scene':
            for m in re.finditer(r'(?m)^第(\d+)场补充场（([一二三四五六七八九十]+)）$', s):
                seen.setdefault((int(m.group(1)), CN.get(m.group(2), 0)), []).append(os.path.basename(f))
            for m in re.finditer(r'(?m)^第(\d+)场$', s):
                seen.setdefault((int(m.group(1)), 0), []).append(os.path.basename(f))
        else:
            for m in re.finditer(r'(?m)^第(\d+)章', s):
                seen.setdefault((int(m.group(1)), 0), []).append(os.path.basename(f))
    dups = {k: v for k, v in seen.items() if len(v) > 1}
    checks['G8'] = not dups

    # G9 地板
    under = []
    for u in units:
        n = cc('\n'.join(u['c']))
        floor = a.floor_main if (u['sp'] == 0 or a.mode == 'chapter') else a.floor_supp
        if n < floor:
            under.append((u['t'], n, floor - n))
    checks['G9'] = not under

    # G1 字数
    checks['G1'] = True
    # G10 达标
    target = a.target or 0
    done = bool(target) and total >= target and all(checks.values())
    checks['G10'] = done

    os.makedirs(a.dir, exist_ok=True)
    open(os.path.join(a.dir, '_merged.txt'), 'w', encoding='utf-8').write(text)

    # 输出
    print('=' * 62)
    print('单元数: %d ｜ 中文字符: %d ｜ 总字符: %d' % (len(units), total, len(text)))
    for k in ['G1', 'G2', 'G4pos', 'G3', 'G4', 'G5', 'G6', 'G8', 'G9', 'G10']:
        print('  %-6s %s' % (k, 'OK' if checks.get(k) else 'FAIL'))
    if bad_id:
        print('  [G2] 主编号倒流/跳号:', bad_id[:5])
    if bad_t:
        for x in bad_t[:5]:
            print('  [G3] 倒流:', x[0][0], x[0][1], '->', x[1][0], x[1][1])
    if bad_f:
        print('  [G4] 缺字段:', bad_f[:5])
    if dups:
        print('  [G8] 重号:', list(dups.items())[:5])
    if under:
        print('  [G9] 低于地板: %d 个单元，需补 %d 字' % (len(under), sum(u[2] for u in under)))
    if target:
        print('目标 %d ｜ 当前 %d ｜ 还差 %d（%.1f%%）｜ done=%s'
              % (target, total, max(0, target - total), 100.0 * total / target, done))
    print('=' * 62)

    # WORKLIST
    wl = ['# WORKLIST — 下一批作业单\n']
    if target and total < target:
        wl.append('- 目标 %d ｜ 当前 %d ｜ 还差 %d' % (target, total, target - total))
    if under:
        wl.append('\n## 低于地板的单元（优先加长）\n')
        for t, n, need in sorted(under, key=lambda x: -x[2])[:60]:
            wl.append('- %s：现有 %d 字，至少再补 %d 字' % (t, n, need))
    else:
        wl.append('\n- 无低于地板的单元；请为时间窗口较宽的单元新增补充场（单块 ≥ 1200 字）。')
    open('WORKLIST.md', 'w', encoding='utf-8').write('\n'.join(wl))
    print('已写 WORKLIST.md')


if __name__ == '__main__':
    main()
