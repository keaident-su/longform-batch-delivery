#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dedupe_scan.py —— LFBD v7 闸门 G10：内容重复 / 事实冲突 / 跨来源拼接冲突 扫描

为什么需要它（v6 的真实事故）：
  底稿来自"另一路运行"，后来者往同一场次下面**追加补充场**。出问题的那一条：
    第203场（主场次，7/5 20:30）写"安撞门救人"；新加的 第203场补充场（三）（时间标 7/6 12:00）
    把**同一件事换了一套词重写了一遍**，并且与主场次/另一条补充场在
    小晚的来因、到场人数、绑具种类 上互相矛盾。
  这类问题编号、时间、字段、字数全都对，G2~G9 一个都拦不住；
  而**逐字相似度也拦不住**（作者把句子全换了）。所以本脚本用四路判据：

  G10a 逐字重复     ：任两块间存在 ≥MIN_SUBSTR 字完全相同的段落
  G10b 同场事实冲突 ：同一主场次下各块的 量词/数量、关键道具、出场人物集合 互相打架
  G10c 事件动词重叠 ：时间在后的补充场，与主场次共享 ≥N 个"收束动作"动词 → 疑似重写同一事件
  G10d 正文日期错位 ：正文提到的日期与"时间："字段相差过大
  ＋ 逐场对照表     ：每个有多块的主场次输出 时间/地点/人物/量词/动词 的并排表，供人工或模型复核语义重复

用法：
  python dedupe_scan.py <file_or_dir> [--out report.txt] [--cross-table] [--json]
"""

import os, re, sys, json, argparse, itertools, collections
from difflib import SequenceMatcher

CN = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
FIELD_RE = re.compile(r'^(大纲锚点|时间|地点|出场人物|人物)[：:]')
HEAD_RE = re.compile(r'^(第[一二三四五六七八九十\d]+集|【第?\d*集?时间线|本集概要|本集场次|═+|—{3,})')
MAIN_RE = re.compile(r'^第(\d+)场$')
SUPP_RE = re.compile(r'^第(\d+)场补充场（([一二三四五六七八九十]+)）$')
DATE_RE = re.compile(r'(\d{4})年(\d{1,2})月(\d{1,2})日|([一二三四五六七八九十]+)月([一二三四五六七八九十]+)[日号]')
CNM = {c: i for i, c in enumerate('一二三四五六七八九十', 1)}
CNM.update({'十一': 11, '十二': 12})

# 收束动作 / 事件标志词（用于"事件动词重叠"判据）
ACTION_WORDS = ['踹开','踹门','撞开','撞门','撕开','扯下','按住','按倒','绑','捆','勒','解开','松绑',
                '推倒','掀翻','夺下','抢走','拖走','拉走','抬走','扶起','扶到','背起','抱起',
                '封条','带走','铐','押','押走','拦下','挡住','翻墙','破门','冲进','冲出去','逃出',
                '救出','救下','制止','阻止','摆平','处理掉','灭口','开枪','鸣枪']
# 互斥要素组：同一场次内，不同块若各用其中不同的一个，即为事实冲突
EXCLUSIVE_GROUPS = {
    '绑具': ['胶带', '布条', '绳子', '扎带', '手铐'],
    '封门': ['封条', '封锁线'],
    '载客': ['商务车', '面包车', '越野车', '轿车'],
}
PROPS = [w for g in EXCLUSIVE_GROUPS.values() for w in g]

def cn2i(s):
    if s in CNM: return CNM[s]
    if s.startswith('十') and len(s) > 1: return 10 + CNM.get(s[1], 0)
    return 0

def read_text(target):
    if os.path.isdir(target):
        parts = []
        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__')]
            for f in sorted(files):
                if f.endswith('.txt'):
                    parts.append(open(os.path.join(root, f), encoding='utf-8').read())
        return '\n'.join(parts)
    return open(target, encoding='utf-8').read()

def parse_blocks(text):
    blocks, cur = [], None
    for line in text.split('\n'):
        s = line.strip()
        m, n = MAIN_RE.match(s), SUPP_RE.match(s)
        if m and not n:
            if cur: blocks.append(cur)
            cur = {'title': s, 'num': int(m.group(1)), 'supp': 0, 'lines': [line]}
        elif n:
            if cur: blocks.append(cur)
            cur = {'title': s, 'num': int(n.group(1)), 'supp': CN.get(n.group(2), 0), 'lines': [line]}
        elif cur is not None:
            cur['lines'].append(line)
    if cur: blocks.append(cur)
    return blocks

def body(b):
    out = []
    for l in b['lines']:
        s = l.strip()
        if FIELD_RE.match(s) or HEAD_RE.match(s): continue
        out.append(s)
    return ''.join(c for c in ''.join(out) if '\u4e00' <= c <= '\u9fff')

def field(b, name):
    for l in b['lines']:
        m = re.match(r'^%s[：:]\s*(.*)$' % name, l.strip())
        if m: return m.group(1).strip()
    return ''

def persons(b):
    f = field(b, '出场人物') or field(b, '人物')
    if not f: return set()
    raw = re.split(r'[、，,；;]', f)
    out = set()
    for r in raw:
        r = re.sub(r'（[^）]*）', '', r).strip()
        r = re.sub(r'^.*?\.', '', r)
        if r and r not in ('若干',): out.add(r)
    return out

def nums(b):
    """返回 Counter{(量词+后2字): {数字,...}}，用于比对"同一指涉的数量"""
    txt = '\n'.join(b['lines'])
    d = {}
    for num, unit, tail in re.findall(r'([一二三四五六七八九十两\d]+)(个|名|人|条|把|台|辆|次)([\u4e00-\u9fff]{0,2})', txt):
        d.setdefault(unit + tail, set()).add(num)
    return d

def props(b):
    txt = '\n'.join(b['lines'])
    return {p for p in PROPS if p in txt}

def actions(b):
    txt = '\n'.join(b['lines'])
    return {w for w in ACTION_WORDS if w in txt}

def lcs(a, b, min_len):
    if not a or not b: return None
    sm = SequenceMatcher(None, a, b, autojunk=False)
    m = sm.find_longest_match(0, len(a), 0, len(b))
    return a[m.a:m.a + m.size] if m.size >= min_len else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('target')
    ap.add_argument('--out', default=None)
    ap.add_argument('--min-substr', type=int, default=30)
    ap.add_argument('--cross-table', action='store_true')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    blocks = parse_blocks(read_text(a.target))
    for b in blocks:
        b['body'] = body(b); b['persons'] = persons(b); b['nums'] = nums(b)
        b['props'] = props(b); b['acts'] = actions(b); b['tf'] = field(b, '时间'); b['loc'] = field(b, '地点')

    def tkey(b):
        m = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})[：:](\d{2})', b['tf'])
        return tuple(map(int, m.groups())) if m else None

    mains = [b for b in blocks if b['supp'] == 0]
    supps = [b for b in blocks if b['supp'] > 0]
    by = collections.defaultdict(list)
    for b in blocks: by[b['num']].append(b)
    mains_by = {b['num']: b for b in mains}

    err, warn, info = [], [], []

    # G10a 逐字重复
    cand = [b for b in blocks if len(b['body']) >= a.min_substr]
    for x, y in itertools.combinations(cand, 2):
        sub = lcs(x['body'], y['body'], a.min_substr)
        if sub:
            cover = len(sub) / float(min(len(x['body']), len(y['body'])) or 1)
            if cover >= 0.06:
                err.append(('G10a-逐字重复', '%s <-> %s' % (x['title'], y['title']),
                            '存在 %d 字完全相同的段落（占较短块 %.0f%%）：“%s…”' % (len(sub), cover * 100, sub[:36])))

    # G10b 同场互斥要素冲突 / G10c 事件动词重叠
    def exclusive_conflict(x, y):
        hits = []
        for gname, words in EXCLUSIVE_GROUPS.items():
            a = [w for w in words if w in '\n'.join(x['lines'])]
            b = [w for w in words if w in '\n'.join(y['lines'])]
            if a and b and not (set(a) & set(b)):
                hits.append('%s不一致（一方写“%s”，另一方写“%s”）' % (gname, '、'.join(a), '、'.join(b)))
        return hits

    def num_conflict(x, y):
        ux, uy = x['nums'], y['nums']
        out = []
        for key in set(ux) & set(uy):
            if ux[key] != uy[key]:
                out.append('“%s…”的数量不同（%s vs %s）' % (key, '/'.join(sorted(ux[key])), '/'.join(sorted(uy[key]))))
        return out

    for num, grp in by.items():
        if len(grp) < 2: continue
        m = mains_by.get(num)
        for x, y in itertools.combinations(grp, 2):
            ex = exclusive_conflict(x, y)
            nc = num_conflict(x, y)
            if ex:
                err.append(('G10b-事实冲突', '%s <-> %s' % (x['title'], y['title']),
                            '；'.join(ex + nc)))
            elif nc:
                info.append(('G10b-数量差异(参考)', '%s <-> %s' % (x['title'], y['title']),
                             '；'.join(nc)))
        if m:
            for s2 in [g for g in grp if g['supp'] > 0]:
                ts, tm = tkey(s2), tkey(m)
                if ts and tm and ts > tm:
                    shared = s2['acts'] & m['acts']
                    if len(shared) >= 3:
                        err.append(('G10c-疑似重写', s2['title'],
                            '时间（%s）晚于主场次（%s），却与主场次共享收束动作 %s —— 高度疑似把主场次事件换词重写'
                            % (s2['tf'], m['tf'], '、'.join(sorted(shared)))))
                    elif len(shared) == 2:
                        warn.append(('G10c-疑似重写', s2['title'],
                            '与主场次共享动作 %s，请确认不是重写同一事件' % ('、'.join(sorted(shared)))))

    # G10d 正文日期 vs 时间字段（引用豁免：生日/回顾旧事不算错位）
    REF_WORDS = ('出生', '生日', '那年', '当年', '当时', '记得', '回忆', '上一次', '第一次',
                 '那天', '那一天', '七年前', '六年前', '五年前', '四年前', '三年前', '两年前', '一年前')
    for b in blocks:
        tk = tkey(b)
        if not tk: continue
        for mt in DATE_RE.finditer('\n'.join(b['lines'])):
            d = (int(mt.group(1)), int(mt.group(2)), int(mt.group(3))) if mt.group(1) else (tk[0], cn2i(mt.group(4)), cn2i(mt.group(5)))
            delta = (d[0]-tk[0])*372+(d[1]-tk[1])*31+(d[2]-tk[2])
            if not (d[1] and d[2] and delta < -30):
                continue
            line = mt.string.strip()
            if any(w in line for w in REF_WORDS):
                continue
            warn.append(('G10d-日期错位', b['title'],
                         '正文提到 %d年%d月%d日，与时间字段 %s 相差过大，且不像回顾引用' % (d[0], d[1], d[2], b['tf'])))
            break

    lines = ['=== LFBD G10 内容重复 / 事实冲突 扫描 ===',
             '目标: %s' % a.target,
             '场次块: %d（主场次 %d，补充场 %d）' % (len(blocks), len(mains), len(supps)),
             '结果: 必须修复 %d ｜ 需确认 %d ｜ 参考 %d' % (len(err), len(warn), len(info)), '']
    if err:
        lines.append('—— 必须修复 ——')
        for lv, who, why in err: lines.append('[%s] %s\n    %s' % (lv, who, why))
        lines.append('')
    if warn:
        lines.append('—— 需人工确认 ——')
        for lv, who, why in warn: lines.append('[%s] %s\n    %s' % (lv, who, why))
        lines.append('')
    if info:
        lines.append('')
        lines.append('—— 参考：同场数量差异（仅提示，详见逐场对照表）——')
        for lv, who, why in info[:12]:
            lines.append('[%s] %s\n    %s' % (lv, who, why))
        if len(info) > 12:
            lines.append('... 其余 %d 条见 --cross-table' % (len(info) - 12))
    if not err and not warn: lines.append('✓ 未发现必须修复项')

    if a.cross_table:
        lines.append('')
        lines.append('=== 逐场对照表（仅列同一场次块数≥2；用于复核语义重复）===')
        for num in sorted(by):
            grp = sorted(by[num], key=lambda b: b['supp'])
            if len(grp) < 2: continue
            lines.append('')
            lines.append('■ 第%d场（%d 块）' % (num, len(grp)))
            for b in grp:
                lines.append('  · %-22s 时间=%-18s 地点=%s' % (b['title'], b['tf'][:18], b['loc'][:28]))
                lines.append('      人物=%s' % ('、'.join(sorted(b['persons']))[:70] or '-'))
                lines.append('      量词=%s ｜ 道具=%s' % (
                    '、'.join('%s:%s' % (k, v) for k, v in sorted(b['nums'].items()))[:70] or '-',
                    '、'.join(sorted(b['props'])) or '-'))

    out = '\n'.join(lines)
    print(out)
    if a.out: open(a.out, 'w', encoding='utf-8').write(out)
    if a.json:
        print(json.dumps([{'level': l, 'target': t, 'reason': r} for l, t, r in err + warn], ensure_ascii=False, indent=2))
    return 1 if err else 0

if __name__ == '__main__':
    sys.exit(main())
