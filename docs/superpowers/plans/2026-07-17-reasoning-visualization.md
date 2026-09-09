# 推理可视化 Implementation Plan

> **状态（2026-09-09 补记）：已上线——「推理依据」段在 services prompt 组装中实装；本文 checkbox 未逐项回填，进度以 CHANGELOG 为准（2026-09-09 核对）。**

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让紫微 Agent 输出的分析文本中，每个结论附带可展开/折叠的推理路径

**Architecture:** 纯 prompt + 前端改造，不改后端。Agent prompt 新增「推理依据」输出规范，前端的 `formatCards()` 函数检测 `【推理依据】` 标记并渲染为 `<details>` 折叠卡片

**Tech Stack:** Agent prompt (markdown) + 原生 JS (前端) + CSS

## Global Constraints

- 不改 `analysis_service.py`、`app.py`、`ziwei_calculator.py` 等后端文件
- Agent 输出的原始文本作为 conversationMessages 存储，只在前端渲染时做转换
- 推理依据默认收起，用户点击展开——不打断阅读流
- 全盘解读（模式 A）和多轮追问（模式 B）均适用

---

### Task 1: Prompt — 添加「推理依据」输出规范

**Files:**
- Modify: `.claude/agents/ziwei-master.md`

**Interfaces:**
- Consumes: Agent 当前的 5 章全盘输出格式
- Produces: 新增「推理依据」标注的文本格式

- [ ] **Step 1: 在「输出模式」节中增加推理依据规范**

在 `## 输出模式（分流）` → `模式A：全盘解读` 下，每个章节的输出末尾添加：

```markdown
**推理依据规范（每个结论旁必须有可展开的推理路径）：**

每个章节中，关键结论后面紧跟一个 `【推理依据】` 段落，格式如下：

```
命宫紫微在午庙旺，三方有辅弼会照——格局方向成立，但缺吉化激活，实际助力有限。
【推理依据】
└─ 紫微在午庙旺（能量充足 90%）
└─ 左辅右弼在三方四正会照（非同事，贵人非贴身）
└─ 无化权/化科在命宫或官禄三合 → 虚格，架子在但没激活
└─ ⚠ 结论调低预期，不可过度解读君臣庆会
```

**规则：**
- `【推理依据】` 独占一行，前面是结论
- `└─ ` 开头 = 推理链的一环
- 最后一行以 `→ 结论` 或 `⚠ 风险` 结尾
- **每个 `##` 章节内至少一个推理依据段**，多则不限
- 多轮追问同样适用，但纯文本格式（不写 `└─`，用`- `替代）
```

- [ ] **Step 2: 在格式规则节增加推理依据示例**

在 `### 格式规则` 节末尾追加：

```markdown
**推理依据格式示例**（全盘模式可用）：
```
夫妻宫天相在酉，对宫破军冲照——感情中有格局但被外部力量拉扯。
【推理依据】
└─ 天相在酉亮度平（能量不足 30%）
└─ 对宫破军化禄冲照（外部诱惑/变动力强）
└─ 无吉星解救 → 感情决策易受外部影响
└─ ⚠ 建议等夫妻宫大限吉化引动再确认关系
```

多轮追问纯文本版：
```
夫妻宫天相在酉，对宫破军冲照。
- 天相在酉亮度平，能量偏弱
- 对宫破军化禄冲照，外部诱惑多
- 建议等大限吉化引动再确认
```
```

- [ ] **Step 3: 提交**

```bash
git add .claude/agents/ziwei-master.md
git commit -m "feat: prompt新增推理依据输出规范——每个结论附带可展开推理链"
```

---

### Task 2: 前端 — formatCards 支持推理依据折叠

**Files:**
- Modify: `templates/ziwei.html`（`formatCards` 函数 + CSS）

**Interfaces:**
- Consumes: Task 1 输出的带 `【推理依据】` 标记的文本
- Produces: 前端渲染为可折叠的推理卡片

- [ ] **Step 1: 在 CSS 中添加推理依据样式**

在 `templates/ziwei.html` 的 `<style>` 块末尾添加：

```css
.reasoning-details{margin:6px 0 10px 12px;padding:6px 10px 6px 14px;background:rgba(212,168,67,.04);border-left:2px solid rgba(212,168,67,.25);border-radius:4px;font-size:.82em;line-height:1.7}
.reasoning-details summary{cursor:pointer;color:var(--text-muted);font-size:.78em;font-weight:600;user-select:none;padding:2px 0}
.reasoning-details summary:hover{color:var(--accent)}
.reasoning-details .step{color:var(--text);margin:1px 0;padding:1px 0 1px 8px;border-left:1px solid rgba(212,168,67,.12)}
.reasoning-details .step .label{color:var(--text-muted);font-weight:600}
.reasoning-details .step .conclusion{color:var(--accent)}
.reasoning-details .step .risk{color:#ef5350}
```

- [ ] **Step 2: 修改 `formatCards()` 函数添加推理依据折叠**

找到 `function formatCards(t)`，在其内部 `##` 分段落逻辑之后，添加推理依据替换逻辑：

```js
function formatCards(t){
  t=t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const p=t.split(/^## /gm);
  if(p.length<2){
    // 无 ## 分段（单主题/多轮追问），直接处理推理依据
    return renderReasoning(t);
  }
  let h='';
  for(let i=1;i<p.length;i++){
    const l=p[i].split('\n');
    h+='<div class="a-card"><h2>'+l[0].trim()+'</h2><div class="body">'+
      renderReasoning(l.slice(1).join('\n'))+'</div></div>';
  }
  return h;
}

function renderReasoning(text){
  // 检测 【推理依据】 块并转折叠卡片
  const parts=text.split(/【推理依据】\n?/);
  if(parts.length<2) return text.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>');
  let r=parts[0].replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>');
  for(let i=1;i<parts.length;i++){
    // 推理依据块：提取 └─ 行
    const lines=parts[i].split('\n');
    let steps='<details class="reasoning-details"><summary>🔍 查看推理过程</summary>';
    for(const line of lines){
      const trimmed=line.trim();
      if(trimmed.startsWith('└─ ')){
        const content=trimmed.slice(3);
        let cls='step';
        if(content.startsWith('⚠ ')) cls+=' risk';
        else if(content.startsWith('→ ')) cls+=' conclusion';
        steps+='<div class="'+cls+'">'+content.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')+'</div>';
      }else if(trimmed){
        steps+='<div style="margin-top:4px;color:var(--text)">'+trimmed.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')+'</div>';
      }
    }
    steps+='</details>';
    r+=steps;
    // 处理推理依据后面可能有的剩余内容
    const idx=parts[i].indexOf('\n【');
    if(idx>0) r+=parts[i].slice(idx).replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>');
  }
  return r;
}
```

- [ ] **Step 3: 验证——本地启动 + 手动测试**

```bash
curl -s http://localhost:5000/ziwei | grep formatCards
```

确认页面加载不报错。打开浏览器确认：

1. 输入生辰排盘 → AI 解读 → 观察分析文本是否正常渲染（无推理依据时保持原样）
2. 推理依据段显示为「🔍 查看推理过程」折叠
3. 点击展开看到 `└─` 缩进链
4. 多轮追问无 `##` 时，推理依据仍正确折叠

- [ ] **Step 4: 提交**

```bash
git add templates/ziwei.html
git commit -m "feat: 推理可视化前端——formatCards支持【推理依据】折叠渲染"
```

---

### Task 3: 集成验证 + 修复

**Files:**
- （随验证结果而定）

**Interfaces:**
- Consumes: Task 1 + 2 的交付物
- Produces: 端到端验证通过的推理可视化

- [ ] **Step 1: 启动本地服务 + 浏览器测试**

```bash
python app.py
# → http://localhost:5000/ziwei
```

测试用例：
1. 2005-08-19 01:00 男 → 排盘 → AI解读 → 检查推理依据是否折叠正确
2. 追问"事业怎么样" → 检查纯文本版推理依据格式
3. 切换主题 → 检查推理依据卡片配色正常
4. 切换会话 → 恢复的分析文本推理依据是否仍可折叠

- [ ] **Step 2: 修复发现的问题**

（具体修复根据测试结果决定，预期需要微调 CSS 或 JS 边界情况）

- [ ] **Step 3: 最终提交**

```bash
git add .claude/agents/ziwei-master.md templates/ziwei.html
git commit -m "feat: 推理可视化完整实现——Agent推理链显示+前端折叠卡片"
git push
```

---

### Task 4（可选）: 应用到八字 Agent

**Files:**
- Modify: `.claude/agents/traditional-bazi-master.md`

如果紫微验证通过，八字 Agent 用同样的规范。只是改 print 规范，前端 `formatCards` 是公用的（`index.html` 中也有 `formatCards`）。

- [ ] **Step 1: 八字 prompt 添加同样推理依据规范**

```markdown
在「输出模式」节中添加同样的推理依据规范（格式同紫微）
```

- [ ] **Step 2: 验证八字分析 + 推理折叠**

```bash
# 本地测试八字分析
```
