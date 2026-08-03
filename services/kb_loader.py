#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知识库加载器 — 结构化 JSON 知识库的加载、缓存与按需检索

提供八字/紫微共用领域常量（五行映射）和知识库 JSON 的懒加载+缓存。
支持全量加载（兼容旧代码）和按需检索（新推荐方式）。

2026-08-01 结构层（后端抽象）：
- 两个出口、一个引擎：retrieve_kb（str，工具链/评测用）与 retrieve_hits（命中条目名，注入层 join 用）
- 引擎按 KB_BACKEND 配置切换：lexical（现有分词匹配）→ embedding（向量检索，第二步实现）
- 登记表驱动：受理边界 = dispatch_allowlist（读 evaluation_sets/kb_whitelist.json，13 名，
  full 唯一被拒；schema 是 LLM 推荐名 ≠ 受理边界，hua/sihua_interact 不在 schema 但必须受理）
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

# ═══ 登记表（dispatch 受理边界）═══
# 单点维护：evaluation_sets/kb_whitelist.json 的 dispatch_allowlist 字段（13 名，14 全集减 full）。
# 此处为文件缺失时的内联兜底，与白名单文件保持一致（hash bdc5892b 对应）。
_DISPATCH_ALLOWLIST_FALLBACK = [
    "bazi_basics.json", "bazi_extended.json", "tiaohou.json",
    "signal_rules.json", "shishen_domains.json", "glossary.json",
    "classical_references.json",
    "ziwei_stars.json", "ziwei_fuzuo.json", "ziwei_star_palace.json",
    "ziwei_classics.json", "ziwei_hua.json", "ziwei_sihua_interact.json",
]
_EVAL_WHITELIST_PATH = os.path.join(_ROOT, "evaluation_sets", "kb_whitelist.json")
_dispatch_allowlist_cache: list[str] | None = None


def _load_dispatch_allowlist() -> list[str]:
    """受理名单：优先读白名单文件（单点维护），文件缺失时用内联兜底。"""
    global _dispatch_allowlist_cache
    if _dispatch_allowlist_cache is not None:
        return _dispatch_allowlist_cache
    try:
        with open(_EVAL_WHITELIST_PATH, encoding="utf-8") as f:
            data = json.load(f)
        allow = data.get("dispatch_allowlist")
        if isinstance(allow, list) and allow:
            _dispatch_allowlist_cache = list(allow)
            return _dispatch_allowlist_cache
    except Exception:
        pass
    _dispatch_allowlist_cache = list(_DISPATCH_ALLOWLIST_FALLBACK)
    return _dispatch_allowlist_cache


def _assert_registered(kb_name: str) -> None:
    """登记表驱动：未登记名显式拒绝，不静默兜底。"""
    if kb_name not in _load_dispatch_allowlist():
        raise ValueError(
            f"未登记知识库: {kb_name}。受理边界见 dispatch_allowlist（{_EVAL_WHITELIST_PATH}），"
            f"可选 {sorted(_load_dispatch_allowlist())}"
        )


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


# ═══ 检索后端抽象（2026-08-01 结构层）═══
# 两个出口、一个引擎：
#   retrieve_kb    -> str       （kb_retrieve 工具 / 评测 / 现有调用方，契约不变）
#   retrieve_hits  -> list[str] （注入层 join annotations 用）
# 引擎按 KB_BACKEND 配置切换：lexical（现有分词）→ embedding（第二步实现）。


class BaseBackend:
    """检索后端接口。str 出口与 hits 出口必须共享同一匹配引擎。"""

    def retrieve_str(self, query_keywords: list[str], kb_name: str, top_k: int = 10) -> str:
        raise NotImplementedError

    def retrieve_hits(self, query_keywords: list[str], kb_name: str, top_k: int = 10) -> list:
        raise NotImplementedError


class LexicalBackend(BaseBackend):
    """现有分词/关键词匹配后端（行为与重构前 retrieve_kb 完全一致）。"""

    def retrieve_str(self, query_keywords: list[str], kb_name: str, top_k: int = 10) -> str:
        return _retrieve_kb_lexical_str(query_keywords, kb_name, top_k)

    def retrieve_hits(self, query_keywords: list[str], kb_name: str, top_k: int = 10) -> list:
        return _retrieve_kb_lexical_hits(query_keywords, kb_name, top_k)


# 后端注册表：embedding 后端第二步注册（惰性 import，避免引入重依赖）
_BACKENDS: dict[str, BaseBackend] = {"lexical": LexicalBackend()}


def _get_backend() -> BaseBackend:
    name = os.environ.get("KB_BACKEND", "lexical").strip().lower()
    if name not in _BACKENDS:
        if name == "embedding":
            # 惰性加载：只有显式切到 embedding 才引入 sentence-transformers 重依赖
            try:
                from services.kb_embedding import register_embedding_backend
                register_embedding_backend()
            except Exception as e:
                # 生产兜底：embedding 初始化失败（模型缺失/损坏/依赖不全）时降级 lexical，
                # 不挂服务；降级状态打印到 stderr，供部署监控抓取（见 README 生产切换节）
                print(f"[kb_loader] WARN: embedding 后端初始化失败，降级 lexical: {e}", file=__import__("sys").stderr)
                if "embedding" not in _BACKENDS:
                    _BACKENDS["embedding"] = _BACKENDS["lexical"]
        else:
            raise ValueError(f"未知检索后端: {name}，可选 {sorted(_BACKENDS)}")
    return _BACKENDS[name]


def register_backend(name: str, backend: BaseBackend) -> None:
    """注册后端实现（embedding 后端初始化时调用）。"""
    _BACKENDS[name] = backend


def retrieve_kb(query_keywords: list[str], kb_name: str, top_k: int = 10) -> str:
    """从知识库中检索与关键词相关的条目（str 出口，契约不变）。

    Args:
        query_keywords: 关键词列表（星曜名、格局名、宫位名等）
        kb_name: 知识库文件名（如 "ziwei_stars.json"），必须已登记
        top_k: 最多返回条数

    Returns:
        拼接好的文本片段。未登记知识库显式抛 ValueError。
    """
    _assert_registered(kb_name)
    return _get_backend().retrieve_str(query_keywords, kb_name, top_k)


def retrieve_hits(query_keywords: list[str], kb_name: str, top_k: int = 10) -> list:
    """命中条目名列表（hits 出口，注入层 join annotations 用）。

    与 retrieve_kb 共享同一匹配引擎：同一 keywords 下，
    hits 名单与 str 文本中出现的条目一一对应（一致性由评测侧第三道校验兜底）。
    """
    _assert_registered(kb_name)
    return _get_backend().retrieve_hits(query_keywords, kb_name, top_k)


# ═══ lexical 后端实现 ═══

def _retrieve_kb_lexical_str(query_keywords: list[str], kb_name: str, top_k: int = 10) -> str:
    kb = _load_json_kb(kb_name)
    if not kb:
        return ""

    # ── 特殊结构处理 ──
    # ziwei_stars.json：{星曜名: {庙旺陷: {...}, ...}}
    if kb_name == "ziwei_stars.json":
        return _format_stars(_match_stars(kb, query_keywords, top_k))
    # ziwei_fuzuo.json：{辅星名: {分宫: {...}, 组合: {...}}}（generic 转发）
    if kb_name == "ziwei_fuzuo.json":
        return _format_generic(_match_generic(kb, query_keywords, top_k))
    # ziwei_star_palace.json：{星曜名: {宫位名: "解释"}}
    if kb_name == "ziwei_star_palace.json":
        return _format_star_palace(_match_star_palace(kb, query_keywords, top_k))
    # ziwei_classics.json：古籍引用（generic 转发）
    if kb_name == "ziwei_classics.json":
        return _format_generic(_match_generic(kb, query_keywords, top_k))
    # ziwei_qawenlun.json：诸星问答论（按 star 字段精确匹配）
    if kb_name == "ziwei_qawenlun.json":
        return _format_qawenlun(_match_qawenlun(kb, query_keywords, top_k))
    # ziwei_fu.json：卷一赋文（按正文关键词命中度）
    if kb_name == "ziwei_fu.json":
        return _format_fu(_match_fu(kb, query_keywords, top_k))
    # ziwei_geju.json：格局诗（按格名/关键词命中度）
    if kb_name == "ziwei_geju.json":
        return _format_geju(_match_geju(kb, query_keywords, top_k))
    # ── 通用检索 ──
    return _format_generic(_match_generic(kb, query_keywords, top_k))


def _retrieve_kb_lexical_hits(query_keywords: list[str], kb_name: str, top_k: int = 10) -> list:
    kb = _load_json_kb(kb_name)
    if not kb:
        return []
    if kb_name == "ziwei_stars.json":
        return [name for _, _, name, _ in _match_stars(kb, query_keywords, top_k)]
    if kb_name == "ziwei_fuzuo.json":
        return [key for _, key, _ in _match_generic(kb, query_keywords, top_k)]
    if kb_name == "ziwei_star_palace.json":
        # filtered = {星名: 星数据}，条目名是星名
        return [name for _, _, filtered in _match_star_palace(kb, query_keywords, top_k) for name in filtered]
    if kb_name == "ziwei_classics.json":
        # 条目级：格局名（str 出口仍是 generic dump，hits 出口做条目级供注入层 join）
        return [name for _, name, _ in _match_classics(kb, query_keywords, top_k)]
    if kb_name == "ziwei_qawenlun.json":
        return [p.get('star', '') for _, p in _match_qawenlun(kb, query_keywords, top_k)]
    if kb_name == "ziwei_fu.json":
        return [p.get('title', '') for _, p in _match_fu(kb, query_keywords, top_k)]
    if kb_name == "ziwei_geju.json":
        return [p.get('name', '') for _, p in _match_geju(kb, query_keywords, top_k)]
    return [key for _, key, _ in _match_generic(kb, query_keywords, top_k)]


# ── 诸星问答论匹配（按 star 字段，2026-08-04 加）──

def _match_qawenlun(kb: dict, keywords: list[str], top_k: int) -> list:
    """按 star 字段匹配问答段落：关键词命中星名权重最高，命中问答/正文次之。
    体系过滤：school 字段预留（全书系/中州系/飞星系），当前注入不指定体系；
    将来多体系入库时按引擎体系过滤，防止意象断语混用。"""
    S2T = {'机': '機', '阳': '陽', '贞': '貞', '阴': '陰', '贪': '貪', '门': '門', '杀': '殺',
           '军': '軍', '辅': '輔', '钺': '鉞', '马': '馬', '权': '權', '罗': '羅', '铃': '鈴',
           '虚': '虛', '禄': '祿'}
    norm = lambda s: ''.join(S2T.get(c, c) for c in s)
    norm_kw = [norm(k) for k in keywords]
    hits = []
    for p in kb.get('paragraphs', []) or []:
        star = norm(p.get('star', ''))
        q_text = p.get('question', '') + p.get('text', '')
        score = 0
        for kw in norm_kw:
            if kw and (kw == star or kw in star or star in kw):
                score += 3
            elif kw and kw in q_text:
                score += 1
        if score:
            hits.append((score, p))
    hits.sort(key=lambda x: -x[0])
    return hits[:top_k]


def _format_qawenlun(hits: list) -> str:
    parts = []
    for _, p in hits:
        school_tag = {'quanshu': '（全书系）', 'zhongzhou': '（中州系）', 'feixing': '（飞星系）'}.get(p.get('school', ''), '')
        parts.append(f"【{p.get('star', '')}】{p.get('question', '')}{school_tag}\n{p.get('text', '')}")
    return "\n\n".join(parts)


# ── 卷一赋文匹配（按正文关键词命中度，2026-08-04 加）──

def _match_fu(kb: dict, keywords: list[str], top_k: int) -> list:
    """赋文匹配：关键词在正文命中数打分，取最相关的 1-2 篇（赋文是整体论断，非按星）。"""
    S2T = {'机': '機', '阳': '陽', '贞': '貞', '阴': '陰', '贪': '貪', '门': '門', '杀': '殺',
           '军': '軍', '辅': '輔', '钺': '鉞', '马': '馬', '权': '權', '罗': '羅', '铃': '鈴',
           '虚': '虛', '禄': '祿', '准': '準', '绳': '繩', '发': '發', '补': '補', '率': '率'}
    norm = lambda s: ''.join(S2T.get(c, c) for c in s)
    norm_kw = [norm(k) for k in keywords if k]
    hits = []
    for p in kb.get('paragraphs', []) or []:
        text = (p.get('title', '') + p.get('text', ''))
        score = sum(1 for kw in norm_kw if kw in text)
        if score:
            hits.append((score, p))
    hits.sort(key=lambda x: -x[0])
    return hits[:top_k]


def _format_fu(hits: list) -> str:
    parts = []
    for _, p in hits:
        school_tag = {'quanshu': '（全书系）', 'zhongzhou': '（中州系）', 'feixing': '（飞星系）'}.get(p.get('school', ''), '')
        parts.append(f"【{p.get('title', '')}】{school_tag}\n{p.get('text', '')}")
    return "\n\n".join(parts)


# ── 格局诗匹配（按格名/关键词，2026-08-04 加）──

def _match_geju(kb: dict, keywords: list[str], top_k: int) -> list:
    """格局诗匹配：格名命中权重最高，条件/诗句命中次之。"""
    hits = []
    for p in kb.get('paragraphs', []) or []:
        name = p.get('name', '')
        full = name + p.get('condition', '') + p.get('poem', '')
        score = 0
        for kw in keywords:
            if not kw:
                continue
            if kw in name:
                score += 3
            elif kw in full:
                score += 1
        if score:
            hits.append((score, p))
    hits.sort(key=lambda x: -x[0])
    return hits[:top_k]


def _format_geju(hits: list) -> str:
    parts = []
    for _, p in hits:
        cond = f"（成格条件：{p.get('condition', '')}）" if p.get('condition') else ''
        parts.append(f"【{p.get('name', '')}】{cond}\n{p.get('poem', '')}")
    return "\n\n".join(parts)


# ── 匹配核心（str 与 hits 共用，保证一个引擎）──

def _match_stars(kb: dict, keywords: list[str], top_k: int) -> list:
    """星曜匹配：返回 [(score, section, star_name, summary)]"""
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

    matched.sort(key=lambda x: -x[0])
    return matched[:top_k]


def _format_stars(matched: list) -> str:
    if not matched:
        return ""
    lines = []
    for _, section, name, data in matched:
        prefix = {"main_stars": "⭐", "auspicious_stars": "🟢", "malefic_stars": "🔴"}.get(section, "")
        props = ", ".join(f"{k}:{v}" for k, v in data.items() if v)
        lines.append(f"{prefix} {name}：{props}")
    return "\n".join(lines)


def _match_star_palace(kb: dict, keywords: list[str], top_k: int) -> list:
    """星曜×宫位匹配：返回 [(score, star_name, filtered_palaces)]"""
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
            filtered = {k: v for k, v in palace_data.items()
                       if any(kw in k for kw in keywords)}
            matched.append((score, star_name, filtered))

    matched.sort(key=lambda x: -x[0])
    return matched[:top_k]


def _format_star_palace(matched: list) -> str:
    if not matched:
        return ""
    parts = []
    for _, name, data in matched:
        parts.append(f"### {name}\n{json.dumps(data, ensure_ascii=False, indent=2)}")
    return "\n\n".join(parts)


def _match_generic(kb: dict, keywords: list[str], top_k: int) -> list:
    """通用匹配：遍历所有键值对，返回 [(score, key, value)]"""
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

    matched.sort(key=lambda x: -x[0])
    return matched[:top_k]


def _match_classics(kb: dict, keywords: list[str], top_k: int) -> list:
    """古籍引用条目级匹配：返回 [(score, 格局名, 条目文本)]。

    结构：{_description, sources, patterns: {格局名: 引文+按语 str}}。
    只供 hits 出口用；str 出口保持 generic dump（保护基线锚点）。
    """
    patterns = kb.get("patterns", {})
    if not isinstance(patterns, dict):
        return []
    matched = []
    for name, text in patterns.items():
        if not isinstance(text, str):
            continue
        score = 0
        for kw in keywords:
            if kw in name:
                score += 2
            if kw in text:
                score += 1
        if score > 0:
            matched.append((score, name, text))
    matched.sort(key=lambda x: -x[0])
    return matched[:top_k]


def _format_generic(matched: list) -> str:
    if not matched:
        return ""
    parts = []
    for _, key, value in matched:
        val_str = json.dumps(value, ensure_ascii=False, indent=2) if isinstance(value, (dict, list)) else str(value)
        parts.append(f"### {key}\n{val_str}")
    return "\n\n".join(parts)


# 兼容旧名（_retrieve_fuzuo / _retrieve_classics 曾是独立函数，现为 generic 转发语义）
def _retrieve_fuzuo(kb: dict, keywords: list[str], top_k: int) -> str:
    return _format_generic(_match_generic(kb, keywords, top_k))


def _retrieve_classics(kb: dict, keywords: list[str], top_k: int) -> str:
    return _format_generic(_match_generic(kb, keywords, top_k))


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
