# -*- coding: utf-8 -*-
"""LFBD loop guard: 自查"不许停"是否到位。退出码 0=就绪 / 2=未就绪。"""
import os, sys, json, re
SK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = True
def chk(cond, msg):
    global ok
    print(("  OK  " if cond else "  FAIL") + "  " + msg)
    if not cond: ok = False

print("[1] SKILL.md 是否含 M0《不许停》铁律")
sk = open(os.path.join(SK,'SKILL.md'), encoding='utf-8').read()
chk('M0' in sk, "SKILL.md 含 M0 段")
chk('不许发出任何' in sk or '绝对不许' in sk, "含'不许收尾'硬约束")
chk('gate' in sk and 'exit 0' in sk, "把 gate exit 0 定为唯一收尾条件")
chk('是否还在 ' not in sk, "无残留占位文本")

print("[2] 配套文件")
for f in ['scripts/run_state.py','templates/NO_STOP.md','templates/turn_contract.md']:
    chk(os.path.exists(os.path.join(SK,f)), f)

print("[3] frontmatter 版本与 description 长度")
m = re.search(r'^version:\s*(\S+)', sk, re.M); chk(bool(m), "version = " + (m.group(1) if m else '?'))
d = re.search(r'description: \|\n((?:  .*\n)+)', sk)
if d:
    raw = 'description: |\n' + d.group(1)
    net = len(re.sub(r'\s','', d.group(1)))
    print(f"    description 净字符={net} 原始长度={len(raw)}")
    chk(net <= 950 and len(raw) <= 1024, "description 双口径 ≤ 1024（净 ≤950）")
else:
    chk(False, "未找到 description 块")

print("[4] 客户端配置（Chatbox）")
cfg = os.path.expandvars(r'%APPDATA%\xyz.chatboxapp.app\config.json')
if os.path.exists(cfg):
    try:
        c = json.load(open(cfg, encoding='utf-8'))
        v = c.get('settings',{}).get('pauseOnToolCallLimit')
        chk(v is False, f"pauseOnToolCallLimit = {v}（应为 false）")
    except Exception as e:
        chk(False, "读取 config.json 失败: " + str(e))
else:
    print("  SKIP 未找到 config.json（可忽略；只要客户端里已关掉'每 25 步暂停'即可）")

print("\n结果:", "[OK] 就绪" if ok else "[FAIL] 未就绪（见上）")
sys.exit(0 if ok else 2)
