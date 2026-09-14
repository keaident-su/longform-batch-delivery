# G10 内容一致性检查表 · G10 content-consistency checklist

> 跨来源拼接（接手别人底稿 / 更早批次 / 并行运行）时，**动笔前**逐项打勾。
> Run this BEFORE writing any new block into a draft you did not author yourself.

## 一、先跑机器检查 · Run the machine check first

```bash
python scripts/dedupe_scan.py <src_dir> --cross-table --out g10.txt
```

- [ ] `必须修复` = 0（否则先清 ERROR）
- [ ] 读过 `逐场对照表`（同一场次各块的时间/地点/人物/量词/道具并排）

## 二、动笔前的三条对位规则 · Three alignment rules

- [ ] **时位规则**：新补充场的时间若晚于主场次，就绝不重写主场次已经写完的动作
      （踹门、绑人、救人、离开……）。补充场只能写"之后发生的事"或"另一视角"。
- [ ] **细节服从规则**：同一事件的细节一律沿用底稿已确立的那一版——
      几个人到场、用什么工具、人物为什么在场，不得另起一套。
- [ ] **视角规则**：补充场优先从**别人**的视角写（安保/警方/同事/对手/旁观者），
      主场次已经写过的正面镜头不要再拍一遍。

## 三、写完之后再跑一次 · Re-run after writing

- [ ] `python scripts/dedupe_scan.py <src_dir> --cross-table`
- [ ] `python scripts/build_and_verify.py`（G2–G10 全绿）
- [ ] 汇报表里必须出现 `G10 ✓`

## 四、已知误报，先判后改 · Known false positives

| 现象 | 是否要改 | 判断依据 |
|---|---|---|
| G10a：两块共享同一段"标题/论文名/口号" | 通常不用 | 看覆盖度（<6% 已自动忽略） |
| G10d：正文日期比时间字段早很多 | 看语境 | 含"那年/当时/第一次/生日"的属回顾引用，可保留 |
| G10c：补充场与主场次共享 2 个动作词 | 需人工看 | 只有 ≥3 个才判为疑似重写 |
