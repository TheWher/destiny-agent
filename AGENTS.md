# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## 项目概述

八字排盘 Web 应用 — 符号计算（排盘引擎）+ LLM 推理（DeepSeek API）的混合 AI 架构。
部署地址：`https://thewher.pythonanywhere.com`（PythonAnywhere 免费账户）。

### 🏗️ 架构状态（2026-07-31）

**模块层级**：
```
routes/     ← 只做请求-响应，不写业务逻辑（可 import services/utils/calculators/models）
services/   ← 业务逻辑 + LLM 调用（可 import utils/calculators/models，不可 import routes）
models/     ← 数据层：User 模型、JWT 鉴权、SQLite 存储（可 import utils，不可 import routes/services）
utils/      ← 纯函数，无副作用（不 import 任何本项目模块）
calculators/← 排盘引擎（bazi_calculator.py, ziwei_calculator.py 等，不 import 任何本项目模块）
scripts/    ← 评估脚本 + CLI 工具（可 import 任何模块）
templates/  ← Jinja2 + 内联 JS。JS >200 行应抽到 static/
```

**数据流**：`前端 fetch → Blueprint 路由 → service 函数 → DeepSeek API → SSE/JSON 返回`

**关键文件**：
| 文件 | 行数 | 职责 |
|------|------|------|
| `app.py` | 20 | 入口，argparse + app.run |
| `routes/__init__.py` | ~95 | Flask 工厂 + 启动信息 |
| `routes/ziwei.py` | ~610 | 紫微全部 API（排盘/分析/验盘/会话/流年） |
| `routes/auth.py` | ~90 | 注册/登录/me（JWT 鉴权） |
| `routes/bazi.py` | ~300 | 八字全部 API |
| `models/user.py` | ~170 | User 模型 + PBKDF2 密码 + HMAC-SHA256 JWT |
| `services/ziwei_analysis.py` | ~540 | 紫微分析管道（含验盘截停） |
| `services/llm_client.py` | ~160 | API 调用 + 三层 Key 回退 |

**已知技术债**：
- 146KB 知识库每次全量拼接 → 计划改为按需检索
- 八字推理链在 Prompt 中（9 级） → 考虑剥离到代码层
- 紫微验盘反馈 < 10 条 → 聚合分析暂无统计意义（命中率噪音大）
- 前端多个页面有重复的 HTML/CSS 片段

**决策记录**：见 `docs/adr/`（5 条 ADR）
**变更记录**：见 `CHANGELOG.md`

## 启动与测试

```bash
pip install -r requirements.txt    # flask, fpdf2, requests, zhdate
python app.py                      # → http://localhost:5000
python bazi_calculator.py          # 独立测试排盘引擎
python -c "from bazi_calculator import paipan; print(paipan(2005,8,19,1,35,'男',113.75,'东莞').summary())"
```

首次运行时确保 `config.local.py` 存在（包含 API Key），否则 LLM 分析功能不可用。

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
              ├─ _load_system_prompt()        加载 Agent 定义 (~12K 字符)
              ├─ _build_user_message()        构造结构化分析请求
              └─ DeepSeek API                 Anthropic 兼容端点

辅助模块：
  city_coords.py  — 内置 250+ 中国城市经纬度库，search_city() 模糊匹配
  chart_svg.py    — 纯 Python SVG 生成（五行环图/十二长生轮盘/大运时间轴/大运环图）
```

**关键分工**：符号层做确定性计算（四柱/大运/十神，不允许误差），LLM 层做模糊推理（格局判定/旺衰评估/人生建议，需要经验判断）。两层通过 `plate_to_dict()` 输出的结构化 JSON 耦合。

## API Key 配置（三层回退）

`analysis_service.py` 按以下优先级查找 API Key：

| 优先级 | 来源 | 适用场景 |
|--------|------|----------|
| 1 | 环境变量 `ANTHROPIC_AUTH_TOKEN` | Render 等云平台 |
| 2 | `~/.Codex/settings.json` 的 `env` 块 | 本地开发 |
| 3 | 项目根目录 `config.local.py` | PythonAnywhere（无环境变量 UI） |

`config.local.py` 被 `.gitignore` 忽略，**不会提交到 Git**。部署到 PythonAnywhere 时需手动上传此文件。格式：

```python
API_CONFIG = {
    "base_url": "https://api.deepseek.com/anthropic",
    "model": "deepseek-v4-pro[1m]",
    "api_key": "sk-...",
}
```

## 账号系统（2026-07-31 新增）

### 注册/登录

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/register` | POST | `{email, password}` → `{token, user}` |
| `/api/auth/login` | POST | `{email, password}` → `{token, user}` |
| `/api/auth/me` | GET | Bearer token → `{user}` |

- **JWT**：HMAC-SHA256，3 天有效，存 `localStorage.ziwei_token`
- **密码**：PBKDF2-SHA256（600k 迭代），零外部依赖
- **数据库**：`data/users.db`（SQLite），自动建表
- **JWT_SECRET**：环境变量或 `config.local.py`，默认值仅用于开发

### 会话绑定

登录后创建的紫微会话自动绑定 `user_id`。会话列表按用户隔离：已登录只看到自己的，未登录只看到匿名的。

### 前端状态

- `ziwei.html` 顶部栏：登录/注册按钮 → 切换为邮箱 + 退出按钮
- 弹窗自动切换登录/注册模式，Enter 提交
- 刷新页面时从 `localStorage` 恢复 token，调 `/api/auth/me` 验证

## 密码保护

深度分析（`/api/analyze` 和 `/api/analyze/continue`）支持可选的密码保护。

- 在 `config.local.py` 中设置 `WEB_PASSWORD = "你的密码"` 即可启用
- 留空则不设防，所有人可用
- 前端首次分析时弹出密码框，密码存入 `sessionStorage`（关浏览器即失效）
- 密码错误返回 403 + `need_password: true`，前端自动清除缓存让用户重试

```python
# config.local.py
WEB_PASSWORD = "mypass123"  # 改成你的密码
```

## 限流

| 端点 | 限制 | 说明 |
|------|------|------|
| `/api/analyze` | 3 次/时/IP | 深度分析，token 消耗大（~24K 输出） |
| `/api/analyze/continue` | 5 次/时/IP | 多轮对话续接 |
| 其他 | 无限制 | 排盘、地理编码、图表等纯计算无限制 |

限流基于内存 `defaultdict`，进程重启后清零。

## 反馈日志收集

每次深度分析（含多轮续接）自动保存到 `feedback_logs/`（被 `.gitignore` 忽略）。

```
feedback_logs/
├── 20260603_143025_乙_7752.json   # 首次分析
├── 20260603_144512_乙_3198.json   # 续接对话
└── ...
```

每份 JSON 结构：

```json
{
  "timestamp": "2026-06-03T14:30:25",
  "ip_masked": "192.***",
  "turn_type": "initial" | "continue",
  "plate_summary": {
    "birth": "2005-08-19 01:35",
    "gender": "男",
    "ri_zhu": "乙",
    "sizhu": "乙酉 甲申 乙亥 丁丑",
    "qiyun_age": 3.66
  },
  "conversation": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "请根据以下八字..."},
    {"role": "assistant", "content": "## 命盘综述\n..."}
  ]
}
```

**用途**：积累验盘对话后，可分析 Agent 常犯错误模式、提取验证案例补充 few-shot、打磨推理链。

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
| `/api/analyze/stream` | POST | **三通道 SSE 流式验盘** (GPT-5.5参考) | 同上参数。SSE事件流：progress→verify_complete→result。前端通过 fetch+ReadableStream 消费 |
| `/api/analyze/continue` | POST | **多轮对话续接** | `{messages: [...], reply: "..."}` ；限流 5次/时/IP |
| `/api/analyze/stream/continue` | POST | **三通道 SSE 流式续接** (GPT-5.5参考) | 同上参数。SSE事件流：14阶段进度→result。含隐藏推理层（analysis channel） |
| `/api/chart/wuxing` | POST | 五行环图 SVG | `{wuxing: {木:N, 火:N, ...}}` |
| `/api/chart/changsheng` | POST | 十二长生轮盘 SVG | `{pillars: ..., ri_zhu: ...}` |
| `/api/chart/dayun` | POST | 大运时间轴 SVG | `{dayun: [...], ri_gan: ...}` |
| `/api/chart/dayun-ring` | POST | 大运环形 SVG | `{dayun: [...], ri_gan: ...}` |
| `/api/pdf` | POST | PDF 报告（线上已弃用） | 同排盘参数 |
| `/report` | GET | 打印报告页 | 从 localStorage 读取数据渲染 |

## LLM 分析管道

### 单次分析（`/api/analyze`）

```
analysis_service.py
  │
  ├─ API Key 优先级: 环境变量 → ~/.Codex/settings.json → config.local.py
  ├─ _load_system_prompt(): 读取 .Codex/agents/traditional-bazi-master.md
  │    去除 YAML frontmatter，保留完整 Agent 定义（31 个核心概念 + 7 级推理链）
  ├─ _build_user_message(): 将 plate_dict 转为 Markdown 表格格式的分析请求
  │    （用 Markdown 而非 JSON，因为 LLM 对 Markdown 表格理解更好）
  └─ POST https://api.deepseek.com/anthropic/v1/messages
       model: deepseek-v4-pro[1m], max_tokens: 24576, temperature: 0
```

返回的 `messages` 数组（system + user + assistant）保存在前端，供多轮对话使用。

### 多轮对话（`/api/analyze/continue`）

用户对 Agent 的分析结果进行追问时，将之前的完整 `messages` 数组 + 用户的新 `reply` 发给 `/api/analyze/continue`。服务端提取 system 消息、拼接 user/assistant 历史，追加新 user 消息后调用 API。max_tokens 降至 8192。

**Agent 定义文件**：`.claude/agents/traditional-bazi-master.md`（~998 行），定义了 9 级递进推理链（调候→格局→旺衰→病药→十神→刑冲合害→神煞→大运流年→四维交叉验证）和 35 个核心概念的严格定义。

## PDF 生成（3 个函数，均在 generate_bazi_pdf.py）

| 函数 | 用途 | 线上可用？ |
|------|------|-----------|
| `build_generic_pdf(plate)` | 纯数据报告（四柱/大运/神煞，无断语） | PythonAnywhere 上 fpdf2 + simhei.ttf 不兼容 |
| `build_analysis_pdf(plate, analysis_text)` | 数据 + Agent 分析文本 | 同上 |
| `build_pdf()` | 硬编码 2005-08-19 东莞男命的完整分析报告 | 仅本地 |

**线上替代方案**：浏览器打印 `templates/report.html`（从 localStorage 读 `bazi_plate` + `bazi_analysis` 渲染）。

## 图表（chart_svg.py — 纯 Python，零外部依赖）

四个函数均返回完整 SVG 字符串，通过 `/api/chart/*` 路由以 `image/svg+xml` MIME 返回：
- `wuxing_pie(data, size)` — 环形分区图，按五行占比画弧段
- `changsheng_wheel(pillars, day_gan, size)` — 12 宫轮盘 + 四柱标记 + 图例面板。中心圆按日干五行配色
- `dayun_line(dayun, ri_gan, width, height)` — 水平时间轴，8 步大运
- `dayun_ring(dayun, ri_gan, size)` — 环形大运图，8 步绕圈排列，按天干五行配色（受 Species in Pieces 启发）

## 前端架构

单页应用（`templates/index.html`），基于原生 JS 无框架：

- **排盘 → 分析** 两步走：用户提交表单 → `/api/paipan` → 渲染命盘（含 SVG 图表）→ 用户点击"深度分析"→ `/api/analyze` → 流式渲染 Markdown
- **localStorage 持久化**：`bazi_plate`（排盘结果 JSON）和 `bazi_analysis`（分析文本 + messages 数组）保存在 localStorage，刷新不丢失
- **报告打印**：`/report` 页（`templates/report.html`）从 localStorage 读取数据渲染，浏览器 Ctrl+P 打印
- **长耗时提醒**：分析调用前设置 `beforeunload` 事件，防止用户误关页面（分析耗时 4-6 分钟）
- **Markdown 渲染**：前端用自定义 `formatMarkdown()` 渲染（正则替换，零依赖）
- **交互动画**：
  - 背景呼吸光晕（`body::before` 暖金色 radial-gradient 脉冲，10s 循环）
  - 按钮点击波纹（JS 动态创建 `.btn-ripple` 元素，0.6s 消散）
  - 滚动揭示（IntersectionObserver 监听 h2/h3/blockquote，滚入视口时淡入）
  - 分析完成粒子庆祝（60 颗金色粒子从分析区中心爆开）
  - 卡片悬浮金边脉冲（hover 时左边缘金色 + 淡金阴影 + 微上浮）
  - 表格行悬浮浮起（hover 时暖金底色 + 上浮 1px）
  - 分析章节五行分色（h2 按木火土金水循环配色左边框）

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
- **Python 版本不一致**：WSGI 用 3.11，Bash 默认 3.13。`pip install` 必须用 `python3.11 -m pip --user`，WSGI 文件 `sys.path` 指向 `.local/lib/python3.11/site-packages`
- **唯一可靠重启方式**：Disable → 等几秒 → Enable（Reload 不够）
- **禁止 CSP 头**：`@app.after_request` 设 CSP 会破坏 WSGI 代理层
- **禁止外部 CDN**：`cdn.jsdelivr.net` 等被拦截，所有静态资源本地化
- **API Key**：免费账户无环境变量 UI，需手动上传 `config.local.py` 到 `/home/thewher/mysite/`
- **文件更新**：在 Files 页面直接上传覆盖，或 Bash console 中 `git clone` 后手动补充 `config.local.py`

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
10. **GitHub DNS 被劫持**：`140.82.121.4 github.com` → hosts
11. **PythonAnywhere 创建 Flask 应用时覆盖 app.py**：需重新上传或 `git checkout` 恢复
