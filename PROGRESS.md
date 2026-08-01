## Destiny_agent 进度 （2026-07-31）

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
    - 归属校验（韩湘生审出，`06b9518` 补漏）：声明列表是"关联/使用的工具"不是"拥有的工具"。ToolDef 加 owner 字段（None=未归属/"builtin"=内建/插件名=插件拥有），register_defaults() 末尾 freeze_builtins() 固化内建归属；注入时 owner 非 None 且非本插件 → 跳过 + warn。修掉两个洞：①后 init 插件声明他人工具名静默覆盖先 init 的 policy（拦截随 init 顺序漂）；②插件声明内建工具名把内建 None 免拦覆盖成插件 policy（内建功能被拦坏）
- [ ] Phase 3：热升级（upgrading → swap 原子切换）+ 卸载不丢状态
- [ ] Phase 4：外部插件发现（pip install / git clone → skills/ 目录）

### 部署
`https://thewher.pythonanywhere.com`（PythonAnywhere 免费账户）

### 技术栈
Python 3.11 / Flask / DeepSeek v4-pro / Vanilla JS / SQLite / iztro.js
