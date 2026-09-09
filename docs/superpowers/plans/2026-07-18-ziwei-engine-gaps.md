# 紫微引擎缺口补齐 Implementation Plan

> **状态（2026-09-09 补记）：已上线——来因宫/格局 breaking/流年流曜等引擎缺口已补（见 docs/ziwei-mutual-verification.md 各 TODO 结账段）；checkbox 未逐项回填，进度以 CHANGELOG 为准。**

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 纯 Python 实现宫干飞四化、大限活盘、流月流日三项计算，注入 _build_ziwei_user_message

**Architecture:** 三个函数放 `ziwei_calculator.py`，在 `_build_ziwei_user_message()` 中调用并注入 user message 末尾。不改前端、不改 prompt。

**Tech Stack:** Python, GAN_SIHUA 对照表, 十二宫索引

## Global Constraints

- 所有计算纯 Python，不依赖引擎/外部库
- 结果注入 user message，Agent 看到数据自行使用
- 不改前端、不改 API 路由、不改 prompt 文件
- 测试：50/50 ziwei test pass

---

### Task 1: 宫干飞四化函数

**Files:**
- Modify: `ziwei_calculator.py`（末尾追加新函数）
- Modify: `analysis_service.py`（`_build_ziwei_user_message` 中调用注入）

- [ ] **Step 1: 在 `ziwei_calculator.py` 追加 `compute_palace_flying()`**

```python
# ═══ 宫干飞四化计算 ═══
def compute_palace_flying(plate_dict: dict) -> list[dict]:
    """计算十二宫天干飞四化
    
    每宫天干 → GAN_SIHUA → 四颗星 → 查找该星在哪个宫 → 化入→冲对宫
    
    Returns:
        [{from, stem, flying:{禄:{star,to,冲},权:{...},科:{...},忌:{...}}, key}]
    """
    GAN_SIHUA = {
        '甲': {'禄':'廉贞','权':'破军','科':'武曲','忌':'太阳'},
        '乙': {'禄':'天机','权':'天梁','科':'紫微','忌':'太阴'},
        '丙': {'禄':'天同','权':'天机','科':'文昌','忌':'廉贞'},
        '丁': {'禄':'太阴','权':'天同','科':'天机','忌':'巨门'},
        '戊': {'禄':'贪狼','权':'太阴','科':'右弼','忌':'天机'},
        '己': {'禄':'武曲','权':'贪狼','科':'天梁','忌':'文曲'},
        '庚': {'禄':'太阳','权':'武曲','科':'太阴','忌':'天同'},
        '辛': {'禄':'巨门','权':'太阳','科':'文曲','忌':'文昌'},
        '壬': {'禄':'天梁','权':'紫微','科':'左辅','忌':'武曲'},
        '癸': {'禄':'破军','权':'巨门','科':'太阴','忌':'贪狼'},
    }
    BRANCH_ORDER = '子丑寅卯辰巳午未申酉戌亥'
    palaces = plate_dict.get('palaces', [])
    if not palaces:
        return []
    
    # 星曜→所在宫位 查找表
    star_to_palace = {}
    for p in palaces:
        for s in p.get('major_stars', []) + p.get('minor_stars', []):
            star_to_palace[s['name']] = p
    
    # 宫位名→地支索引
    name_to_branch = {}
    for p in palaces:
        br = p.get('earthly_branch', '')
        idx = BRANCH_ORDER.find(br)
        if idx >= 0:
            name_to_branch[p['name']] = idx
    
    result = []
    for p in palaces:
        stem = p.get('heavenly_stem', '')
        if not stem or stem not in GAN_SIHUA:
            continue
        sihua = GAN_SIHUA[stem]
        flying = {}
        for hua_type_short, star_name in sihua.items():
            target = star_to_palace.get(star_name)
            if target:
                to_name = target['name']
                to_idx = name_to_branch.get(to_name, -1)
                chong_br = BRANCH_ORDER[(to_idx + 6) % 12] if to_idx >= 0 else ''
                chong_name = ''
                for pp in palaces:
                    if pp.get('earthly_branch') == chong_br:
                        chong_name = pp['name']
                        break
                flying[hua_type_short] = {'star': star_name, 'to': to_name, '冲': chong_name}
            else:
                flying[hua_type_short] = {'star': star_name, 'to': None, '冲': None}
        
        jiji = flying.get('忌', {})
        key = f"{p['name']}化忌入{jiji.get('to','?')}冲{jiji.get('冲','?')}" if jiji.get('to') else None
        result.append({'from': p['name'], 'stem': stem, 'flying': flying, 'key': key})
    
    return result
```

- [ ] **Step 2: 在 `analysis_service.py` 的 `_build_ziwei_user_message()` 中调用并注入**

在古籍引用之前（约 line 1376 之前），追加：

```python
    # ═══ 宫干飞四化注入 ═══
    from ziwei_calculator import compute_palace_flying
    palace_flying = compute_palace_flying(plate_dict)
    if palace_flying:
        parts.append("## 宫干飞四化参考")
        for item in palace_flying[:6]:  # 取前6条，避免token膨胀
            fly = item['flying']
            lu = fly.get('禄', {}); quan = fly.get('权', {}); ke = fly.get('科', {}); ji = fly.get('忌', {})
            parts.append(f"- {item['from']}({item['stem']})：{lu['star']}禄→{lu.get('to','?')} / {quan['star']}权→{quan.get('to','?')} / {ke['star']}科→{ke.get('to','?')} / {ji['star']}忌→{ji.get('to','?')}冲{ji.get('冲','?')}")
        parts.append("")
```

- [ ] **Step 3: 验证**

```bash
python -c "
from ziwei_calculator import ziwei_paipan, plate_to_dict, compute_palace_flying
r = ziwei_paipan(2005,8,19,1,gender='男')
pd = plate_to_dict(r, {})
res = compute_palace_flying(pd)
assert len(res) == 12, f'Expected 12, got {len(res)}'
# 验证命宫癸 → 破军禄在父母宫
for item in res:
    if item['from'] == '命宮':
        assert item['flying']['禄']['star'] == '破军'
        assert item['flying']['禄']['to'] == '父母'
        print('✅ 命宫癸飞四化验证通过')
print(f'✅ {len(res)} 条宫干飞四化全正确')
"
```

- [ ] **Step 4: 提交**

```bash
git add ziwei_calculator.py analysis_service.py
git commit -m "feat: 宫干飞四化计算——12宫天干飞化+化忌冲宫"
```

---

### Task 2: 大限活盘函数

**Files:**
- Modify: `ziwei_calculator.py`
- Modify: `analysis_service.py`（追加注入）

- [ ] **Step 1: 在 `ziwei_calculator.py` 追加 `compute_decadal_living()`**

```python
# ═══ 大限活盘计算 ═══
def compute_decadal_living(plate_dict: dict, current_age: int) -> dict | None:
    """计算大限活盘：以当前大限宫位为限年命宫，十二宫名称逆时针旋转
    
    Returns:
        {decade_palace, decade_range, living:{命宫→本命XX, 兄弟→本命XX, ...}}
    """
    palaces = plate_dict.get('palaces', [])
    if not palaces:
        return None
    
    # 找当前年龄对应的大限宫位
    decade_palace = None
    for p in palaces:
        dr = p.get('decadal_range', '')
        if '-' in dr:
            try:
                start, end = int(dr.split('-')[0]), int(dr.split('-')[1])
                if start <= current_age <= end:
                    decade_palace = p
                    break
            except (ValueError, IndexError):
                continue
    
    if not decade_palace:
        return None
    
    PALACE_NAMES = ['命宫','兄弟','夫妻','子女','财帛','疾厄','迁移','交友','官禄','田宅','福德','父母']
    idx = decade_palace.get('index', 0)
    living = {}
    for i, name in enumerate(PALACE_NAMES):
        pidx = (idx + i) % 12
        living[name] = palaces[pidx]['name']
    
    return {
        'decade_palace': decade_palace['name'],
        'decade_range': decade_palace.get('decadal_range', ''),
        'living': living,
    }
```

- [ ] **Step 2: 在 `_build_ziwei_user_message()` 中注入**

```python
    # ═══ 大限活盘注入 ═══
    from ziwei_calculator import compute_decadal_living
    living = compute_decadal_living(plate_dict, current_year - birth_year)
    if living:
        parts.append("## 大限活盘参考")
        parts.append(f"当前走{living['decade_palace']}宫大限（{living['decade_range']}岁）：")
        for limit_name, orig_name in living['living'].items():
            parts.append(f"- 限年{limit_name} ← 本命{orig_name}")
        parts.append("")
```

注意：`birth_year` 需要从 `plate_dict['input']` 解析。

- [ ] **Step 3: 验证**

```bash
python -c "
from ziwei_calculator import ziwei_paipan, plate_to_dict, compute_decadal_living
r = ziwei_paipan(2005,8,19,1,gender='男')
pd = plate_to_dict(r, {})
res = compute_decadal_living(pd, 21)  # 13-22大限
assert res is not None
assert res['decade_palace'] == '兄弟'
assert res['living']['命宫'] == '兄弟'
print(f'✅ 大限活盘：{res[\"decade_palace\"]}宫为命宫')
print(f'   限年命宫→本命{res[\"living\"][\"命宫\"]}')
"
```

- [ ] **Step 4: 提交**

```bash
git add ziwei_calculator.py analysis_service.py
git commit -m "feat: 大限活盘计算——限年命宫+十二宫名称旋转"
```

---

### Task 3: 流月流日函数 + 注入

**Files:**
- Modify: `ziwei_calculator.py`
- Modify: `analysis_service.py`

- [ ] **Step 1: 在 `ziwei_calculator.py` 追加 `compute_flow_month()`**

```python
# ═══ 流月命宫计算 ═══
def compute_flow_month(plate_dict: dict, birth_month_lunar: int, birth_hour: int, target_year: int) -> dict | None:
    """计算指定年份的流月命宫（斗君）
    
    算法：流年地支宫起正月 → 逆数到农历生月 → 顺数到生时 → 定斗君
    
    Args:
        birth_month_lunar: 农历出生月份（1-12）
        birth_hour: 0-23
        target_year: 目标流年
    
    Returns:
        {doujun:正月命宫, flow_months:{1月:XX宫, 2月:XX宫, ...}}
    """
    palaces = plate_dict.get('palaces', [])
    if not palaces:
        return None
    
    BRANCH_ORDER = '子丑寅卯辰巳午未申酉戌亥'
    liunian_zhi_idx = (target_year - 4) % 12  # 流年地支索引
    
    # 逆数到农历生月
    month_idx = (liunian_zhi_idx - (birth_month_lunar - 1)) % 12
    
    # 顺数到生时
    shichen_idx = (birth_hour + 1) // 2 % 12
    doujun_idx = (month_idx + shichen_idx) % 12
    
    flow_months = {}
    for m in range(1, 13):
        idx = (doujun_idx + m - 1) % 12
        flow_months[f"{m}月"] = palaces[idx]['name']
    
    return {
        'doujun': palaces[doujun_idx]['name'],
        'flow_months': flow_months,
    }
```

- [ ] **Step 2: 注入 user message**

```python
    # ═══ 流月参考注入 ═══
    from ziwei_calculator import compute_flow_month
    flow_m = compute_flow_month(plate_dict, birth_month_lunar, birth_hour, current_year)
    if flow_m:
        parts.append("## 流月参考（当年）")
        parts.append(f"斗君（正月命宫）：{flow_m['doujun']}")
        months_str = ' | '.join([f"{k}:{v}" for k, v in flow_m['flow_months'].items()])
        parts.append(months_str)
        parts.append("")
```

- [ ] **Step 3: 验证**

```bash
python -c "
from ziwei_calculator import ziwei_paipan, plate_to_dict, compute_flow_month
r = ziwei_paipan(2005,8,19,1,gender='男')
pd = plate_to_dict(r, {})
# 2005年8月19日01:00 → 农历七月（假设），丑时
res = compute_flow_month(pd, 7, 1, 2026)
assert res is not None
print(f'✅ 流月：正月命宫={res[\"doujun\"]}')
for k, v in list(res['flow_months'].items())[:3]:
    print(f'  {k}: {v}')
"
```

- [ ] **Step 4: 提交**

```bash
git add ziwei_calculator.py analysis_service.py
git commit -m "feat: 流月命宫计算——斗君+12月命宫"
```

---

### Task 4: 集成验证

- [ ] **Step 1: 跑测试**

```bash
python test_ziwei.py
# Expected: 50/50
```

- [ ] **Step 2: 验证注入效果**

```bash
python -c "
from ziwei_calculator import ziwei_paipan, plate_to_dict
from analysis_service import _build_ziwei_user_message
r = ziwei_paipan(2005,8,19,1,gender='男')
pd = plate_to_dict(r, {'birth_datetime':'2005-08-19 01:00','gender':'男'})
msg = _build_ziwei_user_message(pd)
for keyword in ['宫干飞四化', '大限活盘', '流月']:
    if keyword in msg:
        print(f'✅ {keyword} 注入成功')
    else:
        print(f'⚠️ {keyword} 未注入')
"
```

- [ ] **Step 3: 最终推送**

```bash
git add -A && git commit -m "feat: 引擎缺口补齐——宫干飞四化+大限活盘+流月"
git push
```
