# 紫微报告页 Implementation Plan

> **状态（2026-09-09 补记）：已上线——templates/ziwei-report.html 实装（含验盘系统 ziwei-verify.js）；checkbox 未逐项回填，进度以 CHANGELOG 为准（2026-09-09 核对）。**

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将紫微斗数拆分为表单页和报告页。表单页只负责输入+会话选择，报告页输出水墨风十二宫Grid+命盘概览+分析+追问

**Architecture:** 新路由 `/ziwei/report/<session_id>` + 新模板 `ziwei-report.html` + session 存储 `plate_data`。表单页 `/ziwei` 简化去掉 SVG 渲染。报告页从 session 恢复 plate_data 渲染宫格，SSE 流式加载分析文本。

---

### Task 1: backend — session 存储 plate_data + PATCH 支持

**Files:**
- Modify: `app.py`（`_ziwei_sessions` 存储改 schema + 追加 messages 支持）

- [ ] **Step 1: session 结构加 plate_data 字段**

```python
# app.py 约 line 863
_ziwei_sessions[sid] = {
    "id": sid,
    "title": data.get("title", ""),
    "messages": data.get("messages", []),
    "plate_data": data.get("plate_data", {}),  # NEW
    "plate_summary": data.get("plate_summary", ""),
    "created_at": datetime.now().isoformat(),
}
```

修改 `api_ziwei_session()` PUT 分支：读取 `data.get("messages")` 和 `data.get("plate_data")` 都更新。

- [ ] **Step 2: 新增 GET 单条 session 返回完整 plate_data**

确保 `api_ziwei_session()` GET 分支返回 `plate_data` 字段。

- [ ] **Step 3: 新增路由 `/ziwei/report/<sid>`**

```python
@app.route("/ziwei/report/<sid>")
def ziwei_report(sid):
    """水墨风格紫微命盘报告页"""
    return render_template("ziwei-report.html")
```

---

### Task 2: 新建 `templates/ziwei-report.html`

**Files:**
- Create: `templates/ziwei-report.html`

**Interfaces:**
- Consumes: `session_id` from URL → JS 拉 `/api/ziwei/sessions/{sid}` → 拿到 `plate_data` + `messages`
- Produces: 完整报告页

- [ ] **Step 1: 页面骨架 + CSS**

基于 bazi-ziwei-skill 的水墨纸风格（`#f5f1e8` paper, vermillion, jade, ink），构建：

```
┌─ 页面结构 ─────────────────────────────────────┐
│  ┌─ 命盘概要栏 ─────────────────────────────┐  │
│  │ 生辰/五行局/命主/身主/来因宫/生年四化    │  │
│  └──────────────────────────────────────────┘  │
│  ┌─ 4x4 十二宫 Grid ───────────────────────┐  │
│  │ 巳  午  未  申                          │  │
│  │ 辰  center  酉                          │  │
│  │ 卯  寅  丑  亥                          │  │
│  └──────────────────────────────────────────┘  │
│  ┌─ 大运条 ────────────────────────────────┐  │
│  │ 3-12 13-22 23-32 33-42 ...              │  │
│  └──────────────────────────────────────────┘  │
│  ┌─ 分析文本 ─────────────────────────────┐  │
│  │ ...streaming typing effect...            │  │
│  └──────────────────────────────────────────┘  │
│  ┌─ 追问区 ────────────────────────────────┐  │
│  │ [________________________] [发送]       │  │
│  └──────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

CSS 要点：
- :root 水墨色板（paper/ink/vermillion/jade/azure）
- 4x4 CSS Grid（grid-template-columns: repeat(4, 1fr)，高 540px）
- center-palace 占 2×2
- 命宫 vermillion 边框，身宫 inline badge
- 四化颜色标志
- 打印样式 `@media print`

- [ ] **Step 2: JS 拉数据 + 渲染宫格**

```javascript
const sid = window.location.pathname.split('/').pop();
const res = await fetch(`/api/ziwei/sessions/${sid}`);
const session = await res.json();
const plate = session.plate_data;
const palaces = plate.palaces;

// 渲染 4x4 grid
const GRID = {巳:[0,0],午:[1,0],未:[2,0],申:[3,0],辰:[0,1],酉:[3,1],
              卯:[0,2],戌:[3,2],寅:[0,3],丑:[1,3],子:[2,3],亥:[3,3]};
```

渲染逻辑：遍历 palaces → 按 earthly_branch 定位到 GRID → 填充 HTML。

- [ ] **Step 3: 命盘概要栏**

从 plate 提取：`five_elements_class`、`soul_palace`、`body_palace`、生年四化。

- [ ] **Step 4: 大运条**

遍历 palaces，提取 `decadal_range` 和 `decadal_dizhi`，渲染为水平条。
当前年龄高亮。

- [ ] **Step 5: 分析文本区 + SSE 流式**

分析文本区兼容两种模式：
1. 已有分析（session.messages 中有 assistant 回复）→ 直接渲染
2. 无分析 → 自动调 `/api/ziwei/analyze/stream`，SSE 逐段写入（打字机效果）

流式节流：`requestAnimationFrame`，不每字更新。

- [ ] **Step 6: 追问区 + 对话历史**

追问框 + 历史对话渲染（复用当前 ziwei.html 中的 sendChat 逻辑）。
追问完成后追加到 session.messages 并 PATCH 回后端。

- [ ] **Step 7: 宫格交互（点击星曜弹窗）**

每个 cell 的星曜绑定 onclick → showStarDetail，弹窗也包水墨风格。

- [ ] **Step 8: 打印样式**

```css
@media print {
  .no-print { display: none; }
  .report { max-width: 100%; box-shadow: none; border: none; }
  .palace { break-inside: avoid; }
  body { background: white; padding: 0; }
}
```

- [ ] **Step 9: 响应式**

Phone: 宫格缩小至屏幕宽度，分析文本字体调小，追问框全宽。

---

### Task 3: 简化表单页

**Files:**
- Modify: `templates/ziwei.html`

- [ ] **Step 1: 移除 chart-section 中的宫格渲染**

删掉 `renderChart()`、`selectPalace()`、`showStarDetail()` 等 SVG 渲染函数。
保留：表单、生辰输入、排盘按钮、会话列表。

- [ ] **Step 2: 排盘后不再在当前页渲染宫格**

排盘成功后直接 `saveSession()` → 跳转 `/ziwei/report/{session_id}`。

- [ ] **Step 3: 分析按钮改为"生成报告"**

点击 → 调 analyze → saveSession → 跳转报告页。

- [ ] **Step 4: 会话列表点击跳转**

点击历史会话 → `/ziwei/report/{id}`。

---

### Task 4: 集成验证

- [ ] **Step 1: 跑测试**

```bash
python test_ziwei.py  # 50/50
```

- [ ] **Step 2: 全流程测试**

表单页填生辰 → 排盘 → 生成报告 → 跳转报告页 → 宫格渲染正确 → 分析流式加载 → 追问 → 刷新不丢数据 → 打印样式正确

- [ ] **Step 3: 提交推送**
