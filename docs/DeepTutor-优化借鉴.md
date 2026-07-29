# DeepTutor 架构借鉴：紫微项目优化笔记

> 基于 HKUDS/DeepTutor 的 agent-native 架构分析，对照 Destiny_agent 现状，提取可借鉴的优化方向。
>
> 来源：[AGENTS.md](https://github.com/HKUDS/DeepTutor/blob/main/AGENTS.md) + [Issue #264 架构审计](https://github.com/HKUDS/DeepTutor/issues/264)
>
> 整理日期：2026-07-28

---

## 一、现状对照

| 维度 | DeepTutor | Destiny_agent 现状 | 差距 |
|------|-----------|-------------------|------|
| **入口统一** | ChatOrchestrator 统一路由 | routes/ 下蓝图分派 + 各 service 独立调用 | 无统一编排层 |
| **工具层** | ToolRegistry，6 个工具，LLM 按需调用 | 排盘/五行/十神等计算分散在 bazi_calculator + utils | 未注册为 LLM 可调用工具 |
| **能力层** | CapabilityRegistry，3 个多阶段流水线 | 9 级推理链 / 10 步推理链硬编码在 Prompt 内 | 流程写死在 Prompt 而非代码层 |
| **记忆系统** | 跨会话持久化用户画像 | 会话磁盘持久化，无用户维度画像 | 缺少学习画像 |
| **技能格式** | SKILL.md（YAML frontmatter + Markdown） | Agent .md 文件有 YAML frontmatter，但不符合 SKILL.md 规范 | 格式接近但未标准化 |
| **插件系统** | Playground Plugins（manifest.yaml + loader） | skills/ 下仅 code-discipline | 无插件发现机制 |
| **多 Agent 协作** | consult_subagent 在对话中调用其他 Agent | 紫微自动排八字 + 八字独立分析注入紫微 Prompt | 协作方式较耦合 |
| **CLI** | Typer CLI，所有功能命令行可操作 | 无 CLI | 缺少批量测试/调试入口 |
| **知识库检索** | RAG 管道 + 知识库创建 + 多引擎切换 | 16 个 JSON 文件直接加载拼接进 Prompt | 无语义检索，全量拼接 |

---

## 二、核心借鉴：两层插件模型 → 分析编排层

### 2.1 DeepTutor 的设计

```
ChatOrchestrator（统一入口）
    ├── ToolRegistry（Level 1：轻量工具，LLM 按需调用）
    │   ├── rag           → 知识库检索
    │   ├── web_search    → 网页搜索
    │   ├── code_execution → 沙箱代码执行
    │   ├── reason        → 深度推理
    │   ├── brainstorm    → 头脑风暴
    │   └── paper_search  → 论文搜索
    │
    └── CapabilityRegistry（Level 2：多阶段流水线，接管整个回合）
        ├── chat          → responding（默认，工具增强）
        ├── deep_solve    → planning → reasoning → writing
        └── deep_question → ideation → evaluation → generation → validation
```

设计哲学：**Tool 是"词"，Capability 是"句子"。LLM 自己决定用哪些词造句。**

### 2.2 对 Destiny_agent 的映射

```
AnalysisOrchestrator（新增，统一分析编排）
    ├── ToolRegistry
    │   ├── paipan_bazi      → 八字排盘（bazi_calculator）
    │   ├── paipan_ziwei     → 紫微排盘（ziwei_calculator）
    │   ├── wuxing_query     → 五行查询（十神/纳音/藏干/神煞）
    │   ├── star_lookup      → 星曜查询（亮度/四化/辅煞/格局）
    │   ├── liunian_calc     → 流年/大运推算
    │   ├── kb_retrieve      → 知识库语义检索（替代全量拼接）
    │   └── chart_render     → 图表生成
    │
    └── CapabilityRegistry
        ├── bazi_analysis    → 排盘 → 调候 → 格局 → 旺衰 → 病药 → 十神 → 刑冲 → 神煞 → 大运流年 → 交叉验证
        ├── ziwei_analysis   → 排盘 → 命宫定位 → 星曜分布 → 四化飞星 → 格局判定 → 宫位交互 → 大限流年 → 叠盘分析
        ├── verify_panel     → 生成验证问题 → 逐条核对 → 错误标记 → 修正重推
        └── cross_validate   → 八字排盘 → 独立分析 → 结论比对 → 差异注入紫微 Prompt
```

**这层改造的收益**：当前推理链全部写在 Prompt 中（9 级 / 10 步），每次分析都要把完整推理链塞进 system prompt。如果剥离到 Capability 流水线层，LLM 的 system prompt 可以大幅瘦身，推理步骤由代码控制执行顺序，LLM 只负责每步的内容生成。

### 2.3 实施建议

**不改动现有路由层（最小侵入）**。在 `services/` 下新增 `orchestrator.py`，现有 `routes/bazi.py` 和 `routes/ziwei.py` 的 analyze 端点逐步迁移到调用 orchestrator 而不是直接调 service。

```
services/
├── __init__.py
├── llm_client.py           # 保留，底层 API 调用
├── kb_loader.py            # 保留，知识库加载
├── bazi_analysis.py        # 逐步废弃，迁移到 orchestrator
├── ziwei_analysis.py       # 逐步废弃，迁移到 orchestrator
├── orchestrator.py         # 新增：统一分析编排
├── tools/                  # 新增：工具注册
│   ├── __init__.py
│   ├── registry.py         # ToolRegistry
│   ├── paipan_bazi.py      # 八字排盘工具
│   ├── paipan_ziwei.py     # 紫微排盘工具
│   ├── kb_retrieve.py      # 知识库检索工具
│   └── star_lookup.py      # 星曜查询工具
└── capabilities/           # 新增：能力注册
    ├── __init__.py
    ├── registry.py         # CapabilityRegistry
    ├── bazi_pipeline.py    # 八字 9 级推理链
    ├── ziwei_pipeline.py   # 紫微 10 步推理链
    └── verify_pipeline.py  # 验盘流水线
```

---

## 三、知识库检索（替代全量拼接）

### 3.1 现状问题

当前 `_load_system_prompt()` 会把多个 JSON 知识库文件全量拼接进 system prompt：

```python
# bazi_analysis.py
kb = _load_knowledge_base(include_extended=False)
if kb:
    content += kb  # 直接拼接 ~30KB 基础知识

# ziwei_analysis.py
stars_kb = _load_json_kb("ziwei_stars.json")
star_palace = _load_json_kb("ziwei_star_palace.json")
# 拼接 146KB 知识库
```

问题：token 浪费严重，LLM 在不需要的知识条目上消耗注意力。

### 3.2 DeepTutor 的做法

DeepTutor 的 `rag` 工具是一个**按需检索**的工具：LLM 分析时，当它需要某条知识，调用 `rag` 工具去知识库检索相关片段，只返回命中的内容。同时支持多检索引擎切换（LightRAG Server、FAISS、原生向量）。

### 3.3 实施建议

**阶段一：低成本方案（不改 Prompt，改加载方式）**

在 `systems/kb_loader.py` 中增加 `retrieve_kb(query, kb_name)` 函数，基于关键词匹配做轻量检索：

```python
def retrieve_kb(query: str, kb_name: str, top_k: int = 5) -> str:
    """从指定知识库中检索与 query 最相关的条目"""
    kb = _load_json_kb(kb_name)
    # 用 query 中的关键词（星曜名、天干地支、格局名等）匹配 key
    # 返回 top_k 条最相关的内容，而非全量
```

然后在 system prompt 末尾改为按需注入：

```python
# 不再全量拼接，而是在 prompt 末尾加提示
content += "\n## 工具使用说明\n"
content += "当你需要查询特定星曜/格局/神煞的详细信息时，系统会自动检索知识库提供给你。"
content += "你只需正常分析，无需手动触发检索。"
```

**阶段二：向量检索（后续升级）**

引入 embedding + FAISS/ChromaDB，实现真正的语义检索。DeepTutor 支持 LightRAG Server 和 FAISS 两种后端，可以参考其 `services/rag/` 的实现。

---

## 四、持久化用户记忆（命理画像）

### 4.1 DeepTutor 的做法

DeepTutor 的 "Persistent Memory" 在不同功能之间共享用户画像：

> builds a living profile of you: what you've studied, how you learn, and where you're heading. Shared across all features and TutorBots, it gets sharper with every interaction.

### 4.2 对紫微项目的映射

当前项目有会话持久化（sessions/），但没有用户维度的持久化记忆。可以构建**用户命理画像**：

```json
{
  "user_id": "xxx",
  "bazi_profile": {
    "rizhu": "乙木",
    "pattern_summary": "偏财格，身弱喜印比",
    "key_signals": ["巳亥冲", "伤官生财"],
    "verified_facts": ["2018年换工作", "2023年购房"],
    "analysis_history": [
      {"timestamp": "...", "focus": "流年2026", "key_findings": "..."}
    ]
  },
  "ziwei_profile": {
    "ming_gong": "天相同宫",
    "pattern": "府相朝垣格",
    "key_interactions": ["太阴化禄入夫妻", "武曲化权守财帛"],
    "verified_facts": [...]
  },
  "cross_validations": [
    {"bazi_finding": "...", "ziwei_finding": "...", "agreement": true}
  ]
}
```

**收益**：
- 老用户回访时，"上次你问的 XX 格局，这次流年又触发了"——这种跨会话连续性目前是缺失的
- 验盘反馈可以绑定到画像，形成"这个用户验证过的事实库"，后续分析可以直接引用
- 交叉验证的结论可以持久化，不会每次分析都重新计算

### 4.3 实施建议

在 `services/` 下新增 `memory.py`：

```python
class UserMemory:
    def load(uid) -> UserProfile
    def save(uid, profile)
    def update_fact(uid, fact)  # 追加已验证事实
    def get_analysis_context(uid) -> str  # 输出给 LLM 的上下文片段
```

每次分析结束后，将分析结论（尤其是用户核实的）追加到 memory 中。下次分析前，从 memory 读取相关上下文注入 system prompt。

---

## 五、技能文件格式标准化

### 5.1 现状对照

| | DeepTutor SKILL.md | Destiny_agent Agent 定义 |
|---|---|---|
| **格式** | YAML frontmatter + Markdown | YAML frontmatter + Markdown |
| **位置** | 技能目录下 SKILL.md | .claude/agents/*.md |
| **发现机制** | EduHub / ClawHub 注册表 | 硬编码路径 |
| **元数据** | name, description, trigger, tools 权限 | 无标准化元数据 |

### 5.2 实施建议

将现有 Agent 定义移到 `skills/` 下，统一为 SKILL.md 格式：

```
skills/
├── code-discipline/
│   └── SKILL.md              # 已有
├── bazi-master/
│   ├── SKILL.md              # 从 .claude/agents/traditional-bazi-master.md 迁移
│   └── references/
│       ├── tiaohou.json
│       └── signal_rules.json
├── ziwei-master/
│   ├── SKILL.md              # 从 .claude/agents/ziwei-master.md 迁移
│   └── references/
│       ├── stars.json
│       ├── palaces.json
│       └── patterns.json
└── verify-specialist/
    └── SKILL.md              # 验盘专用 Agent
```

增加 `skill_loader.py` 实现技能发现和加载，类似 DeepTutor 的 plugin loader。

---

## 六、CLI 入口（批量测试与调试）

### 6.1 DeepTutor 的 CLI 设计

```bash
deeptutor run chat "Explain Fourier transform"       # 单次分析
deeptutor run deep_solve "Solve x^2=4" -t rag --kb my-kb  # 带工具的能力
deeptutor chat                                        # 交互 REPL
deeptutor kb create my-kb --doc textbook.pdf          # 知识库管理
deeptutor memory show                                 # 记忆查询
```

### 6.2 对紫微项目的价值

当前测试只能跑 `test_paipan.py` 和 `test_ziwei.py`，没有命令行入口来：
- 快速分析一批命盘（回归测试）
- 切换不同 Agent Prompt 版本对比效果
- 查看验盘反馈聚合报告
- 管理会话和知识库

### 6.3 实施建议

新增 `cli.py` 作为项目入口：

```bash
# 单次分析
python cli.py analyze bazi --year 2005 --month 8 --day 19 --hour 1 --gender 男

# 批量回归测试
python cli.py batch-test --cases cases/verify_set.json --agent bazi-master

# Agent 版本对比
python cli.py compare --case "乙木命造" --agent-a bazi-master-v2 --agent-b bazi-master-v3

# 会话管理
python cli.py sessions list
python cli.py sessions show <session_id>

# 验盘报告
python cli.py verify-report --since 2026-07-01

# 知识库管理
python cli.py kb list
python cli.py kb stats ziwei_stars.json
```

---

## 七、扩展性：插件系统骨架

### 7.1 DeepTutor 的插件模型

```
deeptutor/plugins/
├── loader.py              # 插件发现（从 manifest.yaml）
└── deep_research/         # 一个插件示例
```

插件通过 `manifest.yaml` 声明身份、依赖、入口点，loader 自动发现和注册。

### 7.2 对紫微项目的映射

当前命理分析只支持梁湘润体系（八字）和三合中州派（紫微）。但不同流派（子平、盲派、新派 / 飞星派、中州派、四化派）的分析方法差异很大。如果未来要支持多流派，插件系统可以让每个流派作为一个独立 skill 包，动态加载。

### 7.3 实施建议

**现在不需要完整做，但预留骨架**。在 `skills/` 下统一用 SKILL.md 格式存放所有 Agent 定义，在 `services/skill_loader.py` 中实现技能扫描和注册。这样后续加新流派时，只需在 `skills/` 下加一个目录，无需改动核心代码。

---

## 八、优化优先级矩阵

| 优先级 | 优化项 | 改动量 | 收益 | 风险 |
|--------|--------|--------|------|------|
| **P0** | 知识库按需检索（替代全量拼接） | 中 | 高：token 节省 40-60%，分析质量提升 | 低：不改 Prompt 结构 |
| **P0** | CLI 入口（批量测试 + 调试） | 小 | 高：测试效率飞跃 | 无 |
| **P1** | 技能文件标准化 + skill_loader | 中 | 中：可维护性 + 扩展性基础 | 低：现有路径兼容即可 |
| **P1** | 分析编排层（Tool/Capability 注册） | 大 | 高：架构升级，为后续铺路 | 中：需要渐进迁移 |
| **P2** | 持久化用户记忆（命理画像） | 中 | 中：用户体验提升 | 低：独立模块 |
| **P3** | 插件系统 + 多流派支持 | 大 | 高：产品差异化 | 中：需前期骨架就绪 |

---

## 九、Issue #264 的教训

社区对 DeepTutor 的审计提出了几条通用教训，对紫微项目同样适用：

1. **概念数量已是复杂度**。不要为了一致性无限加抽象层。每加一层（Tool、Capability、Plugin、Memory），先问"这层解决了什么当前已有的问题"。不为未来的问题加现在的层。

2. **扩展点需要显式约定**。如果紫微项目要加入插件系统或技能注册，一开始就写清楚"什么时候该用 Tool，什么时候该用 Capability，什么时候该用 Skill"，而不是通过隐式代码约定。

3. **写一份面向维护者的架构文档**。当前 AGENTS.md 写得很好，但偏操作手册。可以加一份架构决策记录（ADR）：
   - 为什么符号计算和 LLM 推理要分两层？
   - 为什么知识库用 JSON 而非数据库？
   - 推理链是放在 Prompt 中还是代码中？

---

## 十、参考资源

- [DeepTutor AGENTS.md](https://github.com/HKUDS/DeepTutor/blob/main/AGENTS.md)
- [DeepTutor Issue #264 架构审计](https://github.com/HKUDS/DeepTutor/issues/264)
- [DeepTutor 论文 (arXiv:2604.26962)](https://arxiv.org/abs/2604.26962)
- [DeepTutor 官网文档](https://hkuds.github.io/DeepTutor/)
- [nanobot — DeepTutor 的 agent 运行时](https://github.com/HKUDS/nanobot)
