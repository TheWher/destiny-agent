<div align="center">

# 🏯 八字 & 紫微 · AI 命理分析

**符号计算 + LLM 推理的混合 AI 架构 · 双术数系统**

🔗 **体验地址：[https://thewher.pythonanywhere.com](https://thewher.pythonanywhere.com)**

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-black?logo=flask)](https://flask.palletsprojects.com/)
[![AI](https://img.shields.io/badge/AI-GLM--5.3%20%7C%20DeepSeek-5b6ee1)](https://open.bigmodel.cn)
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
- **双盘互证**：紫微分析自动排八字盘 + 独立八字预分析，结论交叉比对注入，报告页亮互证徽章
- 双 Agent 定义文件：八字 120KB + 紫微 48KB

</td>
<td width="50%">

### 🎯 验盘闭环
- **八字**：双模式分流（极端冲合信号 → 100% / 均衡大运主题确认 → 71%）
- **紫微**：6 级信号优先级表（S~E）· stop_sequences 截停 · 逐条用户确认面板
- 反馈保存 → 聚合分析脚本 → 错误模式发现 → Prompt 注入迭代
- 反馈带盘指纹 + 错误原因标签 + 来源标记 · 假阳性/假阴性分化统计

### 🛡️ 可信度设计（差异化核心）
- **双盘互证**：每次紫微解读后台自动排八字盘并独立预分析，结论交叉比对注入——报告页亮 🧭 双盘互证版徽章
- **断语古籍核验**：引用按「原文 / 转述」分级标注，出处与知识库同源 join，假出处从结构上杜绝；语料含《紫微斗数全书》明刻本数据层 10.2 万字（识典官方数据）+ 207 篇整理库
- **干支铁律**：前端/服务层禁止按公式自算干支，一律引擎注入（立春/农历双口径分治），机检尺守护清零判据
- **来因宫（钦天派）**：锚位表 + 盘面映射，双锚校验尺断言锁定
- **格局核验**：引擎判定 + 破格/受损/常见误解显式标注（✅⚠️❌），词典与引擎双写对齐

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
# config.local.py（不提交 Git）—— 任何 Anthropic 兼容端点均可
API_CONFIG = {
    "base_url": "https://open.bigmodel.cn/api/anthropic",  # 智谱 GLM（当前线上）
    "model": "GLM-5.3",
    "api_key": "your-key",
}
# DeepSeek 同样可用：base_url=https://api.deepseek.com/anthropic, model=deepseek-v4-pro
WEB_PASSWORD = "your-password"    # 可选，保护深度分析
ADMIN_TOKEN = "your-admin-token"  # 可选，保护反馈报告端点
JWT_SECRET = "random-64-hex"      # 可选；不设则自动生成持久化随机密钥（data/jwt_secret.key）
```

```bash
# 测试（pytest 常驻回归，当前基线 159 绿）
python -m pytest -q

# 机检尺（口径/纪律守护，改对应层后必跑）
python scripts/check_ganzhi.py            # 干支自算清零判据（前端/服务层禁自算，一律引擎注入）
python scripts/verify_laiyin_anchors.py   # 来因宫双锚校验尺
python scripts/verify_geju_mingzhu.py     # 日月系格局口径尺（6 盘 19 断言）

# 验盘反馈聚合
python scripts/evaluate_ziwei_verify.py  # 默认写 data/reports/report_cache.json
```

---

## 🚀 部署（PythonAnywhere）

- 仓库路径 `~/destiny-agent`；`config.local.py` 不走 Git，需手动上传到项目根（与 `app.py` 同级）
- 重启唯一可靠方式：Web 面板 **Disable → 等 3 秒 → Enable**（Reload 不够）
- 依赖用 `requirements-prod.txt`（免费档 ~6MB；**勿装 sentence-transformers**，会拉 500MB torch 超配额）
- 静态资源版本号取 git 短哈希自动破缓存；`/` 为落地页，应用在 `/app` 与 `/ziwei`
- 详细清单见 [DEPLOY_CHECKLIST.md](DEPLOY_CHECKLIST.md)

---

## 🏗️ 架构

```
app.py (20 行入口)
  └── routes/              # Flask 蓝图 — 只做请求-响应
  │   ├── pages.py          # 页面路由（/ 落地页 · /app 八字 · /ziwei 紫微 · /ziwei/report/<sid> 分享报告）
  │   ├── bazi.py           # 八字 API
  │   ├── ziwei.py          # 紫微 API（含 share/ 会话快照）
  │   ├── auth.py           # 注册/登录（JWT）+ 管理后台
  │   ├── payment.py        # 订单/邀请码开 Pro
  │   ├── events.py         # 埋点
  │   └── charts.py         # 图表 API
  └── services/            # 业务逻辑
  │   ├── orchestrator.py    # Tool/Capability/Skill 编排 + Function Calling 循环
  │   ├── plugin_manager.py  # 插件六态生命周期 + 沙箱
  │   ├── llm_client.py      # LLM 调用（Anthropic 兼容端点可换）+ 兜底轮 + SSE
  │   ├── kb_loader.py       # 知识库检索（lexical/embedding 双后端）
  │   ├── kb_inject.py       # 注入层：出处同源 join，假出处结构上杜绝
  │   ├── bazi_analysis.py   # 八字分析全管道（含验盘/信号对照）
  │   └── ziwei_analysis.py  # 紫微分析全管道（含验盘/修正循环）
  └── models/user.py       # SQLite：用户/订单/埋点（PBKDF2 + JWT，零外部依赖）
  └── utils/               # 纯工具（auth 限流/cache/feedback/geo/plate/tier）
  └── knowledge_base/      # 24 结构化 JSON + obsidian 207 篇 + SDZJ0170 刻本数据层 10.2 万字
  └── bazi_calculator.py   # 八字引擎（sxtwl + Meeus 回退）
  └── ziwei_calculator.py  # 紫微引擎（iztro-py 封装 + 格局判定 + 来因宫）
```

| 层 | 技术 |
|:---:|---|
| **后端** | `Flask 3.1` · `requests` · `zhdate` · `iztro-py` |
| **前端** | 原生 JS · 零框架 · CSS Variables 水墨设计系统 · 桌面分栏 · 移动端自适应 |
| **AI** | `GLM-5.3` / `DeepSeek v4-pro`（Anthropic 兼容端点可换） · stop_sequences 截停 + 空响应兜底轮 · prompt 缓存命中 |
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
