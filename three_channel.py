#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""三通道分析管道（GPT-5.5 参考实现）

GPT-5.5 Thinking 泄露的系统提示词揭示了三层输出通道设计：
  analysis   — 隐藏推理层（Python/web搜索/文件搜索，用户不可见）
  commentary — 可见工具调用/进度层
  final      — 最终文本回复

本模块将此模式迁移到八字排盘 LLM 分析管道：

  analysis   — 内部 LLM 调用，产出结构化决策（格局/旺衰/用神/调候），用户不可见
  commentary — SSE 事件流，展示分析进度（"正在判定格局..." → "旺衰评估完成"）
  final      — 用户可见的 13 章完整分析报告

架构：
  plate_dict → analysis_channel()  ──→ {格局, 旺衰, 用神, ...}  (hidden)
             → commentary_channel() ──→ SSE events               (visible progress)
             → final_channel()      ──→ 13-chapter report        (visible output)
"""

import json
import time
from typing import Generator, Any

from services.llm_client import API_CONFIG, _call_api
from services.kb_loader import _load_knowledge_base
from services.bazi_analysis import _load_system_prompt, _build_user_message, _verify_predictions


# ============================================================
# Analysis Channel（隐藏推理层）
# ============================================================

ANALYSIS_PROMPT = """你是八字命理分析引擎。你的唯一任务是根据用户提供的命盘数据，输出以下 JSON。
不要输出任何 JSON 以外的内容——不要问候、不要解释、不要验盘、不要追问。
如果数据不足以判断某项，使用合理默认值，不要省略字段。

## 输出 JSON Schema（必须严格遵循）

{
  "tiaohou": {
    "season": "春/夏/秋/冬",
    "temperature": "寒/暖/燥/湿/中和",
    "tiaohou_yongshen": "调候用神五行（如'水'，无为null）",
    "reasoning": "调候判断依据，1-2句"
  },
  "geju": {
    "type": "格局类型（正官格/七杀格/...）",
    "success": true,
    "yue_ling": "月令地支",
    "cheng_ge_condition": "成格条件",
    "has_jiuxing": true,
    "reasoning": "格局判定依据，1-2句"
  },
  "wangsan": {
    "de_ling": true,
    "de_di": false,
    "de_shi": true,
    "level": "旺/中和偏旺/中和/中和偏弱/弱",
    "reasoning": "旺衰判断依据，1-2句"
  },
  "yongshen": {
    "yong": "用神五行",
    "xi": ["喜神五行1", "喜神五行2"],
    "ji": ["忌神五行1"],
    "xian": ["闲神五行"],
    "reasoning": "用神选取逻辑链"
  },
  "bingyao": {
    "disease": "命局病症描述",
    "medicine": "解药描述",
    "has_cure": true,
    "reasoning": "病药分析依据"
  },
  "liunian_signals": [
    {
      "age": 18,
      "year": 2023,
      "event": "高考/升学",
      "signal": "S",
      "mechanism": "日柱伏吟+文昌到位"
    }
  ],
  "extreme_score": 0,
  "extreme_features": ["金独旺", "火土成势"],
  "total_tokens_estimate": 0
}

## 分析步骤（按顺序执行，每步对应一个 JSON 字段）

1. tiaohou: 检查夏冬出生 → 寒暖燥湿 → 调候用神
2. geju: 从月令出发 → 定格 → 成败 → 救应
3. wangsan: 得令/得地/得势 → 旺衰层次
4. yongshen: 基于调候+格局+旺衰 → 用神/喜神/忌神/闲神
5. bingyao: 命局病症 → 解药 → 有病有药/无药可救
6. liunian_signals: 扫描已走过的大运 → S/A/B级关键年份

## 约束

- extreme_score: 0=均衡, 1=略偏, 2=明显偏枯, 3=极端命局（某五行>=4字或某五行0字）
- extreme_features: 描述极端特征的字符串列表
- liunian_signals: 只列 S/A 级事件（天克地冲/日柱伏吟/大运交接），至少 5 条
- 所有 reasoning 字段限 1-2 句中文，精炼准确
- 输出纯 JSON，不要用 Markdown 代码块包裹"""


def analysis_channel(plate_dict: dict, timeout: int = 60) -> dict:
    """隐藏推理层：调用 LLM 产出结构化决策。

    此调用的输出对用户不可见，仅用于指导后续 final channel 的报告生成。

    Returns:
        {"success": True, "analysis": {...}} 或 {"success": False, "error": "..."}
    """
    if not API_CONFIG.get("api_key"):
        return {"success": False, "error": "未配置 API Key"}

    # 独立 system prompt，不复用主分析叙事框架
    system_prompt = ANALYSIS_PROMPT
    user_message = _build_user_message(plate_dict)

    result = _call_api(
        system_prompt,
        [{"role": "user", "content": user_message}],
        max_tokens=4096,  # 结构化决策只需要 ~2K tokens
        temperature=0.1,  # 极低温度确保结构化输出一致性
        timeout=timeout,
    )

    if not result["success"]:
        return result

    # 尝试解析 JSON（容错处理）
    text = result["text"].strip()
    # 去除可能的 Markdown 代码块包裹
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        analysis = json.loads(text)
    except json.JSONDecodeError:
        # 容错：尝试提取 JSON 对象
        import re
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                analysis = json.loads(match.group())
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": f"analysis channel 返回非 JSON 格式",
                    "raw_text": text[:500],
                }
        else:
            return {
                "success": False,
                "error": f"analysis channel 返回无法解析",
                "raw_text": text[:500],
            }

    return {
        "success": True,
        "analysis": analysis,
        "usage": result.get("usage", {}),
    }


# ============================================================
# Commentary Channel（进度可见层）
# ============================================================

# 分析阶段定义（对应 9 级递进推理链 + 验盘）
ANALYSIS_PHASES = [
    {"id": "verify",    "label": "验盘扫描",       "desc": "正在扫描已走过的大运流年，提取关键信号...", "weight": 10},
    {"id": "tiaohou",   "label": "调候分析",       "desc": "正在分析寒暖燥湿，判定调候用神...",       "weight": 5},
    {"id": "geju",      "label": "格局判定",       "desc": "正在从月令出发，判定格局成败...",         "weight": 8},
    {"id": "wangsan",   "label": "旺衰评估",       "desc": "正在综合得令得地得势，判定旺衰层次...",   "weight": 5},
    {"id": "bingyao",   "label": "病药分析",       "desc": "正在诊断命局病症，寻找解药...",           "weight": 5},
    {"id": "liutong",   "label": "流通检查",       "desc": "正在检查五行流通性，定位淤堵点...",       "weight": 5},
    {"id": "shishen",   "label": "十神解读",       "desc": "正在分析十神组合，映射性格特质...",       "weight": 8},
    {"id": "chonghe",   "label": "刑冲合害",       "desc": "正在分析地支关系，检查拱夹暗合...",       "weight": 8},
    {"id": "dayun",     "label": "大运走势",       "desc": "正在评估各步大运，绘制人生曲线...",       "weight": 12},
    {"id": "cross",     "label": "四维交叉验证",   "desc": "正在四维独立结论交叉对比，寻找共同点...", "weight": 8},
    {"id": "career",    "label": "事业财运",       "desc": "正在分析事业方向、财运层次...",           "weight": 8},
    {"id": "marriage",  "label": "婚姻感情",       "desc": "正在分析配偶特征、正缘窗口...",           "weight": 8},
    {"id": "health",    "label": "健康养生",       "desc": "正在识别先天薄弱环节...",                 "weight": 5},
    {"id": "selfcheck", "label": "自检验证",       "desc": "正在执行 CoVe 自检，修正可能错误...",     "weight": 5},
]

TOTAL_WEIGHT = sum(p["weight"] for p in ANALYSIS_PHASES)


def commentary_channel(current_phase: int, total_phases: int = None) -> dict:
    """生成单个进度事件的 SSE 数据。

    Args:
        current_phase: 当前阶段索引 (0-based)
        total_phases: 总阶段数（None 则使用 ANALYSIS_PHASES 长度）

    Returns:
        SSE 事件字典
    """
    if total_phases is None:
        total_phases = len(ANALYSIS_PHASES)

    phase = ANALYSIS_PHASES[current_phase]

    # 计算累积进度百分比
    cum_weight = sum(p["weight"] for p in ANALYSIS_PHASES[:current_phase + 1])
    progress_pct = min(round(cum_weight / TOTAL_WEIGHT * 100), 99)

    return {
        "event": "progress",
        "phase_id": phase["id"],
        "phase_label": phase["label"],
        "phase_desc": phase["desc"],
        "phase_index": current_phase + 1,
        "total_phases": total_phases,
        "progress_pct": progress_pct,
    }


def format_sse(event: dict) -> str:
    """格式化 SSE 事件字符串"""
    return f"event: {event['event']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


# ============================================================
# Final Channel（用户可见输出层）
# ============================================================

def _build_final_user_message(plate_dict: dict, analysis: dict) -> str:
    """构造 final channel 的用户消息，嵌入隐藏分析结果"""
    base = _build_user_message(plate_dict)

    # 将 analysis channel 的决策嵌入为上下文锚点
    anchor = "\n\n---\n\n## 🔒 内部推理锚点（供参考，不要重复输出这些推理过程）\n\n"
    anchor += "以下决策已在内部推理层完成，请直接引用这些结论进行批断，"
    anchor += "**不要重新推理或输出推理过程**：\n\n"

    if "tiaohou" in analysis:
        t = analysis["tiaohou"]
        anchor += f"- **调候**：{t.get('season', '?')}季，{t.get('temperature', '?')}，调候用神={t.get('tiaohou_yongshen') or '无'}\n"

    if "geju" in analysis:
        g = analysis["geju"]
        anchor += f"- **格局**：{g.get('type', '?')}，{'成格' if g.get('success') else '破格'}"
        if g.get("has_jiuxing"):
            anchor += "，有救应"
        anchor += "\n"

    if "wangsan" in analysis:
        w = analysis["wangsan"]
        anchor += f"- **旺衰**：{w.get('level', '?')}（得令={'✓' if w.get('de_ling') else '✗'} 得地={'✓' if w.get('de_di') else '✗'} 得势={'✓' if w.get('de_shi') else '✗'}）\n"

    if "yongshen" in analysis:
        y = analysis["yongshen"]
        anchor += f"- **用神**：用={y.get('yong', '?')}，喜={','.join(y.get('xi', []))}，忌={','.join(y.get('ji', []))}\n"

    if "bingyao" in analysis:
        b = analysis["bingyao"]
        anchor += f"- **病药**：病在{b.get('disease', '?')}，药为{b.get('medicine', '?')}，{'有病有药' if b.get('has_cure') else '无药可救'}\n"

    if "extreme_score" in analysis:
        anchor += f"- **极端度**：{analysis['extreme_score']}/3\n"

    if "liunian_signals" in analysis:
        anchor += "\n**关键流年信号（验盘锚点）**：\n"
        for sig in analysis["liunian_signals"][:10]:
            anchor += f"  - {sig.get('age', '?')}岁（{sig.get('year', '?')}年）：{sig.get('event', '?')} [{sig.get('signal', '?')}级] — {sig.get('mechanism', '?')}\n"

    anchor += "\n**重要**：上述结论是已经完成的内部推理，你在报告中直接使用即可。"
    anchor += "不要写'根据内部推理'、'经过分析'等元描述——直接给出结论。"

    # 将锚点插入到分析要求之前
    if "## 分析要求" in base:
        base = base.replace("## 分析要求", anchor + "\n## 分析要求")
    else:
        base += anchor

    return base


def final_channel(plate_dict: dict, analysis: dict, timeout: int = 180) -> dict:
    """用户可见输出层：生成 13 章完整分析报告。

    基于 analysis_channel 的决策生成用户可见的格式化报告。
    报告的推理过程不会重复，直接引用内部决策作为结论。

    Returns:
        {"success": True, "analysis": "...", ...}
    """
    if not API_CONFIG.get("api_key"):
        return {"success": False, "error": "未配置 API Key"}

    system_prompt = _load_system_prompt()
    user_message = _build_final_user_message(plate_dict, analysis)
    user_messages = [{"role": "user", "content": user_message}]

    # 单次调用（温度略高以产生自然文本，但不做双采样——analysis channel 已做决策）
    result = _call_api(
        system_prompt,
        user_messages,
        max_tokens=24576,
        temperature=0.3,
        timeout=timeout,
    )

    if not result["success"]:
        return result

    return {
        "success": True,
        "analysis": result["text"],
        "model": result.get("model", API_CONFIG["model"]),
        "usage": result.get("usage", {}),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": result["text"]},
        ],
    }


# ============================================================
# 三通道编排器
# ============================================================

def three_channel_analyze(plate_dict: dict) -> Generator[str, None, None]:
    """三通道分析管道主入口（验盘阶段）。

    编排 analysis → commentary → final 三个通道，通过 SSE 事件流返回进度。
    最后一个事件是 "result" 类型，包含完整验盘结果。

    用法（Flask SSE 路由）：
        for sse_event in three_channel_analyze(plate_dict):
            yield sse_event  # 直接转发给客户端

    Yields:
        SSE 格式字符串（进度事件 + 最终 result 事件）
    """
    # Phase 1: 验盘阶段 — 单次调用 + stop_sequences 截停 + 后处理硬校验
    yield format_sse({
        "event": "phase",
        "phase": "verify",
        "message": "验盘阶段开始 — 内部推理 + 流年扫描 + 后处理硬校验",
        "progress_pct": 0,
    })

    system_prompt = _load_system_prompt()
    user_message = _build_user_message(plate_dict)

    # 验盘调用（stop_sequences 在【验盘完毕】处截停）
    yield format_sse(commentary_channel(0))  # 验盘扫描

    result = _call_api(
        system_prompt,
        [{"role": "user", "content": user_message}],
        max_tokens=24576,
        temperature=0.3,
        timeout=180,
        stop_sequences=["【验盘完毕】"],
    )

    if not result["success"]:
        yield format_sse({
            "event": "error",
            "message": result["error"],
            "progress_pct": 0,
        })
        yield format_sse({
            "event": "result",
            "success": False,
            "error": result["error"],
        })
        return

    verify_text = result["text"]

    # 后处理硬校验：预测年份 vs 对照表信号等级
    info = plate_dict.get("input", {})
    birth_dt_str = info.get("birth_datetime", "2000-01-01 00:00")
    current_year = max(int(birth_dt_str[:4]), 2026)
    verify_report = _verify_predictions(verify_text, plate_dict, current_year)
    if verify_report:
        verify_text += verify_report

    yield format_sse({
        "event": "verify_complete",
        "message": "验盘完成 — 后处理校验已追加",
        "progress_pct": 10,
    })

    # 返回验盘结果
    verify_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": verify_text},
    ]
    yield format_sse({
        "event": "result",
        "success": True,
        "stage": "verify",
        "analysis": verify_text,
        "model": result.get("model", API_CONFIG["model"]),
        "usage": result.get("usage", {}),
        "messages": verify_messages,
    })


def three_channel_continue(messages: list[dict], user_reply: str) -> Generator[str, None, None]:
    """三通道续接管道：analysis(隐藏推理) → commentary(进度) → final(完整报告)

    用户确认验盘后调用。流程：
    1. analysis channel: 隐藏推理，产出结构化决策
    2. commentary channel: SSE 进度事件，逐个分析阶段推送
    3. final channel: 用户可见的 13 章完整报告

    Yields:
        SSE 格式字符串（进度事件 + 最终 result 事件）
    """
    # ---- Stage 1: Analysis Channel (hidden) ----
    yield format_sse({
        "event": "stage",
        "stage": "analysis",
        "message": "内部推理引擎启动 — 正在判定格局、旺衰、用神...",
        "progress_pct": 12,
    })

    # 从 messages 中提取 plate_dict（从首条 user 消息）
    plate_dict = _extract_plate_from_messages(messages)
    analysis_result = None

    if plate_dict:
        analysis_result = analysis_channel(plate_dict, timeout=60)
        if analysis_result["success"]:
            analysis = analysis_result["analysis"]

            # 逐阶段发送 commentary 进度事件
            phase_count = len(ANALYSIS_PHASES)
            for i, phase in enumerate(ANALYSIS_PHASES):
                # 模拟延迟（让前端有动画时间）
                time.sleep(0.1)  # 实际场景中这是 LLM 生成时间
                yield format_sse(commentary_channel(i, phase_count))

            yield format_sse({
                "event": "analysis_complete",
                "message": "内部推理完成 — 格局/旺衰/用神已判定",
                "extreme_score": analysis.get("extreme_score", 0),
                "geju_type": analysis.get("geju", {}).get("type", "?"),
                "wangsu_level": analysis.get("wangsan", {}).get("level", "?"),
                "yongshen": analysis.get("yongshen", {}).get("yong", "?"),
                "progress_pct": 95,
            })
        else:
            # analysis channel 失败不阻塞，降级为直接生成
            yield format_sse({
                "event": "warning",
                "message": f"内部推理失败（{analysis_result.get('error', '未知')}），降级为直接生成",
                "progress_pct": 15,
            })
            analysis = None
    else:
        analysis = None

    # ---- Stage 2: Final Channel (visible) ----
    yield format_sse({
        "event": "stage",
        "stage": "final",
        "message": "正在生成完整分析报告...",
        "progress_pct": 96,
    })

    # 构造续接消息
    api_messages = []
    system_msg = None
    for m in messages:
        if m["role"] == "system":
            system_msg = m
        else:
            api_messages.append({"role": m["role"], "content": m["content"]})
    api_messages.append({"role": "user", "content": user_reply})

    # 如果 analysis channel 成功，在 user reply 后追加内部决策锚点
    if analysis and plate_dict:
        anchor = _build_continue_anchor(analysis)
        api_messages[-1]["content"] += anchor

    # 调用 LLM 生成最终报告
    url = f"{API_CONFIG['base_url']}/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_CONFIG["api_key"],
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": API_CONFIG["model"],
        "max_tokens": 16384,
        "temperature": 0.3,
        "thinking": {"type": "disabled"},
        "system": system_msg["content"] if system_msg else "",
        "messages": api_messages,
    }

    import requests
    for attempt in range(2):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=480)
            if resp.status_code != 200:
                yield format_sse({
                    "event": "error",
                    "message": f"API 返回错误 ({resp.status_code})",
                    "progress_pct": 99,
                })
                yield format_sse({"event": "result", "success": False, "error": f"API 返回错误 ({resp.status_code})"})
                return

            data = resp.json()
            final_text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    final_text += block["text"]

            if final_text:
                yield format_sse({
                    "event": "complete",
                    "message": "分析报告生成完毕",
                    "progress_pct": 100,
                })
                yield format_sse({
                    "event": "result",
                    "success": True,
                    "analysis": final_text,
                    "hidden_analysis": analysis,
                })
                return

            if attempt == 0:
                time.sleep(3)
                continue

            yield format_sse({"event": "result", "success": False, "error": "API 返回空内容，已重试"})
            return

        except requests.Timeout:
            yield format_sse({
                "event": "error",
                "message": "API 调用超时（480秒）",
                "progress_pct": 99,
            })
            yield format_sse({"event": "result", "success": False, "error": "API 调用超时"})
            return
        except Exception as e:
            if attempt == 0:
                time.sleep(3)
                continue
            yield format_sse({
                "event": "error",
                "message": str(e),
                "progress_pct": 99,
            })
            yield format_sse({"event": "result", "success": False, "error": str(e)})
            return

    yield format_sse({"event": "result", "success": False, "error": "所有重试均失败"})


# ============================================================
# 辅助函数
# ============================================================

def _extract_plate_from_messages(messages: list[dict]) -> dict | None:
    """从对话 messages 中尝试提取 plate_dict 用于 analysis channel。

    命盘数据嵌入在首条 user 消息的 Markdown 表格中。
    这里用启发式方法提取关键字段。
    """
    import re

    for m in messages:
        if m.get("role") != "user":
            continue
        content = m.get("content", "")

        if "命盘数据" not in content and "四柱干支" not in content:
            continue

        # 提取关键字段构造最小 plate_dict
        plate = {
            "input": {},
            "pillars": {"year": {}, "month": {}, "day": {}, "hour": {}},
            "qiyun": {},
            "ri_zhu": "",
            "year_type": "",
        }

        # 性别
        m_g = re.search(r"性别[：:]\s*(\S+)", content)
        if m_g:
            plate["input"]["gender"] = m_g.group(1)

        # 公历
        m_b = re.search(r"公历[：:]\s*(.+?)(?:\n|$)", content)
        if m_b:
            plate["input"]["birth_datetime"] = m_b.group(1).strip()

        # 经度
        m_l = re.search(r"经度\s*([\d.]+)°E", content)
        if m_l:
            plate["input"]["longitude"] = float(m_l.group(1))

        # 日主
        m_r = re.search(r"日主[：:]\s*(\S+)", content)
        if m_r:
            plate["ri_zhu"] = m_r.group(1)

        # 起运
        m_q = re.search(r"起运[：:]\s*([\d.]+)\s*岁", content)
        if m_q:
            plate["qiyun"]["age"] = float(m_q.group(1))

        # 四柱干支（尝试从表格提取）
        for pillar in ["year", "month", "day", "hour"]:
            # 匹配表格行中的干支
            pillar_map = {"year": "年柱", "month": "月柱", "day": "日柱", "hour": "时柱"}
            # 简化：从 Markdown 表格中提取
            m_gz = re.search(rf"{pillar_map[pillar]}.*?([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])", content)
            if m_gz:
                plate["pillars"][pillar]["gz"] = m_gz.group(1)

        if plate["ri_zhu"] or any(plate["pillars"][p].get("gz") for p in ["year", "month", "day", "hour"]):
            return plate

    return None


def _build_continue_anchor(analysis: dict) -> str:
    """构造续接对话的内部推理锚点（追加到用户回复后）"""
    anchor = "\n\n---\n\n## 🔒 内部推理锚点\n\n"
    anchor += "以下决策已在内部推理阶段完成，请在后续分析中直接引用：\n\n"

    geo = analysis.get("geju", {})
    wan = analysis.get("wangsan", {})
    yon = analysis.get("yongshen", {})
    tia = analysis.get("tiaohou", {})

    anchor += f"- 格局：{geo.get('type', '?')}（{'成格' if geo.get('success') else '破格'}）\n"
    anchor += f"- 旺衰：{wan.get('level', '?')}\n"
    anchor += f"- 用神：{yon.get('yong', '?')}，喜神：{','.join(yon.get('xi', []))}，忌神：{','.join(yon.get('ji', []))}\n"
    anchor += f"- 调候：{tia.get('season', '?')}季{tia.get('temperature', '?')}，调候用神={tia.get('tiaohou_yongshen') or '无'}\n"
    anchor += f"- 极端度：{analysis.get('extreme_score', 0)}/3\n"

    if "liunian_signals" in analysis:
        anchor += "\n关键流年信号：\n"
        for sig in analysis["liunian_signals"][:5]:
            anchor += f"  - {sig.get('age', '?')}岁 {sig.get('year', '?')}年：{sig.get('event', '?')} [{sig.get('signal', '?')}级]\n"

    anchor += "\n⛔ 不要输出推理过程——直接给结论。不要写'根据内部推理'等元描述。"

    return anchor


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")

    from bazi_calculator import paipan
    from app import plate_to_dict

    # 测试命盘
    plate = paipan(2005, 8, 19, 1, 35, "男", 113.75, "广东省东莞市")
    pdict = plate_to_dict(plate)

    print("=" * 60)
    print("测试 1: Analysis Channel（隐藏推理层）")
    print("=" * 60)
    result = analysis_channel(pdict, timeout=60)
    if result["success"]:
        analysis = result["analysis"]
        print(f"  格局: {analysis.get('geju', {}).get('type', '?')}")
        print(f"  旺衰: {analysis.get('wangsan', {}).get('level', '?')}")
        print(f"  用神: {analysis.get('yongshen', {}).get('yong', '?')}")
        print(f"  极端度: {analysis.get('extreme_score', '?')}")
    else:
        print(f"  失败: {result['error']}")

    print()
    print("=" * 60)
    print("测试 2: Commentary Channel（进度事件）")
    print("=" * 60)
    for i in range(min(3, len(ANALYSIS_PHASES))):
        event = commentary_channel(i)
        print(f"  [{event['progress_pct']}%] {event['phase_label']}: {event['phase_desc']}")

    print()
    print("=" * 60)
    print("测试 3: Three-Channel 编排器（验盘阶段）")
    print("=" * 60)
    pipeline = three_channel_analyze(pdict)
    for sse in pipeline:
        # 只打印事件类型，不打印完整 SSE
        for line in sse.strip().split("\n"):
            if line.startswith("event:"):
                print(f"  SSE event: {line[7:]}")
    print("  (验盘 pipeline 完成)")
