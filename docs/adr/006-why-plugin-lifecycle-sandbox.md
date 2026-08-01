# ADR-006: 插件系统设计——生命周期、沙箱隔离与版本兼容

**日期**: 2026-08-01
**状态**: 已采纳 (Accepted)

## 背景

编排层（ADR-001 的两层架构扩展）已完成 ToolRegistry + IntentRouter + CapabilityRegistry + FunctionCallingLoop + SkillRegistry 全链路。当前 Skill 注册是硬编码的 `register_defaults()`，缺乏外部插件发现、动态加载和卸载能力。

P3 插件系统的目标是：允许第三方（或项目内不同模块）以独立包形式发布 Skill，运行时动态加载、升级、卸载，不影响主 Cycle 稳定性。

## 参考基线

DeepTutor 的插件系统（[Issue #264 审计](https://github.com/HKUDS/DeepTutor/issues/264)）：
- **已有的**: manifest.yaml 驱动加载、opt-in + 优雅降级、Docker sidecar 沙箱
- **缺失的**: 版本化 manifest（SemVer 契约）、兼容性校验、热加载/卸载不丢状态、生命周期状态机（仅 boolean enable）

我们的设计目标：在 DeepTutor 的基础上补全它缺失的四个维度，同时保持它们的优雅降级哲学。

## 决策

### 1. 插件生命周期状态机

DeepTutor 只有两态（enabled/disabled），我们采用六态：

```
                 register()
  [absent]  ────────────────→  [registered]
                                  │
                          enable() │  ← 校验 manifest + 依赖
                                  ↓
                              [enabled]
                                  │
                          init()   │  ← 加载模块、注册 Tool/Skill
                                  ↓
   [error]  ←── 初始化失败 ──  [active]  ←── 正常运行
       ↑    
       │    recovery() ──→  [enabled]   ← 重走 enable() 校验（幂等，用于临时故障恢复）
       │
       │    disable()  ──→  [disabled]  ← 放弃重试，手动 disable 后再走注册路径
       │    
       │                 reload()│  ← 加载新版、切换引用
       │                         ↓
       │                     [upgrading]
       │                         │
       │             swap()      │  ← 原子切换：旧引用 → 新引用
       │                         ↓
       │                     [active]（新版）
       │
       └── 任何状态异常 ──→  [error]
                                  │
                          disable()│
                                  ↓
                             [disabled]
                                  │
                          unregister()
                                  ↓
                             [absent]
```

关键属性：

- **registered → enabled → active** 是正向激活路径，分三步而非一步到位，给校验和初始化留独立阶段
- **upgrading** 是过渡态，`swap()` 原子切换到新版
- **error** 是吸收态，任何状态异常都到此。恢复路径两条：
  - `error → enabled`（recovery）：重走 `enable()` 校验，用于临时故障恢复，幂等可重试
  - `error → disabled`：放弃重试，手动 disable 后再走完整注册路径
- **error 态下已注册的 Tool/Skill**：标记 stale 但保留在 Registry 中（不响应新请求），避免其他插件报"依赖缺失"。这与 upgrading 态的旧引用策略一致
- **disabled** 保留 Tool/Skill 注册但不路由新请求
- 正在执行的 cycle 不受 disable/unregister 影响，等完成后才释放引用

### 2. 优雅降级

继承 DeepTutor 的核心哲学并强化：

```
第三方插件任何异常 → 捕获 → 日志 → 主 Cycle 继续

具体场景：
- Plugin init 抛异常     → 标记 error，不阻塞其他插件加载
- Tool 执行抛异常        → 返回 ErrorResult，LLM 收到错误而非崩溃
- Function Calling 循环中 → 记录 tool_error，循环继续，不中断
- 插件依赖缺失           → 标记 error，SkillRegistry 跳过该插件
- 网络超时               → 超时熔断，tool 返回 "调用超时"
```

这是硬约束：**插件层的任何故障都不应传播到编排层，更不应传播到 LLM 对话流**。

### 3. 沙箱隔离

我们的场景比 DeepTutor 简单（无代码执行需求），采用文件系统 + 网络两层限制：

**文件系统**

```
插件可读写: sessions/{plugin_name}/     ← 插件私有数据
插件只读:   knowledge_base/             ← 共享知识库
插件禁访:   sessions/（其他用户目录）
           data/
           config.local.py              ← API key 等敏感配置
           .git/
```

通过 `SandboxPolicy` 声明，路径校验在 `ToolRegistry.call()` 层统一拦截（方案A）：
- 调用前校验参数中的文件路径是否在 SandboxPolicy 允许的范围内
- 路径参数在 Tool Schema 的 `parameters.properties` 中标注 `"format": "path"` 来区分，不需要猜语义
- 不改 Tool 函数内部代码，拦截对 Tool 完全透明

```python
class SandboxPolicy:
    plugin_name: str
    rw_paths: list[str]      # 默认 [f"sessions/{plugin_name}/"]
    ro_paths: list[str]      # 默认 ["knowledge_base/"]
    forbidden_paths: list[str]  # 默认 ["data/", "config.local.py", ".git/"]
```

**网络**

- 默认：禁出站
- 需要联网的插件在 `manifest.yaml` 中声明 `requires_network: true`
- 声明后 PluginManager 注入 `httpx` client，统一走代理和限速
- 不声明的插件：尝试网络调用 → 抛出 `NetworkNotAllowedError`

### 4. 版本兼容契约

**manifest.yaml 必须字段**:

```yaml
name: "bazi_extended"
version: "1.2.0"           # SemVer
api_version: "1"           # 编排层 API 版本，major 不兼容
requires:
  plugins:
    bazi_basics: ">=1.0.0"
  python: ">=3.10"
capabilities:
  - bazi_advanced_analysis
tools:
  - wuxing_extended
  - shensha_analysis
sandbox:
  requires_network: false
  rw_paths_extra: []
```

**版本冲突处理**:

| 场景 | 行为 |
|------|------|
| `api_version` 不兼容 | 拒绝加载，标记 error |
| 依赖插件版本不满足 | 拒绝加载，标记 error |
| 同名 Skill 新旧并存 | upgrading 过渡态，swap 后旧引用释放 |
| 旧版本 Tool Schema 变更 | 视为 breaking change（major bump） |
| 旧版本 Tool 行为变更（输出语义不同） | 视为 breaking change（major bump） |
| 仅新增可选参数 | minor bump，向后兼容 |

**命理场景特殊性**: 判定"分析结论差异算不算 breaking change"的规则：
- 算法变更导致同一命盘输出不同结论 → **算 breaking**（major bump）
- 仅新增分析维度（原有结论不变）→ minor bump
- 仅修复明显错误 → patch bump

**版本校验的可选增强——快照测试**（不阻塞 Phase 1）:

manifest.yaml 中的 `tests` 可选字段：

```yaml
tests:
  snapshot_dir: "tests/snapshots/"
  golden_inputs:
    - year: 2005; month: 8; day: 19; hour: 1; gender: "男"
```

PluginManager 在 `enable()` 阶段运行快照测试：对 `golden_inputs` 执行 Tool → 对比上一次的 snapshot → 有差异 → 如果是 major bump 则通过（预期 breaking），minor/patch bump 则阻断（异常变更）。不强制但有的话校验可靠度上一个数量级。Phase 2 落地。

### 5. manifest.yaml 驱动加载

继承 DeepTutor 的 loader 模式，与现有 SkillDef 对齐：

```
插件包结构：
my_skill/
├── manifest.yaml          ← 元数据 + 依赖 + sandbox 声明
├── __init__.py            ← 导出 register(registry) 函数
├── capability.py          ← CapabilityDef 子类
└── tools.py               ← Tool 函数定义（可选）
```

加载流程：

```
1. PluginManager.discover("skills/")  → 扫描子目录找 manifest.yaml
2. 对每个 manifest:
   a. 校验版本兼容（api_version）
   b. 检查依赖（requires.plugins 是否满足）
   c. 校验 SandboxPolicy
   d. import 插件模块
   e. 调用 register(registry) → 插件自行注册 Tool / Skill / Capability
3. PluginManager 维护已加载插件列表 + 状态
```

## 代价

- 六态状态机增加了 PluginManager 的复杂度（当前 SkillRegistry 无状态管理）
- 文件路径校验中间件需要拦截所有 Tool 的文件 I/O 调用
- `upgrading → swap` 原子切换在 Python 中需要引用计数管理（旧引用在 cycle 执行完前不能释放）
- manifest 校验逻辑需要持续维护，与 SkillDef 的变化同步

## 为什么不

- **不用 DeepTutor 的 boolean enable**: 缺少中间态无法处理 upgrade/unload/error 场景，Issue #264 已经验证了这个缺陷
- **不用 Docker sidecar 沙箱**: 我们的插件是 Python 模块导入，不是独立进程，Docker 隔离过重且启动开销大。文件路径拦截器更轻量
- **不做 AST 级 import 白名单**: 信任模型不同——我们的插件来自可信源（项目内或经过审核的第三方），不需要限制 Python 标准库调用，重点是数据隔离而非代码隔离

## 与其他 ADR 的关系

- **ADR-001** (符号-LLM 分层): 插件系统中的 Tool 注册直接扩展符号计算层
- **ADR-002** (JSON KB): 插件的知识库访问受 SandboxPolicy 的 `ro_paths` 控制
- 编排层 (ToolRegistry + SkillRegistry + FunctionCallingLoop) 是插件系统的直接宿主

## 实现阶段

1. **Phase 1**: PluginManager + 六态状态机 + manifest 校验 → 静态插件加载
2. **Phase 2**: SandboxPolicy + 文件路径拦截器 + 网络管控
3. **Phase 3**: 热升级（upgrading → swap 原子切换）+ 卸载不丢状态
4. **Phase 4**: 外部插件发现（pip install / git clone → skills/ 目录）

Phase 1 即可满足 P3 的基本需求。Phase 2-4 按需推进。
