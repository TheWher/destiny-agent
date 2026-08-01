# 检索器后端对比报告 — lexical vs embedding

日期：2026-08-01
评测集：seed_pairs.json v0.2（103 对：87 run + 16 graduated/cff）
口径：exact_contain、k=5、同批 pair、同 dry_run_check 脚本
后端切换：`KB_BACKEND=lexical|embedding`（注册表驱动，出口契约不变）

## 结果总览

| 指标 | lexical 基线 | embedding | 变化 |
|---|---|---|---|
| 命中率 | 100.0%（注水） | 100.0% | 持平 |
| 平均返回长度 | 2423 B | 331 B | ↓86% |
| 最大返回长度 | 6416 B | 703 B | ↓89% |
| 文件级 dump 对 | 25/87 | 0/87 | ↓100% |
| 返回 ≥1.6KB 占比 | 100% | 0% | ↓100% |
| hits↔str 一致性 | 87/87 | 87/87 | 持平 |

## 按文件粒度分布（平均返回字节）

| 文件 | lexical | embedding |
|---|---|---|
| tiaohou.json | 6353 | 181 |
| ziwei_classics.json | 1707 | 243 |
| ziwei_fuzuo.json | 2434 | 186 |
| ziwei_hua.json | 2017 | 204 |
| ziwei_star_palace.json | 1718 | 566 |
| 全库 | 2423 | 331 |

## 验收线判定（韩湘生定案标准）

- 文件级对 43→0（登记化前口径 27，动态判定 25）：**embedding 0 → PASS**
- 平均返回长度减半（≤1640 及格 / ≤1100 优良）：**331B → 优良（接近条目级）**
- 预期优良区间 400~1100B，实测 331B 低于区间下沿：star_palace 566B 在区间内，
  tiaohou/classics/hua/fuzuo 条目本身短（20~170B），top-5 拼接后落在 180~270B，属正常。

## 结论

1. embedding 后端将返回粒度从"文件级/块级 dump"收敛到"条目级"，命中率未损（100%）。
2. 粒度改善带来 token 成本与信号密度双重收益：每查询返回从 2.4KB 降到 331B。
3. lexical 的 100% 命中率是粒度注水（100% 返回 ≥1.6KB）；embedding 的 100% 是条目级真实命中。
4. 一致性断言双后端均通过，两个出口共享引擎无漂移。

## 技术备注

- 模型：BAAI/bge-small-zh-v1.5（本地，512 维），模型文件存 models/bge-small-zh-v1.5/
- 下载源：ModelScope（hf-mirror/直连均超时或限速，ModelScope ~6.5MB/s）
- query 编码：关键词分别编码取平均（整句拼接对"专名+槽位"型查询区分度不足，实测 zp_029 不命中）
- 编码对称性：query/passage 同一 encode 调用、同一 normalize_embeddings=True
- 依赖：sentence-transformers>=2.7.0 已入 requirements.txt（环境实测 5.5.1 + torch 2.12.0+cpu 可用）
