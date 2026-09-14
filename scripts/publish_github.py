#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LFBD v7 — 把一个目录整体推送到 GitHub 仓库（UTF-8 安全，走 REST API，不依赖 git）

用法 / Usage:
  export GH_TOKEN=ghp_xxx            # 或 set GH_TOKEN=...
  python publish_github.py --dir ./longform-batch-delivery --repo keaident-su/longform-batch-delivery \
      --message "feat: LFBD v7" --description "..."

说明 / Notes:
  - 只做新增/更新，不删除远端文件。
  - 大文件（>1MB）会走 Git Data API 分块提交（本脚本默认不处理，必要时扩展）。
  - token 绝不写入文件；只从环境变量读取。
"""
import os, sys, json, base64, argparse, urllib.request, urllib.error


def api(path, method='GET', data=None):
    token = os.environ.get('GH_TOKEN', '')
    if not token:
        sys.exit('missing env GH_TOKEN')
    req = urllib.request.Request('https://api.github.com' + path, method=method)
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('User-Agent', 'l fbd-publisher')
    body = None
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, body, timeout=60) as r:
            return r.status, json.loads(r.read().decode('utf-8') or '{}')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8') or '{}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--repo', required=True, help='owner/name')
    ap.add_argument('--message', default='update')
    ap.add_argument('--branch', default='main')
    ap.add_argument('--description', default=None)
    a = ap.parse_args()

    st, me = api('/user')
    if st != 200:
        sys.exit('auth failed: %s' % me)

    # 确保仓库存在
    st, repo = api('/repos/' + a.repo)
    if st == 404:
        owner, name = a.repo.split('/')
        print('creating repo', a.repo)
        st, repo = api('/user/repos', 'POST', {'name': name, 'private': False,
                                               'description': a.description or ''})
        if st not in (200, 201):
            sys.exit('create repo failed: %s' % repo)
    else:
        if a.description:
            api('/repos/' + a.repo, 'PATCH', {'description': a.description})

    skip_dirs = {'.git', '__pycache__', 'node_modules'}
    count = 0
    for root, dirs, files in os.walk(a.dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fn in files:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, a.dir).replace('\\', '/')
            raw = open(full, 'rb').read()
            content = base64.b64encode(raw).decode('ascii')
            st, cur = api('/repos/%s/contents/%s?ref=%s' % (a.repo, rel, a.branch))
            payload = {'message': '%s: %s' % (a.message, rel), 'content': content, 'branch': a.branch}
            if st == 200:
                payload['sha'] = cur['sha']
            st, res = api('/repos/%s/contents/%s' % (a.repo, rel), 'PUT', payload)
            print(('  OK  ' if st in (200, 201) else '  FAIL') + ' ' + rel + ('' if st in (200, 201) else ' -> ' + str(res)[:120]))
            if st in (200, 201):
                count += 1
    print('pushed %d files to https://github.com/%s' % (count, a.repo))


if __name__ == '__main__':
    main()
