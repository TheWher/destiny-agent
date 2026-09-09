# 多体系交叉：八字→紫微 Implementation Plan

> **状态（2026-09-09 补记）：已上线——ziwei_analysis 八字交叉参考段实装；checkbox 未逐项回填，进度以 CHANGELOG 为准（2026-09-09 核对）。**

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 紫微 AI 解读时，后端自动调用八字排盘，将日主/喜用/强弱注入 user message，实现交叉引用

**Architecture:** `/api/ziwei/analyze` 中从 `plate_dict['input']['birth_datetime']` 解析生辰，调 `bazi_calculator.paipan()` 算出 `bazi_ref` dict，传给 `analyze_ziwei()` → `_build_ziwei_user_message()` 注入格式化文本

**Tech Stack:** Python, Flask, bazi_calculator, analysis_service

## Global Constraints

- `gender` 缺失或为空 → 不排八字，不注入
- `birth_datetime` 不可 parse → 不排八字，不注入
- paipan 异常 → logging.warning 记录，不中断流程
- `plate_dict['input']['birth_datetime']` 是 ziwei_paipan 返回时写入的字符串，格式 `"2005-08-19 01:00"`，已是公历

---

### Task 1: app.py — 在 analyze 端点中生成 bazi_ref

**Files:**
- Modify: `app.py:745-790`（`api_ziwei_analyze`）和 `app.py:792-820`（`api_ziwei_analyze_stream`）

**Interfaces:**
- Consumes: `plate_dict['input']['birth_datetime']` + `plate_dict['input']['gender']`
- Produces: `bazi_ref` dict → 传给 `analyze_ziwei(plate_dict, timeout=600, bazi_ref=bazi_ref)`

- [ ] **Step 1: 在 `api_ziwei_analyze()` 中，调 `analyze_ziwei` 之前插入 bazi_ref 生成逻辑**

位置：`api_ziwei_analyze()` 函数内，`plate_dict = data["plate"]` 之后、调用 `analyze_ziwei` 之前：

```python
# ═══ 八字参考：自动排盘用于交叉验证 ═══
bazi_ref = None
input_info = plate_dict.get("input", {})
birth_dt_str = input_info.get("birth_datetime", "")
gender = input_info.get("gender", "")
if birth_dt_str and gender in ("男", "女"):
    import re
    m = re.match(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})", birth_dt_str)
    if m:
        try:
            from bazi_calculator import paipan
            y, mo, d, h, mi = int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5])
            bp = paipan(y, mo, d, h, mi, gender=gender, apply_solar_correction=False)
            dayun_str = ""
            if getattr(bp, "dayun", []):
                du = bp.dayun[0]
                dayun_str = f"{du['gz']}（{du['start_age']}-{du['end_age']}岁）"
            bazi_ref = {
                "rizhu": bp.sizhu["day"]["gz"],
                "ri_gan_wuxing": bp.sizhu["day"]["gan_wuxing"],
                "strength": "身强" if getattr(bp, "shenqiang", False) else "身弱",
                "xiyong": getattr(bp, "xiyong", [])[:3],
                "geju": getattr(bp, "geju", ""),
                "dayun": dayun_str,
            }
        except Exception as e:
            import logging
            logging.warning(f"bazi_ref generation failed: {e}")
```

然后将调用改为：

```python
result = analyze_ziwei(plate_dict, timeout=600, bazi_ref=bazi_ref)
```

- [ ] **Step 2: 在 `api_ziwei_analyze_stream()` 中做同样的修改**

找到 SSE 流式端点中对 `analyze_ziwei` 的调用（约 line 800），插入同样逻辑。

- [ ] **Step 3: 提交**

```bash
git add app.py
git commit -m "feat: 紫微分析时自动计算八字参考——提取日主/喜用/强弱注入bazi_ref"
```

---

### Task 2: analysis_service.py — bazi_ref 参数传递 + 注入 user message

**Files:**
- Modify: `analysis_service.py`（`analyze_ziwei` 和 `_build_ziwei_user_message`）

**Interfaces:**
- Consumes: `bazi_ref` dict from Task 1
- Produces: user message 末尾的「八字参考」段

- [ ] **Step 1: 修改 `analyze_ziwei()` 函数签名，接收 bazi_ref**

```python
def analyze_ziwei(plate_dict: dict, timeout: int = 120, bazi_ref: dict = None) -> dict:
    ...
    user_message = _build_ziwei_user_message(plate_dict, bazi_ref=bazi_ref)
```

- [ ] **Step 2: 修改 `_build_ziwei_user_message()` 函数，注入八字参考**

```python
def _build_ziwei_user_message(plate_dict: dict, bazi_ref: dict = None) -> str:
    ...
    # 在古籍引用之后、分析要求之前
    if bazi_ref:
        parts.append("")
        parts.append("## 八字参考（用于交叉验证）")
        parts.append(f"日主：{bazi_ref.get('rizhu', '?')}（{bazi_ref.get('ri_gan_wuxing', '?')}，{bazi_ref.get('strength', '?')}）")
        if bazi_ref.get('xiyong'):
            parts.append(f"喜用：{'、'.join(bazi_ref['xiyong'])}")
        if bazi_ref.get('geju'):
            parts.append(f"格局：{bazi_ref['geju']}")
        if bazi_ref.get('dayun'):
            parts.append(f"当前大运：{bazi_ref['dayun']}")
```

- [ ] **Step 3: 验证——跑测试**

```bash
python test_ziwei.py
python test_paipan.py --smoke
```

Expected: 50/50 + 5/5 passed

- [ ] **Step 4: 手动验证注入效果**

```bash
python -c "
from ziwei_calculator import ziwei_paipan, plate_to_dict
from analysis_service import _build_ziwei_user_message
r = ziwei_paipan(2005,8,19,1,gender='男')
pd = plate_to_dict(r, {'birth_datetime':'2005-08-19 01:00','gender':'男'})
msg = _build_ziwei_user_message(pd, bazi_ref={
    'rizhu':'乙酉','ri_gan_wuxing':'木','strength':'身弱',
    'xiyong':['火','土'],'geju':'七杀格','dayun':'辛巳(3-12岁)'
})
if '八字参考' in msg:
    print('✅ 注入成功')
else:
    print('❌ 注入失败')
"
```

Expected: `✅ 注入成功`

- [ ] **Step 5: 提交**

```bash
git add analysis_service.py
git commit -m "feat: 八字参考段注入紫微user message——analyze_ziwei接收bazi_ref参数"
```

---

### Task 3: 集成验证

- [ ] **Step 1: 启动本地服务，完整走一遍**

```bash
python app.py
# → http://localhost:5000/ziwei
# 输入生辰 → 排盘 → AI 解读
# 检查分析文本中是否出现类似「八字参考：乙酉日主，木，身弱…」的描述
```

- [ ] **Step 2: 验证错误降级**

```bash
python -c "
from analysis_service import _build_ziwei_user_message
# bazi_ref=None → 不注入，不报错
msg = _build_ziwei_user_message({'palaces':[]}, bazi_ref=None)
assert '八字参考' not in msg
print('✅ 降级正确')
# bazi_ref={} → 也正常
msg2 = _build_ziwei_user_message({'palaces':[]}, bazi_ref={})
print('✅ 空dict不报错')
"
```

- [ ] **Step 3: 最终推送**

```bash
git add -A
git commit -m "feat: 多体系交叉——八字→紫微自动注入(日主/喜用/强弱)"
git push
```
