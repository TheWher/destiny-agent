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
- [ ] Phase 3：热升级（upgrading → swap 原子切换）+ 卸载不丢状态
- [ ] Phase 4：外部插件发现（pip install / git clone → skills/ 目录）

### 部署
`https://thewher.pythonanywhere.com`（PythonAnywhere 免费账户）

### 技术栈
Python 3.11 / Flask / DeepSeek v4-pro / Vanilla JS / SQLite / iztro.js
