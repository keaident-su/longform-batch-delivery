#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""overnight_driver.py - LFBD 无人值守驱动（在聊天之外跑循环）

用法（OpenAI 兼容 / Chatbox AI 兼容端点均可）：
  set LFBD_API_KEY=sk-xxx
  set LFBD_BASE_URL=https://api.openai.com/v1      # 或你的兼容端点
  set LFBD_MODEL=gpt-4o-mini
  python scripts/overnight_driver.py --out out/act5 --target 200000 --scene-file skeleton.txt

它会：读骨架 -> 逐块调用模型生成 -> 追加落盘 -> 统计汉字 -> 达到 target 才退出。
把目标写进 --target，跑到 0 差才停；中途不问你任何问题。
"""
import os, sys, json, time, argparse, urllib.request, urllib.error

def cjk(s): return sum(1 for c in s if '\u4e00' <= c <= '\u9fff')

def call_api(base, key, model, messages, temperature=1.0):
    body = json.dumps({"model": model, "messages": messages, "temperature": temperature}).encode()
    r = urllib.request.Request(base.rstrip('/') + "/chat/completions", data=body, method="POST")
    r.add_header("Authorization", "Bearer " + key)
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=300) as resp:
        d = json.loads(resp.read().decode())
    return d["choices"][0]["message"]["content"]

SYS = ("你是长文分批生成器。只输出正文，不要解释、不要总结、不要提问。"
       "严格遵守给定的大纲锚点与时间线，密度优先（汉字/段>=120），禁止碎片化断句与机械重复。")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--target", type=int, default=200000)
    ap.add_argument("--scene-file", required=True, help="每行一个作业单（锚点/时间/地点/人物）")
    ap.add_argument("--base-url", default=os.environ.get("LFBD_BASE_URL", "https://api.openai.com/v1"))
    ap.add_argument("--model", default=os.environ.get("LFBD_MODEL", "gpt-4o-mini"))
    ap.add_argument("--chunk-target", type=int, default=1800)
    a = ap.parse_args()
    key = os.environ.get("LFBD_API_KEY", "").strip()
    if not key:
        print("ERROR: 先设置环境变量 LFBD_API_KEY"); return 2
    os.makedirs(a.out, exist_ok=True)
    jobs = [l.strip() for l in open(a.scene_file, encoding="utf-8") if l.strip()]
    done = ""
    total = 0
    for i, job in enumerate(jobs, 1):
        for f in os.listdir(a.out):
            if f.endswith(".txt"): total += cjk(open(os.path.join(a.out, f), encoding="utf-8").read())
        if total >= a.target:
            print(f"达到目标 {total}/{a.target}，退出。"); return 0
        prompt = f"作业 {i}/{len(jobs)}：\n{job}\n\n请写 {a.chunk_target} 字以上的正文（只用中文）。"
        last_err = None
        for attempt in range(3):
            try:
                txt = call_api(a.base_url, key, a.model,
                               [{"role": "system", "content": SYS}, {"role": "user", "content": prompt}])
                break
            except Exception as e:
                last_err = e; time.sleep(5)
        else:
            print(f"[{i}] 连续失败，跳过：{last_err}"); continue
        fn = os.path.join(a.out, f"{i:04d}.txt")
        open(fn, "w", encoding="utf-8").write(txt.strip() + "\n")
        c = cjk(txt); total += c
        print(f"[{i}/{len(jobs)}] +{c} 字  当前 {total}/{a.target}")
        sys.stdout.flush()
    print(f"骨架跑完，当前 {total}/{a.target}。" + ("" if total >= a.target else "未达标：请补骨架再跑一轮。"))
    return 0 if total >= a.target else 1

if __name__ == "__main__":
    sys.exit(main())
