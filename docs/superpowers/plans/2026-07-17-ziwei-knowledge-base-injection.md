# 紫微知识库注入 Implementation Plan

> **状态（2026-09-09 补记）：已上线——kb_inject.join_classics_str 同源注入实装（2026-09-09 起 str 出口亦真伪分层）；checkbox 未逐项回填，进度以 CHANGELOG 为准。**

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将中州派辅佐煞曜讲义注入知识库，实现选择性注入+ KB 引用规则

**Architecture:** 新建 `ziwei_fuzuo.json`（14 星×分宫+组合规则），改造 `_build_ziwei_user_message()` 按命盘实际星曜选择性注入（带优先级排序），prompt 新增强制引用规则

**Tech Stack:** JSON 知识库 + Python + Agent prompt

## Global Constraints

- KB 分宫键名用中文宫名（命宮/兄弟/夫妻/子女/財帛/疾厄/迁移/交友/官祿/田宅/福德/父母），与 `pal['name']` 一致
- 组合规则注入前需 `_match_combo()` 检查当前命盘是否满足触发条件
- 最多注入 6 条，按优先级降序：命宫身宫(3) > 关键宫位+组合(2) > 其他(1)
- 命盘 `minor_stars` 为空时，"中州派辅佐煞曜参考"段完全省略
- 不改前端、不改 API 路由、不改现有 KB 文件

---

### Task 1: 新建 `knowledge_base/ziwei_fuzuo.json`

**Files:**
- Create: `knowledge_base/ziwei_fuzuo.json`

**Interfaces:**
- Consumes: 中州派辅佐煞曜讲义原文（已从 ab.newdu.com 抓取）
- Produces: 结构化 JSON，含 14 星×分宫 + 组合规则

- [ ] **Step 1: 创建文件骨架**

```json
{
  "_description": "中州派辅佐煞曜详解——14星×分宫+组合规则",
  "_source": "王亭之《中州派紫微斗数深造讲义·辅佐煞曜篇》",
  "天魁": { "五行": "阳火", "总论": "...", "分宫": {}, "组合": {} },
  "天钺": { "五行": "阴火", "总论": "...", "分宫": {}, "组合": {} },
  "左辅": { "五行": "阳土", "总论": "...", "分宫": {}, "组合": {} },
  "右弼": { "五行": "阴水", "总论": "...", "分宫": {}, "组合": {} },
  "文昌": { "五行": "阳金", "总论": "...", "分宫": {}, "组合": {} },
  "文曲": { "五行": "阴水", "总论": "...", "分宫": {}, "组合": {} },
  "禄存": { "五行": "阴土", "总论": "...", "分宫": {}, "组合": {} },
  "天马": { "五行": "阳火", "总论": "...", "分宫": {}, "组合": {} },
  "擎羊": { "五行": "阳金带阳火", "总论": "...", "分宫": {}, "组合": {} },
  "陀罗": { "五行": "阴金带阴火", "总论": "...", "分宫": {}, "组合": {} },
  "火星": { "五行": "阳火", "总论": "...", "分宫": {}, "组合": {} },
  "铃星": { "五行": "阴火", "总论": "...", "分宫": {}, "组合": {} },
  "地空": { "五行": "阴火", "总论": "...", "分宫": {}, "组合": {} },
  "地劫": { "五行": "阳火", "总论": "...", "分宫": {}, "组合": {} }
}
```

- [ ] **Step 2: 填入辅曜（天魁、天钺、左辅、右弼）分宫与组合**

从讲义原文提取：
- 天魁：分宫取有独特含义的（命宫/父母/田宅/福德/夫妻/疾厄）+ 组合（坐贵向贵、魁钺夹命、魁钺分坐命身宫、魁钺与昌曲凑会、魁钺与羊陀凑会）
- 天钺：同天魁结构，补充单星胡涂桃花规则
- 左辅：分宫取命宫/兄弟/夫妻/子女/财帛/迁移/交友/官禄/父母 + 组合（辅弼夹丑未、辅弼辰戌对拱、辅弼夹紫破/天府/日月、单星+廉贞化忌+擎羊）
- 右弼：同左辅结构，补充单星结合火铃/羊陀起障碍的规则

- [ ] **Step 3: 填入佐曜（文昌、文曲、禄存、天马）分宫与组合**

从讲义原文提取：
- 文昌/文曲：分宫取有独特含义的 + 组合（昌曲夹命、昌曲夹夫妻宫、昌曲对拱、昌曲化忌→文书失误、疾厄宫见昌曲化忌）
- 禄存：分宫 + 组合（羊陀夹、禄存被破、禄存与化禄暗合、双禄交流）
- 天马：分宫 + 组合（禄马交驰、迭禄迭马、天马与陀罗、天马与空曜）

- [ ] **Step 4: 填入六煞（擎羊、陀罗、火星、铃星、地空、地劫）分宫与组合**

从讲义原文提取。无独特含义的宫位用 `"—"` 标记。

- [ ] **Step 5: 验证 JSON 格式**

```bash
python -c "import json; d=json.load(open('knowledge_base/ziwei_fuzuo.json','r',encoding='utf-8')); print(f'OK: {len(d)} top keys'); assert len(d) == 16"
```

Expected: `OK: 16 top keys`（含 _description 和 _source）

- [ ] **Step 6: 提交**

```bash
git add knowledge_base/ziwei_fuzuo.json
git commit -m "feat(kb): 新建中州派辅佐煞曜知识库——14星×分宫+组合规则"
```

---

### Task 2: Prompt 新增 KB 引用规则

**Files:**
- Modify: `.claude/agents/ziwei-master.md`

- [ ] **Step 1: 在六煞分析模板后追加 KB 引用规则**

找到 `**六煞分析模板**（每颗煞星必须按此格式）：` 行，在其下方追加：

```markdown
**知识库引用规则（硬性）**：
- 所有辅星/煞星的分析结论必须引用 `ziwei_fuzuo.json` 原文
- 输出格式：「XX 星在 XX 宫：中州派云'原文摘要'→结合本命盘表现为 XXX」
- 禁止笼统说"煞星不好"/"辅星加分"而不给出依据
```

- [ ] **Step 2: 在禁忌中追加 KB 引用禁令**

找到 `## 禁忌` 节，追加一行：

```
- 不凭训练记忆分析辅星/煞星——必须引用知识库原文（ziwei_fuzuo.json）
```

- [ ] **Step 3: 提交**

```bash
git add .claude/agents/ziwei-master.md
git commit -m "feat(prompt): 新增知识库引用规则——辅星煞星分析必须引用原文"
```

---

### Task 3: 后端选择性注入逻辑

**Files:**
- Modify: `analysis_service.py`（`_build_ziwei_user_message()` 函数）

**Interfaces:**
- Consumes: `_load_json_kb("ziwei_fuzuo.json")` 加载 KB（复用已有缓存模式）
- Produces: 在当前 user message 中插入"中州派辅佐煞曜参考"段

- [ ] **Step 1: 在 `_build_ziwei_user_message()` 中，古籍引用之前插入注入逻辑**

找到 `_build_ziwei_user_message()` 函数末尾的古籍引用部分，在此之前插入：

```python
# ═══ 中州派辅佐煞曜选择性注入 ═══
fuzuo_kb = _load_json_kb("ziwei_fuzuo.json")
if fuzuo_kb:
    relevant_entries = []  # (priority, text)
    BRANCH_ORDER = '子丑寅卯辰巳午未申酉戌亥'
    
    for pal in plate_dict.get('palaces', []):
        pname = pal.get('name', '')
        tags = pal.get('tags', [])
        
        # 优先级：命宫身宫3 > 关键宫位+组合规则2 > 其他1
        if '命宫' in tags: pri = 3
        elif '身宫' in tags: pri = 3
        elif pname in ('迁移','夫妻','財帛','官祿','疾厄'): pri = 2
        else: pri = 1
        
        for s in pal.get('minor_stars', []):
            name = s.get('name', '')
            if name not in fuzuo_kb: continue
            star_data = fuzuo_kb[name]
            
            # 分宫条目
            if '分宫' in star_data and pname in star_data['分宫']:
                entry = star_data['分宫'][pname]
                if entry and entry != '—':
                    relevant_entries.append((pri, f"- {name}在{pname}：{entry}"))
            
            # 组合规则——需匹配当前命盘才注入
            if '组合' in star_data:
                for combo_key, combo_desc in star_data['组合'].items():
                    if _match_combo(combo_key, pal, plate_dict, fuzuo_kb, BRANCH_ORDER):
                        relevant_entries.append((2, f"- 组合：{combo_key}——{combo_desc}"))
    
    # 按优先级降序，取前 6 条
    relevant_entries.sort(key=lambda x: -x[0])
    top = [text for _, text in relevant_entries[:6]]
    
    if top:
        parts.append("\n## 中州派辅佐煞曜参考（按命盘实际星曜引用）")
        parts.extend(top)
```

- [ ] **Step 2: 在 `_build_ziwei_user_message()` 函数外新增 `_match_combo()` 辅助函数**

```python
def _match_combo(combo_key: str, pal: dict, plate_dict: dict, fuzuo_kb: dict, branch_order: str) -> bool:
    """检查组合规则是否匹配当前命盘"""
    # 建立 branch→palace 快速查找表
    branch_to_pal = {p['earthly_branch']: p for p in plate_dict.get('palaces', [])}
    
    # 夹宫类：如"辅弼夹丑未"
    if '夹' in combo_key:
        br = pal.get('earthly_branch', '')
        idx = branch_order.find(br)
        if idx < 0: return False
        prev_br = branch_order[(idx - 1) % 12]
        next_br = branch_order[(idx + 1) % 12]
        # 前后宫存在于盘中即视为可能被夹，注入以作参考
        return prev_br in branch_to_pal and next_br in branch_to_pal
    
    # 对拱/对星类
    if '对拱' in combo_key or '对星' in combo_key:
        return True
    
    # 单星类
    if '单星' in combo_key:
        has_peer = len(pal.get('minor_stars', [])) > 1
        return not has_peer
    
    return True
```

- [ ] **Step 3: 验证——运行测试和手动检查**

```bash
python test_ziwei.py
```

Expected: 50/50 pass

手动检查注入效果：

```bash
python -c "
from ziwei_calculator import ziwei_paipan, plate_to_dict
from analysis_service import _build_ziwei_user_message
r = ziwei_paipan(2005, 8, 19, 1, gender='男')
pd = plate_to_dict(r, {})
msg = _build_ziwei_user_message(pd)
if '中州派辅佐煞曜参考' in msg:
    print('✅ 注入成功')
    # 打印注入段落
    lines = msg.split('\\n')
    in_section = False
    for l in lines:
        if '中州派辅佐煞曜参考' in l: in_section = True
        if in_section:
            print(l)
            if l.strip() == '' and in_section: break
else:
    print('⚠️ 未注入（可能是 minor_stars 为空）')
"
```

- [ ] **Step 4: 边界测试——无辅星命盘**

```bash
# 找一个 minor_stars 全空的命盘测试
# 如果不方便找，可直接 mock plate_dict
python -c "
from analysis_service import _build_ziwei_user_message
msg = _build_ziwei_user_message({'palaces': []})
assert '中州派辅佐煞曜参考' not in msg
print('✅ 空命盘不注入')
"
```

- [ ] **Step 5: 提交**

```bash
git add analysis_service.py
git commit -m "feat(backend): 辅佐煞曜选择性注入——按命盘实际星曜+优先级排序+组合匹配"
```

---

### Task 4: 集成验证

- [ ] **Step 1: 启动本地服务 + 测试全流程**

```bash
python app.py
# → http://localhost:5000
# 输入 2005-08-19 01:00 男 → 排盘 → AI 解读
```

- [ ] **Step 2: 检查分析文本是否出现\"中州派辅佐煞曜参考\"段**

应包含辅星原文引用，如"火星在官祿：中州派云…→结合本命盘…"

- [ ] **Step 3: 最终提交 + 推送**

```bash
git add -A
git push origin master
```
