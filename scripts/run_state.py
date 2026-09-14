#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_state.py —— LFBD v9 运行状态机：轮数契约 + 双阶段循环 + 停止谓词

【为什么有 v8 还不够】
v8 把"完成"变成了退出码（gate: 0=DONE / 1=RUNNING / 2=BLOCKED），
但它只有"字数"和"闸门"两态，没有把"跑几轮"这件事**先算出来、写死成契约**。

用户真正要的是这个流程：

    ① 设轮数 x = 目标字数 ÷ (单轮输出上限 × 0.8)
    ② 先按契约跑满 x 轮（不间断、不问）
    ③ 跑完后**用多种方式**核字数
    ④ 不够 → 继续补字数，回到 ③
    ⑤ 够了 → 再排查其它问题（编号/时间/字段/重号/G10 一致性…）
    ⑥ 全部通过 → 停；否则 → 修，修完回到 ③

v9 就是把这六步写成代码：**轮数契约（rounds）+ 双阶段（GENERATE / AUDIT / REPAIR）+ 多路字数核算**。

三条硬机制
  M1 停止谓词：`gate` 退出码是唯一合法的"完成"判据。0=DONE / 1=RUNNING / 2=BLOCKED。
  M2 轮末契约：每轮只许以 ✅ DONE 或 ⏩ RESUME 结尾，禁止任何提问/征询/提议。
  M3 吞吐升级梯 + 轮数契约：x 先算出来；每轮逼单块变长（单元数下降、单块上升）。

【四种状态】
  GENERATE  字数未达标 → 按作业单继续写
  AUDIT     字数刚达标 → 跑全部闸门
  REPAIR    闸门有问题 → 按清单修，不写新内容
  DONE      字数达标 + 闸门全过 + 交付物在 → 允许停

零第三方依赖（stdlib only）。

--- 命令 ---------------------------------------------------------------
  python scripts/run_state.py init --target 170000 --cap 12000 --util 0.8
  python scripts/run_state.py next        # 现在该干什么（一句话 + 退出码）
  python scripts/run_state.py plan        # 本轮作业单：N 单元 × 每单元 M 字
  python scripts/run_state.py count       # 多路字数核算（汉字/含标点/总字符/去空白/docx）
  python scripts/run_state.py tick --added 9200 --units 5 --cursor 214
  python scripts/run_state.py gate        # 唯一合法的"能不能停"判据
  python scripts/run_state.py report      # 固定汇报表
  python scripts/run_state.py resume      # 一行续跑指令
"""

import argparse
import datetime
import glob as globmod
import json
import math
import os
import re
import subprocess
import sys
import zipfile

STATE_FILE = "run_state.json"

CJK = re.compile(r"[\u4e00-\u9fff]")
CJK_PUNCT = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff01-\uff5e]")
CN_NUMS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
           "七": 7, "八": 8, "九": 9, "十": 10}

DEFAULTS = {
    "version": "10.0.0",
    "target": 0,
    "cap": 12000,               # 模型单轮输出上限（中文字符）
    "util": 0.8,                # 利用率：单轮只按 80% 计
    "per_round": 0,             # = round(cap * util)
    "rounds_planned": 0,        # x = ceil(target / per_round)
    "chunks_per_turn": 8,       # 一个回合里链式跑几块（回合内不许收尾）
    "density": {"cjk_per_para": 120, "dialogue_ratio": 0.5},
    "turns_needed": 0,          # ≈ ceil(rounds_planned / chunks_per_turn)
    "steps_per_window": 25,     # Chatbox Work Mode：每 25 次连续工具调用暂停一次
    "calls_per_chunk": 2,       # 写一块大约要几次工具调用（write_file + 校验）
    "phase": "GENERATE",
    "mode": "RUN_TO_COMPLETION",
    "no_user_input": True,
    "glob": ["scenes/*.txt"],
    "prefix": "",
    "floors": {"main": 700, "sub": 500},
    "units_per_turn_max": 12,
    "target_cpu": 2000,
    "cpu_max": 3500,
    "cpu_growth": 1.35,
    "floor_mult": 1.4,
    "primary": "cjk",
    "docx_tolerance": 0.02,     # docx 与源文件字数允许的相对偏差
    "required_fields": ["时间[：:]", "地点[：:]", "(出场人物|人物)[：:]"],
    "time_regex": r"^时间[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})[：:](\d{2})",
    "unit_regex": r"^第(\d+)(场|章)$",
    "subunit_regex": r"^第(\d+)场补充场（([一二三四五六七八九十]+)）$",
    "deliverables": [],
    "cursor": {"episode": 0, "scene": 0, "note": ""},
    "history": [],
    "calibrated": {},
    "gates": {},
    "updated_at": "",
}

RESUME_LINE = (
    "继续按 LFBD v9 运行契约执行：读 run_state.json，跑 "
    "`python scripts/run_state.py next` 看当前阶段，"
    "本轮**链式跑满 chunks_per_turn 块**（块与块之间不许输出任何汇总/汇报/结尾语），再跑 "
    "`python scripts/run_state.py gate`；未 exit 0 不许停、不许提问、不许征求确认。"
)


# ==========================================================================
# 状态读写
# ==========================================================================
def load():
    d = {}
    if os.path.exists(STATE_FILE):
        try:
            d = json.load(open(STATE_FILE, encoding="utf-8"))
        except Exception:
            d = {}
    for k, v in DEFAULTS.items():
        d.setdefault(k, v)
    return d


def save(d):
    d["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    json.dump(d, open(STATE_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    write_ledger_md(d)


def write_ledger_md(d):
    h = d.get("calibrated", {})
    md = [
        "# RUN STATE（LFBD v9）", "",
        "| 项目 | 值 |", "|---|---|",
        "| 目标字数 | %s |" % d.get("target"),
        "| 单轮上限 × 利用率 | %s × %s = %s 字/轮 |"
        % (d.get("cap"), d.get("util"), d.get("per_round")),
        "| 轮数契约 x | %s |" % d.get("rounds_planned"),
        "| 已完成轮次 | %s |" % len(d.get("history", [])),
        "| 当前阶段 | **%s** |" % d.get("phase"),
        "| 累计字数 | %s |" % d.get("current_total", 0),
        "| 还差 | %s |" % max(0, (d.get("target") or 0) - (d.get("current_total") or 0)),
        "| 实测吞吐 | %s 字/单元 ｜ %s 字/轮 |"
        % (h.get("chars_per_unit", 0), h.get("chars_per_turn", 0)),
        "| 本轮每单元目标 | %s 字 |" % d.get("target_cpu"),
        "| 游标 | 集 %s ｜ 场 %s |"
        % (d["cursor"].get("episode"), d["cursor"].get("scene")),
        "| 更新时间 | %s |" % d.get("updated_at"), "",
        "## 轮次记录", "", "| 轮 | 范围 | 新增 | 单元 | 字/单元 | 累计 |",
        "|---|---|---|---|---|---|",
    ]
    for b in d.get("history", []):
        md.append("| %s/%s | %s | +%s | %s | %s | %s |" % (
            b.get("turn"), d.get("rounds_planned", "?"), b.get("range", ""),
            b.get("added"), b.get("units"), b.get("cpu", 0), b.get("total")))
    open("LEDGER.md", "w", encoding="utf-8").write("\n".join(md) + "\n")


def cjk_len(s):
    return len(CJK.findall(s))


# ==========================================================================
# 源文件扫描
# ==========================================================================
def collect_files(d):
    files = []
    for g in d["glob"]:
        files.extend(globmod.glob(g, recursive=True))
    files = sorted(set(os.path.normpath(f) for f in files))
    if d.get("prefix"):
        files = [f for f in files if os.path.basename(f).startswith(d["prefix"])]
    return files


def parse_units(text, d):
    ure = re.compile(d["unit_regex"])
    sre = re.compile(d["subunit_regex"])
    units, cur, lead = [], None, []
    for line in text.split("\n"):
        s = line.strip()
        if ure.match(s) or sre.match(s):
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


def unit_key(header, d):
    m = re.match(d["unit_regex"], header)
    if m:
        return (int(m.group(1)), 0)
    m = re.match(d["subunit_regex"], header)
    if m:
        return (int(m.group(1)), CN_NUMS.get(m.group(2), 0))
    return (0, 0)


def scan(d):
    files = collect_files(d)
    units, texts = [], []
    for f in files:
        t = open(f, encoding="utf-8").read()
        texts.append(t)
        for u in parse_units(t, d):
            u["file"] = os.path.basename(f)
            units.append(u)
    units.sort(key=lambda u: unit_key(u["header"], d))
    whole = "\n".join(texts)
    return {"files": files, "units": units, "text": whole}


# ==========================================================================
# 多路字数核算（用户的第 ③ 步：用不同方式查字数）
# ==========================================================================
def docx_text(path):
    """从 .docx 里抽纯文本（stdlib，不解压到磁盘）。"""
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
    except Exception:
        return ""
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


def count_methods(d, sc):
    t = sc["text"]
    m = {
        "cjk": len(CJK.findall(t)),
        "cjk_punct": len(CJK_PUNCT.findall(t)),
        "total": len(t),
        "non_space": len(re.sub(r"\s", "", t)),
    }
    dx = ""
    for pat in d.get("deliverables", []):
        for h in globmod.glob(pat):
            dx += docx_text(h) + "\n"
    if dx:
        m["docx_cjk"] = len(CJK.findall(dx))
        m["docx_total"] = len(dx)
        m["docx_non_space"] = len(re.sub(r"\s", "", dx))
    return m


def effective_count(d, m):
    """
    判定"字数达标"用哪个口径——取**最严**的那个：
      * 有交付物时：min(源文件汉字, docx 汉字)，保证 docx 也真的达标
      * 无交付物时：源文件汉字
    """
    eff = m.get(d.get("primary", "cjk"), m.get("cjk", 0))
    if "docx_cjk" in m:
        eff = min(eff, m["docx_cjk"])
    return eff


# ==========================================================================
# 闸门（M1 停止谓词的全部判据）
# ==========================================================================
def check_gates(d, sc, skip_g10=False):
    issues, notes = [], []
    units = sc["units"]

    seen = {}
    for u in units:
        seen.setdefault(unit_key(u["header"], d), []).append(u["file"])
    for k, v in sorted({k: v for k, v in seen.items() if len(v) > 1}.items()):
        issues.append("重号：第%d场 补(%d) 出现在 %s" % (k[0], k[1], ", ".join(v)))

    prev = 0
    for u in units:
        k = unit_key(u["header"], d)
        if k[1] == 0:
            if k[0] <= prev:
                issues.append("主编号倒流/重复：%s" % u["header"])
            prev = k[0]

    last_main, sub_map, order_err = None, {}, 0
    for u in units:
        k = unit_key(u["header"], d)
        if k[1] != 0:
            if last_main != k[0]:
                order_err += 1
            sub_map.setdefault(k[0], []).append(k[1])
        else:
            last_main = k[0]
    if order_err:
        issues.append("补充场错位：%d 处不在对应主场次正下方" % order_err)
    for n, ords in sorted(sub_map.items()):
        if sorted(ords) != list(range(1, len(ords) + 1)):
            issues.append("第%d场补充场序号不连续/重号：%s" % (n, ords))

    times = []
    for u in units:
        m = re.search(d["time_regex"], u["text"], re.M)
        if m:
            times.append((u["header"], tuple(map(int, m.groups()))))
    for i in range(1, len(times)):
        if times[i][1] <= times[i - 1][1]:
            issues.append("时间倒流：%s → %s" % (times[i - 1][0], times[i][0]))

    missing = 0
    for u in units:
        for pat in d["required_fields"]:
            if not re.search(pat, u["text"]):
                missing += 1
                if missing <= 8:
                    issues.append("缺字段 %s：%s" % (u["header"], pat))
    if missing > 8:
        issues.append("…另有 %d 处字段缺失" % (missing - 8))

    frag = re.findall(r'["“][\u4e00-\u9fff]{1,4}，[说道问答喊叫][：，]', sc["text"])
    if frag:
        issues.append("对话标签逗号错误 %d 处，例：%s" % (len(frag), frag[:3]))
    mx = cur = 0
    for line in sc["text"].split("\n"):
        if not line.strip():
            cur += 1
            mx = max(mx, cur)
        else:
            cur = 0
    if mx >= 3:
        issues.append("连续空行 %d 行（≥3 视为注水）" % mx)

    short = []
    for u in units:
        k = unit_key(u["header"], d)
        floor = d["floors"]["main"] if k[1] == 0 else d["floors"]["sub"]
        n = cjk_len(u["text"])
        if n < floor:
            short.append((u["header"], n, floor))
    if short:
        notes.append("低于地板 %d 个单元，需补约 %d 字"
                     % (len(short), sum(f - n for _, n, f in short)))

    g10 = (0, 0)
    dirs = sorted({os.path.dirname(f) or "." for f in sc["files"]})
    scan_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dedupe_scan.py")
    if skip_g10:
        notes.append("G10 已按 --skip-g10 跳过")
    elif scan_py and os.path.exists(scan_py) and dirs:
        try:
            r = subprocess.run([sys.executable, scan_py, dirs[0]],
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            out = (r.stdout or "") + (r.stderr or "")
            m2 = re.search(r"必须修复\s*(\d+)\s*｜\s*需确认\s*(\d+)", out)
            if m2:
                g10 = (int(m2.group(1)), int(m2.group(2)))
                if g10[0]:
                    issues.append("G10 内容冲突：必须修复 %d 条（跑 dedupe_scan.py --cross-table 看明细）" % g10[0])
        except Exception as e:
            notes.append("G10 跳过（%s）" % e)
    else:
        notes.append("G10 跳过：未找到 dedupe_scan.py 或源目录")

    for pat in d.get("deliverables", []):
        hits = [h for h in globmod.glob(pat) if os.path.getsize(h) > 0]
        if not hits:
            notes.append("交付物未生成：%s" % pat)
            continue
        bad = []
        for h in hits:
            try:
                with zipfile.ZipFile(h) as z:
                    if z.testzip() is not None:
                        bad.append(h)
            except Exception:
                bad.append(h)
        if bad:
            issues.append("交付物损坏/无法打开：%s" % ", ".join(bad))

    return issues, notes, short, g10


# ==========================================================================
# 状态判定（六步流程的机器实现）
# ==========================================================================
def evaluate(d, skip_g10=False):
    sc = scan(d)
    m = count_methods(d, sc)
    eff = effective_count(d, m)
    target = d["target"]
    issues, notes, short, g10 = check_gates(d, sc, skip_g10)

    if target and eff < target:
        phase, code = "GENERATE", 1
    else:
        blocking = [i for i in issues
                    if i.startswith(("重号", "G10", "交付物损坏"))]
        if blocking:
            phase, code = "BLOCKED", 2
        elif issues or short:
            phase, code = "REPAIR", 2
        elif d.get("deliverables") and not any(
                globmod.glob(p) for p in d["deliverables"]):
            phase, code = "REPAIR", 2
        else:
            phase, code = "DONE", 0

    return {"sc": sc, "m": m, "eff": eff, "issues": issues, "notes": notes,
            "short": short, "g10": g10, "phase": phase, "code": code}


def next_plan(d, sc, short):
    """吞吐升级梯 + 轮数契约：返回 (units, cpu, planned)。"""
    prev_cpu = 0
    if d["history"]:
        prev_cpu = d["history"][-1].get("cpu", 0) or 0
    budget = d.get("per_round") or int(d["cap"] * d["util"])
    cpu = max(int(d["floors"]["main"] * d["floor_mult"]),
              int(prev_cpu * d["cpu_growth"]) if prev_cpu else d["target_cpu"])
    cpu = min(cpu, d["cpu_max"])
    units = max(1, min(d["units_per_turn_max"], budget // max(1, cpu)))
    return units, cpu, units * cpu


def print_next_plan(d, sc, short, m=None, eff=None, chunks=1):
    units, cpu, planned = next_plan(d, sc, short)
    eff = eff if eff is not None else (m or {}).get("cjk", 0)
    remain = max(0, d["target"] - eff)
    rounds = -(-remain // max(1, planned)) if planned else 0
    cur = d["cursor"]
    done_rounds = len(d["history"])
    x = max(1, d["rounds_planned"])
    k = max(1, min(chunks, d.get("chunks_per_turn", 1)))
    print("\n下一批作业单：")
    print("  · 轮次：第 %d 轮 / 共 %d 轮（契约）" % (done_rounds + 1, d["rounds_planned"]))
    print("  · 单元数 %d 个 ｜ 每单元 ≥ %d 中文字符 ｜ 计划共 %d 字"
          % (units, cpu, planned))
    print("  · 起点：接在游标之后（集 %s ／ 场 %s）%s"
          % (cur.get("episode"), cur.get("scene"),
             ("，备注：" + cur.get("note")) if cur.get("note") else ""))
    print("  · 铁令：**加长单块，不要增加块数**（每单元低于 %d 字即不合格）" % cpu)
    if k > 1:
        _end = done_rounds + k
        _tag = "" if _end <= x else "（已超契约 x=%d，按契约自动续跑）" % x
        print("  · **轮内链式续跑**：本回合连跑 %d 块（第 %d—%d 轮%s），中间**不得收尾、不得报告**"
              % (k, done_rounds + 1, _end, _tag))
        for i in range(k):
            print("      %d) 第 %d 轮：%d 单元 × %d 字 = %d 字"
                  % (i + 1, done_rounds + i + 1, units, cpu, planned))
        print("  · 本回合合计计划 %d 字；写满后再跑 gate" % (k * planned))
        print("  · **回合内不许收尾**：块与块之间不输出任何汇总、表格或结尾语")
        print("  · 密度要求：汉字/段 ≥ %d；对白行占比 ≤ %.0f%%（用密集叙述，不要一句一换行）"
              % (d.get("density", {}).get("cjk_per_para", 120),
                 d.get("density", {}).get("dialogue_ratio", 0.5) * 100))
    print("  · 按当前计划，还需约 %d 轮" % rounds)
    if short:
        print("  · 存量欠账：%d 个单元低于地板（前 5 个）" % len(short))
        for h, n, f in short[:5]:
            print("      - %s（现 %d，需 +%d）" % (h, n, f - n))
    print("  · 写完立刻跑：python scripts/run_state.py gate")


# ==========================================================================
# 命令
# ==========================================================================
def cmd_init(a):
    d = load()
    d["target"] = a.target
    if a.cap:
        d["cap"] = a.cap
    if a.util:
        d["util"] = a.util
    if a.glob:
        d["glob"] = a.glob
    if a.prefix is not None:
        d["prefix"] = a.prefix
    if a.floors:
        main, _, sub = a.floors.partition(",")
        d["floors"] = {"main": int(main), "sub": int(sub or main)}
    if a.deliverable:
        d["deliverables"] = a.deliverable
    if a.units_per_turn_max:
        d["units_per_turn_max"] = a.units_per_turn_max

    d["per_round"] = int(round(d["cap"] * d["util"]))
    d["rounds_planned"] = int(math.ceil(d["target"] / max(1, d["per_round"])))
    if a.chunks_per_turn:
        d["chunks_per_turn"] = a.chunks_per_turn
    d["turns_needed"] = int(math.ceil(d["rounds_planned"] / max(1, d["chunks_per_turn"])))
    if a.steps_per_window:
        d["steps_per_window"] = a.steps_per_window
    if a.calls_per_chunk:
        d["calls_per_chunk"] = a.calls_per_chunk
    cw = max(1, d["steps_per_window"] // max(1, d["calls_per_chunk"]))
    d["chunks_per_window"] = cw
    d["windows_needed"] = int(math.ceil(d["rounds_planned"] / cw))
    d["phase"] = "GENERATE"
    d["mode"] = "RUN_TO_COMPLETION"
    d["no_user_input"] = True
    d["target_cpu"] = min(d["cpu_max"],
                          max(d["target_cpu"], int(d["floors"]["main"] * d["floor_mult"])))
    save(d)

    print("=" * 64)
    print("轮数契约已设定")
    print("=" * 64)
    print("  目标字数        %d 字（中文字符）" % d["target"])
    print("  单轮上限        %d 字" % d["cap"])
    print("  利用率          %s（只按 %.0f%% 计，留安全边际）" % (d["util"], d["util"] * 100))
    print("  每轮计划产出    %d 字" % d["per_round"])
    print("  ────────────────────────────────────────")
    print("  轮数 x          ceil(%d / %d) = %d 轮"
          % (d["target"], d["per_round"], d["rounds_planned"]))
    print("  轮内链式块数 k  %d 块/回合（受 harness 迭代上限约束）" % d["chunks_per_turn"])
    print("  ────────────────────────────────────────")
    print("  需你接续的次数   ceil(%d / %d) = %d 次"
          % (d["rounds_planned"], d["chunks_per_turn"], d["turns_needed"]))
    print("                  （不链式的话是 %d 次；链式把接续次数压到约 1/k）"
          % d["rounds_planned"])
    print("")
    print("  —— Chatbox Work Mode 检查点 ——")
    print("  每 %d 次工具调用暂停一次（产品硬护栏，不可配置）" % d["steps_per_window"])
    print("  每块约 %d 次调用 → 每个窗口可写 %d 块" % (d["calls_per_chunk"], d["chunks_per_window"]))
    print("  **预计只需点 %d 次 Continue**" % d["windows_needed"])
    print("  扫描范围        %s ｜ 前缀 %r" % (d["glob"], d["prefix"]))
    print("  本轮每单元目标  %d 字" % d["target_cpu"])
    print("  首个作业单      python scripts/run_state.py plan --chunks %d"
          % d["chunks_per_turn"])
    print()
    print("  流程：① 跑满 %d 轮 → ② 多路核字数 → ③ 不够就补 → " % d["rounds_planned"])
    print("        ④ 够了再排查问题 → ⑤ 全过才停，否则修完重来")
    return 0


def cmd_next(a):
    d = load()
    r = evaluate(d, a.skip_g10)
    d["phase"] = r["phase"]
    save(d)
    eff, tgt = r["eff"], d["target"]
    print("阶段：%s ｜ 字数 %d / %d（%.1f%%）｜ 轮 %d/%d"
          % (r["phase"], eff, tgt,
             (100.0 * eff / tgt) if tgt else 0.0,
             len(d["history"]), d["rounds_planned"]))
    if r["phase"] == "GENERATE":
        print("→ 现在该做的：**继续写**（字数没到，禁止宣布完成）")
        print_next_plan(d, r["sc"], r["short"], r["m"], eff)
        print("")
        print(RESUME_LINE)
        return 1
    if r["phase"] == "REPAIR":
        print("→ 现在该做的：**先修问题**，再重跑 gate（不要停下提问）")
        for i in r["issues"][:15]:
            print("  ✗ " + i)
        for h, n, f in r["short"][:10]:
            print("  ✗ 低于地板：%s：%d < %d" % (h, n, f))
        print("")
        print(RESUME_LINE)
        return 2
    if r["phase"] == "BLOCKED":
        print("→ 现在该做的：**先处理必修复项**，再重跑 gate")
        for i in r["issues"]:
            print("  ✗ " + i)
        print("")
        print(RESUME_LINE)
        return 2
    print("→ 全部通过。可以停。允许在回复里写「完成」。")
    return 0


def cmd_count(a):
    d = load()
    sc = scan(d)
    m = count_methods(d, sc)
    eff = effective_count(d, m)
    tgt = d["target"]
    print("=" * 64)
    print("多路字数核算")
    print("=" * 64)
    rows = [("cjk", "源文件·汉字数（主口径）"),
            ("cjk_punct", "源文件·汉字+全角标点"),
            ("non_space", "源文件·去空白总字符"),
            ("total", "源文件·总字符（含英文/换行）"),
            ("docx_cjk", "交付 docx·汉字数"),
            ("docx_non_space", "交付 docx·去空白总字符"),
            ("docx_total", "交付 docx·总字符")]
    for k, label in rows:
        if k in m:
            bar = "✓" if m[k] >= tgt else " "
            print("  %-26s %8d  %s" % (label, m[k], bar))
        elif k.startswith("docx"):
            print("  %-26s %8s  （未配置交付物）" % (label, "—"))
    print("  " + "-" * 44)
    print("  判定口径（取最严）：%d 字" % eff)
    print("  目标：%d 字 ｜ 差距：%d 字" % (tgt, max(0, tgt - eff)))
    if "docx_cjk" in m:
        delta = abs(m["docx_cjk"] - m["cjk"]) / max(1, m["cjk"])
        flag = "⚠ 偏差 %.1f%%，docx 可能漏内容" % (delta * 100) \
            if delta > d["docx_tolerance"] else "✓ 与源文件一致"
        print("  docx 一致性：%s" % flag)
    print("=" * 64)
    return 0 if (not tgt or eff >= tgt) else 1


def cmd_gate(a):
    d = load()
    r = evaluate(d, a.skip_g10)
    d["phase"] = r["phase"]
    d["current_total"] = r["eff"]
    if d["target"]:
        d["progress_pct"] = round(100.0 * r["eff"] / d["target"], 1)
    save(d)

    print("=" * 64)
    print("目标 %d ｜ 当前 %d（最严口径）｜ 还差 %d（%.1f%%）｜ 轮 %d/%d"
          % (d["target"], r["eff"], max(0, d["target"] - r["eff"]),
             100.0 * r["eff"] / d["target"] if d["target"] else 0.0,
             len(d["history"]), d["rounds_planned"]))
    print("=" * 64)

    if r["code"] == 1:
        print("\n状态：RUNNING（exit 1）—— 阶段 GENERATE：字数未达标，禁止宣布完成")
        for n in r["notes"]:
            print("  · " + n)
        print_next_plan(d, r["sc"], r["short"], r["m"], r["eff"])
        print("\n⏩ RESUME")
        print(RESUME_LINE)
        return 1

    if r["code"] == 2:
        name = "BLOCKED" if r["phase"] == "BLOCKED" else "REPAIR"
        print("\n状态：%s（exit 2）—— 先修下列问题，再重跑 gate。" % name)
        print("注意：这不是「停下来问」，是「修完接着跑」。")
        for i in r["issues"]:
            print("  ✗ " + i)
        for h, n, f in r["short"][:10]:
            print("  ✗ 低于地板：%s：%d < %d（需 +%d）" % (h, n, f, f - n))
        if len(r["short"]) > 10:
            print("  ✗ …另有 %d 个单元低于地板" % (len(r["short"]) - 10))
        print("\n⏩ RESUME")
        print(RESUME_LINE)
        return 2

    deliv = []
    for pat in d.get("deliverables", []):
        deliv.extend(globmod.glob(pat))
    print("\n状态：DONE（exit 0）✅")
    print("  字数 %d ≥ 目标 %d ｜ 编号连续 ｜ 时间单调 ｜ 字段齐全 ｜ 无退化 ｜ "
          "地板达标 ｜ G10 必须修复 %d" % (r["eff"], d["target"], r["g10"][0]))
    if deliv:
        print("  交付物：%s" % ", ".join(deliv))
    print("\n可以停。允许在回复里写「完成」。")
    return 0


def cmd_plan(a):
    d = load()
    r = evaluate(d, a.skip_g10)
    print_next_plan(d, r["sc"], r["short"], r["m"], r["eff"], chunks=a.chunks)
    return 0


def cmd_tick(a):
    d = load()
    sc = scan(d)
    m = count_methods(d, sc)
    eff = effective_count(d, m)
    prev = d.get("current_total", 0)
    added = a.added if a.added is not None else max(0, eff - prev)
    units = a.units or max(1, len(sc["units"]))
    cpu = int(added / units) if units else 0

    d["history"].append({
        "turn": len(d["history"]) + 1,
        "range": a.range or "",
        "added": added,
        "units": units,
        "cpu": cpu,
        "total": eff,
        "at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    d["current_total"] = eff
    if d["target"]:
        d["progress_pct"] = round(100.0 * eff / d["target"], 1)
    d["calibrated"] = {"chars_per_unit": cpu, "chars_per_turn": added}
    if a.cursor is not None:
        d["cursor"]["scene"] = a.cursor
    if a.episode is not None:
        d["cursor"]["episode"] = a.episode
    if a.note is not None:
        d["cursor"]["note"] = a.note

    d["target_cpu"] = min(d["cpu_max"],
                          max(int(d["floors"]["main"] * d["floor_mult"]),
                              int(cpu * d["cpu_growth"])))
    if d["phase"] == "GENERATE" and d["target"] and eff >= d["target"]:
        d["phase"] = "AUDIT"
    save(d)

    n, x = len(d["history"]), d["rounds_planned"]
    print("已记账：第 %d/%d 轮 ｜ +%d 字 ／ %d 单元 ｜ 实测 %d 字/单元"
          % (n, x, added, units, cpu))
    print("累计 %d ｜ 还差 %d ｜ 完成度 %.1f%% ｜ 阶段 %s"
          % (eff, max(0, d["target"] - eff), d.get("progress_pct", 0), d["phase"]))
    if len(d["history"]) >= 2:
        prev_added = d["history"][-2]["added"]
        if added < prev_added * 0.9:
            print("⚠ 吞吐停滞：本轮 %d < 上轮 %d → 下一轮每单元目标提到 %d 字"
                  % (added, prev_added, d["target_cpu"]))
    print("下一轮：每单元 ≥ %d 字" % d["target_cpu"])
    if n >= x and d["phase"] == "GENERATE":
        print("⚠ 已跑满契约轮数 x=%d 但字数仍未达标 —— 按契约**自动续跑**，直至达标。" % x)
    return 0


def cmd_report(a):
    d = load()
    r = evaluate(d, a.skip_g10)
    cal = d.get("calibrated", {})
    units, cpu, planned = next_plan(d, r["sc"], r["short"])
    remain = max(0, d["target"] - r["eff"])
    print("## 第 %d/%d 轮已交付" % (len(d["history"]), d["rounds_planned"]))
    print("| 项目 | 值 |")
    print("|---|---|")
    print("| 目标 | %d |" % d["target"])
    print("| 当前（最严口径） | %d |" % r["eff"])
    print("| 还差 | %d |" % remain)
    print("| 完成度 | %.1f%% |" % (100.0 * r["eff"] / d["target"] if d["target"] else 0))
    print("| 阶段 | %s |" % r["phase"])
    print("| 单元数 | %d |" % len(r["sc"]["units"]))
    print("| 实测吞吐 | %s 字/单元 ｜ %s 字/轮 |"
          % (cal.get("chars_per_unit", 0), cal.get("chars_per_turn", 0)))
    print("| 下一轮 | %d 单元 × %d 字 = %d 字 | 还需约 %d 轮 |"
          % (units, cpu, planned, -(-remain // max(1, planned))))
    return 0


def cmd_calibrate(a):
    """用实测数据反推 cap：把"单轮输出上限"换成真实观测值，重算 x。"""
    d = load()
    hist = d.get("history", [])
    if not hist:
        print("还没有轮次记录，先跑至少一轮 tick 再校准。")
        return 2
    cpus = [h.get("cpu", 0) for h in hist if h.get("cpu")]
    if not cpus:
        print("历史记录里没有 chars_per_unit，无法校准。")
        return 2
    cpus.sort()
    med = cpus[len(cpus) // 2]
    old_cap = d["cap"]
    old_x = d["rounds_planned"]
    # 单块实测产出 → 反推单次回复的真实容量（块 = 一次回复的产出）
    d["cap"] = max(500, med)
    d["per_round"] = int(round(d["cap"] * d["util"]))
    d["rounds_planned"] = int(math.ceil(d["target"] / max(1, d["per_round"])))
    cw = max(1, d["steps_per_window"] // max(1, d["calls_per_chunk"]))
    d["chunks_per_window"] = cw
    d["windows_needed"] = int(math.ceil(d["rounds_planned"] / cw))
    d["turns_needed"] = int(math.ceil(d["rounds_planned"] / max(1, d["chunks_per_turn"])))
    save(d)
    print("已按实测校准：")
    print("  单块实测中位数   %d 字（样本 %d 块）" % (med, len(cpus)))
    print("  单轮上限 cap     %d → %d" % (old_cap, d["cap"]))
    print("  轮数 x           %d → %d" % (old_x, d["rounds_planned"]))
    print("  **预计点 Continue 次数：%d**" % d["windows_needed"])
    return 0


def density_stats(sc):
    """统计正文密度：对白段产出率极低，必须能量化地盯住。"""
    text = sc["text"]
    cjk = len(CJK.findall(text))
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    lines = [l for l in text.split("\n") if l.strip()]
    dlg = [l for l in lines
           if l.strip().startswith(("\u201c", "\""))
           or "\uff1a\u201c" in l or '\uff1a"' in l]
    return {
        "cjk": cjk,
        "paras": len(paras),
        "lines": len(lines),
        "cjk_per_para": round(cjk / max(1, len(paras)), 1),
        "cjk_per_line": round(cjk / max(1, len(lines)), 1),
        "dialogue_ratio": round(len(dlg) / max(1, len(lines)), 3),
    }


def cmd_density(a):
    d = load()
    sc = scan(d)
    s = density_stats(sc)
    th = d.get("density", {})
    pmin = th.get("cjk_per_para", 120)
    dmax = th.get("dialogue_ratio", 0.5)
    print("=" * 64)
    print("正文密度核算（对白段汉字产出率极低，这是最大的隐形浪费）")
    print("=" * 64)
    print("  汉字总数            %d" % s["cjk"])
    print("  段落数 / 行数        %d / %d" % (s["paras"], s["lines"]))
    print("  汉字/段            %8.1f   （目标 ≥ %d）%s"
          % (s["cjk_per_para"], pmin, "" if s["cjk_per_para"] >= pmin else "  ← 偏低"))
    print("  汉字/行            %8.1f" % s["cjk_per_line"])
    print("  对白行占比         %7.1f%%  （目标 ≤ %.0f%%）%s"
          % (s["dialogue_ratio"] * 100, dmax * 100,
             "" if s["dialogue_ratio"] <= dmax else "  ← 偏高，一行一句最费回合预算"))
    ok = s["cjk_per_para"] >= pmin and s["dialogue_ratio"] <= dmax
    print("  结论：%s" % ("密度达标" if ok else "**密度不合格：下一块请用密集叙述写，不要一句一换行**"))
    print("=" * 64)
    return 0 if ok else 2


def cmd_resume(a):
    print(RESUME_LINE)
    return 0


def cmd_where(a):
    d = load()
    print("状态文件：%s" % os.path.abspath(STATE_FILE))
    print("模式：%s（no_user_input=%s）" % (d.get("mode"), d.get("no_user_input")))
    print("轮数契约：x = %d 轮 ｜ 每轮 %d 字（%d × %s）"
          % (d["rounds_planned"], d["per_round"], d["cap"], d["util"]))
    print("轮内链式：k = %d 块/回合 ｜ 需接续约 %d 次"
          % (d.get("chunks_per_turn", 1), d.get("turns_needed", 0)))
    print("Work Mode：每 %s 次调用暂停 ｜ 每窗口 %s 块 ｜ 预计点 %s 次 Continue"
          % (d.get("steps_per_window"), d.get("chunks_per_window", 0),
             d.get("windows_needed", 0)))
    print("阶段：%s ｜ 扫描：%s ｜ 前缀：%r" % (d["phase"], d.get("glob"), d.get("prefix")))
    print("目标：%s ｜ 地板：%s ｜ 本轮每单元目标：%s"
          % (d.get("target"), d.get("floors"), d.get("target_cpu")))
    return 0


def main():
    ap = argparse.ArgumentParser(description="LFBD v9 运行状态机")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("init"); p.set_defaults(f=cmd_init)
    p.add_argument("--target", type=int, required=True)
    p.add_argument("--cap", type=int, default=12000, help="模型单轮输出上限（中文字符）")
    p.add_argument("--util", type=float, default=0.8, help="利用率，默认 0.8")
    p.add_argument("--chunks-per-turn", type=int, default=3, dest="chunks_per_turn",
                   help="一个回合里链式跑几块（默认 3）")
    p.add_argument("--steps-per-window", type=int, default=25, dest="steps_per_window",
                   help="Work Mode 每多少次工具调用暂停一次（默认 25）")
    p.add_argument("--calls-per-chunk", type=int, default=2, dest="calls_per_chunk",
                   help="写一块大约几次工具调用（默认 2）")
    p.add_argument("--glob", action="append")
    p.add_argument("--prefix", default=None)
    p.add_argument("--floors", default="")
    p.add_argument("--units-per-turn-max", type=int, default=0, dest="units_per_turn_max")
    p.add_argument("--deliverable", action="append")

    for name, fn in (("gate", cmd_gate), ("plan", cmd_plan), ("report", cmd_report),
                     ("next", cmd_next), ("count", cmd_count),
                     ("density", cmd_density)):
        p = sp.add_parser(name); p.set_defaults(f=fn)
        p.add_argument("--skip-g10", action="store_true")
        if name == "plan":
            p.add_argument("--chunks", type=int, default=1,
                           help="打印 N 块的连续作业单（轮内链式续跑）")

    for name, fn in (("resume", cmd_resume), ("where", cmd_where),
                     ("calibrate", cmd_calibrate)):
        p = sp.add_parser(name); p.set_defaults(f=fn)

    p = sp.add_parser("tick"); p.set_defaults(f=cmd_tick)
    p.add_argument("--added", type=int, default=None)
    p.add_argument("--units", type=int, default=0)
    p.add_argument("--range", default="")
    p.add_argument("--cursor", type=int, default=None)
    p.add_argument("--episode", type=int, default=None)
    p.add_argument("--note", default=None)

    a = ap.parse_args()
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
