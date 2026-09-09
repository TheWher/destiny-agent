# 多智能体编排 Implementation Plan

> **状态（2026-09-09 补记）：已上线——services/orchestrator.py + plugin_manager.py 实装（pytest test_orchestrator/test_plugin_manager 常驻回归）；checkbox 未逐项回填，进度以 CHANGELOG 为准。**

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将紫微单 Agent(612行)拆为 3 专项 Agent(格局/四化/宫位联动) + 1 合成 Agent，并行调用后合成最终报告

**Architecture:** 4 个独立 prompt 文件 + 后端 `analyze_ziwei()` 改为 asyncio.gather 并行调用 + 1 次合成调用。格局/四化/宫位 Agent 互不依赖，输出 JSON 结构化数据，合成 Agent 只做叙事不重新分析。

**Tech Stack:** Python/Flask, asyncio/aiohttp, DeepSeek API, JSON

## Global Constraints

- 3 个专项 Agent 必须并行调用，不可串行
- 每个专项 Agent 输出严格 JSON schema，不可输出自由散文
- 合成 Agent 不做新命理判断，只整合前三个 Agent 的输出
- 知识库按 Agent 裁剪注入，不注入无关 KB
- 不改前端、不改现有 KB 文件（新建除外）

---

### Task 0: 新建 `knowledge_base/ziwei_sihua_interact.json`

**Files:**
- Create: `knowledge_base/ziwei_sihua_interact.json`

**Interfaces:**
- Consumes: 当前 `ziwei-master.md` prompt 中的 15 条四化互涉规则 + `ziwei_hua.json` 四化表
- Produces: 结构化 JSON，供四化 Agent 注入

- [ ] **Step 1: 创建四化互涉规则表**

```json
{
  "_description": "四化互涉规则——四层四化叠加/对冲/自化互涉",
  "_source": "ziwei-master.md v7 方法论 §2",
  "同类型叠加": [
    {"rule": "生年忌 + 大限忌同宫 → 课题加剧，十年内集中爆发"},
    {"rule": "生年忌 + 流年忌同宫 → 年度压力触发先天课题"},
    {"rule": "生年禄 + 大限禄同宫 → 十年好运加成"},
    {"rule": "生年禄 + 流年禄同宫 → 机遇年，短期利好"},
    {"rule": "大限禄 + 流年禄同宫 → 十年好运中的小高峰"}
  ],
  "不同类型对冲": [
    {"rule": "生年禄 + 大限忌同宫 → 先天好运在十年内受压制"},
    {"rule": "大限禄 + 流年忌 → 十年好运中遇年度波折"},
    {"rule": "生年忌 + 大限禄同宫 → 先天课题在十年内缓解"},
    {"rule": "大限权 + 流年忌 → 十年掌控力增强遇年度阻力"},
    {"rule": "生年科 + 大限忌 → 学术名声领域十年挑战"}
  ],
  "自化互涉": [
    {"rule": "自化忌 → 该宫事务反复、自我消耗"},
    {"rule": "自化禄 → 该宫事务有内在生机"},
    {"rule": "自化权 → 该宫事务内在驱动力强"},
    {"rule": "自化科 → 该宫事务自带梳理能力"}
  ],
  "判断优先级": "先同宫（同宫叠加 > 对宫冲照 > 三合会照），再生年 > 大限 > 流年",
  "禁止": ["用流年四化推导先天性格", "用生年四化解释流年事件", "跨宫跳级推四化链"]
}
```

- [ ] **Step 2: 验证 JSON 格式**

```bash
python -c "import json; d=json.load(open('knowledge_base/ziwei_sihua_interact.json','r',encoding='utf-8')); print('OK:', list(d.keys()))"
```

- [ ] **Step 3: 提交**

```bash
git add knowledge_base/ziwei_sihua_interact.json
git commit -m "feat(kb): 新建四化互涉规则表——15条叠加/对冲/自化规则"
```

---

### Task 1: 格局 Agent prompt

**Files:**
- Create: `.claude/agents/ziwei-geju.md`

**Interfaces:**
- Consumes: `plate_dict`（十二宫分布/主星亮度/三方四正）+ `ziwei_stars.json` + `ziwei_star_palace.json`
- Produces: JSON `{agent, conclusions, key_stars, patterns, confidence}`

- [ ] **Step 1: 创建格局 Agent prompt 文件**

从 `ziwei-master.md` 中提取格局相关方法论（§4 格局判定 + §1 亮度体系 + §6 对宫冲照 + 24 格局表），精简为 ~150 行：

```markdown
---
name: "ziwei-geju"
description: "紫微斗数格局专项Agent——判定主星组合、三方四正、格局成格/破格"
---

你是紫微斗数格局分析专家。你是三个专家之一，你的职责是分析命盘的格局结构。

## 数据契约
你收到的 user message 包含：
- **十二宫分布表**（干支/主星[含亮度]/辅星/生年四化/命宫身宫标记）
- **命盘概要**（五行局/命宫/身宫位置）
- **星曜知识库原文**（主星特性、庙旺利陷分宫解读）

## 格局判定方法论
从 ziwei-master.md 提取格局相关核心规则：
- 亮度体系 7 级（引用了亮度修正表）
- 24 格局体系表（核心 8 格局 + 常见 16 格局）
- 对宫冲照（6 组对宫 + 7 级冲照力度）
- 五层受损判定（打到核心？能否补救？）

## 输出 JSON Schema（严格遵循，禁止输出 Markdown）
```json
{
  "agent": "geju",
  "conclusions": ["结论1", "结论2"],
  "key_stars": [{"name": "紫微", "palace": "命宫", "branch": "午", "brightness": "庙", "state": "庙旺"}],
  "patterns": [{"name": "杀破狼格", "status": "成格/虚格/破格/不构成", "detail": "..."}],
  "conflict_palaces": [{"from": "命宫", "to": "迁移", "type": "冲照", "level": "强"}],
  "confidence": "high/medium/low"
}
```

## 约束
- 只分析格局相关内容，不分析四化，不分析宫位联动
- 只输出 JSON，不输出任何散文、说明、注释
- confidence=high 当命中确定性高，low 当数据不足以确定
```

- [ ] **Step 2: 提交**

```bash
git add .claude/agents/ziwei-geju.md
git commit -m "feat(agent): 格局专项Agent——主星组合+三方四正+格局判定"
```

---

### Task 2: 四化 Agent prompt

**Files:**
- Create: `.claude/agents/ziwei-sihua.md`

**Interfaces:**
- Consumes: `plate_dict` + `ziwei_hua.json` + `ziwei_sihua_interact.json`（Task 0）
- Produces: JSON `{agent, sihua_paths, interactions, conclusions, confidence}`

- [ ] **Step 1: 创建四化 Agent prompt 文件**

从 `ziwei-master.md` 提取四化方法论（§2 四层四化权重体系 + 四化互涉规则 + 四化叠加/对冲规则），精简为 ~120 行：

```markdown
---
name: "ziwei-sihua"
description: "紫微斗数四化专项Agent——分析化禄/权/科/忌飞化路径和互涉"
---

你是紫微斗数四化分析专家。你是三个专家之一，你的职责是分析命盘的四化能量流向。

## 数据契约
你收到的 user message 包含：
- **十二宫分布表**
- **生年四化表**
- **大限四化表**
- **当前大限**
- **当前流年表**
- **四化知识库原文**（四化规则表 + 互涉规则）

## 四化方法论
从 ziwei-master.md 提取：
- 四层四化权重体系（生年★★★★★/大限★★★★/自化★★★/流年★★）
- 15 条互涉规则（同类型叠加/不同类型对冲/自化互涉）

## 输出 JSON Schema（严格遵循）
```json
{
  "agent": "sihua",
  "sihua_paths": [
    {"type": "生年化禄", "star": "天机", "from_palace": "兄弟", "to_palace": "兄弟", "layer": "生年"},
    {"type": "大限化忌", "star": "太阴", "from_palace": "官禄", "to_palace": "官禄", "layer": "大限"}
  ],
  "interactions": [
    {"rule": "生年忌+大限忌同宫", "palace": "官禄", "effect": "课题加剧"},
    {"rule": "生年禄+流年禄", "palace": "夫妻", "effect": "机遇年"},
  ],
  "conclusions": ["结论1", "结论2"],
  "confidence": "high/medium/low"
}
```

## 约束
- 只分析四化相关内容，不分析格局，不分析宫位联动
- 只输出 JSON
- confidence=high 当生年四化明确、互涉规则清晰
```

- [ ] **Step 2: 提交**

```bash
git add .claude/agents/ziwei-sihua.md
git commit -m "feat(agent): 四化专项Agent——化禄权科忌飞化路径+互涉规则"
```

---

### Task 3: 宫位联动 Agent prompt

**Files:**
- Create: `.claude/agents/ziwei-palace.md`

**Interfaces:**
- Consumes: `plate_dict` + `ziwei_fuzuo.json` + 八字交叉参考（`bazi_ref`）
- Produces: JSON `{agent, cross_references, conclusions, confidence}`

- [ ] **Step 1: 创建宫位联动 Agent prompt 文件**

从 `ziwei-master.md` 提取宫位相关方法论（§5 身宫 + §6 对宫冲照 + §7 三方四正 + §8 截空旬空 + §9 流年命宫 + §10 宫位联动表），精简为 ~120 行：

```markdown
---
name: "ziwei-palace"
description: "紫微斗数宫位联动专项Agent——分析十二宫交叉关联、冲照、身宫走势"
---

你是紫微斗数宫位联动分析专家。你是三个专家之一，你的职责是分析十二宫之间的交叉关联。

## 数据契约
你收到的 user message 包含：
- **十二宫分布表**（含身宫标记）
- **辅佐煞曜知识库原文**（六吉六煞分宫详解）
- **八字参考**（日主/喜用/强弱，用于辅助判断宫位能量）

## 宫位联动方法论
从 ziwei-master.md 提取：
- 身宫独立分析框架（4 维 + 年龄权重 + 命身同宫）
- 对宫冲照 6 组（命↔迁、夫↔官、财↔福…）
- 宫位联动表（事业→官+财+命+迁；感情→夫+福+命+迁…）
- 截空/旬空效应
- 流年命宫叠加规则

## 输出 JSON Schema（严格遵循）
```json
{
  "agent": "palace",
  "cross_references": [
    {"from": "夫妻", "to": "官禄", "type": "冲照", "effect": "感情波动影响事业", "level": "强"},
    {"from": "财帛", "to": "福德", "type": "冲照", "effect": "物质追求影响精神满足", "level": "中"}
  ],
  "body_palace": {"location": "福德", "weight": "40%", "trend": "35岁后精神追求成为重心"},
  "conclusions": ["结论1", "结论2"],
  "confidence": "high/medium/low"
}
```

## 约束
- 只分析宫位联动和身宫，不分析格局，不分析四化
- 只输出 JSON
```

- [ ] **Step 2: 提交**

```bash
git add .claude/agents/ziwei-palace.md
git commit -m "feat(agent): 宫位联动专项Agent——十二宫交叉+冲照+身宫"
```

---

### Task 4: 合成 Agent prompt

**Files:**
- Create: `.claude/agents/ziwei-synth.md`

**Interfaces:**
- Consumes: 前三个 Agent 的 JSON 输出
- Produces: 最终 markdown 报告（5 章全盘格式）

- [ ] **Step 1: 创建合成 Agent prompt 文件**

```markdown
---
name: "ziwei-synth"
description: "紫微斗数合成Agent——将三个专项Agent的分析整合为流畅的命盘解读报告"
---

你是紫微斗数报告合成专家。你的任务是整合格局、四化、宫位联动三个专家的分析结论，输出一份流畅的命盘解读。

## 输入格式
你收到的 user message 包含三个 JSON 块的拼接：
```
[格局 Agent 的输出 JSON]
[四化 Agent 的输出 JSON]
[宫位联动 Agent 的输出 JSON]
```

## 合成规则
- **禁止添加新的命理判断**——你的任务只是整合三份已有结论，不重新分析
- **风格统一**——将三份 JSON 结论翻译为日常语言
- **矛盾处理**——如果三份结论中有冲突，在报告中诚实说明「格局师认为XX，但宫位师提示YY，建议折中看待」
- **叙事顺序**：命盘底色（格局为主）→ 事业（格局+宫位联动）→ 感情（宫位联动+四化）→ 大限（四化+宫位联动）→ 流年（三合一）

## 输出格式
标准 5 章全盘 markdown 格式（与现有 ziwei-master.md 模式A一致）：
1. `## 🎯 命盘底色`
2. `## 💼 事业格局`
3. `## ❤️ 感情因缘`
4. `## 🔮 当前大限`
5. `## 📅 近三年流年`

## 约束
- 不做新命理判断，只整合已有结论
- 引用结论时标注来源（如"格局分析显示…""四化分析显示…"）
- 结尾强制引导追问
```

- [ ] **Step 2: 提交**

```bash
git add .claude/agents/ziwei-synth.md
git commit -m "feat(agent): 合成Agent——将三专项结论整合为命盘解读报告"
```

---

### Task 5: 后端改造——并行调用 + 合成

**Files:**
- Modify: `analysis_service.py`（`analyze_ziwei()` 重写）

**Interfaces:**
- Consumes: `plate_dict` + 4 个新 prompt 文件
- Produces: 最终分析文本

- [ ] **Step 1: 重写 `analyze_ziwei()` 为并行架构**

```python
import asyncio
import json

def analyze_ziwei(plate_dict: dict, timeout: int = 120, bazi_ref: dict = None) -> dict:
    """多智能体编排：3 并行 + 1 合成"""
    
    # 构建三个专项 Agent 的 user message（裁剪 KB 注入）
    geju_msg = _build_geju_user_message(plate_dict)
    sihua_msg = _build_sihua_user_message(plate_dict)
    palace_msg = _build_palace_user_message(plate_dict, bazi_ref)
    
    # 加载四个 prompt
    geju_sp = _load_agent_prompt("ziwei-geju")
    sihua_sp = _load_agent_prompt("ziwei-sihua")
    palace_sp = _load_agent_prompt("ziwei-palace")
    synth_sp = _load_agent_prompt("ziwei-synth")
    
    # 并行调用三个专项 Agent
    async def run_parallel():
        async with aiohttp.ClientSession() as session:
            tasks = [
                _call_api_json(geju_sp, [{"role": "user", "content": geju_msg}], timeout),
                _call_api_json(sihua_sp, [{"role": "user", "content": sihua_msg}], timeout),
                _call_api_json(palace_sp, [{"role": "user", "content": palace_msg}], timeout),
            ]
            return await asyncio.gather(*tasks, return_exceptions=True)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results = loop.run_until_complete(run_parallel())
    loop.close()
    
    # 解析 JSON 输出
    geju_out, sihua_out, palace_out = results
    # 对每个输出做 json.loads 解析，失败时降级为空 dict
    
    # 构建合成 Agent 的输入
    synth_input = f"【格局分析】\n{json.dumps(geju_out, ensure_ascii=False)}\n\n【四化分析】\n{json.dumps(sihua_out, ensure_ascii=False)}\n\n【宫位联动分析】\n{json.dumps(palace_out, ensure_ascii=False)}"
    
    # 调用合成 Agent
    synth_result = _call_api_text(synth_sp, [{"role": "user", "content": synth_input}], timeout)
    
    return {"success": True, "analysis": synth_result}
```

- [ ] **Step 2: 实现辅助函数**

```python
# _load_agent_prompt(path) — 读取 .claude/agents/ 下的 prompt 文件
# _call_api_json(sp, messages, timeout) — 调用 API，强制要求 JSON 输出
# _call_api_text(sp, messages, timeout) — 调用 API，返回文本
def _load_agent_prompt(name: str) -> str:
    """加载 Agent prompt 文件"""
    path = os.path.join(os.path.dirname(__file__), '.claude', 'agents', f'{name}.md')
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(__file__), '..', '.claude', 'agents', f'{name}.md')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""
```

- [ ] **Step 3: 实现三个 user message 构建函数（裁剪 KB 注入）**

```python
def _build_geju_user_message(plate_dict: dict) -> str:
    """格局 Agent 的 user message——只注入 stars + star_palace KB"""
    base = _build_base_message(plate_dict)  # 十二宫分布 + 命盘概要
    # 注入星曜知识库
    stars_kb = _load_json_kb("ziwei_stars.json")
    palace_kb = _load_json_kb("ziwei_star_palace.json")
    if stars_kb:
        base += f"\n## 星曜知识库\n{json.dumps(stars_kb, ensure_ascii=False)}"
    if palace_kb:
        base += f"\n## 宫位星曜解读\n{json.dumps(palace_kb, ensure_ascii=False)}"
    return base

def _build_sihua_user_message(plate_dict: dict) -> str:
    """四化 Agent 的 user message——只注入四化 KB"""
    base = _build_base_message(plate_dict)
    hua_kb = _load_json_kb("ziwei_hua.json")
    interact_kb = _load_json_kb("ziwei_sihua_interact.json")
    if hua_kb:
        base += f"\n## 四化对照表\n{json.dumps(hua_kb, ensure_ascii=False)}"
    if interact_kb:
        base += f"\n## 四化互涉规则\n{json.dumps(interact_kb, ensure_ascii=False)}"
    return base

def _build_palace_user_message(plate_dict: dict, bazi_ref: dict = None) -> str:
    """宫位联动 Agent 的 user message——只注入 fuzuo KB + 八字参考"""
    from app import _compute_bazi_ref  # 或有其他方式获取 bazi_ref
    base = _build_base_message(plate_dict)
    fuzuo_kb = _load_json_kb("ziwei_fuzuo.json")
    if fuzuo_kb:
        base += f"\n## 辅佐煞曜知识库\n{json.dumps(fuzuo_kb, ensure_ascii=False)}"
    if bazi_ref:
        base += f"\n## 八字参考\n{json.dumps(bazi_ref, ensure_ascii=False)}"
    return base
```

- [ ] **Step 4: 提交**

```bash
git add analysis_service.py
git commit -m "feat(backend): 多智能体编排——asyncio.gather并行3专项+合成Agent"
```

---

### Task 6: 集成验证

- [ ] **Step 1: 跑测试**

```bash
python test_ziwei.py
python app.py  # 启动
```

- [ ] **Step 2: 浏览器全流程测试**

输入命盘 → 排盘 → AI 解读 → 检查分析质量

- [ ] **Step 3: 最终推送**

```bash
git add -A && git commit -m "feat: 多智能体编排完整实现——格局/四化/宫位三并行+合成"
git push
```
