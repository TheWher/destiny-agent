# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

八字排盘 Web 应用 — 符号计算（排盘引擎）+ LLM 推理（DeepSeek API）的混合 AI 架构。
部署地址：`https://thewher.pythonanywhere.com`（PythonAnywhere 免费账户）。

## 引擎透传铁律（紫微斗数）

紫微排盘模块（ziwei_calculator.py）是 iztro-py 的**薄封装**：

- **引擎有输出的字段，项目层一律透传，禁止自行计算命理值**。宫位名、五行局、长生12神、四化、亮度等全部来自 iztro 原生，项目层只做格式化/翻译
- **干支一律用引擎注入值，禁止前端/项目层按公历年自算**（2026-08-04 补，当日两次强化）。曾踩坑：来因宫/年柱前端 `(birthYear-4)%10/12` 自算、校验器 `calc_sizhu(年,1,1)` 探测——都是公历年口径，年初立春前生人系统性错一年。生年干支由引擎立春分界算好（`plate.year_gz`）透传，前端/校验器只用该值。**前端任何干支相关计算默认视为残留，不存在“合法的前端干支计算”**；引擎注入失败显式缺失（来因宫显“—”、年柱显“?”），不做兜底自算，缺失即暴露。
  - **检查命令**：`python scripts/check_ganzhi.py`（指纹 `(x-4)%10/12`，全库扫项目层，引擎本体除外）。白名单外零命中才算合规（exit 0）；白名单仅认已记档的流年/大运公历口径（1-2 月窗口差一年待办），新口径须先记档再入白名单。流年/大运引擎化后清空白名单，零命中零白名单 = “干支自算彻底清零”客观判据。每次改动干支相关代码后必跑
- 曾踩过的坑：宫位功能名错位（PALACE_NAMES_CN 固定表）、十二长生排法（用八字日干长生顶紫微五行局长生）——根因都是“项目层自算覆盖原生”
- **断言/期望值锚定铁律**（2026-08-04 补，当日两救：干支口径、布宫方向）：凡涉及宫位/干支口径的期望值（测试断言、校验脚本、清单校验尺），**先跑引擎实测锚定再写，推导只能当假设不能当期望**。断言分两层：数学层（五虎遁、同阴阳等纯数学自洽，不依赖引擎）+ 宫位/口径层（期望值必须锚定引擎实测，禁止人脑推导直接写进断言）。推导与引擎实现冲突时，**引擎实测是仲裁**
- 互证八字段（四柱/五行局/命身宫/紫微/十四主星/辅星/生年四化/大限起岁顺逆）是"禁止自算"的检查表：项目层出现这八类字段的自算逻辑 = 代码审查红旗
- 需要自定义口径时（如展示格式），写在展示层，不进计算层

## 协作协议（2026-08-04 定，来源：#ch_63d75a 三方共识 + Anthropic context engineering 系列）

背景：当日三次事故（甲年假设=数据前提未确认、顺布/逆布=方向假设共享未验证、干支口径）共同根因——结论从对话漂入 artifact 时未带来源与验证状态，验证链各层共享同一错误假设。

**① 结论格式规范（五要素）**：任何结论进 artifact（清单/CLAUDE.md/断言/commit message）前过一遍模板：
1. **结论**：一句话说清
2. **层标注**：数学层 / 口径层 / 本人确认层
3. **信息源类型**：推导（待验证）/ 引擎实测 / 本人确认 / 二手书证
4. **验证状态**：已验证 / 待验证 / 待确认
5. **前提/适用范围**：结论在什么条件下成立（防前提漂移，例："King 真盘数据为真"）

**② 验证声明层标注**：说"过目/验证/复核"时，必须标注：验了什么层、用什么信息源验的、哪层没验。禁止裸声明"复核完了"（2026-08-04 顺布事故即栽于此）。

**③ 机检优先**：可机检量第一反应跑工具，禁止人脑推理接力。可机检清单（新增结论类型先问"能不能机检"）：干支计算、日期换算、宫位方向、阴阳属性、格局判定。对应检查命令：`python scripts/verify_laiyin_anchors.py`、`python scripts/check_ganzhi.py`、`python test_paipan.py`、`python scripts/verify_geju_mingzhu.py`（格局口径类断言；已挂入 test_ziwei.py 常驻回归，定义一改全真盘自动回归）、`python scripts/regression_baseline.py`（2026-08-05 补：九本账手动轨唯一官方回归入口，落 docs/regression_baseline/ 基线 json 可 diff，绿色口径=exit 0 + stderr 干净，与 pytest 轨全绿同标准）。

**④ 数据来源标签**：数据点一律带来源（本人确认/引擎实测/二手来源/推导待验证）四选一；推导性结论验证前不得进期望值区，只作假设标注（配套锚定铁律）。

**⑤ 独立信息源原则**：交叉验证的独立单位是信息源，不是换人。验证链至少一层吃独立于推导链的信息源（引擎实测/真盘/本人确认），判据：该层输入必须是推导链任何人都没碰过的原始数据。共享同一推导输入的多人验证 = 集体幻觉。

**⑥ 对话=暂存区，artifact=真相区**：结论落 artifact 后对话可丢弃；artifact（清单/CLAUDE.md/commit）才是权威。续线读 artifact 与关键 commit，不翻聊天记录。**自指约束**：本协议本身已落此文件，"对话可丢弃"才成立。

**⑦ 球消息模板（面向 King 的待办/拍板消息）**：自带四要素——是什么（一句说清）、几个选项、各自影响、出处（翻书/古籍依据）。禁止裸抛内部黑话（口径/修订痕迹/来因宫等术语须展开到一屏可决策）。背景：2026-08-05 King 问"什么东西口径三选一"暴露待办没传到位，按模板列三件事后 King 一轮拍板，23 分钟跑完整生命周期；模板配得上拍板速度。**上球前置问（2026-08-05 补，King 反馈"究竟要干什么"触发）**：上球前先问"这事能不能我们直接做掉"。可执行判据按第④条来源标签分层：信息能否落在"本人确认"层以外——能落二手书证/引擎实测/推导的我们自己做，只有生辰、拍板这类只能 King 给的才上球。查不到就标待核实或放弃（"或者放弃"也是选项，别死磕）。核心教训：**上球前先穷尽自己的手段**。实证：翻书三件事 2026-08-05 网络查证全部自行解决，上球更多是惯性。

## 启动与测试

```bash
pip install -r requirements.txt    # flask, fpdf2, requests, zhdate
python app.py                      # → http://localhost:5000
```

首次运行时确保 `config.local.py` 存在（包含 API Key），否则 LLM 分析功能不可用。

```bash
# 排盘引擎测试（24条用例，12个分类）
python test_paipan.py              # 全部
python test_paipan.py --verbose    # 详细
python test_paipan.py --smoke      # 5条冒烟用例

# Agent 评估（本地工具，不上传生产）
python evaluate_agent.py consistency     # 内部一致性检查
python evaluate_agent.py verify-report   # 验盘命中率统计（需先有标注数据）
python evaluate_agent.py blind-test      # 名人命例盲测
python blind_test_balanced.py            # 均衡命局专项盲测（马云/李娜/王菲）

# 单条排盘验证
python -c "from bazi_calculator import paipan; print(paipan(2005,8,19,1,35,'男',113.75,'东莞').summary())"
```

## 架构：符号计算 + LLM 推理 双层设计

```
用户输入 → Flask API → 符号计算层 (bazi_calculator.py)
                            │
                            ├─ sxtwl (C++ 高精度，优先)
                            └─ 纯 Python 回退 (Meeus 天文算法，零依赖)
                            │
                      输出 BaziPlate 对象
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
         plate_to_dict()  chart_svg.py  generate_bazi_pdf.py
         (JSON 序列化)    (SVG 图表)    (PDF 报告)
              │
              ▼
         analysis_service.py
         (LLM 推理层)
              │
              ├─ config.local.py              API Key（不提交 Git）
              ├─ _load_system_prompt()        加载 Agent 定义（八字 123KB + 紫微 10KB）
              ├─ _build_user_message()        构造结构化分析请求
              ├─ _analysis_cache              服务端结果缓存（同命盘秒返）
              └─ DeepSeek API                 Anthropic 兼容端点

  three_channel.py — GPT-5.5 三通道管道（analysis→commentary→final），SSE流式推送
  city_coords.py  — 内置 250+ 中国城市经纬度库，search_city() 模糊匹配
  chart_svg.py    — 纯 Python SVG 生成（五行环图/十二长生轮盘/大运时间轴/大运环图）
```

**关键分工**：符号层做确定性计算（四柱/大运/十神，不允许误差），LLM 层做模糊推理（格局判定/旺衰评估/人生建议，需要经验判断）。两层通过 `plate_to_dict()` 输出的结构化 JSON 耦合。

**Agent 定义文件**（均被 git 追踪，随代码一同部署）：

| Agent | 路径 | 行数 | 大小 | 核心 |
|-------|------|------|------|------|
| 八字 | `.claude/agents/traditional-bazi-master.md` | ~1,508 | 123KB | 梁湘润体系·9级递进推理链·42概念·13错误模式 |
| 紫微 | `.claude/agents/ziwei-master.md` | ~612 | 12KB | 三合中州派·10步推理链·四层四化权重·24格局分层判定·破格五级穿透·风险过滤 |

**知识库文件**：`knowledge_base/` 目录下 14 个结构化 JSON（八字 9 个 + 紫微 5 个），总大小 ~120KB。`analysis_service.py` 通过 `_load_json_kb()` 按需加载并内存缓存，替代了原先内联 Python dict 的数据管理方式。

## API Key 配置（三层回退）

`analysis_service.py` 按以下优先级查找 API Key：

| 优先级 | 来源 | 适用场景 |
|--------|------|----------|
| 1 | 环境变量 `ANTHROPIC_AUTH_TOKEN` | Render 等云平台 |
| 2 | `~/.claude/settings.json` 的 `env` 块 | 本地开发 |
| 3 | 项目根目录 `config.local.py` | PythonAnywhere（无环境变量 UI） |

`config.local.py` 被 `.gitignore` 忽略，**不会提交到 Git**。部署到 PythonAnywhere 时需手动上传此文件。格式：

```python
API_CONFIG = {
    "base_url": "https://api.deepseek.com/anthropic",
    "model": "deepseek-v4-pro[1m]",
    "api_key": "sk-...",
}
```

## 解读门槛（2026-08-03：登录优先，密码兜底）

解读（深度分析：八字 `/api/analyze` 系 + 紫微 `/api/ziwei/analyze` 系）的访问规则：

- **已登录用户（free/pro）免密解读**：后端 `check_password()`（utils/auth.py）先解析 JWT，登录用户直接放行
- **未登录用户**：持有访问密码（`WEB_PASSWORD`，config.local.py 配置）可解读；无密码返回 403 + `need_password: true`，前端弹"登录引导 + 密码入口"对话框（tier.js `promptLoginOrPassword`，注册入口仅在紫微系页面显示）
- 密码错误返回 403 + `need_password: true`；密码存入 `sessionStorage`（关浏览器即失效）；密码错误 5 次锁 IP 3 分钟，锁仅作用于密码通道，登录用户不受影响
- 页面差异：八字页（index.html）无登录体系，解读仅走密码通道；紫微系（ziwei-report.html / ziwei.html）登录与密码双通道，解读请求带 Bearer token 后后端免密
- **注意（语义迁移 2026-08-03）**：WEB_PASSWORD 为空时，匿名请求从"全员放行"变为"请先登录或注册"（不再有匿名通道）。本地跑 smoke 脚本需在 config.local.py 设 WEB_PASSWORD 或模拟登录态

```python
# config.local.py
WEB_PASSWORD = "mypass123"  # 改成你的密码
```

## 限流

| 端点 | 限制 | 说明 |
|------|------|------|
| `/api/analyze` | 3 次/时/IP | 深度分析，token 消耗大（~24K 输出）；**缓存命中不消耗配额** |
| `/api/analyze/continue` | 30 次/时/对话 | 多轮对话续接（对话粒度，不同对话互不影响），IP 全局兜底 100次/时 |
| `/api/analyze/stream` | 3 次/时/IP | 三通道流式验盘，同 analyze |
| `/api/analyze/stream/continue` | 30 次/时/对话 | 三通道流式续接，同 continue |
| 其他 | 无限制 | 排盘、地理编码、图表等纯计算无限制 |

限流基于内存 `defaultdict`，进程重启后清零。

## 分析结果缓存与断线恢复

深度分析耗时 4-6 分钟，期间切标签页或关页面会导致 HTTP 请求中断。三层防护：

1. **服务端缓存**（`app.py`）：`_make_cache_key()` 按四柱+性别+起运哈希 → 命中则秒返，不消耗限流。最大 50 条，1 小时 TTL
2. **客户端 pending 持久化**（`index.html`）：分析开始时 `bazi_analysis_pending` 存入 localStorage，成功后清除。页面加载时检测到未过期 pending 自动重试
3. **运行时恢复**：`visibilitychange` 检测标签页切回 + fetch AbortError/NetworkError 自动指数退避重试（5s/15s/30s，最多 3 次），8 分钟超时 AbortController 取消

密码不存 localStorage，重试时需重新输入。

## 反馈日志与验盘系统

每次深度分析自动保存到 `feedback/`（被 `.gitignore` 忽略）。

```
feedback/
├── 20260615_034827_乙_8592.json   # 首次分析（含 verification 字段）
├── 20260615_035456_乙_6601.json   # 续接对话
└── ...
```

每份 JSON 含 `verification` 字段（用户通过前端面板提交后写入）：

```json
{
  "verification": {
    "predictions": [
      {"index": 0, "label": "correct", "user_note": "确实考上二本，发挥更好"},
      {"index": 1, "label": "partially_correct", "user_note": "方向对，但时间偏晚"}
    ],
    "summary": {"total": 2, "correct": 1, "wrong": 0, "partially_correct": 1, "hit_rate": 0.75}
  }
}
```

**用途**：积累标注数据 → `evaluate_agent.py verify-report` 统计命中率 → 提取错误模式 → 更新 Agent few-shot。

## 密码防爆破

`check_password()` 函数中集成：同一 IP 输错 5 次 → 锁定 3 分钟。正确输入后自动清零。规则：`PW_MAX_TRIES=5`, `PW_LOCKOUT_MINUTES=3`。

## 核心数据流

```python
from bazi_calculator import paipan
plate = paipan(year, month, day, hour, minute=0, gender='男', longitude=113.75, location='')
# → BaziPlate 对象，调用 plate.compute() 后包含:
#   plate.sizhu / plate.qiyun / plate.dayun / plate.shishen
#   plate.nayin / plate.kongwang / plate.canggan / plate.changsheng
#   plate.taiyuan / plate.minggong / plate.shengong

from app import plate_to_dict
data = plate_to_dict(plate)  # → JSON-serializable dict，包含神煞/空亡标记
```

## API 路由一览

| 路由 | 方法 | 用途 | 关键参数 |
|------|------|------|----------|
| `/` | GET | 首页 | — |
| `/api/paipan` | POST | 排盘 | `year/month/day/hour/minute/gender/longitude`，可选 `is_lunar: true`、`solar_correction`（分钟） |
| `/api/geocode?q=` | GET | 地名→经纬度 | 内置 250+ 城市优先，Nominatim 回退 |
| `/api/cities?q=` | GET | 城市模糊搜索 | 前端自动补全用 |
| `/api/network-info` | GET | 本机局域网 IP | — |
| `/api/qrcode?url=` | GET | 生成访问二维码 | 重定向到 qrserver.com |
| `/api/analyze` | POST | **LLM 深度分析** | `{plate: plate_dict}` 或直接传出生参数；限流 3次/时/IP |
| `/api/analyze/stream` | POST | **三通道 SSE 流式验盘** (GPT-5.5参考) | 同上参数。SSE事件流：progress→verify_complete→result |
| `/api/analyze/continue` | POST | **多轮对话续接** | `{messages: [...], reply: "..."}` ；限流 30次/时/IP |
| `/api/analyze/stream/continue` | POST | **三通道 SSE 流式续接** (GPT-5.5参考) | 同上参数。14阶段进度→result，含隐藏推理层 |
| `/api/chart/wuxing` | POST | 五行环图 SVG | `{wuxing: {木:N, 火:N, ...}}` |
| `/api/chart/changsheng` | POST | 十二长生轮盘 SVG | `{pillars: ..., ri_zhu: ...}` |
| `/api/chart/dayun` | POST | 大运时间轴 SVG | `{dayun: [...], ri_gan: ...}` |
| `/api/chart/dayun-ring` | POST | 大运环形 SVG | `{dayun: [...], ri_gan: ..., current_age: N}` — current_age 高亮当前步 |
| `/api/glossary/lookup?term=` | GET | **术语查询** | 服务端44术语词典，`?term=all` 返回全部 |
| `/api/glossary/references` | GET | **古籍引用** | 返回字段级古籍引用，前端 tooltip 用 |
| `/api/verify` | POST | 保存验盘反馈 | `{feedback_file: "2026...json", predictions: [{index, label, user_note}]}` |
| `/api/feedback/list` | GET | 反馈日志摘要 | `?limit=50&verified_only=1` |
| `/api/pdf` | POST | PDF 报告（线上已弃用） | 同排盘参数 |
| `/report` | GET | 打印报告页 | 从 localStorage 读取数据渲染 |

## LLM 分析管道

### 单次分析（`/api/analyze`）— 验盘阶段

```
analysis_service.py
  │
  ├─ API Key 优先级: 环境变量 → ~/.claude/settings.json → config.local.py
  ├─ _load_system_prompt(): 读取 .claude/agents/traditional-bazi-master.md
  ├─ _build_user_message(): 将 plate_dict 转为 Markdown 表格
  │    ├─ compute_spread() → 决定验盘模式（极端/均衡）
  │    ├─ _build_year_lookup_table() → 流年对照表（均衡模式含🆕首现候选）
  │    └─ 注入 knowledge_base JSON（_load_json_kb 按需加载，内存缓存）
  ├─ _verify_predictions(): 后处理硬校验（排盘引擎 vs LLM 输出）
  └─ DeepSeek API: model=deepseek-v4-pro[1m], max_tokens=24576, temperature=0.3
       stop_sequences=['【验盘完毕】'] 物理截停验盘阶段
```

返回的 `messages` 数组（system + user + assistant）保存在前端 `conversationMessages`。

### 多轮对话（`/api/analyze/continue`）— 正式批断

用户确认验盘后，将完整 `messages` + 新 `reply` 发给 `/api/analyze/continue`。服务端提取 system、拼接历史、追加新消息后调用 API。**max_tokens: 16384, temperature: 0.3**。续接成功后客户端将新回复**累加到 `analysisText` 并写回 localStorage**，确保打印报告包含完整对话。

### 验盘纠正优先级

Agent 定义中硬性规定：用户验盘阶段的纠正具有最高优先级。一旦用户确认某条验证正确或指出错误，后续所有分析章节必须以纠正后的信息为准。每个分析章开头需回顾已验证事件作为锚点。

## PDF 生成（3 个函数，均在 generate_bazi_pdf.py）

| 函数 | 用途 | 线上可用？ |
|------|------|-----------|
| `build_generic_pdf(plate)` | 纯数据报告（四柱/大运/神煞，无断语） | PythonAnywhere 上 fpdf2 + simhei.ttf 不兼容 |
| `build_analysis_pdf(plate, analysis_text)` | 数据 + Agent 分析文本 | 同上 |
| `build_pdf()` | 硬编码 2005-08-19 东莞男命的完整分析报告 | 仅本地 |

**线上替代方案**：浏览器打印 `templates/report.html`（从 localStorage 读 `bazi_plate` + `bazi_analysis` 渲染）。

## 图表（chart_svg.py — 纯 Python，零外部依赖）

四个函数均返回完整 SVG 字符串，通过 `/api/chart/*` 路由以 `image/svg+xml` MIME 返回：
- `wuxing_pie(data, size=380)` — 环形分区图，按五行占比画弧段
- `changsheng_wheel(pillars, day_gan, size=420)` — 12 宫轮盘 + 四柱标记 + 底部图例（悬停看解释）
- `dayun_line(dayun, ri_gan, width=960)` — 水平时间轴，8 步大运
- `dayun_ring(dayun, ri_gan, size=400, current_age=-1)` — 环形大运图，传 current_age 可高亮当前所在大运（脉冲动画 + "当前"角标 + 中心显示当前干支）

⚠️ SVG 坐标用 `'{:.1f}'.format()` 不要 `int()`，否则节点抖动。不可在 f-string 内用 `\` 转义符。

## 前端架构

单页应用（`templates/index.html`），基于原生 JS 无框架。**桌面端左右分栏**（左侧 400px 表单边栏 + 右侧主内容），移动端自动回退单列。

- **快捷输入**：`200508190135` 一键填表，回车触发排盘
- **排盘 → 确认 → 分析** 四步走：提交表单 → `/api/paipan` → Bento Grid + 确认排盘卡片（四柱摘要复核）→ Agent 验盘 → 续接批断
- **粘性操作栏三态**：排盘 / 确认命盘 / 分析中，`position: fixed` 贴底
- **逐字段验证**：blur 触发行内红边框错误提示（替代全量 validateInput）
- **古籍 tooltip**：表单标签 hover 📜 展示古籍原文，数据来自 `/api/glossary/references`
- **Bento 结果网格**：基本信息+神煞2列，四柱+大运全宽，图表 2x2 排列
- **验盘反馈面板**：Agent 验盘后自动提取预测 → 用户逐条确认 → `/api/verify` 写入 feedback JSON
- **骨架屏加载** + 断线恢复（pending 持久化 + visibilitychange + 指数退避重试）
- **历史命例**：localStorage 最多 20 条，支持命名/删除/一键恢复
- **词条弹窗**：44 术语自动高亮，服务端 `/api/glossary/lookup` 统一管理

## 地理编码管道

```
用户输入地名 → /api/cities?q= (模糊搜索，前端自动补全)
                  │
                  └─ city_coords.py  search_city()  内置 250+ 城市，零延迟
                                                    支持省+市、市名、区县名
用户选择城市 → /api/geocode?q= (精确查询)
                  │
                  ├─ city_coords.py  search_city()  优先
                  └─ Nominatim (OSM)                 回退，需网络
```

## 部署注意事项

### PythonAnywhere（主部署）
- **仓库路径**：`~/destiny-agent`（注意不是 `~/mysite`）
- **Python 版本不一致**：WSGI 用 3.11，Bash 默认 3.13。`pip install` 必须用 `python3.11 -m pip --user`
- **唯一可靠重启方式**：Disable → 等几秒 → Enable（Reload 不够）
- **禁止 CSP 头**：`@app.after_request` 设 CSP 会破坏 WSGI 代理层
- **禁止外部 CDN**：`cdn.jsdelivr.net` 等被拦截，所有静态资源本地化
- **API Key**：免费账户无环境变量 UI，需手动上传 `config.local.py`。验证：`python3.11 -c "from analysis_service import API_CONFIG; print('OK' if API_CONFIG.get('api_key') else 'MISSING')"`
- **更新流程**：`cd ~/destiny-agent && git pull origin master` → 确认 config.local.py 存在 → Disable → Enable
- **untracked 文件冲突**：PythonAnywhere 手动上传的文件与 git pull 冲突时，`rm` 冲突文件后重新 pull（不是 `git stash`——stash 只处理 tracked 文件）

### Render（备用）
- `render.yaml` 自动配置，需在 Dashboard 手动添加 `ANTHROPIC_AUTH_TOKEN` 环境变量
- 启动命令：`python app.py --no-debug --port $PORT --host 0.0.0.0`

## 常见踩坑

1. **zhdate 版本**：`zhdate>=0.1`（不是 `>=1.0`），`>=1.0` 会安装失败
2. **API Key 不能提交 Git**：Key 在 `config.local.py`（被 `.gitignore` 忽略），不要在任何 `.py` 文件中硬编码。已通过 `git log` 确认历史中无 Key 泄露
3. **PythonAnywhere 部署后缺少 config.local.py**：`git pull` 不会下载此文件，需手动上传。验证：`python3.11 -c "from analysis_service import API_CONFIG; print('OK' if API_CONFIG.get('api_key') else 'MISSING')"`
4. **深度分析 4-6 分钟**：12K+ system prompt + 24K token 输出，关闭页面前有 `beforeunload` 提醒
5. **起运计算精度差异**：sxtwl 3.66 岁 vs 纯 Python 回退 3.77 岁，差异 ~0.1 岁（约 1 个月），属 Meeus 算法与 sxtwl 的精度差异
6. **节气缓存**：`_ST_CACHE` 预计算 3年×24节气，首次排盘后缓存命中，从 5000+ 次计算降到 72 次
7. **BaziPlate.start_year 初始值**：`calc_dayun()` 中硬编码了 2005，但 `plate.compute()` 会调用 `round(y + du['start_age'])` 修正
8. **夜子时处理**：23:00-23:59（夜子时）日柱按次日算，时柱按次日日干起五鼠遁，`calc_sizhu()` 中 `is_yezi` 分支处理
9. **时区**：`calc_qiyun` 中 `birth_dt` 无时区时自动设为 UTC+8（北京时）
10. **Git DNS 污染**：国内间歇性阻断。`git config --global http.proxy http://127.0.0.1:7890` 开代理
11. **PythonAnywhere 创建 Flask 应用时覆盖 app.py**：需重新上传或 `git checkout` 恢复
12. **分析缓存键**：`_make_cache_key()` 基于四柱+性别+起运，缓存命中返回 `cached: true`
13. **打印报告只有验盘**：续接后需累加新回复到 `analysisText` 并写回 localStorage
14. **f-string + SVG**：不可在 f-string 内用 `\`。用 `'{:.1f}'.format()` 替代
15. **`git add -A` 是地雷**：永远显式 `git add <具体文件>`，feedback/ 等隐私文件在 .gitignore
16. **交付铁律**：`ast.parse` → `test_paipan.py` 24/24 → 关键路径验证 → 全通过才 commit+push
17. **真太阳时 Agent 消息**：`birth_datetime` 必须显示用户原始输入时间，不能显示校正后的
18. **continue timeout**：`max_tokens=16384` 需 timeout≥480s（DeepSeek ~50tok/s）
19. **`plate.sizhu` 是 dict 不是 tuple**：取日柱用 `plate.sizhu['day']['gz']`
20. **Agent 定义中禁止残留工具调用指令**：2026-07-13 发现 Agent MD 中残留 11.6KB 记忆系统指令，导致 API 调用时 Agent 输出 `<read_file>` 幻觉，王菲盲测从 60% 跌至 0%。已删除。
21. **均衡命局 Agent 门禁**：无 ≥15 岁候选年时必须诚实跳过，禁止用童年年份凑数。候选表中有硬性门禁规则。

## Agent 优化策略（2026-06-16 盲测驱动，2026-07-13 均衡突破）

### 核心发现：极端度 = 命中率最强预测因子

```
16人盲测数据（2026-06-16）：
  极端度3+(极端命局):  6/6  = 100%
  极端度2:             7/9  = 78%
  极端度1:             3/8  = 38%
  极端度0(均衡命局):   0/3  = 0%  ← 2026-06-16

均衡命局专项重测（2026-07-13，十神到位→大运降级）：
  马云(spread=1):  0/3（诚实跳过，0候选）
  李娜(spread=1):  2/2 = 100%
  王菲(spread=2):  3/5 = 60%
  合计: 5/10 = 50%  |  排除马云: 5/7 = 71%
```

### 验盘策略总纲（2026-07-13：双模式分流 + 均衡降级）

```
plate_dict → compute_spread()
  ├─ spread ≥ 3 → 冲合信号表（极端命局，已验证 100%/78%）
  └─ spread ≤ 2 → 十神到位法 → 无≥15岁候选 → 大运主题确认（50-71%）
```

| 命局类型 | spread | 验盘策略 | 命中率 | 核心动作 |
|----------|--------|----------|--------|----------|
| 极端 | ≥3 | 冲合信号表 | 100% | 找S/A级年份 → 时间锚定 |
| 均衡 | ≤2 | 大运主题确认 | 50-71% | 🆕首现过滤 → 无候选→降级大运主题 |

**均衡命局结论（2026-07-13）**：十神"从无到有"全在童年（≤8岁）——十天干每10年轮一圈，任何十神10岁前必以天干出现。过滤age≥15后三人的🆕首现候选均为0。降级为大运主题确认后，命中来自大运交接年±2年容差。流年级时间信号在均衡命局中理论上不存在——不是方法问题，是信息论上限。

### ShenSuan 模式适配（2026-07-13）

对标 [ShenSuan](https://github.com/BIG-CR/ShenSuan)（26种方法/追问交互/结构化JSON），取长补短：

**知识结构化**：54KB 单一 Agent Markdown → 7个 `knowledge_base/*.json`（24KB）：
| 文件 | 条数 | 用途 |
|------|------|------|
| `tiaohou.json` | 120 | 穷通宝鉴调候用神表 |
| `signal_rules.json` | 7数据块 | 冲合/三合/驿马/墓库（从 `_evaluate_liunian_signal` 提取） |
| `shishen_domains.json` | 40 | 十神×年龄→领域映射（从 `_map_shishen_to_domain` 提取） |
| `glossary.json` | 44 | 术语定义（前端→服务端统一管理） |
| `classical_references.json` | 5 | 古籍引用→表单tooltip映射 |

**交互升级**：排盘确认步骤 + 粘性操作栏三态切换 + 逐字段blur验证 + 古籍📜tooltip

### 流年信号优先级（极端命局验盘专用）

| 等级 | 关系 | 精度 | 验盘用途 |
|------|------|------|----------|
| S | 天克地冲/日柱伏吟 | ±0年 | 首选 |
| A | 日柱伏吟 | ±0年 | 首选 |
| B | 六冲日/月/年支 | ±1年 | 2选1 |
| C | 三合/六合日/月支 | ±1年 | 配合B |
| D | 驿马到位 | ±2年 | 备选 |
| E | 墓库开闭 | ±2年 | 备选 |
| 兜底 | 大运交接年 | ±1年 | 必用 |

### 13条错误模式

| # | 模式 | 来源 |
|---|------|------|
| 1 | 低估禄印帮扶力度 | 用户验盘纠正 |
| 2 | 旺衰层次混淆 | 一致性检查 |
| 3 | 驿马应期宽泛 | 用户验盘纠正 |
| 4 | 均衡命局泛化预测 | 盲测(王菲/林青霞) |
| 5 | 学历时代校正 | 盲测(成龙/林青霞) |
| 6 | 名人识别污染 | 盲测(蒋介石/毛泽东) |
| 7 | 跳过验盘流程 | 盲测(毛泽东) |
| 8 | 国际命例学历偏差 | 盲测(科比) |
| 9 | 特征型→时间型切换 | 盲测(张艺谋重测) |
| 10 | 童年搬家不可靠 | 盲测(马云/成龙) |
| 11 | 叙事膨化 | 完整分析对比 |
| 12 | 均衡命局强凑3条 | 2026-06-24 新增 |
| 13 | 干支-西历心算错误 | 2026-06-24 新增 |

### Agent 定义统计

- 路径：`.claude/agents/traditional-bazi-master.md`
- 大小：~54KB
- 核心概念：42个（23个标注经典出处）
- 推理链：9级递进（调候→格局→旺衰→病药→流通→十神→刑冲合害→大运→四维交叉）
- 错误模式：13条（盲测驱动）
- 流年信号优先级表：S/A/B/C/D/E 6级（极端命局专用）
- **十神→人生领域映射表**：10十神×3年龄段（均衡命局专用）
- 叙事等级制度：1-5级
- 禁用戏剧化词：7个
- 验盘策略：spread双模式分流（≥3冲合信号，≤2十神到位）
- **均衡命局验盘规则（2026-06-29）**：十神到位三步法则——查🆕首现→年龄映射→时间锚定。禁止冲合信号选年、禁止凑3条、禁止特征型问题
- **诚实降级**：首现 < 3 → 告知信号不足，不强制验盘

### 紫微斗数 Agent 定义统计（2026-07-17：v7）

- 路径：`.claude/agents/ziwei-master.md`
- 大小：612 行 / 12KB
- 推理链：10 步强制推理（含亮度自检步骤）
- 核心方法论：
  - **亮度体系**：7 级（庙旺得利平不陷），后端 `_BRIGHTNESS_FIX` 全量修正 iztro 引擎偏差（14星×12地支）
  - **四层四化权重**：生年(★★★★★)/大限(★★★★)/本宫自化(★★★)/流年(★★)，15 条互涉规则
  - **身宫独立框架**：4 维分析 + 4 段年龄权重表 + 命身同宫处理
  - **对宫冲照**：6 组对宫分析维度 + 7 级冲照力度（含冲照带忌）
  - **格局系统**：24 格局三列核验（必要条件+条件受损+吉化加分），五层穿透判定
  - **破格分层**：打到核心？+ 能否补救？→ 五级受损/四层应对，不说"格局破了"
  - **对星组合**：昌曲/辅弼/魁钺/火铃 5 组 + 禄存专项（羊陀夹制/被破）
  - **空宫借星**：7 场景规则（借星不带四化，冲照传导）
  - **流年命宫**：三步法 + 3 条叠加规则
  - **截空/旬空**：效应表 + 分析模板
- 多轮对话：4 套关联模板（纯文本格式，禁 markdown）+ 超出范围标准回复
- 风险过滤：5 禁 + 5 缓冲 + 化忌模板 + 桃花专项 + 化权夫妻宫模板
- 输出模式：全盘(A) 5 章标推理链步骤 + 单主题(B)，结尾强制引导追问
- 引擎修正：`_BRIGHTNESS_FIX` 20 条（令东来参考表），`detect_patterns()` 已移除（格局全权交 Agent）

### 验盘截停 + 后处理硬校验（2026-06-25 新增，替换双采样）

**旧方案**：双采样自一致性（Pass1 temp=0.3 + Pass2 temp=0.7）→ 成本¥0.03/次，UX差（用户手动对比两段文本），拦截率不确定。

**新方案**：
1. `stop_sequences=['【验盘完毕】']` — Agent验盘完物理截停
2. `_verify_predictions(analysis_text, plate_dict, current_year)` — 后处理硬校验
3. 成本：¥0/次（纯Python），可靠性：排盘引擎硬事实 vs LLM交叉

### 对照表注入管道

`analysis_service.py` 函数：
- `compute_spread(plate_dict)` → `(spread, label, counts)` — 五行极端度，决定验盘模式
- `_get_yuanju_shishen_set(plate_dict)` — 原局十神集合（天干+藏干本气/中气）
- `_get_liunian_shishen_info(ri_gan, ganzhi)` — 流年干支十神
- `_evaluate_liunian_signal(...)` → `(level, desc)` — 六级信号判定
- `_build_year_lookup_table(plate_dict, current_year, spread, balanced)` → markdown — 双模式对照表（均衡+十神🆕列，极端+信号列）
- `_verify_predictions(analysis_text, plate_dict, current_year)` → markdown — 后处理硬校验
- `_call_api(... stop_sequences=list)` — API截停参数

### 均衡命局验盘演进（2026-06-29 → 2026-07-13）

**2026-06-29 十神到位法**：不找冲合异常，找十神"从无到有"——原局没有的十神在大运/流年首次出现=新人生领域启动。

**2026-07-13 实测结论**：十神"从无到有"全在童年（≤8岁），过滤age≥15后三人候选均为0。因为十天干每10年轮一圈，任何十神10岁前必以天干出现。降级为大运主题确认。

**最终方案**：均衡命局诚实告知信号不足 → 大运主题确认 → 大运交接年命中率50-71%（±2年容差）。流年级时间信号在均衡命局中理论上不存在——不是方法问题，是信息论上限。
