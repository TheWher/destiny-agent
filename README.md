<div align="center">

# 🏯 八字 & 紫微 · AI 命理分析

**符号计算 + LLM 推理的混合 AI 架构 · 双术数系统**

🔗 **体验地址：[https://thewher.pythonanywhere.com](https://thewher.pythonanywhere.com)**

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-black?logo=flask)](https://flask.palletsprojects.com/)
[![DeepSeek](https://img.shields.io/badge/AI-DeepSeek%20v4--pro-purple)](https://deepseek.com)
[![iztro-py](https://img.shields.io/badge/紫微-iztro--py-7c4dff)](https://pypi.org/project/iztro-py/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Deploy](https://img.shields.io/badge/Deploy-PythonAnywhere-orange)](https://thewher.pythonanywhere.com)

</div>

---

## ✨ 亮点

<table>
<tr>
<td width="50%">

### 🔮 精准排盘
- sxtwl C++ 库 + Meeus 天文算法双引擎
- 真太阳时自动校正 · 250+ 城市经纬度库
- 四柱/大运/十神/神煞/空亡/藏干 一键计算
- iztro-py 紫微引擎 · 14 主星亮度全量修正

### 🧠 AI 深度分析
- **八字**：梁湘润体系 9 级递进推理链 · 42 核心概念 · 13 条盲测错误模式
- **紫微**：10 步强制推理链 · 四层四化权重（15 条互涉）· 24 格局三列核验 · 破格五层穿透
- **交叉验证**：紫微分析自动排八字盘 + 调八字 Agent 独立分析，结论注入紫微 Prompt
- 双 Agent 定义文件：八字 120KB + 紫微 48KB

</td>
<td width="50%">

### 🎯 验盘闭环
- **八字**：双模式分流（极端冲合信号 → 100% / 均衡大运主题确认 → 71%）
- **紫微**：6 级信号优先级表（S~E）· stop_sequences 截停 · 逐条用户确认面板
- 反馈保存 → 聚合分析脚本 → 错误模式发现 → Prompt 注入迭代
- 反馈带盘指纹 + 错误原因标签 + 来源标记 · 假阳性/假阴性分化统计

### 📊 可视化 & 交互
- 五行环图 / 十二长生轮盘 / 大运环图
- 紫微十二宫 Grid：楷体主星 + 四化色块 + 杂曜全量 + 长生角标
- 三合四正连线（hover 高亮）· 飞星标记 · 流曜渲染
- 三层叠盘（大限+流年+流月可叠加）· 叠盘 AI 分析
- SSE 流式解读 · 水墨宣纸风 · 暗色主题
- 会话磁盘持久化 + 历史会话管理（重命名/删除/切换器）
- 复制链接跨设备查看

</td>
</tr>
</table>

---

## ⚡ 快速开始

```bash
pip install -r requirements.txt
python app.py          # → http://localhost:5000
```

配置 API Key（三选一：环境变量 / `~/.claude/settings.json` / `config.local.py`）：

```python
# config.local.py（不提交 Git）
API_CONFIG = {
    "base_url": "https://api.deepseek.com/anthropic",
    "model": "deepseek-v4-pro",
    "api_key": "sk-...",
}
WEB_PASSWORD = "your-password"    # 可选，保护深度分析
ADMIN_TOKEN = "your-admin-token"  # 可选，保护反馈报告端点
```

```bash
# 测试
python test_paipan.py --smoke      # 八字冒烟测试
python test_paipan.py              # 24 条全量
python test_ziwei.py               # 紫微测试
python scripts/evaluate_ziwei_verify.py  # 验盘反馈聚合（默认写 data/reports/report_cache.json）
```

---

## 🏗️ 架构

```
app.py (20 行入口)
  └── routes/          # Flask 蓝图 — 页面 + API
  │   ├── pages.py      # 页面路由（/ /app /ziwei /report …）
  │   ├── bazi.py       # 八字 API（/api/paipan /api/analyze …）
  │   ├── ziwei.py      # 紫微 API（/api/ziwei/*）
  │   └── charts.py     # 图表 API（/api/chart/*）
  └── services/        # 业务逻辑 — LLM 分析管道
  │   ├── llm_client.py      # API 调用 + 三层 Key 回退 + SSE 流式
  │   ├── kb_loader.py       # 知识库加载 + 五行常量
  │   ├── bazi_analysis.py   # 八字分析全管道
  │   └── ziwei_analysis.py  # 紫微分析全管道（含验盘）
  └── utils/           # 工具函数
      ├── auth.py       # 密码保护 + 限流
      ├── cache.py      # 分析结果缓存
      ├── feedback.py   # 反馈日志保存
      ├── geo.py        # 地理编码
      └── plate.py      # 命盘序列化
```

| 层 | 技术 |
|:---:|---|
| **后端** | `Flask 3.1` · `requests` · `zhdate` · `iztro-py` |
| **前端** | 原生 JS · 零框架 · CSS Variables 水墨设计系统 · 桌面分栏 · 移动端自适应 |
| **AI** | `DeepSeek v4-pro` · Anthropic 兼容端点 · stop_sequences 截停 |
| **排盘** | sxtwl C++ (八字) · Meeus 回退 · iztro-py (紫微) |
| **流式** | SSE (Server-Sent Events) · ReadableStream |
| **部署** | PythonAnywhere · Render 备用 |

---

## 🚀 生产切换 embedding 检索后端

知识库检索器支持双后端（`KB_BACKEND=lexical|embedding`），生产已切 embedding（粒度收益：
平均返回 2.4KB→331B，token 省 ~86%）。切换三步：

1. **下载模型**：`python scripts/fetch_embedding_model.py`（从 ModelScope 拉取 bge-small-zh-v1.5 到 `models/`，
   幂等可重复执行；HuggingFace 直连在国内网络极慢，勿用）
2. **设置环境变量**（PythonAnywhere 面板 → Web → 环境变量）：
   - `KB_BACKEND=embedding`
   - `KB_EMBEDDING_MODEL=<项目路径>/models/bge-small-zh-v1.5`
   - `KB_EMBEDDING_MIN_SCORE=0.55`（阈值标定：0.60 完美分界但余量仅 0.02，0.55 留安全垫，误杀优先于假阳性）
3. **升级套餐**：PythonAnywhere Developer 档（$10/mo，免费档 1 个月过期且单 worker/休眠不适合生产）

**降级兜底**：embedding 模型加载失败（缺失/损坏/依赖不全）自动降级 lexical 并打印
`[kb_embedding] WARN`，不挂服务。部署后留意日志，出现 WARN 说明模型路径/文件有问题。

**生产档回归**（动 knowledge_base 数据后必跑）：
```bash
KB_BACKEND=embedding KB_EMBEDDING_MIN_SCORE=0.55 python evaluation_sets/dry_run_check.py
# 预期：run=87 passed=87，文件级 0，平均 ~300B；同时重跑 threshold_eval.py 看 0.60 分界是否漂移
```

---

## 📡 API

### 八字

| 路由 | 方法 | 说明 |
|------|:---:|------|
| `/api/paipan` | POST | 排盘 |
| `/api/analyze` | POST | AI 深度分析（验盘阶段） |
| `/api/analyze/stream` | POST | 三通道 SSE 流式验盘 |
| `/api/analyze/continue` | POST | 多轮对话续接 |
| `/api/analyze/stream/continue` | POST | 三通道 SSE 流式续接 |
| `/api/chart/wuxing` | POST | 五行环图 SVG |
| `/api/chart/changsheng` | POST | 十二长生轮盘 SVG |
| `/api/chart/dayun` | POST | 大运时间轴 SVG |
| `/api/chart/dayun-ring` | POST | 大运环图 SVG |
| `/api/geocode?q=` | GET | 地名 → 经纬度 |
| `/api/cities?q=` | GET | 城市模糊搜索 |
| `/api/glossary/lookup?term=` | GET | 术语词典 |
| `/api/verify` | POST | 验盘反馈保存 |
| `/api/pdf` | POST | PDF 报告 |

### 紫微

| 路由 | 方法 | 说明 |
|------|:---:|------|
| `/api/ziwei/paipan` | POST | 紫微排盘 |
| `/api/ziwei/analyze` | POST | 深度分析（含验盘截停） |
| `/api/ziwei/analyze/stream` | POST | SSE 流式解读 |
| `/api/ziwei/analyze/continue` | POST | 多轮对话续接 |
| `/api/ziwei/analyze/yearly` | POST | 流年聚焦解读 |
| `/api/ziwei/horoscope` | POST | 流年盘 + 流曜计算 |
| `/api/ziwei/sessions` | GET/POST | 会话列表 / 创建 |
| `/api/ziwei/sessions/<id>` | GET/PUT/PATCH/DELETE | 会话 CRUD |
| `/api/auth/register` | POST | 注册（返回 JWT） |
| `/api/auth/login` | POST | 登录（返回 JWT） |
| `/api/auth/me` | GET | 获取当前用户信息 |
| `/api/ziwei/verify` | POST | 验盘反馈保存 |
| `/api/ziwei/feedback/report` | GET | 聚合报告（ADMIN_TOKEN 保护） |

---

## 📈 验盘性能

### 八字（16 人盲测）

```
极端命局（spread ≥ 3）：  100% (6/6)
略偏命局（spread = 2）：   78% (7/9)
均衡命局（spread ≤ 2）：   71% (5/7)
时间型预测：              92%
特征型预测：              38%
```

### 紫微（验盘闭环已就绪，等待反馈积累）

- 6 级信号优先级表（S ±1年 ~ E ±3年）
- stop_sequences 截停 + 用户逐条确认面板
- 反馈 JSON 含盘指纹 + 错误原因标签 + 来源标记
- `scripts/evaluate_ziwei_verify.py` 聚合分析：命中率/信号等级/领域/错误成本矩阵

---

## 📄 许可证

MIT © TheWher
