#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""build_and_verify.py —— 长文本"重建 + 校验"通用模板

用途：把分散在多个源文件里的单元（场/章/节）合并成正确的顺序，并跑一遍质量闸门。
默认适配中文剧本结构（`第N场` + `第N场补充场（一）`），可用 CONFIG / 命令行改。

用法：
  python build_and_verify.py --src "scenes/act5a_*.txt" --title 上册
  python build_and_verify.py --src "scenes/ch*.txt" --unit-pattern "第%d章" \
        --fields 标题 时间 地点 --time-regex "\d{4}-\d{2}-\d{2}" --out merged.txt --docx out.docx

退出码：0 = 全部通过；1 = 有闸门失败。
"""
import argparse
import glob
import re
import sys

CONFIG = {
    # 单元标题：主单元
    "main_pattern": r"^第(\d+)场$",
    # 单元标题：附属单元（补充场），编号用中文数码
    "sub_pattern": r"^第(\d+)场补充场（([一二三四五六七八九十]+)）$",
    # 时间戳
    "time_regex": r"时间[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})[：:](\d{2})",
    # 每单元必填字段（出现在单元体内即可）
    "fields": ["大纲锚点", "时间：", "地点：", "出场人物："],
    # 卷/集标题（用于检查结构完整性）
    "section_pattern": r"^第[一二三四五六七八九十]+季·第\d+集",
    "expect_sections": 0,   # >0 时校验数量
}

CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def build_splitter():
    mp = CONFIG["main_pattern"][1:-1]          # 去掉 ^ $
    sp = CONFIG["sub_pattern"][1:-1]
    return re.compile(r"(?m)^(?=第\d+场(?:补充场（[一二三四五六七八九十]+）)?[ \t]*$)")


def parse(files):
    splitter = build_splitter()
    main_re = re.compile(CONFIG["main_pattern"])
    sub_re = re.compile(CONFIG["sub_pattern"])
    rows = []
    for f in files:
        text = open(f, encoding="utf-8").read()
        parts = splitter.split(text)
        leading, chunks = parts[0], parts[1:]
        for i, p in enumerate(chunks):
            head = p.split("\n", 1)[0].strip()
            m2, m = main_re.match(head), sub_re.match(head)
            if m2:
                n, sub = int(m2.group(1)), 0
            elif m:
                n, sub = int(m.group(1)), CN.get(m.group(2), 0)
            else:
                continue
            body = (leading.rstrip("\n") + "\n" + p) if (i == 0 and leading.strip()) else p
            cjk = sum(1 for c in body if "\u4e00" <= c <= "\u9fff")
            rows.append({"n": n, "sub": sub, "head": head, "body": body, "cjk": cjk})
    rows.sort(key=lambda r: (r["n"], r["sub"]))
    return rows


def check(rows):
    fails, warns = [], []
    # G2 编号连续
    mains = [r["n"] for r in rows if r["sub"] == 0]
    if mains:
        exp = list(range(min(mains), max(mains) + 1))
        if mains != exp:
            fails.append("G2 主编号不连续：缺 %s，重复 %s"
                         % ([x for x in exp if x not in mains],
                            [x for x in set(mains) if mains.count(x) > 1]))
    # 附属单元紧跟主单元 + 序号连续
    last = None
    per = {}
    for r in rows:
        if r["sub"] == 0:
            last = r["n"]
        else:
            if r["n"] != last:
                fails.append("G2 附属单元错位：%s" % r["head"])
            per.setdefault(r["n"], []).append(r["sub"])
    for n, ss in per.items():
        if ss != list(range(1, len(ss) + 1)):
            fails.append("G2 附属单元序号异常：第%d -> %s" % (n, ss))
    # G3 时间单调
    ts, prev = [], None
    for r in rows:
        m = re.search(CONFIG["time_regex"], r["body"])
        if not m:
            warns.append("缺时间戳：%s" % r["head"])
            ts.append(None)
            continue
        g = m.groups()
        t = tuple(int(x) for x in g) if len(g) == 5 else (int(g[0]),)
        ts.append(t)
    for i in range(1, len(ts)):
        if ts[i] and ts[i - 1] and ts[i] <= ts[i - 1]:
            fails.append("G3 时间不递增：%s" % rows[i]["head"])
    # G4 字段
    for r in rows:
        for f in CONFIG["fields"]:
            if f not in r["body"]:
                fails.append("G4 缺字段 [%s]：%s" % (f, r["head"]))
    # G5 结构
    secs = [r for r in rows if re.search(CONFIG["section_pattern"], r["body"])]
    if CONFIG["expect_sections"] and len(secs) != CONFIG["expect_sections"]:
        fails.append("G5 卷/集标题数 %d ≠ 期望 %d" % (len(secs), CONFIG["expect_sections"]))
    # G6 退化
    bad_pat = re.compile(r"[\u4e00-\u9fff]{2,4}，[\u4e00-\u9fff]{1,2}[。，！？]")
    frag = 0
    for r in rows:
        hits = bad_pat.findall(r["body"])
        if hits:
            frag += len(hits)
            warns.append("G6 疑似碎片断句：%s -> %s" % (r["head"], hits[:3]))
    max_blank = 0
    for r in rows:
        cur = mx = 0
        for line in r["body"].split("\n"):
            cur = cur + 1 if not line.strip() else 0
            mx = max(mx, cur)
        max_blank = max(max_blank, mx)
    if max_blank > 2:
        fails.append("G6 空行注水：最大连续空行 %d" % max_blank)
    return fails, warns, max_blank, frag


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", action="append", required=True, help="源文件 glob，可多次")
    ap.add_argument("--title", default="文集")
    ap.add_argument("--out", default=None, help="合并后的 txt")
    ap.add_argument("--docx", default=None, help="输出 docx（需 python-docx）")
    ap.add_argument("--unit-pattern", default=None, help="如 '第%d章'")
    ap.add_argument("--fields", nargs="*", default=None)
    ap.add_argument("--time-regex", default=None)
    ap.add_argument("--expect-sections", type=int, default=0)
    ap.add_argument("--strict-frag", action="store_true")
    a = ap.parse_args()

    if a.fields is not None:
        CONFIG["fields"] = a.fields
    if a.time_regex:
        CONFIG["time_regex"] = a.time_regex
    if a.expect_sections:
        CONFIG["expect_sections"] = a.expect_sections
    if a.unit_pattern:
        u = a.unit_pattern.replace("%d", r"(\d+)")
        CONFIG["main_pattern"] = "^" + u + "$"

    files = []
    for g in a.src:
        files += sorted(glob.glob(g))
    if not files:
        print("没有匹配到源文件：", a.src)
        return 1

    rows = parse(files)
    fails, warns, max_blank, frag = check(rows)
    total = sum(r["cjk"] for r in rows)

    print("[%s] 单元=%d 中文字符=%d" % (a.title, len(rows), total))
    print("  G1 字数: %d" % total)
    print("  G2 编号: %s" % ("FAIL" if any(x.startswith("G2") for x in fails) else "OK"))
    print("  G3 时间: %s" % ("FAIL" if any(x.startswith("G3") for x in fails) else "OK"))
    print("  G4 字段: %s" % ("FAIL" if any(x.startswith("G4") for x in fails) else "OK"))
    print("  G5 结构: %s" % ("FAIL" if any(x.startswith("G5") for x in fails) else "OK"))
    print("  G6 退化: 最大空行=%d 疑似碎片=%d" % (max_blank, frag))
    for w in warns[:10]:
        print("   ⚠", w)
    for f in fails:
        print("   ✗", f)

    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write("\n\n".join(r["body"].rstrip() for r in rows))
        print("  ->", a.out)
    if a.docx:
        try:
            from docx import Document
            from docx.shared import Pt
            from docx.oxml.ns import qn
            doc = Document()
            st = doc.styles["Normal"]
            st.font.name = "宋体"
            st.font.size = Pt(11)
            st._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "宋体")
            for r in rows:
                for line in r["body"].split("\n"):
                    s = line.strip()
                    if not s:
                        continue
                    p = doc.add_paragraph()
                    run = p.add_run(s)
                    run.font.name = "宋体"
                    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "宋体")
                doc.add_paragraph()
            doc.save(a.docx)
            print("  ->", a.docx)
        except ImportError:
            print("  (跳过 docx：未安装 python-docx)")

    # G6 的"疑似碎片断句"是启发式提示，仅告警不判失败；连续空行>=3 才算失败。
    print("RESULT:", "PASS" if not fails else "FAIL(%d)" % len(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
