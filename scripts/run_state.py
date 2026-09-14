#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_state.py —— LFBD v8 运行状态机：停止谓词 + 轮末契约 + 吞吐升级梯

【为什么要有这个脚本】
v7 有 G1–G10，但没有任何东西能**拒绝**模型提前宣布"完成"。
于是真实事故长这样：目标 170,000 字，写到 27,822 字（16.4%）就交付了，
末尾还附一句"要不要先出上册，回我一句"——那只是变相的"停下来问"。

根因：**"完成"是模型的主观判断，不是一个可验证的事实。**

v8 把"完成"变成**退出码**：

    python scripts/run_state.py gate
      exit 0  → DONE     ：字数达标 且 全部闸门通过 且 交付物存在
      exit 1  → RUNNING  ：字数未达标 → 打印下一批作业单 + 一行 RESUME 续跑指令
      exit 2  → BLOCKED  ：存在必须处理的问题（重号 / G10 事实冲突 / 结构错乱）

**只有 exit 0 才允许在回复里写"完成"。** 其余一律继续写，且不许提问。

三条机制
  M1 停止谓词（Stop Predicate）：gate 的退出码是唯一的"完成"判据。
  M2 轮末契约（Turn-end Contract）：每轮只许以 `✅ DONE` 或 `⏩ RESUME` 结尾；
     禁止任何提问、征询、提议（"要不要…""如果你希望…""回我一句…"全部违规）。
  M3 吞吐升级梯（Escalation Ladder）：plan 不按"上一轮写了多少"顺延，而是**逼单块变长**：
         target_cpu = max(floor_main * 1.4, prev_cpu * 1.35)   （上限 cpu_max）
         units      = turn_budget // target_cpu
     块数自动下降、每块自动变长。这正是"加长单块，不要增加块数"的可执行版本。

零第三方依赖（stdlib only）。兼容 LEDGER.md / ledger.json 生态。

--- 常用命令 -------------------------------------------------------------
  python scripts/run_state.py init --target 170000 --glob "scenes/act4*_*.txt" --prefix act4
  python scripts/run_state.py gate           # 唯一的"能不能停"判据（看退出码）
  python scripts/run_state.py plan           # 只打印下一批作业单
  python scripts/run_state.py tick --added 9200 --units 5 --cursor 214 --note "第7集完"
  python scripts/run_state.py report         # 固定汇报表
  python scripts/run_state.py resume         # 打印一行续跑指令（贴回对话框即可）
  python scripts/run_state.py where          # 打印状态文件路径与当前口径
"""

import argparse
import datetime
import glob as globmod
import json
import os
import re
import subprocess
import sys
import zipfile

STATE_FILE = "run_state.json"
CJK = re.compile(r"[\u4e00-\u9fff]")

CN_NUMS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
           "七": 7, "八": 8, "九": 9, "十": 10}

DEFAULTS = {
    "version": "8.0.1",
    "target": 0,
    "mode": "RUN_TO_COMPLETION",       # 用户在本项目中已下过"全部写完"的总指令
    "no_user_input": True,             # 轮末禁止提问/征询
    "glob": ["scenes/*.txt"],
    "prefix": "",
    "floors": {"main": 700, "sub": 500},
    "turn_budget": 10000,              # 单轮安全产出（中文字符），保守初值
    "units_per_turn_max": 12,
    "target_cpu": 2000,                # 本轮"每单元目标字数"
    "cpu_max": 3500,
    "cpu_growth": 1.35,
    "floor_mult": 1.4,
    "required_fields": ["时间[：:]", "地点[：:]", "(出场人物|人物)[：:]"],
    "time_regex": r"^时间[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})[：:](\d{2})",
    "unit_regex": r"^第(\d+)(场|章)$",
    "subunit_regex": r"^第(\d+)场补充场（([一二三四五六七八九十]+)）$",
    "episode_required": False,
    "deliverables": [],                # 例：["*上册*.docx", "*下册*.docx"]
    "cursor": {"episode": 0, "scene": 0, "note": ""},
    "history": [],
    "gates": {},
    "updated_at": "",
}

RESUME_LINE = (
    "继续按 LFBD v8 运行契约执行：读 run_state.json，跑 "
    "`python scripts/run_state.py plan`，按作业单把本轮到上限写满，再跑 "
    "`python scripts/run_state.py gate`；未 exit 0 不许停、不许提问、不许征求确认。"
)


# --------------------------------------------------------------------------
# 状态读写
# --------------------------------------------------------------------------
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
    """同步一份人读账本，保证换会话时人也能一眼看懂。"""
    h = d.get("calibrated", {})
    md = [
        "# RUN STATE（LFBD v8）", "",
        "| 项目 | 值 |", "|---|---|",
        "| 目标 | %s |" % d.get("target"),
        "| 当前 | %s |" % d.get("current_total", 0),
        "| 还差 | %s |" % max(0, (d.get("target") or 0) - (d.get("current_total") or 0)),
        "| 完成度 | %s%% |" % d.get("progress_pct", 0),
        "| 本轮每单元目标字数 | %s |" % d.get("target_cpu"),
        "| 实测 | %s 字/单元 ｜ %s 字/轮 |" % (h.get("chars_per_unit", 0),
                                             h.get("chars_per_turn", 0)),
        "| 游标 | 集 %s ｜ 场 %s |" % (d["cursor"].get("episode"), d["cursor"].get("scene")),
        "| 模式 | %s（no_user_input=%s） |" % (d.get("mode"), d.get("no_user_input")),
        "| 更新时间 | %s |" % d.get("updated_at"), "",
        "## 轮次记录", "", "| 轮 | 范围 | 新增 | 单元 | 字/单元 | 累计 |",
        "|---|---|---|---|---|---|",
    ]
    for b in d.get("history", []):
        md.append("| %s | %s | +%s | %s | %s | %s |" % (
            b.get("turn"), b.get("range", ""), b.get("added"), b.get("units"),
            b.get("cpu", 0), b.get("total")))
    open("LEDGER.md", "w", encoding="utf-8").write("\n".join(md) + "\n")


def cjk_len(s):
    return len(CJK.findall(s))


# --------------------------------------------------------------------------
# 扫描源文件
# --------------------------------------------------------------------------
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
    return {
        "files": files,
        "units": units,
        "total": cjk_len(whole),
        "total_chars": len(whole),
        "text": whole,
    }


# --------------------------------------------------------------------------
# 闸门（M1 停止谓词的全部判据）
# --------------------------------------------------------------------------
def check_gates(d, sc, skip_g10=False):
    """返回 (issues, notes, short, g10)。issues 非空 → 不允许 DONE。"""
    issues, notes = [], []
    units = sc["units"]

    # --- 编号：无重号、主编号严格递增 ---
    seen = {}
    for u in units:
        seen.setdefault(unit_key(u["header"], d), []).append(u["file"])
    dups = {k: v for k, v in seen.items() if len(v) > 1}
    if dups:
        for k, v in sorted(dups.items()):
            issues.append("重号：第%d场 补(%d) 出现在 %s" % (k[0], k[1], ", ".join(v)))

    prev, order_err = 0, 0
    for u in units:
        k = unit_key(u["header"], d)
        if k[1] == 0:
            if k[0] <= prev:
                issues.append("主编号倒流/重复：%s" % u["header"])
            prev = k[0]

    # --- 补充场必须紧跟同号主场次，且序号 (一)(二)… 连续 ---
    last_main, sub_map = None, {}
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

    # --- 时间戳严格单调递增 ---
    times = []
    for u in units:
        m = re.search(d["time_regex"], u["text"], re.M)
        if m:
            times.append((u["header"], tuple(map(int, m.groups()))))
    for i in range(1, len(times)):
        if times[i][1] <= times[i - 1][1]:
            issues.append("时间倒流：%s → %s" % (times[i - 1][0], times[i][0]))

    # --- 必填字段 ---
    missing = 0
    for u in units:
        for pat in d["required_fields"]:
            if not re.search(pat, u["text"]):
                missing += 1
                if missing <= 8:
                    issues.append("缺字段 %s：%s" % (u["header"], pat))
    if missing > 8:
        issues.append("…另有 %d 处字段缺失" % (missing - 8))

    # --- 退化：对话标签逗号 + 连续空行 ---
    frag = re.findall(r'"[\u4e00-\u9fff]{1,4}，[说道问答喊叫][：，]', sc["text"])
    frag += re.findall(r'“[\u4e00-\u9fff]{1,4}，[说道问答喊叫][：，]', sc["text"])
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

    # --- 单元地板（只在字数达标后作为硬闸门；未达标时只出作业单） ---
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

    # --- G10 内容重复 / 事实冲突 ---
    g10_must, g10_warn = 0, 0
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
            m = re.search(r"必须修复\s*(\d+)\s*｜\s*需确认\s*(\d+)", out)
            if m:
                g10_must, g10_warn = int(m.group(1)), int(m.group(2))
                if g10_must:
                    issues.append("G10 内容冲突：必须修复 %d 条（跑 dedupe_scan.py --cross-table 看明细）" % g10_must)
        except Exception as e:
            notes.append("G10 跳过（%s）" % e)
    else:
        notes.append("G10 跳过：未找到 dedupe_scan.py 或源目录")

    # --- 交付物 ---
    for pat in d.get("deliverables", []):
        hits = globmod.glob(pat)
        good = [h for h in hits if os.path.getsize(h) > 0]
        if not good:
            notes.append("交付物未生成：%s" % pat)
        else:
            bad = []
            for h in good:
                try:
                    with zipfile.ZipFile(h) as z:
                        if z.testzip() is not None:
                            bad.append(h)
                except Exception:
                    bad.append(h)
            if bad:
                issues.append("交付物损坏/无法打开：%s" % ", ".join(bad))

    return issues, notes, short, (g10_must, g10_warn)


# --------------------------------------------------------------------------
# 命令实现
# --------------------------------------------------------------------------
def cmd_init(a):
    d = load()
    d["target"] = a.target
    if a.glob:
        d["glob"] = a.glob
    if a.prefix is not None:
        d["prefix"] = a.prefix
    if a.turn_budget:
        d["turn_budget"] = a.turn_budget
    if a.units_per_turn_max:
        d["units_per_turn_max"] = a.units_per_turn_max
    if a.floors:
        main, _, sub = a.floors.partition(",")
        d["floors"] = {"main": int(main), "sub": int(sub or main)}
    if a.deliverable:
        d["deliverables"] = a.deliverable
    d["mode"] = "RUN_TO_COMPLETION"
    d["no_user_input"] = True
    d["target_cpu"] = min(d["cpu_max"], max(d["target_cpu"], int(d["floors"]["main"] * d["floor_mult"])))
    save(d)
    print("已初始化运行状态：目标 %d ｜ 扫描 %s ｜ 每轮 %d 字 ｜ 本轮每单元目标 %d 字"
          % (d["target"], d["glob"], d["turn_budget"], d["target_cpu"]))
    return 0


def cmd_gate(a):
    d = load()
    sc = scan(d)
    total = sc["total"]
    target = d["target"]
    remain = max(0, target - total)
    pct = round(100.0 * total / target, 1) if target else 0.0

    issues, notes, short, g10 = check_gates(d, sc, a.skip_g10)

    print("=" * 64)
    print("目标 %d ｜ 当前 %d ｜ 还差 %d（%.1f%%）｜ 单元 %d ｜ 文件 %d"
          % (target, total, remain, pct, len(sc["units"]), len(sc["files"])))
    print("=" * 64)

    blocking = [i for i in issues if i.startswith("重号") or i.startswith("G10")
                or i.startswith("交付物损坏")]
    if blocking:
        print("\n状态：BLOCKED（exit 2）—— 先修下列问题，再继续往下写。")
        print("注意：BLOCKED 不是「停下来问」，而是「修完接着跑」。")
        for i in blocking:
            print("  ✗ " + i)
        print("\n⏩ RESUME（修完立刻续跑，不要停下征求确认）")
        print(RESUME_LINE)
        return 2

    if target and total < target:
        print("\n状态：RUNNING（exit 1）—— 字数未达标，禁止宣布完成")
        if notes:
            for n in notes:
                print("  · " + n)
        if issues:
            print("  （另有 %d 项待处理，达标后将成为硬闸门）" % len(issues))
        print_next_plan(d, sc, short)
        print("\n⏩ RESUME")
        print(RESUME_LINE)
        return 1

    if issues or short:
        print("\n状态：BLOCKED（exit 2）—— 字数已达标，但下列闸门未过，仍不许停")
        for i in issues:
            print("  ✗ " + i)
        for h, n, f in short[:10]:
            print("  ✗ 低于地板：%s：%d < %d" % (h, n, f))
        if len(short) > 10:
            print("  ✗ …另有 %d 个单元低于地板" % (len(short) - 10))
        print("\n⏩ RESUME（改完立刻重跑 gate，不要停下征求确认）")
        print(RESUME_LINE)
        return 2

    # --- 数字达标 + 全部闸门通过 ---
    deliv = []
    for pat in d.get("deliverables", []):
        deliv.extend(globmod.glob(pat))
    if d.get("deliverables") and not deliv:
        print("\n状态：BLOCKED（exit 2）—— 字数与闸门均过，但交付物未生成：%s"
              % d["deliverables"])
        print("\n⏩ RESUME（生成交付物后重跑 gate）")
        print(RESUME_LINE)
        return 2

    print("\n状态：DONE（exit 0）✅")
    print("  字数 %d ≥ 目标 %d ｜ 编号连续 ｜ 时间单调 ｜ 字段齐全 ｜ 无退化 ｜ "
          "地板达标 ｜ G10 必须修复 %d" % (total, target, g10[0]))
    if deliv:
        print("  交付物：%s" % ", ".join(deliv))
    print("\n可以停。允许在回复里写「完成」。")
    return 0


def next_plan(d, sc, short):
    """吞吐升级梯：返回 (units, cpu, planned)。"""
    floor_main = d["floors"]["main"]
    prev_cpu = 0
    if d["history"]:
        prev_cpu = d["history"][-1].get("cpu", 0) or 0
    cpu = max(int(floor_main * d["floor_mult"]),
              int(prev_cpu * d["cpu_growth"]) if prev_cpu else d["target_cpu"])
    cpu = min(cpu, d["cpu_max"])
    units = max(1, min(d["units_per_turn_max"], d["turn_budget"] // max(1, cpu)))
    return units, cpu, units * cpu


def print_next_plan(d, sc, short):
    units, cpu, planned = next_plan(d, sc, short)
    remain = max(0, d["target"] - sc["total"])
    rounds = -(-remain // max(1, planned)) if planned else 0
    cur = d["cursor"]
    print("\n下一批作业单：")
    print("  · 单元数 %d 个 ｜ 每单元 ≥ %d 中文字符 ｜ 计划共 %d 字"
          % (units, cpu, planned))
    print("  · 起点：接在游标之后（集 %s ／ 场 %s）%s"
          % (cur.get("episode"), cur.get("scene"),
             ("，备注：" + cur.get("note")) if cur.get("note") else ""))
    print("  · 铁令：**加长单块，不要增加块数**（每单元低于 %d 字即不合格）" % cpu)
    print("  · 按当前计划，还需约 %d 轮" % rounds)
    if short:
        print("  · 存量欠账：%d 个单元低于地板，先补这些最省事（前 5 个）" % len(short))
        for h, n, f in short[:5]:
            print("      - %s（现 %d，需 +%d）" % (h, n, f - n))
    print("  · 写完立刻跑：python scripts/run_state.py gate")


def cmd_plan(a):
    d = load()
    sc = scan(d)
    issues, notes, short, g10 = check_gates(d, sc, a.skip_g10)
    print_next_plan(d, sc, short)
    return 0


def cmd_tick(a):
    d = load()
    sc = scan(d)
    prev_total = d.get("current_total", 0)
    added = a.added if a.added is not None else max(0, sc["total"] - prev_total)
    units = a.units or max(1, len(sc["units"]))

    cpu = int(added / units) if units else 0
    d["history"].append({
        "turn": len(d["history"]) + 1,
        "range": a.range or "",
        "added": added,
        "units": units,
        "cpu": cpu,
        "total": sc["total"],
        "at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    d["current_total"] = sc["total"]
    d["target"] = d["target"] or a.target or 0
    d["calibrated"] = {"chars_per_unit": cpu, "chars_per_turn": added}
    d["progress_pct"] = round(100.0 * sc["total"] / d["target"], 1) if d["target"] else 0.0
    if a.cursor is not None:
        d["cursor"]["scene"] = a.cursor
    if a.episode is not None:
        d["cursor"]["episode"] = a.episode
    if a.note is not None:
        d["cursor"]["note"] = a.note

    # 吞吐升级梯：把下一轮的每单元目标顶上去
    prev_cpu = cpu
    new_cpu = max(int(d["floors"]["main"] * d["floor_mult"]),
                  int(prev_cpu * d["cpu_growth"]))
    d["target_cpu"] = min(d["cpu_max"], new_cpu)
    save(d)

    remain = max(0, d["target"] - sc["total"])
    print("已记账：本批 +%d 字 ／ %d 单元 ｜ 实测 %d 字/单元" % (added, units, cpu))
    print("累计 %d ｜ 还差 %d ｜ 完成度 %.1f%%" % (sc["total"], remain, d["progress_pct"]))
    if len(d["history"]) >= 2:
        prev_added = d["history"][-2]["added"]
        if added < prev_added * 0.9:
            print("⚠ 吞吐停滞：本轮 %d < 上轮 %d。下一轮每单元目标提高到 %d 字"
                  "（减少单元数来腾出长度）" % (added, prev_added, d["target_cpu"]))
    print("下一轮：每单元 ≥ %d 字" % d["target_cpu"])
    return 0


def cmd_report(a):
    d = load()
    sc = scan(d)
    total, target = sc["total"], d["target"]
    remain = max(0, target - total)
    pct = round(100.0 * total / target, 1) if target else 0.0
    cal = d.get("calibrated", {})
    units, cpu, planned = next_plan(d, sc, [])
    print("## 第 %d 轮已交付" % len(d["history"]))
    print("| 项目 | 值 |")
    print("|---|---|")
    print("| 目标 | %d |" % target)
    print("| 当前 | %d |" % total)
    print("| 还差 | %d |" % remain)
    print("| 完成度 | %.1f%% |" % pct)
    print("| 单元数 | %d |" % len(sc["units"]))
    print("| 实测吞吐 | %s 字/单元 ｜ %s 字/轮 |"
          % (cal.get("chars_per_unit", 0), cal.get("chars_per_turn", 0)))
    print("| 下一轮 | %d 单元 × %d 字 = %d 字 | 还需约 %d 轮 |"
          % (units, cpu, planned, -(-remain // max(1, planned))))
    issues, notes, short, g10 = check_gates(d, sc, a.skip_g10)
    print("\n闸门：编号 %s ｜ 时间 %s ｜ 字段 %s ｜ G10 必须修复 %d"
          % ("OK" if not any(i.startswith(("重号", "主编号", "补充场")) for i in issues) else "FAIL",
             "OK" if not any(i.startswith("时间") for i in issues) else "FAIL",
             "OK" if not any(i.startswith("缺字段") for i in issues) else "FAIL",
             g10[0]))
    return 0


def cmd_resume(a):
    print(RESUME_LINE)
    return 0


def cmd_where(a):
    d = load()
    print("状态文件：%s" % os.path.abspath(STATE_FILE))
    print("模式：%s（no_user_input=%s）" % (d.get("mode"), d.get("no_user_input")))
    print("扫描：%s ｜ 前缀：%r" % (d.get("glob"), d.get("prefix")))
    print("目标：%s ｜ 地板：%s ｜ 每轮预算：%s ｜ 本轮每单元目标：%s"
          % (d.get("target"), d.get("floors"), d.get("turn_budget"), d.get("target_cpu")))
    return 0


def main():
    ap = argparse.ArgumentParser(description="LFBD v8 运行状态机")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("init"); p.set_defaults(f=cmd_init)
    p.add_argument("--target", type=int, required=True)
    p.add_argument("--glob", action="append")
    p.add_argument("--prefix", default=None)
    p.add_argument("--turn-budget", type=int, default=0, dest="turn_budget")
    p.add_argument("--units-per-turn-max", type=int, default=0, dest="units_per_turn_max")
    p.add_argument("--floors", default="")
    p.add_argument("--deliverable", action="append")

    p = sp.add_parser("gate"); p.set_defaults(f=cmd_gate); p.add_argument("--skip-g10", action="store_true")
    p = sp.add_parser("plan"); p.set_defaults(f=cmd_plan); p.add_argument("--skip-g10", action="store_true")
    p = sp.add_parser("report"); p.set_defaults(f=cmd_report); p.add_argument("--skip-g10", action="store_true")
    p = sp.add_parser("resume"); p.set_defaults(f=cmd_resume)
    p = sp.add_parser("where"); p.set_defaults(f=cmd_where)

    p = sp.add_parser("tick"); p.set_defaults(f=cmd_tick)
    p.add_argument("--added", type=int, default=None)
    p.add_argument("--units", type=int, default=0)
    p.add_argument("--range", default="")
    p.add_argument("--cursor", type=int, default=None)
    p.add_argument("--episode", type=int, default=None)
    p.add_argument("--note", default=None)
    p.add_argument("--target", type=int, default=0)

    a = ap.parse_args()
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
