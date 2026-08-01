## Destiny_agent 进度 （2026-08-01）

### 知识库接入形态审计（韩湘生核实 + hanako 落档，2026-08-01）

**KB 四类接入形态（决定性，评测/检索改造按此分层）：**
- 直读注入：ziwei_stars / ziwei_hua 速查表（`_load_json_kb` 直读，不进检索路径）
- 检索注入：ziwei_fuzuo + ziwei_classics（`_build_ziwei_user_message` 里 `retrieve_kb` 仅这两处）
- 工具可达：ziwei_star_palace（kb_retrieve 工具链，LLM 自主决定查不查，非确定性注入）
- 未登记的工具可达：ziwei_classics_full（75 段，dispatch 层 `if "classics" in kb_name` 会受理走 _retrieve_classics，但 orchestrator schema 未登记该名，LLM 默认不传；比 star_palace 弱一档、比死资产活一档。修正：不是死资产）

**接口边界定案（2026-08-01，韩湘生）：注册不动、后端可换。**
- embedding 替换只换检索后端内部实现；ToolDef / schema / kb_name dispatch 一概不动
- 落地：`_retrieve_*` 家族收敛成后端概念，embedding 是换后端，dispatch 匹配逻辑零改动
- 好处：评测时间窗只卡“后端替换”一个点，pair 池三层替换前后跑同一套工具调用，对比条件天然干净

**文档债（待修）：**
- `services/ziwei_analysis.py:54` 注释“ziwei_star_palace.json 不在此处加载，由 _build_ziwei_user_message 按需检索”是过时注释，与实现矛盾：`_build_ziwei_user_message` 实际只检索 fuzuo + classics，star_palace 走 kb_retrieve 工具链。照注释找注入会扑空，需删除或改写。
- `services/kb_loader.py:123` 注释把 classics 与 classics_full 并列“古籍引用”，含糊但不全错（dispatch 确实共用 _retrieve_classics），真问题是 schema 未登记 full。建议改为“classics 系共用 _retrieve_classics，full 未登记”。
- ziwei_classics.json 真伪分层已核：14 条干净真引文 / 3 条混合（紫微独坐、巨日同宫、杀破狼格）/ 23 条纯转述（含 13 条单星条目书名号挂现代白话）。计划拆字段：引文/按语/来源真伪标记，外层“格局名→条目” key 形态不动（评测 target 依赖此结构，零返工）。
- classics_full 75 段 source 标注（gusuifu/quanji/quanshu）实为主题标签非原文出处，全库零整篇原文。source 降级排后（死数据不影响用户），第一优先级是 classics.json 引文标记。

### 已上线

### 已上线
- 紫微斗数全流程：排盘（iztro 引擎）→ 确认 → AI 验盘 → 正式解读（SSE 流式，2-4 分钟）
- 多轮追问：报告页内嵌聊天，Markdown 渲染
- 验盘闭环：6 级信号预测 + 逐条确认面板 + 错误原因（支持自由输入）
- 会话持久化：服务端存储，支持重命名/删除，输入页加载历史
- 八字排盘：符号计算 + LLM 推理 + SVG 图表
- 暗色主题 + thinking-orbs 加载动画（Canvas）

### 今日新增
- 账号系统：邮箱+密码注册/登录，JWT 鉴权（3 天有效期），零外部依赖，SQLite 存储
- 登录/注册后会话列表自动刷新 + 报告页登录态
- 未登录旧会话归属迁移（device fingerprint 匹配 + 孤儿认领弹窗）
- 付费层级权限控制：Free 5次/h → Pro 20次/h，tier 差异化限流（user_id key 隔离 8 个独立 action 桶），admin API 手动升降级，前端升级引导 toast
- 全站移动端适配：480px 手机断点全覆盖（6 个文件），表单/十二宫格/运限轴/聊天区均适配

### 待完成
- [ ] 支付接入（Stripe，已后置——先手动改库验证付费意愿）
- [ ] Pro 专属功能：大限流年深度解读

### P3 插件系统（Phase 1 已完成，ADR-006 已采纳）
- [x] Phase 1：PluginManager + 六态状态机 + manifest 校验（`4249f86`，116/116 测试）
- [x] Phase 2 依赖解析放 init 阶段 + 版本号比对（`fc84c4b` + `7c2e399`，47/47 纯函数 + 14 依赖集成断言）
    - 实现思路（hanako 提供）：init_all 对依赖图跑 Kahn 拓扑排序，依赖先 init；有环 → 进 error 态，错误信息列出环上插件名，不报"检测到循环依赖"；版本比对（>=1.0.0）与环检测同条落地
    - 边界：依赖 init 失败进 error 时，依赖方应同步 error 并注明"依赖 X 处于 error 态"，符合优雅降级（递归传播 `7c2e399` 已验证 A→B→C 链）
    - prerelease 语义：1.0.0-alpha 与 1.0.0 视为同版本（当前实现），记此约定不改实现
    - 版本表活性：init_all 版本表只喂 active 插件 + 本次 init 插件，error/disabled 不喂入
    - 复杂度：Kahn O(V*E)，插件量小无所谓，量大了换反向邻接表
- [x] rw_paths_extra 与 forbidden 冲突优先级（已定：deny-first，禁止永远胜出；validate_path 先查 forbidden 再查 allowed）
- [x] Sandbox 文件路径拦截接入 ToolRegistry.call()（方案A，路径参数标 format:path）✅ 本次落地
    - 归属关系（hanako 抛出）：ToolDef 加 sandbox_policy 字段（内建为 None 免拦），插件 init 时 PluginManager 注入 policy，call() 层只查 tool.sandbox_policy，不反向依赖 PluginManager（避免 orchestrator→plugin_manager 循环）
    - 注入时序（hanako 钉）：policy 注入在 register_fn 拿到 registered_tools 列表之后遍历注入，挂在 init() 后半段、ACTIVE 切换前，不与 register 前段打架；外层 init_all 拓扑序只定调用顺序，两层不冲突
    - 路径基准（hanako 钉）：validate_path 带 base_dir 参数（项目根唯一基准）；绝对路径先 relpath 归一，相对路径视为项目根相对（不做 relpath，避免对相对输入按 CWD 解析导致基准漂移）
    - 跨盘兑底（hanako 钉）：Windows 上 os.path.relpath 跨盘抛 ValueError（D:\ 与 C:\），try/except 兑住当越界拦截，不穿透到 call()
    - fallback 清理（hanako 发现）："共享知识库默认允许读取"冗余分支已删除（ro_paths 默认已有 knowledge_base/），knowledge_base_evil/x 不再被放行
    - 边界匹配通用规则（韩湘生补）：所有前缀匹配统一带分隔符边界（norm_path == path 或 startswith(path + os.sep)），data/cache_evil 不再漏拦
    - normpath 前提（hanako 补）：比较前声明条目与输入都先过 normpath（顺带消尾斜杠），声明 data/cache// 双斜杠也能命中
    - write 约定（本次落地）：format:path 参数的写意图用参数 schema 的 write: true 标注，默认读
    - 注入边界（本次落地）：只注入插件 register() 显式返回的 tools 列表；未声明的 Tool 保持 None 不拦（方案 A 声明式边界，硬约束挂 Phase 4 manifest 校验强制检查 parameters schema）
    - 归属校验（韩湘生审出，`b0d6f8c` 补漏）：声明列表是"关联/使用的工具"不是"拥有的工具"。ToolDef 加 owner 字段（None=未归属/"builtin"=内建/插件名=插件拥有），register_defaults() 末尾 freeze_builtins() 固化内建归属；注入时 owner 非 None 且非本插件 → 跳过 + warn。修掉两个洞：①后 init 插件声明他人工具名静默覆盖先 init 的 policy（拦截随 init 顺序漂）；②插件声明内建工具名把内建 None 免拦覆盖成插件 policy（内建功能被拦坏）。recovery 路径韩湘生补测：error → recovery → init 重新固化 owner + 重注入，幂等通
- [x] Phase 2 正式关闭（`b0d6f8c`）：依赖解析（拓扑序 + 递归传播 + 优雅降级）+ Sandbox 拦截（注入时序 + 归属固化 + 跨盘兜底 + 边界匹配）双线闭环，合龙成立
- [ ] Phase 3：热升级（upgrading → swap 原子切换）+ 卸载不丢状态
- [ ] Phase 4：外部插件发现（pip install / git clone → skills/ 目录）

### 检索器后端化（2026-08-01，embedding 上线）
- 后端抽象：BaseBackend + 注册表，`KB_BACKEND=lexical|embedding` 配置切换引擎，`retrieve_kb`/`retrieve_hits` 双出口一个引擎（签名不变，外部契约零变化）
- 登记表驱动：受理边界 = kb_whitelist.json 的 dispatch_allowlist（13 名），full 唯一被拒，未登记名显式报错不静默兜底（白名单 14 全集管存在性、受理 13 名单管 dispatch，两层各司其职）
- embedding 后端（`services/kb_embedding.py`）：BAAI/bge-small-zh-v1.5 本地模型（512 维），条目抽取对齐各 KB 答案单位（star_palace 星×宫格、classics pattern、hua 化曜×宫、fuzuo 辅星×宫、tiaohou 单行）；query 关键词分别编码取平均（整句拼接对"专名+槽位"查询区分度不足）；query/passage 编码对称（同一 encode、同一 normalize）
- 评测（dry_run_check）：三态验收线（文件级对→0 + 平均 1640 及格 / ~1KB 优良）、cff 16 对 graduated 跳过留档、粒度判定改动态（返回长度 vs 文件大小，不再硬编码 UNIT_MAP）、hits↔str 一致性第三道校验
- 对比结果（`evaluation_reports/backend_compare_20260801.md`）：命中 100% 持平，平均返回 2423→331B（↓86%），文件级 25→0，≥1.6KB 占比 100%→0%，一致性 87/87 双后端通过。验收线：文件级 0 PASS、平均 331B 优良
- 模型文件不入库（models/bge-small-zh-v1.5/ 已 gitignore），下载源 ModelScope（hf-mirror/直连超时或限速）；sentence-transformers>=2.7.0 入 requirements.txt
- 注入层（`services/kb_inject.py`）：检索 hits → join classics annotations sidecar → 分层呈现（原文/混合带引文+出处，转述按语不带引号，假出处结构上编不出来）；条件式裁剪：plate_ctx 与 hits 有交集才裁（防 zc_ 纯提问裁空），∩ 空回退全量宁多勿空；数据层一致性检查 40 格局 1 矛盾（紫微独坐：混合但无 quotes，渲染已防御降级）

### 部署
`https://thewher.pythonanywhere.com`（PythonAnywhere 免费账户）

### 技术栈
Python 3.11 / Flask / DeepSeek v4-pro / Vanilla JS / SQLite / iztro.js
