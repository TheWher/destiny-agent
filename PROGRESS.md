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
- [ ] Phase 2 待办（来自 hanako 审阅钉项，勿沉底）：
  - [ ] 依赖解析放 init 阶段 + 版本号比对（enable 只做结构校验，运行时解析已延迟）
    - 实现思路（hanako 提供）：init_all 对依赖图跑 Kahn 拓扑排序，依赖先 init；有环 → 进 error 态，错误信息列出环上插件名，不报"检测到循环依赖"；版本比对（>=1.0.0）与环检测同条落地
    - 边界：依赖 init 失败进 error 时，依赖方应同步 error 并注明"依赖 X 处于 error 态"，符合优雅降级
  - [ ] rw_paths_extra 与 forbidden 冲突优先级理清
  - [ ] Sandbox 文件路径拦截真正接入 ToolRegistry.call()（方案A，路径参数标 format:path）
    - 归属关系（hanako 抛出）：Tool→Plugin 映射缺失，插件注册 Tool 时需绑定 SandboxPolicy；内建 Tool 免拦（可信代码）
    - 落法建议：ToolDef 加 sandbox_policy 字段（内建为 None 免拦），插件 init 时 PluginManager 注入 policy，call() 层只查 tool.sandbox_policy，不反向依赖 PluginManager（避免 orchestrator→plugin_manager 循环）
    - 注入时序（hanako 钉）：policy 注入必须在 register_fn 拿到 registered_tools 列表之后遍历注入，挂在 init() 后半段、ACTIVE 切换前，不与 register 前段打架
    - 路径基准（hanako 钉）：validate_path 需统一基准，拦截前 normpath + 转相对项目根（建议 SandboxPolicy.validate_path 带 base_dir 参数），否则绝对路径被误拦、插件功能直接坏
    - 跨盘兑底（hanako 钉）：Windows 上 os.path.relpath 跨盘抛 ValueError（D:\ 与 C:\），归一化需 try/except 兑住，抛了当越界拦截，不穿透到 call()
    - fallback 清理（hanako 发现）：validate_path 末尾"共享知识库默认允许读取"分支 startswith("knowledge_base") 无斜杠边界，knowledge_base_evil/x 可被放行；ro_paths 默认已有 knowledge_base/，该分支冗余，base_dir 重构时一并删除
    - 边界匹配通用规则（韩湘生补）：所有前缀匹配统一带分隔符边界（norm_path == path 或 startswith(path + os.sep)），防止 rw_paths_extra 等不带尾斜杠条目时 data/cache_evil 被放行
    - normpath 前提（hanako 补）：比较前声明条目与输入都先过 normpath（顺带消掉尾斜杠），再按边界匹配比较；否则声明 data/cache/ 时 path + os.sep 拼出 data/cache// 双斜杠，匹配失效
    - 协调点：依赖解析（外层，init_all 拓扑序）与 policy 注入（内层，单个插件 init 内）不冲突，外层定调用顺序，内层各自注入
    - 纯函数已落地 `fc84c4b`：resolve_dependencies(dep_graph, available_versions) -> ResolveResult，47/47 测试
    - prerelease 语义（hanako 审阅）：1.0.0-alpha 与 1.0.0 视为同版本（当前实现）；严格 SemVer 下 prerelease 只匹配 prerelease 约束，内部插件生态影响有限，记此约定不改实现
    - 版本表活性（hanako 审阅）：available_versions 是存在性证据非活性证据；init_all 接入时版本表来源限定为已 active 插件，error/disabled 态不喂入，与依赖 error 同步传播相接
    - 接入要求（hanako 钉）：接 init_all 时状态校验 + 版本表来源两件事不可漏
    - 复杂度：Kahn O(V*E)，插件量小无所谓，量大了换反向邻接表
- [ ] Phase 3：热升级（upgrading → swap 原子切换）+ 卸载不丢状态
- [ ] Phase 4：外部插件发现（pip install / git clone → skills/ 目录）

### 部署
`https://thewher.pythonanywhere.com`（PythonAnywhere 免费账户）

### 技术栈
Python 3.11 / Flask / DeepSeek v4-pro / Vanilla JS / SQLite / iztro.js
