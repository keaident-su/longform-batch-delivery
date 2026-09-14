# 轮末契约卡片（LFBD v8）

> 把这张卡片复制到项目根，命名 `TURN_CONTRACT.md`。
> 每轮开工前读一遍；每轮收工前对照最后三行自检。

---

## 一、本项目已授权"跑到底"

```
mode            = RUN_TO_COMPLETION
no_user_input   = true
```

含义：用户已经下过"全部写完"的总指令。**此后每一轮都不需要再征求任何确认。**
唯一合法的停止条件是 `run_state.py gate` 返回 **exit 0**。

---

## 二、每轮固定动作（顺序不许变）

```
1. python scripts/run_state.py where      # 一屏看清当前口径（换会话必跑）
2. python scripts/run_state.py plan       # 拿作业单：单元数 × 每单元字数
3. 按作业单写，落盘（只写源文件，正文不进聊天）
4. python scripts/run_state.py tick --added <新增字数> --units <单元数> --cursor <最新编号>
5. python scripts/run_state.py gate
6. 看退出码 → 决定结尾写什么
```

---

## 三、结尾写什么（二选一，没有第三种）

| gate 退出码 | 状态 | 结尾必须写 |
|---|---|---|
| **0** | DONE | `✅ DONE` + 一句"目标/当前/闸门全过/交付物" |
| **1** | RUNNING | `⏩ RESUME` + `run_state.py resume` 的原文 |
| **2** | BLOCKED | 先修问题 → **修完接着跑** → 结尾同样写 `⏩ RESUME` |

---

## 四、禁止清单（出现任意一条 = 本轮违规）

- ❌ 任何提问：`要不要…`／`需要我继续吗？`／`可以吗？`
- ❌ 任何条件式征询：`如果你想…回我一句'继续'`／`你希望先出哪一册？`
- ❌ 任何"下轮再写"的收尾，除非紧跟 `⏩ RESUME` 块
- ❌ 字数没到就在回复里出现"已完成""全部搞定""交付完毕"
- ❌ 把几万字正文贴进聊天（正文只落盘）

---

## 五、收工前最后三行自检

```
[ ] run_state.py gate 的退出码是 0 吗？不是 → 回去写。
[ ] 我的结尾是 ✅ DONE 或 ⏩ RESUME 吗？都不是 → 改。
[ ] 我这一轮有没有问用户任何问题？有 → 删掉，改成 RESUME。
```
