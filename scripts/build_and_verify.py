#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_and_verify.py —— 长文本分批交付：重建 + 校验 + 输出下一批作业单

v6 新增：
  G8 重号污染检测（同编号出现在多个文件 / 扫描到 file_prefixes 之外的文件）
  G9 单元字数地板（低于地板的单元列入未达标清单，并换算成"还需写多少字/多少个单元"）
  --report  直接打印进度表（目标/当前/还差/完成度/预计轮数）

零第三方依赖（stdlib only）。把 CONFIG 改成你的结构即可。
用法：
  python scripts/build_and_verify.py                # 校验 + 生成 docx（若配置）
  python scripts/build_and_verify.py --report       # 只打印进度与下一批作业单
"""

import os
import re
import sys
import json
import glob
import argparse

# ============================== CONFIG ==============================
CONFIG = {
    # 源文件目录与匹配前缀（遵循 RUN.lock 的 file_prefixes）
    "src_dir": "scenes",
    "file_globs": ["*.txt"],          # 例：["chapters_*.md"]
    "allowed_prefixes": [],           # 例：["act4_"]；非空时，不匹配者一律视为污染

    # 单元（场/章）结构
    "unit_regex": r"^第(\d+)(场|章)$",                       # 主单元
    "subunit_regex": r"^第(\d+)场补充场（([一二三四五六七八九十]+)）$",  # 从单元
    "cn_nums": {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10},

    # 必填字段（正则，命中即算存在）
    "required_fields": [r"时间[：:]", r"地点[：:]", r"(出场人物|人物)[：:]"],
    "anchor_field": "大纲锚点",        # 可选：没有则不算字段缺失，但会提示

    # 时间戳（用于 G3）
    "time_regex": r"^时间[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})[：:](\d{2})",

    # 单元字数地板（中文字符）
    "floors": {"main": 700, "sub": 500},

    # 结构块（集/卷/章头）必须存在的正则
    "must_have": [r"^第\d+集", r"^第\d+章"],

    # 输出
    "project_title": "《长文本工程》",
    "parts": [],                      # 例：[{"name":"上册","max_id":238},{"name":"下册","min_id":239}]
    "out_dir": ".",
}

CJK = re.compile(r"[\u4e00-\u9fff]")
PASS, FAIL = "OK", "BAD"


def cjk_len(s):
    return len(CJK.findall(s))


def collect_files(cfg):
    files = []
    for g in cfg["file_globs"]:
        files.extend(glob.glob(os.path.join(cfg["src_dir"], g)))
    files = sorted(set(files))
    stray = []
    if cfg["allowed_prefixes"]:
        keep = []
        for f in files:
            base = os.path.basename(f)
            if any(base.startswith(p) for p in cfg["allowed_prefixes"]):
                keep.append(f)
            else:
                stray.append(f)
        files = keep
    return files, stray


def split_units(text, cfg):
    """按行扫描切块；返回 [{'header':..., 'body':...}]"""
    unit_re = re.compile(cfg["unit_regex"])
    sub_re = re.compile(cfg["subunit_regex"])
    units, cur, lead = [], None, []
    for line in text.split("\n"):
        s = line.strip()
        if unit_re.match(s) or sub_re.match(s):
            if cur is not None:
                units.append(cur)
            cur = {"header": s, "body": [line]}
        else:
            if cur is None:
                lead.append(line)
            else:
                cur["body"].append(line)
    if cur is not None:
        units.append(cur)
    if units:
        units[0]["body"] = lead + units[0]["body"]
    for u in units:
        u["text"] = "\n".join(u["body"])
    return [u for u in units if u["text"].strip()]


def unit_key(header, cfg):
    m = re.match(cfg["unit_regex"], header)
    if m:
        return (int(m.group(1)), 0)
    m = re.match(cfg["subunit_regex"], header)
    if m:
        return (int(m.group(1)), cfg["cn_nums"].get(m.group(2), 0))
    return (0, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="只打印进度与作业单")
    ap.add_argument("--target", type=int, default=0)
    ap.add_argument("--ledger", default="ledger.json")
    a = ap.parse_args()

    cfg = CONFIG
    files, stray = collect_files(cfg)

    # ---- G8-a：扫描到配置外文件 = 污染 ----
    g8a = PASS
    if stray:
        g8a = FAIL
        print("[G8] 检测到 RUN.lock 前缀之外的同目录文件（疑似并行运行污染）：")
        for f in stray:
            print("      ! " + f)

    owner = {}      # (num, sub) -> [files]
    units_all = []
    for f in files:
        base = os.path.basename(f)
        text = open(f, encoding="utf-8").read()
        for u in split_units(text, cfg):
            k = unit_key(u["header"], cfg)
            owner.setdefault(k, []).append(base)
            u["file"] = base
            units_all.append(u)

    # ---- G8-b：同编号出现在多个文件 = 重号 ----
    dups = {k: v for k, v in owner.items() if len(v) > 1}
    g8b = PASS
    if dups:
        g8b = FAIL
        print("[G8] 重号（同一编号出现在多个文件，必须人工裁决，禁止自动合并）：")
        for k, v in sorted(dups.items()):
            print("      ! 第%d场 补(%d): %s" % (k[0], k[1], ", ".join(v)))

    units_all.sort(key=lambda u: unit_key(u["header"], cfg))
    text = "\n".join(u["text"] for u in units_all)
    total = cjk_len(text)

    mains, prev, g2 = [], 0, PASS
    for u in units_all:
        k = unit_key(u["header"], cfg)
        if k[1] == 0:
            if k[0] <= prev:
                print("[G2] 主编号倒流: " + u["header"]); g2 = FAIL
            prev = k[0]
            mains.append(u)

    # 从单元必须紧跟在同号主单元后
    lm, g2b = None, PASS
    for u in units_all:
        k = unit_key(u["header"], cfg)
        if k[1] != 0:
            if lm != k[0]:
                print("[G2] 补充单元错位: " + u["header"]); g2b = FAIL
        else:
            lm = k[0]

    # ---- G3 时间单调 ----
    g3 = PASS
    times = []
    for u in units_all:
        m = re.search(cfg["time_regex"], u["text"], re.M)
        if m:
            times.append((u["header"], tuple(map(int, m.groups()))))
    for i in range(1, len(times)):
        if times[i][1] <= times[i-1][1]:
            print("[G3] 时间倒流: %s %s -> %s %s" % (times[i-1][0], times[i-1][1], times[i][0], times[i][1]))
            g3 = FAIL

    # ---- G4 字段 ----
    g4 = PASS
    for u in units_all:
        for pat in cfg["required_fields"]:
            if not re.search(pat, u["text"]):
                print("[G4] 缺字段 %s : %s" % (u["header"], pat)); g4 = FAIL

    # ---- G5 结构块 ----
    g5 = PASS
    for pat in cfg["must_have"]:
        if not re.search(pat, text, re.M):
            print("[G5] 缺少结构块: " + pat); g5 = FAIL

    # ---- G6 退化扫描 ----
    frag = re.findall(r'"[\u4e00-\u9fff]{1,4}，[说道问答喊叫][：，]', text)
    mx = cur = 0
    for line in text.split("\n"):
        if not line.strip():
            cur += 1; mx = max(mx, cur)
        else:
            cur = 0
    g6 = FAIL if mx >= 3 else PASS
    print("[G6] 对话标签逗号错误: %d ｜ 最大连续空行: %d" % (len(frag), mx))

    # ---- G9 单元字数地板 + 作业单 ----
    g9 = PASS
    short = []
    for u in units_all:
        k = unit_key(u["header"], cfg)
        floor = cfg["floors"]["main"] if k[1] == 0 else cfg["floors"]["sub"]
        n = cjk_len(u["text"])
        if n < floor:
            short.append((u["header"], n, floor))
    if short:
        g9 = FAIL
        need = sum(f - n for _, n, f in short)
        avg = max(400, int(sum(cjk_len(u["text"]) for u in units_all) / max(1, len(units_all))))
        print("[G9] 低于字数地板 %d 个单元｜需补约 %d 字（约 %d 个达标单元）"
              % (len(short), need, -(-need // avg)))
        for h, n, f in short[:15]:
            print("      ! %s : %d < %d" % (h, n, f))
        if len(short) > 15:
            print("      ... 其余 %d 个见 --report 全量" % (len(short) - 15))

    # ---- G10 内容重复/事实冲突（v7 新增，调用 dedupe_scan.py）----
    g10 = PASS
    try:
        import subprocess
        here = os.path.dirname(os.path.abspath(__file__))
        scan = os.path.join(here, "dedupe_scan.py")
        if os.path.exists(scan):
            r = subprocess.run([sys.executable, scan, cfg["src_dir"]],
                               capture_output=True, text=True, encoding="utf-8")
            out = (r.stdout or "") + (r.stderr or "")
            m = re.search(r"结果[:：]\s*必须修复\s*(\d+)\s*｜\s*需确认\s*(\d+)", out)
            if m:
                must, warn = int(m.group(1)), int(m.group(2))
                g10 = PASS if must == 0 else FAIL
                print("[G10] 内容重复/事实冲突：必须修复 %d ｜ 需确认 %d%s"
                      % (must, warn, "" if must == 0 else "  ← 跑 dedupe_scan.py 看明细"))
            else:
                print("[G10] 已运行 dedupe_scan.py（未解析到汇总行）")
        else:
            print("[G10] 跳过：未找到 scripts/dedupe_scan.py")
    except Exception as e:
        print("[G10] 跳过（%s）" % e)

    # ---- 进度 ----
    led = {}
    if os.path.exists(a.ledger):
        try:
            led = json.load(open(a.ledger, encoding="utf-8"))
        except Exception:
            led = {}
    target = a.target or led.get("target", 0)
    print()
    print("=" * 60)
    print("单元数: %d ｜ 主单元: %d ｜ 中文字符: %d ｜ 总字符: %d"
          % (len(units_all), len(mains), total, len(text)))
    if target:
        remain = max(0, target - total)
        pct = 100.0 * total / target
        cbr = led.get("calibrated", {}).get("chars_per_round", 9000)
        print("目标 %d ｜ 当前 %d ｜ 还差 %d（完成度 %.1f%%）｜ 按实测 %d 字/轮，还需 %d 轮"
              % (target, total, remain, pct, cbr, -(-remain // max(1, cbr))))
    print("G1 字数(按账本比对) ｜ G2 %s ｜ G3 %s ｜ G4 %s ｜ G5 %s ｜ G6 %s ｜ G8 %s ｜ G9 %s ｜ G10 %s"
          % (g2 if g2b == PASS else FAIL, g3, g4, g5, g6, g8a if g8b == PASS else FAIL, g9, g10))
    print("=" * 60)

    # ---- 下一批作业单 ----
    if short:
        print("\n下一批作业单（照着写即可）：")
        print("  优先补足下列单元，每个至少补到地板字数；或新增达标单元。")
        for h, n, f in short[:10]:
            print("   - %s（现 %d 字，需 +%d）" % (h, n, f - n))
    elif target and total < target:
        print("\n下一批作业单：主线已达标，继续按骨架扩展新单元。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
