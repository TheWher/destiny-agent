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
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# ── 类型定义 ─────────────────────────────────────────────

@dataclass
class ToolDef:
    """Tool 注册定义"""
    name: str
    description: str                          # LLM 可读的功能描述
    fn: Callable[..., dict]                   # 实际执行函数
    parameters: dict = field(default_factory=dict)  # 参数 schema（JSON Schema 格式）
    category: str = "general"                 # 分类：paipan / query / render / external

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


# ── 注册表 ──────────────────────────────────────────────

class ToolRegistry:
    """Level 1：轻量工具注册表

    工具是无状态的纯函数包装，供 LLM 在分析过程中按需调用。
    所有工具必须返回 dict，包含 success 字段。
    """

    def __init__(self):
        self._tools: dict[str, ToolDef] = {}

    def register(self, tool: ToolDef) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolDef]:
        return self._tools.get(name)

    def list_all(self) -> list[ToolDef]:
        return list(self._tools.values())

    def list_by_category(self, category: str) -> list[ToolDef]:
        return [t for t in self._tools.values() if t.category == category]

    def call(self, name: str, **kwargs) -> ToolResult:
        """执行一个已注册的工具"""
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{name}' not found")
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
            traceback.print_exc()
            return CapabilityResult(success=False, error=f"{e}", elapsed_ms=elapsed)


# ── 意图路由 ────────────────────────────────────────────

class IntentRouter:
    """用户意图 → 能力匹配 → 工具路由

    编排层最核心的分派逻辑。独立于 Orchestrator 注入，
    便于后续切换匹配策略（关键词 → embedding → LLM 语义路由）。

    使用方式：
        router = IntentRouter(keywords={
            "ziwei_analysis": ["紫微", "斗数", "命盘", "星曜", "十二宫"],
            "bazi_analysis": ["八字", "四柱", "十神", "用神", "大运"],
            "verify_panel": ["验盘", "验证", "核对", "校准"],
            "cross_validate": ["交叉", "比对", "综合分析", "全面"],
        })
        cap_name = router.resolve("帮我看看八字格局")  # → "bazi_analysis"
        all_caps = router.resolve_all("全面分析")       # → [("cross_validate", 0.6), ...]
    """

    def __init__(self, keywords: dict[str, list[str]] = None):
        """
        Args:
            keywords: {capability_name: [触发关键词列表]}
                      如果不传，使用内置默认关键词表。
        """
        self._keywords = keywords or self._default_keywords()

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

    def __init__(self, router: IntentRouter = None):
        self.tools = ToolRegistry()
        self.capabilities = CapabilityRegistry()
        self.router = router or IntentRouter()  # 可注入自定义路由
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
                    "kb_name": {"type": "string", "description": "知识库名：ziwei_stars/ziwei_fuzuo/ziwei_star_palace/ziwei_classics/signal_rules"},
                    "top_k": {"type": "integer", "description": "返回条目数"},
                },
                "required": ["query", "kb_name"],
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
            tools=["paipan_bazi", "wuxing_query", "kb_retrieve"],
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
            tools=["paipan_ziwei", "star_lookup", "kb_retrieve"],
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
            tools=["kb_retrieve"],
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
            tools=["paipan_bazi", "paipan_ziwei", "wuxing_query", "star_lookup", "kb_retrieve"],
        ))

    # ── 初始化 ────────────────────────────────────────

    def register_defaults(self):
        """注册所有内置 Tool 和 Capability"""
        if self._defaults_registered:
            return
        self._register_paipan_tools()
        self._register_query_tools()
        self._register_capabilities()
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
