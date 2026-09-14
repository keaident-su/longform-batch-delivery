#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish_github.py —— 把一个技能/目录整体推送到 GitHub 仓库（UTF-8 安全）

设计要点（解决中文乱码）：
  * 一律以 UTF-8 读文件、以 base64 提交（GitHub Contents API 的原生格式），
    不经过任何本地代码页，中文不会变成 ????。
  * 默认先取目标的 blob SHA，存在则 update，不存在则 create。

用法：
  export GITHUB_TOKEN=ghp_xxx          # Windows: set GITHUB_TOKEN=ghp_xxx
  python scripts/publish_github.py \
      --repo keaident-su/longform-batch-delivery \
      --src . --branch main --message "skill: v6.0.0" \
      --desc "A batching/delivery protocol for ultra-long text · 长文本分批交付协议" \
      [--exclude .git --exclude __pycache__] [--dry-run]

安全：
  * Token **只从环境变量读取**，绝不写进任何文件、绝不打印。
  * 本脚本不上传 .git、__pycache__、node_modules、*.pyc。
"""

import os, sys, base64, argparse, json, urllib.request, urllib.error

API = "https://api.github.com"
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".idea", ".vscode", "dist", "build"}
SKIP_EXT = {".pyc", ".pyo", ".log"}


def req(method, url, token, data=None):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    r = urllib.request.Request(url, data=body, method=method)
    r.add_header("Authorization", "token " + token)
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("User-Agent", "lfbd-publish")
    if body:
        r.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(r, timeout=40) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"_http": e.code, "_msg": str(e)}


def walk(src, excludes):
    out = []
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and d not in excludes]
        for f in files:
            if os.path.splitext(f)[1] in SKIP_EXT or f in excludes:
                continue
            p = os.path.join(root, f)
            rel = os.path.relpath(p, src).replace("\\", "/")
            out.append((rel, p))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--src", default=".")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--message", default="chore: publish skill")
    ap.add_argument("--desc", default="")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("ERROR: 请先设置环境变量 GITHUB_TOKEN（不要写在文件里）。")
        return 2

    who = req("GET", API + "/user", token)
    if "_http" in who:
        print("ERROR: token 无效或无权限：%s" % who); return 3
    print("已认证：%s" % who.get("login"))

    files = walk(a.src, set(a.exclude))
    print("待上传文件 %d 个" % len(files))

    ok, fail = 0, []
    for rel, path in files:
        raw = open(path, "rb").read()
        content = base64.b64encode(raw).decode("ascii")
        url = "%s/repos/%s/contents/%s" % (API, a.repo, rel)
        cur = req("GET", url + "?ref=" + a.branch, token)
        sha = cur.get("sha") if isinstance(cur, dict) else None
        payload = {"message": "%s : %s" % (a.message, rel),
                   "content": content, "branch": a.branch}
        if sha:
            payload["sha"] = sha
        if a.dry_run:
            print("  [dry-run] %s%s" % (rel, " (update)" if sha else " (create)"))
            ok += 1
            continue
        res = req("PUT", url, token, payload)
        if "_http" in res:
            print("  ! %s -> %s" % (rel, res)); fail.append(rel)
        else:
            print("  ✓ %s%s" % (rel, " (update)" if sha else " (create)"))
            ok += 1

    if a.desc and not a.dry_run:
        d = req("PATCH", "%s/repos/%s" % (API, a.repo), token,
                {"description": a.desc, "has_wiki": False, "has_projects": False})
        print("仓库描述已更新" if "_http" not in d else "描述更新失败: %s" % d)

    print("\n完成：成功 %d ｜ 失败 %d" % (ok, len(fail)))
    if fail:
        print("失败清单：" + ", ".join(fail))
    return 0


if __name__ == "__main__":
    sys.exit(main())
