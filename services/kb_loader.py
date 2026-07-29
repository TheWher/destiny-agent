#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知识库加载器 — 结构化 JSON 知识库的加载、缓存与按需检索

提供八字/紫微共用领域常量（五行映射）和知识库 JSON 的懒加载+缓存。
支持全量加载（兼容旧代码）和按需检索（新推荐方式）。
"""

import json
import os

# 干支→五行映射（模块级缓存，也存在于 knowledge_base/signal_rules.json）
_WX_GAN = {'甲':'木','乙':'木','丙':'火','丁':'火','戊':'土','己':'土','庚':'金','辛':'金','壬':'水','癸':'水'}
_WX_ZHI = {'子':'水','丑':'土','寅':'木','卯':'木','辰':'土','巳':'火','午':'火','未':'土','申':'金','酉':'金','戌':'土','亥':'水'}

# JSON 知识库缓存
_kb_cache: dict[str, dict] = {}
_KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'knowledge_base')

# 知识库路径（相对于项目根目录）
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_PATH = os.path.join(_ROOT, "knowledge_base", "bazi_basics.json")
KB_EXTENDED_PATH = os.path.join(_ROOT, "knowledge_base", "bazi_extended.json")


def _load_json_kb(filename: str) -> dict:
    """加载 knowledge_base/*.json 并缓存。返回 dict，失败返回 {}。"""
    if filename in _kb_cache:
        return _kb_cache[filename]
    path = os.path.join(_KB_DIR, filename)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        _kb_cache[filename] = data
        return data
    except Exception:
        return {}


def _load_knowledge_base(include_extended: bool = False) -> str:
    """加载结构化知识库，注入为权威上下文。

    默认只加载核心防幻觉表（天干/地支/藏干/冲合/十神/十二长生），约6KB。
    include_extended=True 时追加纳音/神煞/建除/星宿，约7KB额外。
    """
    import json

    parts = []
    # 基础库（核心防幻觉 — 永远加载）
    if os.path.exists(KB_PATH):
        with open(KB_PATH, "r", encoding="utf-8") as f:
            kb = json.load(f)
        sections = [
            ("天干（五行/生克/五合/禄神）", "天干"),
            ("地支（藏干/六冲/六合/三合/三刑/六害）", "地支"),
            ("驿马（三合局对冲位）", "驿马"),
            ("五行生克", "五行生克"),
            ("十神（日干与他干关系）", "十神"),
            ("十二长生（天干坐地支状态）", "十二长生"),
        ]
        for label, key in sections:
            if key in kb:
                parts.append(f"### {label}\n{json.dumps(kb[key], ensure_ascii=False, indent=2)}")

    # 扩展库（按需加载）
    if include_extended and os.path.exists(KB_EXTENDED_PATH):
        with open(KB_EXTENDED_PATH, "r", encoding="utf-8") as f:
            kb2 = json.load(f)
        ext_sections = [
            ("六十甲子纳音（干支→纳音五行）", "六十甲子纳音"),
            ("神煞系统（天乙/文昌/桃花/羊刃/华盖/劫煞/孤辰寡宿/天月德/将星/天医/空亡）", "神煞"),
            ("建除十二神", "建除十二神"),
            ("二十八宿", "二十八宿"),
        ]
        for label, key in ext_sections:
            if key in kb2:
                parts.append(f"### {label}\n{json.dumps(kb2[key], ensure_ascii=False, indent=2)}")

    if not parts:
        return ""
    return "\n\n## 📚 权威知识库（结构化数据 —— 所有干支判断的唯一依据）\n\n" + "\n\n".join(parts)


# ═══ 按需检索（2026-07-29 新增） ═══

def retrieve_kb(query_keywords: list[str], kb_name: str, top_k: int = 10) -> str:
    """从知识库中检索与关键词相关的条目，替代全量拼接。

    Args:
        query_keywords: 关键词列表（星曜名、格局名、宫位名等）
        kb_name: 知识库文件名（如 "ziwei_stars.json"）
        top_k: 最多返回条数

    Returns:
        拼接好的文本片段，或空字符串。

    匹配策略：
    - 遍历知识库的所有键和值中的字符串
    - 任何关键词出现在键或值中 → 该条目匹配
    - 按匹配关键词数量降序排列
    - 返回 top_k 条

    对于特殊结构的知识库（如 ziwei_stars.json 是 dict-of-dict），
    会在星曜名层面做精确匹配，而非遍历所有叶子值。
    """
    kb = _load_json_kb(kb_name)
    if not kb:
        return ""

    # ── 特殊结构处理 ──
    # ziwei_stars.json：{星曜名: {庙旺陷: {...}, ...}}
    if kb_name == "ziwei_stars.json":
        return _retrieve_stars(kb, query_keywords, top_k)

    # ziwei_fuzuo.json：{辅星名: {分宫: {...}, 组合: {...}}}
    if kb_name == "ziwei_fuzuo.json":
        return _retrieve_fuzuo(kb, query_keywords, top_k)

    # ziwei_star_palace.json：{星曜名: {宫位名: "解释"}}
    if kb_name == "ziwei_star_palace.json":
        return _retrieve_star_palace(kb, query_keywords, top_k)

    # ziwei_classics.json / ziwei_classics_full.json：古籍引用
    if "classics" in kb_name:
        return _retrieve_classics(kb, query_keywords, top_k)

    # ── 通用检索 ──
    return _retrieve_generic(kb, query_keywords, top_k)


def _retrieve_stars(kb: dict, keywords: list[str], top_k: int) -> str:
    """检索星曜数据：按星曜名匹配，返回精简摘要而非全量"""
    # 简体→繁体映射（盘数据用简体，KB 用繁体）
    S2T = {'机':'機','阳':'陽','贞':'貞','阴':'陰','贪':'貪','巨':'門','杀':'殺','军':'軍','鸾':'鸞','喜':'喜','魁':'魁','钺':'鉞','马':'馬','刑':'刑','姚':'姚','巫':'巫','贵':'貴','寿':'壽','德':'德','哭':'哭','虚':'虛','空':'空','劫':'劫','羊':'羊','陀':'陀','铃':'鈴','火':'火','存':'存','曲':'曲','昌':'昌','弼':'弼','辅':'輔'}
    def norm(s):
        return ''.join(S2T.get(c, c) for c in s)
    norm_kw = [norm(kw) for kw in keywords]

    matched = []
    for section_name in ["main_stars", "auspicious_stars", "malefic_stars"]:
        section = kb.get(section_name, {})
        if not isinstance(section, dict):
            continue
        for star_name, star_data in section.items():
            if not isinstance(star_data, dict):
                continue
            score = 0
            if any(nk in star_name or nk in norm(star_name) for nk in norm_kw):
                score += 3
            for kw in norm_kw:
                for v in star_data.values():
                    if isinstance(v, str) and (kw in v or kw in norm(v)):
                        score += 1
                        break
            if score > 0:
                if section_name == "main_stars":
                    score += 2
                summary = {
                    "element": star_data.get("element", ""),
                    "type": star_data.get("type", ""),
                    "positive": star_data.get("positive", "")[:30] if star_data.get("positive") else "",
                    "negative": star_data.get("negative", "")[:30] if star_data.get("negative") else "",
                }
                if "meaning" in star_data:
                    summary["meaning"] = star_data["meaning"]
                if "nature" in star_data:
                    summary["nature"] = star_data["nature"][:40]
                matched.append((score, section_name, star_name, summary))

    if not matched:
        return ""

    matched.sort(key=lambda x: -x[0])
    lines = []
    for _, section, name, data in matched[:top_k]:
        prefix = {"main_stars": "⭐", "auspicious_stars": "🟢", "malefic_stars": "🔴"}.get(section, "")
        props = ", ".join(f"{k}:{v}" for k, v in data.items() if v)
        lines.append(f"{prefix} {name}：{props}")
    return "\n".join(lines)


def _retrieve_fuzuo(kb: dict, keywords: list[str], top_k: int) -> str:
    """检索辅佐煞曜数据"""
    return _retrieve_generic(kb, keywords, top_k)


def _retrieve_star_palace(kb: dict, keywords: list[str], top_k: int) -> str:
    """检索星曜×宫位组合数据"""
    matched = []
    for star_name, palace_data in kb.items():
        if not isinstance(palace_data, dict):
            continue
        score = 0
        if any(kw in star_name for kw in keywords):
            score += 2
        for palace_name in palace_data:
            if any(kw in palace_name for kw in keywords):
                score += 1
        if score > 0:
            # 只取匹配到的宫位条目
            filtered = {k: v for k, v in palace_data.items()
                       if any(kw in k for kw in keywords)}
            matched.append((score, star_name, filtered))

    if not matched:
        return ""

    matched.sort(key=lambda x: -x[0])
    parts = []
    for _, name, data in matched[:top_k]:
        parts.append(f"### {name}\n{json.dumps(data, ensure_ascii=False, indent=2)}")
    return "\n\n".join(parts)


def _retrieve_classics(kb: dict, keywords: list[str], top_k: int) -> str:
    """检索古籍引用"""
    return _retrieve_generic(kb, keywords, top_k)


def _retrieve_generic(kb: dict, keywords: list[str], top_k: int) -> str:
    """通用检索：遍历所有键值对，做关键词匹配"""
    matched = []
    for key, value in kb.items():
        if not isinstance(value, (str, dict, list)):
            continue
        key_str = str(key)
        val_str = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        score = 0
        for kw in keywords:
            if kw in key_str:
                score += 2
            if kw in val_str:
                score += 1
        if score > 0:
            matched.append((score, key, value))

    if not matched:
        return ""

    matched.sort(key=lambda x: -x[0])
    parts = []
    for _, key, value in matched[:top_k]:
        val_str = json.dumps(value, ensure_ascii=False, indent=2) if isinstance(value, (dict, list)) else str(value)
        parts.append(f"### {key}\n{val_str}")
    return "\n\n".join(parts)


def extract_ziwei_keywords(plate_dict: dict) -> list[str]:
    """从命盘数据中提取检索关键词"""
    keywords = []
    palaces = plate_dict.get("palaces", [])

    for pal in palaces:
        # 主星名
        for s in pal.get("major_stars", []):
            name = s.get("name", "") if isinstance(s, dict) else s
            if name:
                keywords.append(name)
        # 辅星名
        for s in pal.get("minor_stars", []):
            name = s.get("name", "") if isinstance(s, dict) else s
            if name:
                keywords.append(name)
        # 宫位名
        keywords.append(pal.get("name", ""))

    # 格局名
    for pat in plate_dict.get("patterns", []):
        name = pat.get("name", "")
        if name:
            keywords.append(name)

    # 去重
    seen = set()
    unique = []
    for kw in keywords:
        if kw and kw not in seen:
            seen.add(kw)
            unique.append(kw)
    return unique
