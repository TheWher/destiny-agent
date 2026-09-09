# 均衡命局验盘命中率提升 实施计划

> **状态（2026-09-09 补记）：均衡命局验盘战役——8 任务全部 complete（.superpowers/sdd/progress.md 账本为准，commit 链 55eb133..a5b0fec）；本文 checkbox 未逐项回填，进度以 SDD 账本+CHANGELOG 为准。**

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将均衡命局（极端度≤1）验盘命中率从38%提升至55%+，通过后端注入流年干支-西历对照表 + Agent自适应降级

**Architecture:** 后端预计算逐年信号表注入user message → Agent从对照表引用年份（禁止心算）→ 有N条信号只问N条（不硬凑3条）→ 置信度标签 + 诚实告知

**Tech Stack:** Python 3.11, Flask, 纯文本Agent定义 (.md)

## Global Constraints

- 对照表格式：`20XX年（XX干支）`，西历在前、干支在后
- 信号等级：S=天克地冲, A=日柱伏吟, B=六冲日/月/年支, C=三合/六合, D=驿马/大运重现, E=墓库开闭
- 均衡命局验盘条数 = min(3, 可用信号数)，0条信号→明确拒答
- 大运状态标记：🔵当前 / ✅已走完 / ⬜未开始
- Agent禁止心算干支-西历对应，对照表缺失→降级标注
- 遵循现有梁湘润体系（调候→格局→旺衰递进链）

---

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| `analysis_service.py` | 新增 `_evaluate_liunian_signal()` + `_build_year_lookup_table()`，在 `_build_user_message()` 中插入对照表 | 修改 |
| `.claude/agents/traditional-bazi-master.md` §验盘铁律 | 均衡命局自适应降级6条硬性约束 | 修改 |
| `.claude/agents/traditional-bazi-master.md` §验证事件选取 | 更新选取规则，引用对照表 | 修改 |
| `.claude/agents/traditional-bazi-master.md` §错误模式4 | 追加模式4.1（强凑3条）+ 模式4.2（干支心算错误） | 修改 |
| `.claude/agents/traditional-bazi-master.md` §验盘策略总纲 | 追加均衡命局信号提取规则 | 修改 |
| `.claude/agents/traditional-bazi-master.md` §自检清单 | 追加均衡命局Gate Check 6项 | 修改 |
| `test_paipan.py` | 新增 `_evaluate_liunian_signal` 单元测试（S/A/B/C/D/E/—各1条） | 修改 |

---

### Task 1: 后端 — `_evaluate_liunian_signal()` 信号判定函数

**Files:**
- Modify: `analysis_service.py` — 在 `_build_user_message()` 之前新增函数
- Modify: `test_paipan.py` — 新增单元测试

**Interfaces:**
- Consumes: `liunian_ganzhi: str` (如"庚子"), `ri_ganzhi: str`, `yue_zhi: str`, `nian_zhi: str`, `dayun: list[dict]`, `year: int`
- Produces: `tuple[str|None, str|None]` — (信号等级, 说明文字)，无信号返回 (None, None)

- [ ] **Step 1: 写信号判定测试用例**

```python
# 在 test_paipan.py 末尾追加
def test_evaluate_liunian_signal():
    """验证六级流年信号判定逻辑"""
    from analysis_service import _evaluate_liunian_signal
    
    # Mock dayun: 2018-2027 戊戌
    dayun = [{'gz': '戊戌', 'gan': '戊', 'zhi': '戌', 'start_year': 2018, 'start_age': 14.0, 'end_age': 24.0, 'step': 1}]
    
    ri_ganzhi = '甲子'  # 日柱：甲子
    yue_zhi = '申'
    nian_zhi = '辰'
    
    # S级：天克地冲（庚克甲 + 午冲子）
    level, desc = _evaluate_liunian_signal('庚午', ri_ganzhi, yue_zhi, nian_zhi, dayun, 2026)
    assert level == 'S', f"Expected S, got {level}"
    assert '天克地冲' in desc
    
    # A级：日柱伏吟
    level, desc = _evaluate_liunian_signal('甲子', ri_ganzhi, yue_zhi, nian_zhi, dayun, 2020)
    assert level == 'A', f"Expected A, got {level}"
    
    # B级：冲日支
    level, desc = _evaluate_liunian_signal('丙午', ri_ganzhi, yue_zhi, nian_zhi, dayun, 2026)
    assert level == 'B', f"Expected B, got {level}"
    assert '午冲子' in desc
    
    # C级：六合日支
    level, desc = _evaluate_liunian_signal('己丑', ri_ganzhi, yue_zhi, nian_zhi, dayun, 2009)
    assert level == 'C', f"Expected C, got {level}"
    assert '丑合子' in desc or '六合' in desc
    
    # D级：驿马（日支子→驿马在寅）
    level, desc = _evaluate_liunian_signal('甲寅', ri_ganzhi, yue_zhi, nian_zhi, dayun, 2010)
    assert level == 'D', f"Expected D for 驿马, got {level}"
    
    # E级：墓库
    level, desc = _evaluate_liunian_signal('甲辰', ri_ganzhi, yue_zhi, nian_zhi, dayun, 2024)
    assert level == 'E', f"Expected E for 墓库, got {level}"
    
    # —：无信号
    level, desc = _evaluate_liunian_signal('己亥', ri_ganzhi, yue_zhi, nian_zhi, dayun, 2019)
    assert level is None, f"Expected None, got {level}"
    
    print("[PASS] test_evaluate_liunian_signal: 7/7 信号等级判定正确")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd C:\Users\A2260\Desktop\Destiny_agent && PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -c "import analysis_service; print(hasattr(analysis_service, '_evaluate_liunian_signal'))"
# 预期: False
```

- [ ] **Step 3: 实现 `_evaluate_liunian_signal()`**

在 `analysis_service.py` 的 `_build_user_message()` 函数之前（约第140行）插入：

```python
def _evaluate_liunian_signal(liunian_ganzhi, ri_ganzhi, yue_zhi, nian_zhi, dayun, year):
    """
    评估流年信号等级，返回 (等级, 说明)。
    规则与 Agent 定义六级表一致。
    """
    ri_gan = ri_ganzhi[0]
    ri_zhi = ri_ganzhi[1]
    ln_gan = liunian_ganzhi[0]
    ln_zhi = liunian_ganzhi[1]
    
    # 五行相克表
    wuxing = {'甲': '木', '乙': '木', '丙': '火', '丁': '火', '戊': '土',
              '己': '土', '庚': '金', '辛': '金', '壬': '水', '癸': '水'}
    ke_chain = {'木': '土', '土': '水', '水': '火', '火': '金', '金': '木'}
    
    # 地支六冲
    chong_pairs = {('子', '午'), ('丑', '未'), ('寅', '申'), ('卯', '酉'),
                   ('辰', '戌'), ('巳', '亥')}
    
    # S级：天克地冲（流年与日柱同时干克+支冲）
    gan_ke = ke_chain.get(wuxing.get(ln_gan, ''), '') == wuxing.get(ri_gan, '')
    zhi_chong = (ln_zhi, ri_zhi) in chong_pairs or (ri_zhi, ln_zhi) in chong_pairs
    if gan_ke and zhi_chong:
        return ('S', f'天克地冲日柱（{liunian_ganzhi} vs {ri_ganzhi}）')
    
    # A级：日柱伏吟
    if liunian_ganzhi == ri_ganzhi:
        return ('A', '日柱伏吟')
    
    # B级：六冲日/月/年支
    for label, target_zhi in [('日支', ri_zhi), ('月支', yue_zhi), ('年支', nian_zhi)]:
        if (ln_zhi, target_zhi) in chong_pairs or (target_zhi, ln_zhi) in chong_pairs:
            return ('B', f'冲{label}（{ln_zhi}冲{target_zhi}）')
    
    # C级：三合/六合日支/月支
    sanhe_trios = [('申', '子', '辰'), ('亥', '卯', '未'), ('寅', '午', '戌'), ('巳', '酉', '丑')]
    liuhe = {('子', '丑'), ('寅', '亥'), ('卯', '戌'), ('辰', '酉'), ('巳', '申'), ('午', '未')}
    for label, target in [('日支', ri_zhi), ('月支', yue_zhi)]:
        for trio in sanhe_trios:
            if ln_zhi in trio and target in trio:
                return ('C', f'三合{label}（{ln_zhi}入{""}{trio}{""}局）')
        if (ln_zhi, target) in liuhe or (target, ln_zhi) in liuhe:
            return ('C', f'六合{label}（{ln_zhi}合{target}）')
    
    # D级：驿马/大运重现
    yima_map = {'申': '寅', '子': '寅', '辰': '寅', '寅': '申', '午': '申', '戌': '申',
                '巳': '亥', '酉': '亥', '丑': '亥', '亥': '巳', '卯': '巳', '未': '巳'}
    if yima_map.get(ri_zhi) == ln_zhi:
        for d in dayun:
            if d['start_year'] <= year <= d['start_year'] + 9:
                dz_zhi = d['zhi']
                if (ln_zhi, dz_zhi) in chong_pairs or (dz_zhi, ln_zhi) in chong_pairs:
                    return ('D', '驿马到位（流年冲大运驿马）')
        return ('D', '驿马到位')
    
    for d in dayun:
        if d['start_year'] <= year <= d['start_year'] + 9 and liunian_ganzhi == d['gz']:
            return ('D', '大运干支重现')
    
    # E级：墓库开闭
    muku = {'辰', '戌', '丑', '未'}
    if ln_zhi in muku and (ln_zhi == ri_zhi or (ln_zhi, ri_zhi) in chong_pairs or (ri_zhi, ln_zhi) in chong_pairs):
        return ('E', '墓库引动')
    
    return (None, None)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd C:\Users\A2260\Desktop\Destiny_agent && PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -c "
from analysis_service import _evaluate_liunian_signal
# 快速冒烟
dayun = [{'gz': '戊戌', 'gan': '戊', 'zhi': '戌', 'start_year': 2018, 'start_age': 14.0, 'end_age': 24.0, 'step': 1}]
assert _evaluate_liunian_signal('庚午', '甲子', '申', '辰', dayun, 2026)[0] == 'S'
assert _evaluate_liunian_signal('甲子', '甲子', '申', '辰', dayun, 2020)[0] == 'A'
assert _evaluate_liunian_signal('丙午', '甲子', '申', '辰', dayun, 2026)[0] == 'B'
assert _evaluate_liunian_signal('己亥', '甲子', '申', '辰', dayun, 2019)[0] is None
print('ALL PASS')
"
```

- [ ] **Step 5: 提交**

```bash
cd C:\Users\A2260\Desktop\Destiny_agent
git add analysis_service.py test_paipan.py
git commit -m "feat: _evaluate_liunian_signal 六级流年信号判定函数"
```

---

### Task 2: 后端 — `_build_year_lookup_table()` 对照表生成

**Files:**
- Modify: `analysis_service.py` — 在 `_evaluate_liunian_signal()` 之后新增函数

**Interfaces:**
- Consumes: `plate: BaziPlate`（需 `.birth_dt.year`, `.sizhu`, `.dayun` 属性）, `current_year: int`
- Produces: `str` — 完整 Markdown 对照表（逐年全量，含信号标记+大运状态）

- [ ] **Step 1: 写对照表格式测试**

```python
# 在 test_paipan.py 末尾追加
def test_build_year_lookup_table():
    """验证对照表生成格式"""
    from analysis_service import _build_year_lookup_table
    from bazi_calculator import paipan
    
    plate = paipan(2005, 8, 19, 1, 35, '男', 113.75, '东莞')
    table = _build_year_lookup_table(plate, 2010)
    
    # 格式检查
    assert '## 流年干支-西历对照表' in table, '缺少标题'
    assert '出生年：2005年' in table, '缺少出生年'
    assert '日柱：' in table, '缺少日柱'
    assert '| 年份 | 干支 | 所属大运 | 信号等级 | 信号说明 |' in table, '缺少表头'
    assert '2005' in table, '缺少出生年行'
    assert '2010' in table, '缺少当前年行'
    assert '🔵当前' in table, '缺少当前大运标记'
    
    # 逐年行数 = (2010 - 2005 + 1) + 表头2行 + section header等
    lines = table.strip().split('\n')
    data_lines = [l for l in lines if l.startswith('| 20')]
    assert len(data_lines) == 6, f'预期6年数据行，实际{len(data_lines)}'
    
    # 格式：20XX年（干支）
    assert '2005年（乙酉）' in table, '缺少出生年对照'
    
    print("[PASS] test_build_year_lookup_table: 对照表格式正确")
```

- [ ] **Step 2: 实现 `_build_year_lookup_table()`**

在 `analysis_service.py` 中 `_evaluate_liunian_signal()` 之后插入：

```python
def _build_year_lookup_table(plate, current_year):
    """生成 流年干支-西历对照表（均衡命局验盘专用）"""
    birth_year = plate.birth_dt.year
    sizhu = plate.sizhu  # (年柱, 月柱, 日柱, 时柱)
    ri_ganzhi = sizhu[2]
    yue_zhi = sizhu[1][1]
    nian_zhi = sizhu[0][1]
    dayun = plate.dayun  # list[dict] with gz/gan/zhi/start_year
    
    tian_gan = '甲乙丙丁戊己庚辛壬癸'
    di_zhi = '子丑寅卯辰巳午未申酉戌亥'
    
    lines = []
    lines.append('## 流年干支-西历对照表')
    lines.append('')
    lines.append(f'出生年：{birth_year}年 → 当前年：{current_year}年')
    lines.append(f'日柱：{ri_ganzhi}')
    lines.append('')
    lines.append('### 逐年流年信号')
    lines.append('')
    lines.append('| 年份 | 干支 | 所属大运 | 信号等级 | 信号说明 |')
    lines.append('|------|------|----------|----------|----------|')
    
    for year in range(birth_year, current_year + 1):
        stem_idx = (year - 4) % 10
        branch_idx = (year - 4) % 12
        ganzhi = tian_gan[stem_idx] + di_zhi[branch_idx]
        
        # 找该年所属大运 + 状态
        dayun_label = '—'
        for d in dayun:
            start_y = d['start_year']
            end_y = start_y + 9
            if start_y <= year <= end_y:
                if current_year > end_y:
                    status = '✅'
                elif current_year < start_y:
                    status = '⬜'
                else:
                    status = '🔵当前'
                dayun_label = f"{d['gz']}({start_y}-{end_y}) {status}"
                break
        
        # 评估信号等级
        signal_level, signal_desc = _evaluate_liunian_signal(
            ganzhi, ri_ganzhi, yue_zhi, nian_zhi, dayun, year
        )
        
        level_str = signal_level if signal_level else '—'
        desc_str = signal_desc if signal_desc else '—'
        lines.append(f'| {year}年（{ganzhi}） | {ganzhi} | {dayun_label} | {level_str} | {desc_str} |')
    
    return '\n'.join(lines)
```

- [ ] **Step 3: 运行测试确认通过**

```bash
cd C:\Users\A2260\Desktop\Destiny_agent && PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -c "
from analysis_service import _build_year_lookup_table
from bazi_calculator import paipan
plate = paipan(2005, 8, 19, 1, 35, '男', 113.75, '东莞')
t = _build_year_lookup_table(plate, 2010)
print(t)
print('---')
print(f'行数: {len(t.split(chr(10)))}')
"
```

- [ ] **Step 4: 提交**

```bash
cd C:\Users\A2260\Desktop\Destiny_agent
git add analysis_service.py test_paipan.py
git commit -m "feat: _build_year_lookup_table 流年干支-西历对照表生成"
```

---

### Task 3: 后端 — 对照表注入 `_build_user_message()`

**Files:**
- Modify: `analysis_service.py:143` — 在排盘数据与分析要求之间插入对照表调用

**Interfaces:**
- Consumes: `_build_year_lookup_table(plate, current_year)` from Task 2
- Produces: 修改后的 user message 字符串，含对照表 section

- [ ] **Step 1: 定位插入点**

当前 `_build_user_message()` 结构：
```python
# ~Line 143: def _build_user_message(plate_dict):
#   ... 构建 user_msg_parts ...
#   user_msg_parts.append(plate_markdown)     # 排盘数据
#   user_msg_parts.append(analysis_requirements)  # 分析要求
#   return "\n\n".join(user_msg_parts)
```

需在 `plate_markdown` 之后、`analysis_requirements` 之前插入对照表。

- [ ] **Step 2: 插入对照表调用**

在 `_build_user_message()` 中，`plate_markdown` 相关行之后（约第200行），添加：

```python
    # 流年干支-西历对照表（均衡命局验盘专用——Agent禁止心算，必须从此表引用）
    from datetime import datetime
    current_year = datetime.now().year
    lookup_table = _build_year_lookup_table(plate, current_year)
    user_msg_parts.append(lookup_table)
```

- [ ] **Step 3: 验证注入**

```bash
cd C:\Users\A2260\Desktop\Destiny_agent && PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -c "
from analysis_service import _build_user_message
from app import plate_to_dict
from bazi_calculator import paipan
plate = paipan(2005, 8, 19, 1, 35, '男', 113.75, '东莞')
d = plate_to_dict(plate)
msg = _build_user_message(d)
assert '## 流年干支-西历对照表' in msg, '对照表未注入user message'
assert '2005年（乙酉）' in msg, '缺少出生年对照'
assert '日柱' in msg, '缺少日柱信息'
print('对照表注入验证通过')
print(f'User message总长度: {len(msg)} 字符')
"
```

- [ ] **Step 4: 运行全部测试确保不破坏现有功能**

```bash
cd C:\Users\A2260\Desktop\Destiny_agent && PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python test_paipan.py
# 预期: 24/24 全通过
```

- [ ] **Step 5: 提交**

```bash
cd C:\Users\A2260\Desktop\Destiny_agent
git add analysis_service.py
git commit -m "feat: _build_user_message 注入流年干支-西历对照表"
```

---

### Task 4: Agent定义 — 验盘铁律追加（自适应降级6条）

**Files:**
- Modify: `.claude/agents/traditional-bazi-master.md:27` — 在现有验盘铁律后追加

- [ ] **Step 1: 追加自适应降级规则**

在第27行（现有均衡命局验盘铁律）之后插入：

```markdown

**均衡命局验盘自适应降级**（硬性约束，违反即输出格式错误）：

1. **验盘条数 = min(3, 可用信号数)**。可用信号 = 【流年干支-西历对照表】中标记 S/A/B/C/D/E 的年份数（同一信号源不重复计数）。出生年当年和当前年（未走完）不计入可用信号
2. 可用信号 ≥3 → 3条 | 2 → 2条 | 1 → 1条 | 0 → 输出 `【无法确定——命局信号过弱，排盘引擎无可识别强流年信号】` 并跳过验盘，直接进入批断阶段
3. 每条预测行首必须标置信度标签：`【🔴高置信】`(S/A级) | `【🟡中置信】`(B/C级) | `【🔵低置信】`(D/E/大运交接)
4. 信号数 < 3 时，验盘结束后追加诚实告知：
   > "此命局均衡温和，排盘引擎可识别的强信号仅 N 条。以上预测基于这些信号的确定性分析——少的可靠信号好过凑数的猜测。若验证不准确，可能是时辰偏差或夏令时问题，建议确认出生时间精确度。"
5. **凡时间型断言中出现干支-西历对应关系，必须能在【流年干支-西历对照表】中找到完全一致的条目。找不到时输出 `【无法确定——对照表未覆盖】`，禁止心算补全。**
6. **若【流年干支-西历对照表】整个section未出现（后端注入失败），该命例所有时间型预测降级为 `【🔵低置信】`，且每条必须标注 `【干支-西历未确认——对照表缺失】`。**
```

编辑方式：在 `**⚠️ 验盘铁律（最高优先级，覆盖所有其他规则）**：` 段落结束后的空行（第28行）处插入上述文本。

- [ ] **Step 2: 提交**

```bash
cd C:\Users\A2260\Desktop\Destiny_agent
git add .claude/agents/traditional-bazi-master.md
git commit -m "feat(agent): 均衡命局验盘自适应降级6条硬性约束"
```

---

### Task 5: Agent定义 — 验证事件选取规则更新

**Files:**
- Modify: `.claude/agents/traditional-bazi-master.md:1062` — 更新选取原则

- [ ] **Step 1: 更新选取规则**

在第1062行"选取原则"之后、第1064行"针对命主当前年龄段"之前，插入：

```markdown
- **均衡命局（极端度≤1）专用选取规则**：从【流年干支-西历对照表】中提取所有标记 S/A/B/C/D/E 的年份，按信号等级排序。S/A 级优先选取，同等级取最近年份（用户更容易回忆近期事件）。选取数量遵循自适应降级规则（Task 4规则1）。极端命局（极端度≥2）仍使用原有选取逻辑
- **对照表年份引用格式**：`20XX年（XX干支）`——西历在前、干支在后。禁止仅写干支不写西历
```

- [ ] **Step 2: 提交**

```bash
cd C:\Users\A2260\Desktop\Destiny_agent
git add .claude/agents/traditional-bazi-master.md
git commit -m "feat(agent): 均衡命局验证事件选取规则——引用对照表"
```

---

### Task 6: Agent定义 — 错误模式追加（4.1 + 4.2）

**Files:**
- Modify: `.claude/agents/traditional-bazi-master.md:1265` — 在模式4末尾追加

- [ ] **Step 1: 追加两个新错误模式**

在第1265行（`**硬性规则**：如果命局极端度 < 2...`）之后插入：

```markdown

**模式 4.1：均衡命局强凑3条（2026-06-24 新增）**

❌ **错误**：命局极端度=1，对照表仅有1个B级信号（午冲子），但Agent编造了2条"XX年前后可能有重大变化"的模糊预测凑数。

✅ **修正**：只输出1条，标 `【🔴高置信】`，验盘后诚实告知"此命局仅识别到1个强信号"。**1条确认的预测比3条瞎猜的价值高得多。**

**模式 4.2：干支-西历对应心算错误（2026-06-24 新增）**

❌ **错误**：Agent输出"2016年丙申年，那年..."——干支对应来自Agent"心算"（即使恰好正确也不行），用户无法验证引用来源。

✅ **修正**：所有干支-西历对应必须从【流年干支-西历对照表】引用。对照表中未覆盖的年份 → 输出 `【无法确定——对照表未覆盖】`。**即使Agent"知道"某年的干支，也不允许绕过对照表直接输出。** 对照表是唯一的权威来源（single source of truth）。
```

- [ ] **Step 2: 提交**

```bash
cd C:\Users\A2260\Desktop\Destiny_agent
git add .claude/agents/traditional-bazi-master.md
git commit -m "feat(agent): 错误模式4.1-4.2——强凑3条+干支心算防御"
```

---

### Task 7: Agent定义 — 验盘策略总纲 + 自检清单更新

**Files:**
- Modify: `.claude/agents/traditional-bazi-master.md:1353` — 在策略分流表后追加信号提取规则
- Modify: `.claude/agents/traditional-bazi-master.md:1453` — 在现有自检清单后追加Gate Check

**Interfaces:**
- Uses信号提取规则 from Task 4 (references lookup table)
- Uses Gate Check from Task 4 rule definitions

- [ ] **Step 1: 追加均衡命局信号提取规则**

在第1353行（策略分流表 `| 均衡命局...` 行结束）之后插入：

```markdown

**均衡命局验盘可用信号提取**：验盘开始时，从【流年干支-西历对照表】中提取所有信号等级为 S/A/B/C/D/E 的年份行。排除出生年当年（用户不可能记得）和当前年（未走完不可验证）。将提取结果按信号等级排序（S>A>B>C>D>E），同等级按年份倒序（最近优先）。以此列表作为验盘选年的权威来源——不允许在此列表之外自行判断"某年应该也有信号"。
```

- [ ] **Step 2: 追加均衡命局 Gate Check**

在第1453行（`- [ ] "先苦后甜"、"大器晚成"...`）之后插入：

```markdown
- [ ] **均衡命局 Gate Check**（极端度≤1时，验盘输出前逐条检查）：
  - [ ] 验盘条数 ≤ 对照表中可用信号数？
  - [ ] 每条预测是否从对照表引用年份（`20XX年（干支）`格式），而非心算？
  - [ ] 每条是否标了置信度标签（🔴/🟡/🔵）？
  - [ ] 信号数 < 3 时，是否有诚实告知段？
  - [ ] 对照表缺失时，是否降级为 🔵低置信 + 标注 `【干支-西历未确认——对照表缺失】`？
  - [ ] 每条预测中的干支-西历对应，是否能在对照表中找到完全一致的条目？
```

- [ ] **Step 3: 提交**

```bash
cd C:\Users\A2260\Desktop\Destiny_agent
git add .claude/agents/traditional-bazi-master.md
git commit -m "feat(agent): 均衡命局信号提取规则+Gate Check"
```

---

### Task 8: 最终验证

**Files:**
- 验证: `test_paipan.py` 全量运行
- 验证: 端到端 user message 格式检查
- 验证: Agent 定义文件完整性

- [ ] **Step 1: 运行全量测试**

```bash
cd C:\Users\A2260\Desktop\Destiny_agent
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python test_paipan.py
# 预期: 24/24 + 2新增测试 = 全部通过
```

- [ ] **Step 2: 端到端验证 user message 包含对照表**

```bash
cd C:\Users\A2260\Desktop\Destiny_agent
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -c "
from analysis_service import _build_user_message
from app import plate_to_dict
from bazi_calculator import paipan

# 测试50岁命主——逐年全量的极端场景
import datetime
plate = paipan(1976, 3, 15, 8, 0, '男', 116.4, '北京')
d = plate_to_dict(plate)
msg = _build_user_message(d)

# 验证对照表存在且格式正确
assert '## 流年干支-西历对照表' in msg
assert '1976年（丙辰）' in msg
assert str(datetime.datetime.now().year) + '年' in msg

# 验证关键信号标记
assert '信号等级' in msg
assert '信号说明' in msg

# 检查逐年全量行数
born = 1976
current = datetime.datetime.now().year
expected_years = current - born + 1
data_lines = [l for l in msg.split('\n') if l.startswith('| ' + str(born)) or (l.startswith('| 19') or l.startswith('| 20'))]
print(f'逐年数据行数: {len(data_lines)} (预期{expected_years})')
print('端到端验证通过 ✅')
"
```

- [ ] **Step 3: 验证 Agent 定义文件无语法损坏**

```bash
cd C:\Users\A2260\Desktop\Destiny_agent
# 检查改动后的Agent定义行数
wc -l .claude/agents/traditional-bazi-master.md
# 检查所有改动区间是否完整
grep -n "均衡命局验盘自适应降级\|模式 4.1\|模式 4.2\|均衡命局验盘可用信号提取\|均衡命局 Gate Check" .claude/agents/traditional-bazi-master.md
```

- [ ] **Step 4: 提交 + 推送**

```bash
cd C:\Users\A2260\Desktop\Destiny_agent
git add -A
git status
# 确认只有预期文件被修改
git commit -m "feat: 均衡命局验盘命中率提升——对照表注入+自适应降级"
git push origin master
```

---

## 自审清单

- [x] Spec覆盖：对照表生成(§4)→Task 1-2, 对照表注入(§4.2)→Task 3, Agent铁律(§3.1)→Task 4, 选取规则(§3.4)→Task 5, 错误模式(§3.3)→Task 6, 策略总纲+Gate Check(§3.5)→Task 7, 最终验证(§5)→Task 8
- [x] 无占位符：所有代码完整，所有命令可执行
- [x] 类型一致性：`_evaluate_liunian_signal`返回`(str|None, str|None)`，Task 2的`_build_year_lookup_table`正确消费此类型
- [x] 数据结构一致：`plate.dayun`使用dict访问（`d['gz']`, `d['start_year']`等），与`bazi_calculator.py:609`定义一致
