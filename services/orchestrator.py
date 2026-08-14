#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""统一分析编排层

设计哲学（借鉴 DeepTutor 两层插件模型）：
  - Tool 是"词"：轻量计算函数，LLM 按需调用，无状态
  - Capability 是"句子"：多阶段流水线，接管整个分析回合
  - LLM 自己决定用哪些"词"造"句"

最小侵入原则：
  - 不改动现有 routes/ 和 services/*_analysis.py
  - 作为新模块独立存在，现有代码渐进迁移
"""

import json
import os
import re
import time
import traceback
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from services.plugin_manager import SandboxPolicy

# ── 类型定义 ─────────────────────────────────────────────

_META_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "knowledge_base", "obsidian_meta")
_META_CACHE = None


def _obsidian_meta_tags(rel_file: str) -> dict:
    """读取 Obsidian 素材的结构化语义标签（文体/结局梯度/引文链）。

    数据源：knowledge_base/obsidian_meta/*.json（mose 语义资产）：
      - style_tags.json：三层六类文体规格（含章节→文体映射）
      - outcome_grades.json：结局词梯度 L1-L4 定义
      - quote_chains.json：跨卷引文链（去重依据）
    返回：{styles, outcome_grades, quote_chains}；文件缺失时返回空 dict。
    """
    global _META_CACHE
    if _META_CACHE is None:
        cache = {}
        if os.path.isdir(_META_DIR):
            for fn in os.listdir(_META_DIR):
                if not fn.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(_META_DIR, fn), encoding="utf-8") as f:
                        cache[fn] = json.load(f)
                except Exception:
                    cache[fn] = {}
        _META_CACHE = cache
    if not _META_CACHE:
        return {}

    out = {}
    # 1) 文体：从 style_tags 提取 章节→文体 映射（文件级标注：该文件涉及的文体集合）
    st = _META_CACHE.get("style_tags.json", {})
    chapter_style = {}
    for _lname, lv in (st.get("分层") or {}).items():
        for sname, sv in (lv.get("子类") or {}).items():
            for ch in (sv.get("章节") or []):
                chapter_style[ch] = sname
    base = os.path.basename(rel_file)
    styles = []
    for ch, st_name in chapter_style.items():
        if ch in base or ch in _file_title_hint(base, st):
            if st_name not in styles:
                styles.append(st_name)
    if styles:
        out["styles"] = styles

    # 2) 结局词梯度表（供解读 Agent 对照断语严重度）
    og = _META_CACHE.get("outcome_grades.json", {})
    grades = og.get("梯度") or {}
    if grades:
        out["outcome_grades"] = {
            k: {"描述": v.get("描述", ""), "词": v.get("词", [])[:5]}
            for k, v in grades.items()
        }

    # 3) 引文链主题（跨卷同源提示，去重依据）
    qc = _META_CACHE.get("quote_chains.json", {})
    chains = qc.get("链") or []
    if chains:
        out["quote_chains"] = [
            {"主题": c.get("主题"), "关系": c.get("关系")} for c in chains
        ]
    return out


def _file_title_hint(base: str, style_tags: dict) -> str:
    """从文件名提取章节线索（如 juan1/卷之一 等），辅助文体匹配。"""
    hints = []
    if "卷之一" in base or "juan1" in base:
        hints.append("卷之一")
    if "卷之二" in base or "juan2" in base:
        hints.append("卷之二")
    if "卷之三" in base or "juan3" in base:
        hints.append("卷之三")
    if "卷之四" in base or "juan4" in base:
        hints.append("卷之四")
    if "卷之五" in base or "juan5" in base:
        hints.append("卷之五")
    if "命圖" in base or "mingtu" in base:
        hints.append("命圖")
    return "|".join(hints)


@dataclass
class ToolDef:
    """Tool 注册定义"""
    name: str
    description: str                          # LLM 可读的功能描述
    fn: Callable[..., dict]                   # 实际执行函数
    parameters: dict = field(default_factory=dict)  # 参数 schema（JSON Schema 格式）
    category: str = "general"                 # 分类：paipan / query / render / external
    sandbox_policy: Optional["SandboxPolicy"] = None  # 沙箱策略：内建 Tool 为 None（可信免拦），
                                                      # 插件 init 时由 PluginManager 注入
    owner: Optional[str] = None               # 归属：None=未归属；"builtin"=内建；插件名=插件拥有
                                                      # 注入时校验归属，避免声明列表被当所有权用

@dataclass
class CapabilityDef:
    """Capability 注册定义"""
    name: str
    description: str                          # 用自然语言描述的流水线步骤
    fn: Callable[..., dict]                   # 执行函数
    stages: list[str] = field(default_factory=list)  # 流水线阶段名列表
    category: str = "analysis"                # 分类：analysis / verify / cross
    tools: list[str] = field(default_factory=list)   # 关联的 Tool 名列表（用于动态注入）

@dataclass
class ToolResult:
    """Tool 执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    elapsed_ms: float = 0.0

@dataclass
class CapabilityResult:
    """Capability 执行结果"""
    success: bool
    result: Any = None                        # 流水线最终输出
    stage_results: dict[str, Any] = field(default_factory=dict)  # 各阶段输出
    error: Optional[str] = None
    elapsed_ms: float = 0.0
    usage: dict = field(default_factory=dict) # token usage
    traceback: Optional[str] = None           # 内部调试用异常堆栈，勿透出给用户




# ── 注册表 ──────────────────────────────────────────────

class ToolRegistry:
    """Level 1：轻量工具注册表

    工具是无状态的纯函数包装，供 LLM 在分析过程中按需调用。
    所有工具必须返回 dict，包含 success 字段。
    """

    def __init__(self, base_dir: Optional[str] = None):
        """base_dir: 沙箱路径校验的唯一基准（项目根），默认取本文件上级的上级目录"""
        self.base_dir = base_dir or os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        self._tools: dict[str, ToolDef] = {}

    def register(self, tool: ToolDef) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolDef]:
        return self._tools.get(name)

    def freeze_builtins(self) -> None:
        """把当前已注册的 Tool 固化归属为内建（builtin）

        register_defaults() 末尾调用一次（幂等保护由 _defaults_registered 保证）。
        之后插件 init 注入 policy 时，内建工具名不再会被插件声明列表覆盖——
        归属证据在注册时就固化，注入时对不上就跳过。
        """
        for tool in self._tools.values():
            if tool.owner is None:
                tool.owner = "builtin"

    def list_all(self) -> list[ToolDef]:
        return list(self._tools.values())

    def list_by_category(self, category: str) -> list[ToolDef]:
        return [t for t in self._tools.values() if t.category == category]

    def call(self, name: str, **kwargs) -> ToolResult:
        """执行一个已注册的工具

        Phase 2 Sandbox：插件 Tool（sandbox_policy 非 None）在 call() 层统一拦截
        format:path 参数；内建 Tool（policy 为 None）视为可信代码直接放行。
        """
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{name}' not found")

        # Phase 2 Sandbox：带 policy 的插件 Tool 先过路径拦截
        if tool.sandbox_policy is not None:
            denied = self._enforce_sandbox(tool, kwargs)
            if denied:
                return ToolResult(success=False, error=denied)

        t0 = time.perf_counter()
        try:
            data = tool.fn(**kwargs)
            elapsed = (time.perf_counter() - t0) * 1000
            if isinstance(data, dict) and not data.get("success", True):
                return ToolResult(success=False, error=data.get("error", "Unknown"), elapsed_ms=elapsed)
            return ToolResult(success=True, data=data, elapsed_ms=elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            return ToolResult(success=False, error=f"{e}", elapsed_ms=elapsed)

    def _enforce_sandbox(self, tool: ToolDef, kwargs: dict) -> Optional[str]:
        """校验插件 Tool 的 format:path 参数（方案 A：声明式拦截）

        约定（PROGRESS.md Phase 2）：
        - parameters.properties 里 format:path 标注路径参数，write: true 标注写意图（默认读）
        - 只拦显式标注的参数；未标注的不受拦（方案 A 固有边界，硬约束挂 Phase 4 manifest 校验）
        - 基准：self.base_dir（项目根）唯一基准，validate_path 内部先 relpath 归一

        Returns:
            违规时返回错误描述，全部通过返回 None
        """
        policy = tool.sandbox_policy
        props = (tool.parameters or {}).get("properties", {})
        for param_name, schema in props.items():
            if not isinstance(schema, dict) or schema.get("format") != "path":
                continue
            if param_name not in kwargs or kwargs[param_name] is None:
                continue
            is_write = bool(schema.get("write", False))
            value = str(kwargs[param_name])
            if not policy.validate_path(value, is_write=is_write, base_dir=self.base_dir):
                action = "写入" if is_write else "读取"
                return (f"沙箱拦截: 工具 '{tool.name}' 参数 '{param_name}' "
                        f"尝试{action}路径 '{value}'，超出插件允许范围")
        return None

    def to_json_schema(self) -> list[dict]:
        """导出为 LLM function-calling 兼容的 JSON Schema"""
        schemas = []
        for tool in self._tools.values():
            schema = {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters or {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            }
            schemas.append(schema)
        return schemas

    def to_prompt_lines(self, names: Optional[list[str]] = None) -> str:
        """生成 LLM system prompt 中可用的工具说明文本"""
        tools = [self._tools[n] for n in names] if names else self._tools.values()
        lines = ["## 🔧 可用工具", ""]
        for t in tools:
            lines.append(f"- **{t.name}**: {t.description}")
        return "\n".join(lines)


class CapabilityRegistry:
    """Level 2：多阶段流水线注册表

    每个 Capability 是一个完整的分析流水线，接管 LLM 的一个完整回合。
    不同于 Tool 的"按需调用"，Capability 由编排器根据用户意图选择并完整执行。
    """

    def __init__(self):
        self._capabilities: dict[str, CapabilityDef] = {}

    def register(self, cap: CapabilityDef) -> None:
        if cap.name in self._capabilities:
            raise ValueError(f"Capability '{cap.name}' already registered")
        self._capabilities[cap.name] = cap

    def get(self, name: str) -> Optional[CapabilityDef]:
        return self._capabilities.get(name)

    def list_all(self) -> list[CapabilityDef]:
        return list(self._capabilities.values())

    def call(self, name: str, stage_results: dict = None, **kwargs) -> CapabilityResult:
        """执行一个已注册的流水线"""
        cap = self._capabilities.get(name)
        if not cap:
            return CapabilityResult(success=False, error=f"Capability '{name}' not found")
        t0 = time.perf_counter()
        try:
            result = cap.fn(stage_results=stage_results, **kwargs)
            elapsed = (time.perf_counter() - t0) * 1000
            if isinstance(result, dict):
                if not result.get("success", True):
                    return CapabilityResult(success=False, error=result.get("error", "Unknown"), elapsed_ms=elapsed)
                return CapabilityResult(
                    success=True,
                    result=result,
                    elapsed_ms=elapsed,
                    usage=result.get("usage", {}),
                )
            return CapabilityResult(success=True, result=result, elapsed_ms=elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            return CapabilityResult(
                success=False,
                error=f"{e}",
                elapsed_ms=elapsed,
                traceback=traceback.format_exc(),
            )


# ── 技能标准化 ──────────────────────────────────────────

@dataclass
class SkillDef:
    """标准化技能定义

    在 CapabilityDef 外层包标准化元数据壳。
    每个 Skill 对应一个命理分析能力，带版本、触发词、优先级等元数据，
    支持动态注册和发现。
    """
    # 核心标识
    name: str
    description: str
    capability: CapabilityDef                 # 关联的能力流水线

    # 元数据
    version: str = "1.0.0"
    trigger_words: list[str] = field(default_factory=list)  # 触发词（供 IntentRouter 自动构建关键词表）
    priority: float = 1.0                               # 优先级（歧义消解用，越高越优先）
    tags: list[str] = field(default_factory=list)       # 标签（八字/紫微/验盘/交叉）
    author: str = ""

    # 接口契约
    input_schema: dict = field(default_factory=dict)    # 输入 Schema
    output_schema: dict = field(default_factory=dict)   # 输出 Schema

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "trigger_words": self.trigger_words,
            "priority": self.priority,
            "tags": self.tags,
            "stages": self.capability.stages,
            "tools": self.capability.tools,
            "category": self.capability.category,
        }


class SkillRegistry:
    """技能注册表

    动态技能发现机制，替代硬编码四个 Capability。
    每个 Skill 自带 trigger_words，IntentRouter 可以从中自动构建关键词表。
    """

    def __init__(self):
        self._skills: dict[str, SkillDef] = {}

    def register(self, skill: SkillDef) -> None:
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' already registered")
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[SkillDef]:
        return self._skills.get(name)

    def list_all(self) -> list[SkillDef]:
        return list(self._skills.values())

    def list_by_tag(self, tag: str) -> list[SkillDef]:
        return [s for s in self._skills.values() if tag in s.tags]

    def get_capability(self, name: str) -> Optional[CapabilityDef]:
        """从 Skill 中提取关联的 CapabilityDef"""
        skill = self._skills.get(name)
        return skill.capability if skill else None

    def to_router_keywords(self) -> dict[str, list[str]]:
        """导出所有 Skill 的触发词，供 IntentRouter 构建关键词表

        Returns:
            {skill_name: [trigger_word_list], ...}
        """
        return {s.name: s.trigger_words for s in self._skills.values()}

    def to_prompt_lines(self) -> str:
        """生成 skill 清单文本（可注入 system prompt）"""
        lines = ["## 🎯 可用技能", ""]
        for skill in sorted(self._skills.values(), key=lambda s: -s.priority):
            tags_str = ", ".join(skill.tags) if skill.tags else ""
            lines.append(f"- **{skill.name}** (v{skill.version}) [{tags_str}]: {skill.description}")
        return "\n".join(lines)


# ── Function Calling 多轮执行循环 ──────────────────────

class FunctionCallingLoop:
    """多轮 Tool 调用执行循环

    真正的价值不在单次注入，而在多轮执行：
      LLM 调 Tool → 看结果 → 判断要不要再调 → 直到分析完整

    双保险终止条件：
      1. LLM 不再请求 tool_use → 分析完成
      2. round >= max_rounds → 硬截断
    """

    def __init__(self, tools: ToolRegistry, max_rounds: int = 10):
        self.tools = tools
        self.max_rounds = max_rounds

    def run(self,
            system_prompt: str,
            messages: list[dict],
            tool_names: list[str],
            max_tokens: int = 16384,
            temperature: float = 0.7,
            timeout: int = 120) -> dict:
        """执行多轮 function calling 循环

        Args:
            system_prompt: 系统提示词
            messages: 用户消息列表 [{"role": "user", "content": "..."}]
            tool_names: 本轮可用的 Tool 名称列表
            max_tokens: 每轮 API 最大 token
            temperature: 温度
            timeout: 每轮超时

        Returns:
            {
                "success": bool,
                "text": str,              # 最终分析文本
                "rounds": int,            # 总轮数
                "tool_calls": [...],      # 所有 Tool 调用记录
                "usage": {"input_tokens": ..., "output_tokens": ...},
                "finish_reason": str,     # "stop" | "max_rounds"
                "messages": [...],        # 完整对话历史
            }
        """
        from services.llm_client import API_CONFIG
        import requests

        if not API_CONFIG.get("api_key"):
            return {"success": False, "error": "未配置 API Key"}

        # 构建 Tool Schema
        tool_schemas = []
        for name in tool_names:
            tool = self.tools.get(name)
            if tool:
                schema = {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters or {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                }
                tool_schemas.append(schema)

        if not tool_schemas:
            return {"success": False, "error": "没有可用的 Tool"}

        url = f"{API_CONFIG['base_url']}/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": API_CONFIG["api_key"],
            "anthropic-version": "2023-06-01",
        }

        # 将 messages 转换为 Anthropic API 格式
        api_messages = []
        for m in messages:
            api_messages.append({"role": m["role"], "content": m["content"]})

        all_tool_calls = []
        total_usage = {"input_tokens": 0, "output_tokens": 0}
        finish_reason = "stop"
        final_text = ""

        for round_num in range(1, self.max_rounds + 1):
            payload = {
                "model": API_CONFIG["model"],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "thinking": {"type": "disabled"},
                "system": system_prompt,
                "messages": api_messages,
                "tools": tool_schemas,
            }

            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            except requests.Timeout:
                return {"success": False, "error": f"第 {round_num} 轮 API 超时"}
            except Exception as e:
                return {"success": False, "error": f"第 {round_num} 轮 API 调用失败: {e}"}

            if resp.status_code != 200:
                return {"success": False, "error": f"API 返回错误 ({resp.status_code}): {resp.text[:300]}"}

            data = resp.json()
            usage = data.get("usage", {})
            total_usage["input_tokens"] += usage.get("input_tokens", 0)
            total_usage["output_tokens"] += usage.get("output_tokens", 0)

            content_blocks = data.get("content", [])

            # 解析 tool_use 和 text
            tool_uses = []
            text_parts = []
            for block in content_blocks:
                if block.get("type") == "tool_use":
                    tool_uses.append(block)
                elif block.get("type") == "text":
                    text_parts.append(block.get("text", ""))

            round_text = "".join(text_parts)
            if round_text:
                final_text += round_text

            # 没有 tool_use → LLM 认为分析完成
            if not tool_uses:
                finish_reason = "stop"
                break

            # 执行所有 tool_use
            tool_results = []
            for tu in tool_uses:
                tool_name = tu.get("name", "")
                tool_input = tu.get("input", {})
                tool_id = tu.get("id", "")

                result = self.tools.call(tool_name, **tool_input)
                call_record = {
                    "round": round_num,
                    "tool": tool_name,
                    "input": tool_input,
                    "success": result.success,
                    "data": result.data if result.success else None,
                    "error": result.error if not result.success else None,
                    "elapsed_ms": result.elapsed_ms,
                }
                all_tool_calls.append(call_record)

                # 构建 tool_result 内容
                if result.success:
                    result_str = json.dumps(result.data, ensure_ascii=False, default=str)
                else:
                    result_str = f"错误: {result.error}"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result_str[:8000],  # 截断过长内容
                })

            # 将本轮 tool_use + tool_result 追加到对话
            api_messages.append({
                "role": "assistant",
                "content": [{"type": "tool_use", "id": tu["id"], "name": tu["name"], "input": tu["input"]}
                           for tu in tool_uses],
            })
            api_messages.append({
                "role": "user",
                "content": tool_results,
            })

        else:
            # 循环正常结束（达到 max_rounds）
            finish_reason = "max_rounds"

        return {
            "success": True,
            "text": final_text,
            "rounds": round_num,
            "tool_calls": all_tool_calls,
            "usage": total_usage,
            "finish_reason": finish_reason,
            "messages": api_messages,
        }


# ── 意图路由 ────────────────────────────────────────────

class IntentRouter:
    """用户意图 → 能力匹配 → 工具路由

    编排层最核心的分派逻辑。独立于 Orchestrator 注入，
    便于后续切换匹配策略（关键词 → embedding → LLM 语义路由）。

    支持两种关键词来源：
    1. 显式传入 keywords dict
    2. 从 SkillRegistry.to_router_keywords() 自动构建

    使用方式：
        # 显式关键词
        router = IntentRouter(keywords={"bazi_analysis": ["八字", "四柱"], ...})

        # 从 SkillRegistry 自动构建
        skills = SkillRegistry()
        skills.register(SkillDef(name="bazi", trigger_words=["八字", "四柱"], ...))
        router = IntentRouter.from_skills(skills)
    """

    def __init__(self, keywords: dict[str, list[str]] = None):
        self._keywords = keywords or {}

    @classmethod
    def from_skills(cls, skills: "SkillRegistry") -> "IntentRouter":
        """从 SkillRegistry 自动构建关键词表"""
        return cls(keywords=skills.to_router_keywords())

    @staticmethod
    def _default_keywords() -> dict[str, list[str]]:
        """内置默认关键词表，覆盖四大流水线"""
        return {
            "bazi_analysis": [
                "八字", "四柱", "十神", "用神", "忌神", "大运", "流年",
                "格局", "旺衰", "调候", "病药", "刑冲", "神煞", "纳音",
                "日主", "天干", "地支", "藏干", "五行", "起运", "排盘",
                "命理", "算命", "批命", "梁湘润", "穷通宝鉴",
            ],
            "ziwei_analysis": [
                "紫微", "斗数", "命盘", "星曜", "十二宫", "四化",
                "命宫", "财帛", "官禄", "夫妻", "福德", "疾厄",
                "迁移", "交友", "田宅", "父母", "子女", "兄弟",
                "化禄", "化权", "化科", "化忌", "大限", "三方四正",
                "紫微星", "天机", "太阳", "武曲", "天同", "廉贞",
                "天府", "太阴", "贪狼", "巨门", "天相", "天梁",
                "七杀", "破军", "辅星", "煞星", "中州派",
            ],
            "verify_panel": [
                "验盘", "验证", "核对", "校准", "确认", "核实",
                "这些事", "准不准", "对不对", "靠谱", "准确",
            ],
            "cross_validate": [
                "交叉", "比对", "对照", "综合分析", "全面分析",
                "八字和紫微", "紫微和八字", "综合看", "一起看",
                "全面", "完整", "系统",
            ],
        }

    def match(self, user_input: str) -> list[tuple[str, float]]:
        """关键词权重匹配，返回所有能力的匹配分数列表

        评分策略：命中词数越多 → 分数越高。
        归一化分母取 min(总词数, 10)，避免大词库稀释分数。
        分数 ∈ [0.0, 1.0]，1.0 = 命中 ≥10 个关键词。
        """
        if not user_input or not user_input.strip():
            return []

        scored = []
        for cap_name, kws in self._keywords.items():
            hits = sum(1 for kw in kws if kw in user_input)
            if hits == 0:
                continue
            # 归一化：分母取 min(len(kws), 10)，1 hit ≈ 0.1，10+ hits = 1.0
            denom = min(len(kws), 10)
            score = min(hits / denom, 1.0)
            scored.append((cap_name, round(score, 4)))

        scored.sort(key=lambda x: -x[1])
        return scored

    def resolve(self, user_input: str, threshold: float = 0.0) -> Optional[str]:
        """返回得分最高的能力名，无可匹配则返回 None

        默认阈值 0.0：关键词匹配只要有命中即视为意图明确。
        后续切 embedding/LLM 路由时调高阈值（如 0.7）。
        """
        matches = self.match(user_input)
        if not matches:
            return None
        best_name, best_score = matches[0]
        return best_name if best_score >= threshold else None

    def resolve_all(self, user_input: str, threshold: float = 0.0) -> list[tuple[str, float]]:
        """返回所有超过阈值的能力匹配列表

        用于"全面分析"类场景，需要并行跑多个 pipeline。
        第一版直接复用 resolve 结果，后续 embedding 路由时扩展为真正的多路匹配。
        """
        matches = self.match(user_input)
        return [(name, score) for name, score in matches if score >= threshold]


# ── 编排器 ──────────────────────────────────────────────

class AnalysisOrchestrator:
    """统一分析编排器

    整合 ToolRegistry 和 CapabilityRegistry，提供统一的分析入口。
    路由层（routes/）可以调用此编排器代替直接调用 service 函数。

    使用方式：
        orchestrator = AnalysisOrchestrator()
        orchestrator.register_defaults()  # 注册所有内置 Tool 和 Capability

        # 执行八字分析
        result = orchestrator.run("bazi_analysis", plate_dict=plate_dict)

        # 调用单个工具
        stars = orchestrator.tools.call("star_lookup", star_name="紫微")
    """

    def __init__(self, router: IntentRouter = None, skills: "SkillRegistry" = None):
        self.tools = ToolRegistry()
        self.capabilities = CapabilityRegistry()
        self.skills = skills or SkillRegistry()  # 技能注册表（可注入）
        self.router = router or IntentRouter()    # 可注入自定义路由
        self._defaults_registered = False

    # ── 注册内置 Tool ────────────────────────────────

    def _register_paipan_tools(self):
        """注册排盘类工具"""
        from bazi_calculator import paipan as bazi_paipan, TIAN_GAN, DI_ZHI

        def _tool_paipan_bazi(year: int, month: int, day: int, hour: int,
                              minute: int = 0, gender: str = "男",
                              longitude: float = 113.75, location: str = "",
                              apply_solar_correction: bool = True) -> dict:
            """八字排盘"""
            plate = bazi_paipan(year, month, day, hour, minute,
                                gender=gender, longitude=longitude,
                                location=location,
                                apply_solar_correction=apply_solar_correction)
            plate.compute()
            from utils.plate import plate_to_dict
            return plate_to_dict(plate)

        self.tools.register(ToolDef(
            name="paipan_bazi",
            description="八字排盘：输入生辰返回四柱、十神、大运、流年等完整命盘数据",
            fn=_tool_paipan_bazi,
            parameters={
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "出生年"},
                    "month": {"type": "integer", "description": "出生月"},
                    "day": {"type": "integer", "description": "出生日"},
                    "hour": {"type": "integer", "description": "出生时辰(0-23)"},
                    "minute": {"type": "integer", "description": "出生分"},
                    "gender": {"type": "string", "enum": ["男", "女"]},
                    "longitude": {"type": "number", "description": "经度"},
                    "location": {"type": "string", "description": "出生地"},
                    "apply_solar_correction": {"type": "boolean", "description": "是否真太阳时校正"},
                },
                "required": ["year", "month", "day", "hour", "gender"],
            },
            category="paipan",
        ))

        def _tool_paipan_ziwei(year: int, month: int, day: int, hour: int,
                               minute: int = 0, gender: str = "男",
                               is_lunar: bool = False) -> dict:
            """紫微排盘"""
            from ziwei_calculator import ziwei_paipan, plate_to_dict as zv_plate_to_dict
            plate = ziwei_paipan(year, month, day, hour, minute,
                                 gender=gender, is_lunar=is_lunar)
            return zv_plate_to_dict(plate)

        self.tools.register(ToolDef(
            name="paipan_ziwei",
            description="紫微斗数排盘：输入生辰返回十二宫、星曜分布、四化、大限等完整命盘",
            fn=_tool_paipan_ziwei,
            parameters={
                "type": "object",
                "properties": {
                    "year": {"type": "integer"},
                    "month": {"type": "integer"},
                    "day": {"type": "integer"},
                    "hour": {"type": "integer"},
                    "minute": {"type": "integer"},
                    "gender": {"type": "string", "enum": ["男", "女"]},
                    "is_lunar": {"type": "boolean", "description": "是否农历"},
                },
                "required": ["year", "month", "day", "hour", "gender"],
            },
            category="paipan",
        ))

    def _register_query_tools(self):
        """注册查询类工具"""
        from bazi_calculator import get_shishen, TIAN_GAN, DI_ZHI
        from services.kb_loader import (
            _WX_GAN, _WX_ZHI, _load_json_kb, retrieve_kb, extract_ziwei_keywords,
        )

        def _tool_wuxing_query(ri_gan: str = "", target_gan: str = "",
                               target_zhi: str = "") -> dict:
            """五行十神查询"""
            result = {}
            if ri_gan and target_gan:
                result["shishen"] = get_shishen(ri_gan, target_gan)
            if target_gan:
                result["wuxing"] = _WX_GAN.get(target_gan, "?")
            if target_zhi:
                result["zhi_wuxing"] = _WX_ZHI.get(target_zhi, "?")
            return result

        self.tools.register(ToolDef(
            name="wuxing_query",
            description="查询天干地支的五行属性和十神关系",
            fn=_tool_wuxing_query,
            parameters={
                "type": "object",
                "properties": {
                    "ri_gan": {"type": "string", "description": "日干"},
                    "target_gan": {"type": "string", "description": "目标天干"},
                    "target_zhi": {"type": "string", "description": "目标地支"},
                },
            },
            category="query",
        ))

        def _tool_star_lookup(star_name: str = "", stars: list[str] = None) -> dict:
            """星曜查询（支持简繁体自动转换）"""
            kb = _load_json_kb("ziwei_stars.json")
            # 简体→繁体映射
            S2T = {
                '机': '機', '阳': '陽', '贞': '貞', '阴': '陰', '贪': '貪',
                '巨': '門', '门': '門', '杀': '殺', '军': '軍', '鸾': '鸞',
                '魁': '魁', '钺': '鉞', '马': '馬', '刑': '刑', '姚': '姚',
                '巫': '巫', '贵': '貴', '寿': '壽', '德': '德', '哭': '哭',
                '虚': '虛', '空': '空', '劫': '劫', '羊': '羊', '陀': '陀',
                '铃': '鈴', '火': '火', '存': '存', '曲': '曲', '昌': '昌',
                '弼': '弼', '辅': '輔', '喜': '喜', '禄': '祿', '权': '權',
                '科': '科', '忌': '忌', '鸾': '鸞', '龙': '龍', '凤': '鳳',
                '虎': '虎', '华': '華', '盖': '蓋', '池': '池', '阁': '閣',
            }
            def to_traditional(s):
                return ''.join(S2T.get(c, c) for c in s)

            result = {}
            names = stars or ([star_name] if star_name else [])
            for name in names:
                t_name = to_traditional(name)
                found = False
                for section in ["main_stars", "auspicious_stars", "malefic_stars"]:
                    section_data = kb.get(section, {})
                    for sn, sd in section_data.items():
                        # 精确匹配或包含匹配（繁体名）
                        if t_name == sn or name == sn or t_name in sn or name in sn:
                            result[sn] = {
                                "element": sd.get("element", ""),
                                "type": sd.get("type", ""),
                                "positive": sd.get("positive", "")[:60],
                                "negative": sd.get("negative", "")[:60],
                                "section": section,
                            }
                            found = True
                            break
                    if found:
                        break
            return result

        self.tools.register(ToolDef(
            name="star_lookup",
            description="查询紫微斗数星曜的五行、类型、正面/负面特质",
            fn=_tool_star_lookup,
            parameters={
                "type": "object",
                "properties": {
                    "star_name": {"type": "string", "description": "星曜名"},
                    "stars": {"type": "array", "items": {"type": "string"}},
                },
            },
            category="query",
        ))

        def _tool_kb_retrieve(query: str, kb_name: str = "",
                              top_k: int = 5) -> dict:
            """知识库检索"""
            if not kb_name:
                return {"error": "必须指定 kb_name"}
            keywords = query.split()
            text = retrieve_kb(keywords, kb_name, top_k=top_k)
            return {"text": text, "kb_name": kb_name, "top_k": top_k}

        self.tools.register(ToolDef(
            name="kb_retrieve",
            description="从知识库中检索相关条目（星曜、格局、神煞、古籍等）",
            fn=_tool_kb_retrieve,
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词"},
                    "kb_name": {"type": "string", "description": "知识库名。八字: bazi_basics/bazi_extended/tiaohou/signal_rules/shishen_domains/glossary/classical_references。紫微: ziwei_stars/ziwei_fuzuo/ziwei_star_palace/ziwei_classics"},
                    "top_k": {"type": "integer", "description": "返回条目数"},
                },
                "required": ["query", "kb_name"],
            },
            category="query",
        ))

        def _tool_kb_obsidian_retrieve(query: str, system: str = "",
                                       top_k: int = 5) -> dict:
            """Obsidian 知识库检索（古籍断语+出处链证据包）

            双源策略（2026-08-14 团队共识）：同源断语 Obsidian 优先（带出处链），
            JSON 知识库（kb_retrieve）当兜底。本工具命中即返回证据包：
            title/url/source/authority/excerpt + 结构化标签（文体/结局梯度，
            来自 knowledge_base/obsidian_meta/，mose 资产落盘后生效）。
            """
            try:
                from knowledge_base.obsidian_retriever import retrieve, evidence_pack, _normalize, _is_ancient
            except Exception as e:
                return {"error": f"obsidian_retriever 不可用: {e}"}
            sys_filter = system.strip() or None
            hits = retrieve(query, system=sys_filter, top_k=max(top_k * 10, 50))
            # 重排：古籍权威（古籍原文/古籍数字化平台）优先，是解读引用的首选；笔记/MOC 次之
            # （2026-08-14 统一为 retriever._is_ancient 单一来源，消除三处拷贝漂移）
            def _rank_key(item):
                _s, h = item
                if _is_ancient(h.get("authority", "") or ""):
                    return 0
                if h.get("type") in ("moc", "note"):
                    return 1
                return 2
            hits.sort(key=lambda it: (_rank_key(it), -it[0]))
            packs = []
            _obsidian_meta_tags("")
            per_line = {}
            for _fn, _data in (_META_CACHE or {}).items():
                if _fn == "style_tags_per_line.json" and isinstance(_data, list):
                    per_line = {(str(x.get("PageId")), str(x.get("行号"))): x.get("文体", "") for x in _data if x.get("PageId")}
            # 结局梯度词表摊平（per-hit 定级用）：级别从重到轻 + 同级别词长降序，
            # 防子串冲突（「甚㐫」含「㐫」、「是以㐫也」含「㐫也」）让短词先抢
            # （2026-08-14 hanako 抓结构缺口：evidence_pack 无 per-hit 梯度标签，
            #   rev2 措辞「命中条目自带梯度标签」数据层永不成立，恒中性；此段补机器定级）
            _LEVEL_WEIGHT = {"L4_死亡终局": 0, "L4_修辞型": 0, "L3_伤亡": 1, "L2_断凶": 2, "L1_遇凶陈述": 3}
            _og = (_META_CACHE.get("outcome_grades.json") or {}).get("梯度") or {}
            _grade_words = sorted(
                ((lv, w) for lv, v in _og.items() for w in (v.get("词") or [])),
                key=lambda t: (_LEVEL_WEIGHT.get(t[0], 9), -len(t[1])),
            )
            for _score, h in hits[:top_k]:
                ep = evidence_pack(h)
                ep["source_kb"] = "obsidian"
                ep["file"] = h["file"]
                ep["meta"] = _obsidian_meta_tags(h["file"])
                # 结局梯度 per-hit 定级：只扫含查询词的行（按行切分，不依赖表格列数，
                # 防全文别处结局词污染本段定级，如全覽 6 万字别处「命終」误挂到「禄逢冲破」段）；
                # 无命中行则不定级（中性兜底）
                if _grade_words:
                    _rows = [ln for ln in (h.get("body", "") or "").splitlines()
                             if "|" in ln and _normalize(query) in _normalize(ln)]
                    _g = None
                    if _rows:
                        _hay = "\n".join(_rows)
                        _g = next((t for t in _grade_words if t[1] in _hay), None)
                    if _g:
                        ep["meta"]["outcome_grades_level"] = _g[0]
                        ep["meta"]["outcome_grades_word"] = _g[1]
                # 行级文体标签：从素材表格找含查询词的行，按 PageId 查 per_line 表
                if per_line:
                    tags = []
                    for m in re.finditer(r"\|\s*\d+\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|", h.get("body", "")):
                        _ln, _lt, _pid, _txt = m.groups()
                        if _normalize(_txt).find(_normalize(query)) >= 0 and (str(_pid), _ln) in per_line:
                            tags.append({"行号": _ln, "PageId": _pid, "文体": per_line[(str(_pid), _ln)], "原文": _txt.strip()[:50]})
                    if tags:
                        ep["meta"]["line_tags"] = tags[:5]
                packs.append(ep)
            return {
                "text": json.dumps(packs, ensure_ascii=False, indent=1),
                "hits": len(packs),
                "kb": "obsidian",
                "note": "Obsidian 优先于 JSON 库；同源断语以此为准",
            }

        self.tools.register(ToolDef(
            name="kb_obsidian_retrieve",
            description="从 Obsidian 古籍知识库检索断语（带出处链与结构化标签）。断语/古籍引用优先调用本工具，命中即用；kb_retrieve（JSON 库）仅作本工具未命中时的兜底。同源命中时本工具优先（出处链完整、含文体/结局梯度标签）。",
            fn=_tool_kb_obsidian_retrieve,
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词（星曜/断语/宫位等）"},
                    "system": {"type": "string", "description": "体系过滤（三合/飞星），可选"},
                    "top_k": {"type": "integer", "description": "返回条目数"},
                },
                "required": ["query"],
            },
            category="query",
        ))

    def _register_memory_tools(self):
        """注册用户记忆类工具"""
        from services.memory import load_memory, store_memory

        def _tool_memory_retrieve(user_id: str) -> dict:
            """检索用户命理画像"""
            return load_memory(user_id)

        self.tools.register(ToolDef(
            name="memory_retrieve",
            description="检索用户的命理画像：八字/紫微分析历史、已验证人生事实。分析前调用以获取上下文。",
            fn=_tool_memory_retrieve,
            parameters={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "用户标识"},
                },
                "required": ["user_id"],
            },
            category="query",
        ))

        def _tool_memory_store(user_id: str, analysis_type: str = "",
                               findings: str = "", bazi_profile: dict = None,
                               ziwei_profile: dict = None,
                               verified_facts: list = None) -> dict:
            """存储分析结果到用户记忆"""
            return store_memory(
                user_id=user_id,
                analysis_type=analysis_type,
                findings=findings,
                bazi_profile=bazi_profile or {},
                ziwei_profile=ziwei_profile or {},
                verified_facts=verified_facts or [],
            )

        self.tools.register(ToolDef(
            name="memory_store",
            description="保存分析结论到用户记忆：八字/紫微画像、已验证事实。分析完成后调用以持久化。",
            fn=_tool_memory_store,
            parameters={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "用户标识"},
                    "analysis_type": {"type": "string", "description": "分析类型：bazi_analysis / ziwei_analysis / verify_panel / cross_validate"},
                    "findings": {"type": "string", "description": "分析核心发现"},
                    "bazi_profile": {"type": "object", "description": "八字画像更新：{rizhu, pattern_summary, yongshen, key_signals}"},
                    "ziwei_profile": {"type": "object", "description": "紫微画像更新：{ming_gong, pattern, key_interactions}"},
                    "verified_facts": {"type": "array", "items": {"type": "object"}, "description": "已验证事实：[{year, desc}]"},
                },
                "required": ["user_id"],
            },
            category="query",
        ))

    def _register_capabilities(self):
        """注册分析流水线"""

        # ── 八字分析流水线 ──
        def _cap_bazi_analysis(plate_dict: dict, stage_results: dict = None,
                               timeout: int = 120, stream: bool = False, **kwargs) -> dict:
            """八字 9 级递进分析"""
            from services.bazi_analysis import analyze_bazi
            return analyze_bazi(plate_dict, timeout=timeout)

        self.capabilities.register(CapabilityDef(
            name="bazi_analysis",
            description="八字递进分析：排盘→调候→格局→旺衰→病药→十神→刑冲→神煞→大运流年→交叉验证",
            fn=_cap_bazi_analysis,
            stages=[
                "排盘验证", "调候用神", "格局判定",
                "旺衰判断", "病药分析", "十神展开",
                "刑冲合害", "神煞参考", "大运流年", "交叉验证",
            ],
            category="analysis",
            tools=["paipan_bazi", "wuxing_query", "kb_obsidian_retrieve", "kb_retrieve", "memory_retrieve", "memory_store"],
        ))

        # ── 紫微分析流水线 ──
        def _cap_ziwei_analysis(plate_dict: dict, stage_results: dict = None,
                                timeout: int = 120, bazi_ref: dict = None, **kwargs) -> dict:
            """紫微 10 步递进分析"""
            from services.ziwei_analysis import analyze_ziwei
            return analyze_ziwei(plate_dict, timeout=timeout, bazi_ref=bazi_ref)

        self.capabilities.register(CapabilityDef(
            name="ziwei_analysis",
            description="紫微递进分析：排盘→命宫定位→星曜分布→四化飞星→格局判定→宫位交互→大限流年→叠盘分析",
            fn=_cap_ziwei_analysis,
            stages=[
                "排盘验证", "命宫定位", "星曜分布",
                "四化飞星", "格局判定", "宫位交互",
                "大限流年", "叠盘分析",
            ],
            category="analysis",
            tools=["paipan_ziwei", "star_lookup", "kb_obsidian_retrieve", "kb_retrieve", "memory_retrieve", "memory_store"],
        ))

        # ── 验盘流水线 ──
        def _cap_verify_panel(plate_dict: dict, stage_results: dict = None,
                              timeout: int = 120, **kwargs) -> dict:
            """验盘：生成验证问题 → 逐条核对 → 错误标记 → 修正重推"""
            plate_dict = dict(plate_dict)
            plate_dict["_verification_mode"] = True
            from services.ziwei_analysis import analyze_ziwei
            return analyze_ziwei(plate_dict, timeout=timeout)

        self.capabilities.register(CapabilityDef(
            name="verify_panel",
            description="验盘流水线：基于命盘信号倒退人生大事，逐条标注信号等级",
            fn=_cap_verify_panel,
            stages=["信号提取", "事件倒推", "等级标注", "合规校验"],
            category="verify",
            tools=["paipan_bazi", "paipan_ziwei", "kb_obsidian_retrieve", "kb_retrieve", "memory_retrieve", "memory_store"],
        ))

        # ── 交叉验证流水线 ──
        def _cap_cross_validate(plate_dict: dict, stage_results: dict = None,
                                timeout: int = 120, **kwargs) -> dict:
            """交叉验证：八字排盘 → 独立分析 → 结论比对 → 差异注入紫微 Prompt"""
            from bazi_calculator import paipan
            from utils.plate import plate_to_dict
            import re

            input_info = plate_dict.get("input", {})
            birth_str = input_info.get("birth_datetime", "")
            gender = input_info.get("gender", "男")
            m = re.match(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})", birth_str)
            if not m:
                return {"success": False, "error": "无法从紫微盘提取生辰信息"}

            # 排八字
            bp = paipan(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]),
                        gender=gender, apply_solar_correction=False)
            bp.compute()
            bazi_dict = plate_to_dict(bp)

            # 独立分析八字
            from services.bazi_analysis import analyze_bazi
            bazi_result = analyze_bazi(bazi_dict, timeout=timeout)
            bazi_analysis = bazi_result.get("analysis", "") if bazi_result.get("success") else ""

            # 带八字结论注入紫微分析
            from services.ziwei_analysis import analyze_ziwei
            ziwei_result = analyze_ziwei(plate_dict, timeout=timeout, bazi_ref={
                "bazi_analysis": bazi_analysis,
                "pillars": [
                    {"gz": bp.sizhu["year"]["gz"], "gan_wx": bp.sizhu["year"]["wuxing_gan"],
                     "zhi_wx": bp.sizhu["year"]["wuxing_zhi"], "shishen": bp.sizhu["year"]["shishen"]},
                    {"gz": bp.sizhu["month"]["gz"], "gan_wx": bp.sizhu["month"]["wuxing_gan"],
                     "zhi_wx": bp.sizhu["month"]["wuxing_zhi"], "shishen": bp.sizhu["month"]["shishen"]},
                    {"gz": bp.sizhu["day"]["gz"], "gan_wx": bp.sizhu["day"]["wuxing_gan"],
                     "zhi_wx": bp.sizhu["day"]["wuxing_zhi"], "shishen": bp.sizhu["day"]["shishen"]},
                    {"gz": bp.sizhu["hour"]["gz"], "gan_wx": bp.sizhu["hour"]["wuxing_gan"],
                     "zhi_wx": bp.sizhu["hour"]["wuxing_zhi"], "shishen": bp.sizhu["hour"]["shishen"]},
                ],
                "wuxing": bp.wuxing_counts,
                "qiyun": bp.qiyun_desc,
                "dayun": bp.dayun_labels,
            })
            return ziwei_result

        self.capabilities.register(CapabilityDef(
            name="cross_validate",
            description="交叉验证：独立分析八字→独立分析紫微→比对结论→标注一致/分歧",
            fn=_cap_cross_validate,
            stages=["八字排盘", "八字独立分析", "紫微独立分析", "结论比对", "差异注入"],
            category="verify",
            tools=["paipan_bazi", "paipan_ziwei", "wuxing_query", "star_lookup", "kb_obsidian_retrieve", "kb_retrieve", "memory_retrieve", "memory_store"],
        ))

    def _register_skills(self):
        """注册内置 Skill（标准化 Capability 元数据壳）"""
        # 从默认关键词表获取触发词（注册 Skill 时 router 可能尚未从 Skill 重建）
        default_kw = IntentRouter._default_keywords() if hasattr(IntentRouter, '_default_keywords') else {}
        for cap in self.capabilities.list_all():
            trigger_words = self.router._keywords.get(cap.name, default_kw.get(cap.name, []))
            skill = SkillDef(
                name=cap.name,
                description=cap.description,
                capability=cap,
                version="1.0.0",
                trigger_words=trigger_words,
                priority=1.0,
                tags=[cap.category],
            )
            self.skills.register(skill)

    # ── 初始化 ────────────────────────────────────────

    def register_defaults(self):
        """注册所有内置 Tool、Capability 和 Skill"""
        if self._defaults_registered:
            return
        self._register_paipan_tools()
        self._register_query_tools()
        self._register_memory_tools()
        self._register_capabilities()
        self._register_skills()
        # 从 Skill 触发词重建 IntentRouter 关键词表
        if self.skills and self.skills._skills:
            self.router = IntentRouter.from_skills(self.skills)
        # 内建工具归属固化：插件注入时不再能覆盖内建（Phase 2 归属校验）
        self.tools.freeze_builtins()
        self._defaults_registered = True

    # ── 统一执行入口 ──────────────────────────────────

    def run(self, capability_name: str, **kwargs) -> CapabilityResult:
        """执行一个分析流水线（按名称直接调用）"""
        self.register_defaults()
        return self.capabilities.call(capability_name, **kwargs)

    def route(self, user_input: str, threshold: float = 0.0,
              inject_tools: bool = True, **kwargs) -> CapabilityResult:
        """根据用户输入自动匹配并执行能力

        Args:
            user_input: 用户自然语言输入
            threshold: 匹配阈值
            inject_tools: 是否自动注入关联 Tool Schema（按需注入，省 token）
            **kwargs: 传递给能力的参数（如 plate_dict, bazi_ref 等）

        Returns:
            CapabilityResult，匹配失败时 success=False + error 说明
        """
        self.register_defaults()
        cap_name = self.router.resolve(user_input, threshold=threshold)
        if not cap_name:
            return CapabilityResult(
                success=False,
                error=f"无法匹配用户意图: '{user_input[:50]}...'（可用能力: {[c.name for c in self.capabilities.list_all()]}）"
            )
        # 动态注入关联 Tool（只注入该 Capability 需要的，不塞全部）
        if inject_tools:
            cap_tools = self.get_tools_for_capability(cap_name)
            if cap_tools:
                kwargs["tools_description"] = self.tools.to_prompt_lines(cap_tools)
                kwargs["tool_schemas"] = [
                    s for s in self.tools.to_json_schema()
                    if s["name"] in cap_tools
                ]
        return self.capabilities.call(cap_name, **kwargs)

    def route_all(self, user_input: str, threshold: float = 0.7,
                  **kwargs) -> list[CapabilityResult]:
        """根据用户输入匹配所有相关能力并顺序执行

        用于"全面分析"场景，一次请求触发多个 pipeline。
        """
        self.register_defaults()
        matches = self.router.resolve_all(user_input, threshold=threshold)
        if not matches:
            return [CapabilityResult(
                success=False,
                error=f"无法匹配用户意图: '{user_input[:50]}...'"
            )]
        results = []
        for cap_name, score in matches:
            result = self.capabilities.call(cap_name, **kwargs)
            results.append(result)
        return results

    def run_with_fc(self, user_input: str = None,
                    system_prompt: str = None,
                    messages: list[dict] = None,
                    capability_name: str = None,
                    max_rounds: int = 10,
                    max_tokens: int = 16384,
                    temperature: float = 0.7,
                    timeout: int = 120,
                    **kwargs) -> dict:
        """使用 function calling 多轮循环执行分析

        两种调用方式：
        1. 传 user_input → IntentRouter 自动匹配 Capability → 注入关联 Tool → 执行
        2. 传 capability_name → 跳过路由，直接用指定能力的 Tool 集合

        Args:
            user_input: 用户自然语言输入（触发自动路由）
            system_prompt: 系统提示词（必传）
            messages: 初始消息列表 [{"role": "user", "content": "..."}]
            capability_name: 直接指定能力名（跳过路由）
            max_rounds: Tool 调用最大轮数
            max_tokens: 每轮最大 token
            temperature: LLM 温度
            timeout: 每轮超时

        Returns:
            同 FunctionCallingLoop.run() 的返回值
        """
        self.register_defaults()

        # 确定工具集合
        if capability_name:
            tool_names = self.get_tools_for_capability(capability_name)
        elif user_input:
            cap_name = self.router.resolve(user_input)
            if not cap_name:
                return {"success": False, "error": f"无法匹配用户意图: '{user_input[:50]}...'"}
            tool_names = self.get_tools_for_capability(cap_name)
        else:
            return {"success": False, "error": "必须提供 user_input 或 capability_name"}

        if not tool_names:
            return {"success": False, "error": "匹配的能力没有关联 Tool"}

        if not system_prompt:
            return {"success": False, "error": "必须提供 system_prompt"}

        if not messages:
            # 从 kwargs 构建最小消息
            user_msg = kwargs.pop("user_message", user_input or "")
            if not user_msg:
                return {"success": False, "error": "必须提供 messages 或 user_message"}
            messages = [{"role": "user", "content": user_msg}]

        loop = FunctionCallingLoop(self.tools, max_rounds=max_rounds)
        return loop.run(
            system_prompt=system_prompt,
            messages=messages,
            tool_names=tool_names,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )

    def run_with_tools(self, capability_name: str,
                       tool_names: list[str] = None,
                       stream: bool = False,
                       **kwargs) -> CapabilityResult:
        """执行分析流水线，同时注入工具列表到上下文"""
        self.register_defaults()
        tools_desc = self.tools.to_prompt_lines(tool_names) if tool_names else ""
        kwargs["tools_description"] = tools_desc
        return self.capabilities.call(capability_name, **kwargs)

    def get_tools_for_capability(self, capability_name: str) -> list[str]:
        """返回指定能力关联的 Tool 名称列表

        用于动态注入：IntentRouter 匹配到能力后，只注入该能力需要的 Tool Schema，
        而非全量 5 个 Tools 塞进 system prompt。
        """
        self.register_defaults()
        cap = self.capabilities.get(capability_name)
        if not cap:
            return []
        # 过滤：只返回已注册的 Tool（防御性：tools 列表中可能有拼写错误）
        return [t for t in cap.tools if self.tools.get(t) is not None]

    def summary(self) -> dict:
        """返回当前注册状态的摘要"""
        self.register_defaults()
        return {
            "tools": {
                "total": len(self.tools.list_all()),
                "by_category": {
                    cat: len(self.tools.list_by_category(cat))
                    for cat in set(t.category for t in self.tools.list_all())
                },
            },
            "capabilities": {
                "total": len(self.capabilities.list_all()),
                "names": [c.name for c in self.capabilities.list_all()],
            },
            "skills": {
                "total": len(self.skills.list_all()),
                "names": [s.name for s in self.skills.list_all()],
            },
        }


# ── 全局单例（可选） ──────────────────────────────────

# 模块级单例，路由层可以直接 from services.orchestrator import orchestrator 使用
orchestrator = AnalysisOrchestrator()


# ── 测试 ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    orch = AnalysisOrchestrator()
    orch.register_defaults()

    print("=" * 60)
    print("AnalysisOrchestrator 注册摘要")
    print("=" * 60)

    summary = orch.summary()
    print(f"\nTool 注册: {summary['tools']['total']} 个")
    for cat, count in summary['tools']['by_category'].items():
        print(f"  - {cat}: {count}")

    print(f"\nCapability 注册: {summary['capabilities']['total']} 个")
    for name in summary['capabilities']['names']:
        cap = orch.capabilities.get(name)
        print(f"  - {name}: {' → '.join(cap.stages)}")

    print(f"\nSkill 注册: {summary['skills']['total']} 个")
    for name in summary['skills']['names']:
        skill = orch.skills.get(name)
        tags_str = ", ".join(skill.tags) if skill.tags else ""
        print(f"  - {name} v{skill.version} [{tags_str}]: {skill.description[:60]}...")
        print(f"    触发词({len(skill.trigger_words)}): {', '.join(skill.trigger_words[:8])}{'...' if len(skill.trigger_words)>8 else ''}")

    print("\nTool JSON Schema 导出 (示例):")
    schemas = orch.tools.to_json_schema()
    for s in schemas:
        print(f"  {s['name']}: {s['description'][:60]}...")

    print("\n" + "=" * 60)
    print("IntentRouter 匹配测试")
    print("=" * 60)

    test_cases = [
        "帮我看看八字格局和用神",
        "排个紫微斗数命盘",
        "验盘，确认一下对不对",
        "八字和紫微一起综合分析",
        "今天天气不错",  # 无匹配
        "帮我全面完整地看一下",
        "紫微十二宫分布如何",
        "调候用神和病药分析",
    ]
    for tc in test_cases:
        matched = orch.router.resolve(tc)
        all_matched = orch.router.resolve_all(tc)
        all_str = ", ".join(f"{n}({s:.3f})" for n, s in all_matched) if all_matched else "—"
        print(f"  「{tc}」→ {matched or '无匹配'}  [all: {all_str}]")

    print("\n" + "=" * 60)
    print("Tool 调用测试")
    print("=" * 60)
    r = orch.tools.call("star_lookup", star_name="天机")
    print(f"  star_lookup(天机): {r.data}")
    r = orch.tools.call("kb_retrieve", query="天府 财帛", kb_name="ziwei_star_palace.json", top_k=3)
    print(f"  kb_retrieve(天府 财帛): {len(r.data.get('text',''))} 字符")
