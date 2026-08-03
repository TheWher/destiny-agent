#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""紫微斗数深度分析服务

调用 DeepSeek API，以 ziwei-master Agent 的系统提示词为指导进行紫微命盘分析。
"""

import json
import os
import re
import time
import requests

from services.kb_loader import _KB_DIR, _kb_cache, _load_json_kb, KB_PATH, KB_EXTENDED_PATH, retrieve_kb, extract_ziwei_keywords
from services.kb_inject import join_classics_str
from services.llm_client import API_CONFIG, _call_api, _call_api_stream

# Agent 定义文件
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIWEI_AGENT_PATH = os.path.join(_ROOT, ".claude", "agents", "ziwei-master.md")


# 紫微斗数分析
# ============================================================


def _load_ziwei_system_prompt() -> str:
    """加载紫微斗数 Agent 系统提示词，附加星曜知识库"""
    if not os.path.exists(ZIWEI_AGENT_PATH):
        return "你是一位拥有30年实战经验的紫微斗数命理师..."

    with open(ZIWEI_AGENT_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # 去除 YAML frontmatter
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3:].strip()

    # 追加星曜参考（精简表，~2KB）
    stars_kb = _load_json_kb("ziwei_stars.json")
    if stars_kb:
        main = stars_kb.get("main_stars", {})
        if main:
            lines = ["\n## 📚 十四主星速查\n", "| 星曜 | 五行·类型 | 正面特质 | 注意点 |", "|------|-----------|----------|--------|"]
            for name, info in main.items():
                lines.append(f"| {name} | {info.get('element','')}·{info.get('type','')} | {info.get('positive','')[:24]} | {info.get('negative','')[:24]} |")
            aus = stars_kb.get("auspicious_stars", {})
            mal = stars_kb.get("malefic_stars", {})
            if aus or mal:
                lines.append("\n**六吉**：" + "、".join(f"{k}({v.get('meaning','')})" for k, v in aus.items()))
                lines.append("**六煞**：" + "、".join(f"{k}({v.get('meaning','')})" for k, v in mal.items()))
            content += "\n".join(lines)
    # 注：ziwei_star_palace.json 不在此处加载，由 _build_ziwei_user_message 按需检索

    # 追加四化参考（精简表）
    hua_kb = _load_json_kb("ziwei_hua.json")
    if hua_kb:
        tbl = hua_kb.get("table", {})
        if tbl:
            lines = ["\n## 📚 十干四化速查\n", "| 天干 | 化禄 | 化权 | 化科 | 化忌 |", "|------|------|------|------|------|"]
            for gan in "甲乙丙丁戊己庚辛壬癸":
                r = tbl.get(gan, {})
                lines.append(f"| {gan} | {r.get('化祿','')} | {r.get('化權','')} | {r.get('化科','')} | {r.get('化忌','')} |")
            content += "\n".join(lines)

    return content


def _match_combo(combo_key: str, pal: dict, plate_dict: dict, branch_order: str) -> bool:
    """检查中州派组合规则是否匹配当前命盘"""
    if '夹' in combo_key:
        branch_to_pal = {p['earthly_branch']: p for p in plate_dict.get('palaces', [])}
        br = pal.get('earthly_branch', '')
        idx = branch_order.find(br)
        if idx < 0:
            return False
        prev_br = branch_order[(idx - 1) % 12]
        next_br = branch_order[(idx + 1) % 12]
        return prev_br in branch_to_pal and next_br in branch_to_pal
    if '对拱' in combo_key or '对星' in combo_key:
        return True
    if '单星' in combo_key:
        has_peer = len(pal.get('minor_stars', [])) > 1
        return not has_peer
    return True


def _build_ziwei_user_message(plate_dict: dict, bazi_ref: dict = None) -> str:
    """构造紫微斗数分析请求"""
    p = plate_dict
    info = p.get("input", {})
    palaces = p.get("palaces", [])
    year_mutagens = p.get("year_mutagens", [])

    parts = []
    parts.append("请根据以下紫微斗数命盘进行完整的命理分析。")
    parts.append("")
    parts.append("## 命盘概要")
    parts.append("")
    parts.append(f"- 公历出生：{info.get('birth_datetime', '未知')}")
    parts.append(f"- 性别：{info.get('gender', '?')}")
    parts.append(f"- 五行局：{p.get('five_elements_class', '?')}")
    parts.append(f"- 命宫在：{p.get('soul_palace', '?')}宫")
    parts.append(f"- 身宫在：{p.get('body_palace', '?')}宫")
    parts.append("")

    # 十二宫表
    parts.append("## 十二宫分布")
    parts.append("")
    parts.append("| 宫位 | 干支 | 主星 | 辅星 | 杂曜 | 十二长生 | 四化 | 大限 | 标记 |")
    parts.append("|------|------|------|------|------|------|------|------|------|")
    for pal in palaces:
        stars_str = '、'.join(f"{s['name']}[{s['brightness']}]" if isinstance(s, dict) and s.get('brightness') else (s['name'] if isinstance(s, dict) else s) for s in pal['major_stars']) if pal['major_stars'] else '空宫'
        minor_str = '、'.join(s['name'] if isinstance(s, dict) else s for s in pal['minor_stars'][:4]) if pal['minor_stars'] else '—'
        adj_str = '、'.join(s['name'] if isinstance(s, dict) else s for s in pal.get('adjective_stars',[])[:4]) if pal.get('adjective_stars') else '—'
        cs_str = pal.get('changsheng','—')
        mut_str = '、'.join(f"{m['star']}{m['mutagen']}" for m in pal['mutagens']) if pal['mutagens'] else '—'
        tags_str = '、'.join(pal['tags']) if pal['tags'] else ''
        parts.append(
            f"| {pal['name']} | {pal['dizhi']} | {stars_str} | {minor_str} | {adj_str} | {cs_str} | {mut_str} | {pal['decadal_range']} | {tags_str} |"
        )
    parts.append("")

    # 生年四化
    if year_mutagens:
        parts.append("## 生年四化")
        parts.append("")
        for m in year_mutagens:
            parts.append(f"- {m['star']} → {m['mutagen']}（{m['palace']}·{m['branch']}）")
        parts.append("")

    # ═══ 大限四化 + 流年数据（引擎计算，禁止 LLM 自行推算） ═══
    GAN_SIHUA = {
        '甲': {'化禄': '廉贞', '化权': '破军', '化科': '武曲', '化忌': '太阳'},
        '乙': {'化禄': '天机', '化权': '天梁', '化科': '紫微', '化忌': '太阴'},
        '丙': {'化禄': '天同', '化权': '天机', '化科': '文昌', '化忌': '廉贞'},
        '丁': {'化禄': '太阴', '化权': '天同', '化科': '天机', '化忌': '巨门'},
        '戊': {'化禄': '贪狼', '化权': '太阴', '化科': '右弼', '化忌': '天机'},
        '己': {'化禄': '武曲', '化权': '贪狼', '化科': '天梁', '化忌': '文曲'},
        '庚': {'化禄': '太阳', '化权': '武曲', '化科': '太阴', '化忌': '天同'},
        '辛': {'化禄': '巨门', '化权': '太阳', '化科': '文曲', '化忌': '文昌'},
        '壬': {'化禄': '天梁', '化权': '紫微', '化科': '左辅', '化忌': '武曲'},
        '癸': {'化禄': '破军', '化权': '巨门', '化科': '太阴', '化忌': '贪狼'},
    }
    GAN = '甲乙丙丁戊己庚辛壬癸'
    ZHI = '子丑寅卯辰巳午未申酉戌亥'

    import datetime as _dt
    current_year = _dt.date.today().year
    liunian_gan = GAN[(current_year - 4) % 10]
    liunian_zhi = ZHI[(current_year - 4) % 12]
    liunian_gz = liunian_gan + liunian_zhi

    # 前后一年
    prev_gz = GAN[(current_year - 5) % 10] + ZHI[(current_year - 5) % 12]
    next_gz = GAN[(current_year - 3) % 10] + ZHI[(current_year - 3) % 12]

    # 当前年龄
    birth_str = info.get('birth_datetime', '')
    birth_year = int(birth_str[:4]) if birth_str and birth_str[:4].isdigit() else 0
    current_age = current_year - birth_year if birth_year else 0

    # 大限四化表
    parts.append("## 大限四化（宫干飞化，引擎已算好，直接引用）")
    parts.append("")
    parts.append("| 宫位 | 大限干支 | 化禄 | 化权 | 化科 | 化忌 |")
    parts.append("|------|----------|------|------|------|------|")
    current_decadal = None
    for pal in palaces:
        dz = pal.get('decadal_dizhi', '')
        gan = dz[0] if dz and len(dz) >= 1 else ''
        fly = GAN_SIHUA.get(gan, {})
        parts.append(f"| {pal['name']} | {dz or '—'} | {fly.get('化禄','—')} | {fly.get('化权','—')} | {fly.get('化科','—')} | {fly.get('化忌','—')} |")
        # 找当前大限
        dr = pal.get('decadal_range', '')
        if dr and '-' in dr and current_age > 0:
            try:
                lo, hi = dr.split('-')
                if int(lo) <= current_age <= int(hi):
                    current_decadal = pal
            except ValueError:
                pass
    parts.append("")

    # 当前大限
    if current_decadal:
        parts.append("## 当前大限")
        parts.append("")
        cd_name = current_decadal['name']
        cd_range = current_decadal['decadal_range']
        cd_dz = current_decadal.get('decadal_dizhi', '?')
        cd_gan = cd_dz[0] if cd_dz and len(cd_dz) >= 1 else ''
        cd_fly = GAN_SIHUA.get(cd_gan, {})
        parts.append(f"- 当前 {current_age} 岁，正行 **{cd_name}** 大限（{cd_range}岁），大限干支 **{cd_dz}**")
        if cd_fly:
            parts.append(f"- 大限四化：{'、'.join(f'{mu}→{star}' for mu, star in cd_fly.items())}")
            # 找四化落在哪个宫
            for mu, star in cd_fly.items():
                for pal in palaces:
                    for s in pal.get('major_stars', []) + pal.get('minor_stars', []):
                        sn = s['name'] if isinstance(s, dict) else s
                        if sn == star:
                            parts.append(f"  - {mu} **{star}** 在 **{pal['name']}** 宫")
                            break
        parts.append("")

    # 流年
    parts.append("## 当前流年（引擎已算好干支，禁止自行推算）")
    parts.append("")
    parts.append(f"| 年份 | 干支 | 流年四化 |")
    parts.append(f"|------|------|----------|")
    for offset, label in [(-1, f'{current_year-1}年'), (0, f'{current_year}年（当前）'), (1, f'{current_year+1}年')]:
        yg = GAN[(current_year + offset - 4) % 10]
        yz = ZHI[(current_year + offset - 4) % 12]
        y_fly = GAN_SIHUA.get(yg, {})
        fly_str = '、'.join(f'{mu}→{star}' for mu, star in y_fly.items()) if y_fly else '—'
        parts.append(f"| {label} | {yg}{yz} | {fly_str} |")
    parts.append("")
    parts.append("**⛔ 以上所有干支、四化均为排盘引擎精确计算结果。不要自行推算干支，不要编造年份。直接引用上表。**")
    parts.append("")

    # ═══ 中州派辅佐煞曜按需检索 ═══
    keywords = extract_ziwei_keywords(plate_dict)
    fuzuo_text = retrieve_kb(keywords, "ziwei_fuzuo.json", top_k=8)
    if fuzuo_text:
        parts.append("\n## 中州派辅佐煞曜参考（按命盘星曜检索）")
        parts.append(fuzuo_text)

    # ═══ 诸星问答论按需检索（2026-08-04 加，公版古籍，按盘面星曜取对应问答）═══
    qawenlun_text = retrieve_kb(keywords, "ziwei_qawenlun.json", top_k=5)
    if qawenlun_text:
        parts.append("\n## 📖 诸星问答论（全书卷一，公版古籍；星曜特质权威问答，引用时以引擎盘面为准）")
        parts.append(qawenlun_text)

    # ═══ 卷一赋文总纲按需检索（2026-08-04 加，太微/形性/星垣等论断总纲）═══
    fu_text = retrieve_kb(keywords, "ziwei_fu.json", top_k=2)
    if fu_text:
        parts.append("\n## 📜 卷一赋文总纲（全书卷一，公版古籍；论断意象参考，引用时以引擎盘面为准）")
        parts.append(fu_text)

    # ═══ 格局诗按需检索（2026-08-04 加，按盘面格局/星曜关键词取对应格局诗）═══
    geju_kw = list(keywords)
    for pat in (plate_dict.get('patterns') or []):
        if pat.get('name'):
            geju_kw.append(pat['name'])
    geju_text = retrieve_kb(geju_kw, "ziwei_geju.json", top_k=3)
    if geju_text:
        parts.append("\n## 🏛 格局诗（全书卷一，公版古籍；成格条件+断语，核验格局时引用）")
        parts.append(geju_text)

    # ═══ 卷三星曜分宫断语按需检索（2026-08-04 加，按盘面星曜取分宫断语）═══
    juan3_text = retrieve_kb(keywords, "ziwei_juan3.json", top_k=4)
    if juan3_text:
        parts.append("\n## ✨ 星曜分宫断语（全书卷三，公版古籍；庙旺陷+分宫吉凶，断星曜时引用）")
        parts.append(juan3_text)

    # 古籍引用（格局→原文按需检索；join annotations 分层呈现，转述不带引号，防假出处）
    patterns = plate_dict.get('patterns', [])
    if patterns:
        pat_kw = [p.get('name', '') for p in patterns if p.get('name')]
        # plate_ctx = 命盘格局名集合：hits 与之有交集才裁（命中格局不在盘里则回退全量，不裁空）
        plate_ctx = set(pat_kw)
        classics_text = join_classics_str(pat_kw, plate_ctx=plate_ctx, top_k=5)
        if classics_text:
            parts.append("## 📜 古籍引用（按格局检索）")
            parts.append(classics_text)
            parts.append("")
    # ═══ 八字参考注入 ═══
    if bazi_ref:
        parts.append("## 八字参考（交叉验证用）")
        # 四柱
        pillars = bazi_ref.get('pillars', [])
        if pillars:
            parts.append("| | 年柱 | 月柱 | 日柱 | 时柱 |")
            parts.append("|---|---|---|---|---|")
            row_gz = "| 干支 |"
            row_ss = "| 十神 |"
            for p in pillars:
                row_gz += f" {p['gz']}（{p['gan_wx']}/{p['zhi_wx']}) |"
                row_ss += f" {p['shishen']} |"
            parts.append(row_gz)
            parts.append(row_ss)
        # 五行
        wx = bazi_ref.get('wuxing', {})
        if wx:
            parts.append(f"\n五行统计：{' · '.join(f'{k}{v}' for k,v in wx.items())}")
        # 起运 + 大运
        if bazi_ref.get('qiyun'):
            parts.append(f"\n起运：{bazi_ref['qiyun']}")
        dayun = bazi_ref.get('dayun', [])
        if dayun:
            parts.append(f"大运：{' → '.join(dayun)}")
        # 八字独立分析结论
        if bazi_ref.get('bazi_analysis'):
            parts.append("")
            parts.append("## 八字独立分析（梁湘润体系）")
            parts.append(bazi_ref['bazi_analysis'])
            parts.append("")
            parts.append("以上为同一生辰的八字独立分析结论。请在解读紫微盘时，将八字结论作为交叉验证的基准线。")
        elif bazi_ref.get('geju'):
            # 兼容旧格式
            parts.append(f"\n**八字分析结论**：")
            parts.append(f"- 格局：{bazi_ref['geju']}")
            parts.append(f"- 旺衰：{bazi_ref.get('wangsan','?')}")
            xiyong = bazi_ref.get('xiyong', [])
            if xiyong: parts.append(f"- 喜用：{'、'.join(xiyong)}")
            if bazi_ref.get('jieshuo'): parts.append(f"- 综述：{bazi_ref['jieshuo']}")
        # 交叉验证指令（基于测天机方法论）
        parts.append("")
        parts.append("**交叉验证要求**：请结合以上八字数据，在分析紫微盘时做到：")
        parts.append("1. **象的比对**：八字十神与紫微宫位对应（财星↔财帛宫、官星↔官禄宫、印星↔父母宫、比劫↔兄弟宫），比对两者信号是否趋同")
        parts.append("2. **分歧处理**：如八字显示某方向强（如木旺印星重）但紫微对应宫位弱（如父母宫空劫），说明八字的能力/资源 ≠ 该领域的具体关系质量，需分层表述")
        parts.append("3. **时间叠合**：当前大限与八字大运的时间段做对齐，大限与流年叠盘时参考八字的流年干支")
        parts.append("4. **综合结论**：八字定基调（贫富寿夭层次），紫微定场景（职业类型、人际关系具体形态），在分析每个章节时，如八字与紫微信号一致则强化结论，若冲突则指出矛盾并给出辩证解读")
        parts.append("")
    # ═══ 验盘阶段 ═══
    verification = plate_dict.get('_verification_mode', False)
    if verification:
        known_events = plate_dict.get('_known_events', None)
        verified_events = plate_dict.get('_verified_events', None)
        parts.append("## 📍 验盘环节")
        parts.append("")
        if known_events and len(known_events) > 0:
            parts.append("以下为用户提供的已知人生事件，请在正式分析前逐一核验每个事件是否能从命盘中找到对应信号，标注对应信号等级（S/A/B/C/D/E），然后直接进入完整分析。")
            parts.append("")
            for i, evt in enumerate(known_events):
                parts.append(f"{i+1}. **{evt.get('year','')}年**：{evt.get('desc','')}")
            parts.append("")
        elif verified_events:
            parts.append("以下为已验证的人生事件，已确认为正确的锚点。在后续分析中以这些事件为参照。")
            parts.append("")
            for i, evt in enumerate(verified_events):
                parts.append(f"{i+1}. **{evt.get('year','')}年确认事件**：{evt.get('desc','')}")
            parts.append("")
        else:
            ca = plate_dict.get('_current_age', 0)
            parts.append("要求：先不着急输出完整命盘分析。请先做验盘——基于命盘信号，倒退命主可能经历过的3~4件人生大事。")
            parts.append("")
            parts.append("### 验盘信号优先级")
            parts.append("")
            parts.append("| 等级 | 信号 | 精度 | 触发条件 |")
            parts.append("|------|------|------|----------|")
            parts.append("| **S** | 流年命宫=大限命宫=生年忌/禄所在宫（三层叠并） | ±1年 | 三盘重合于关键宫位，人生转折点 |")
            parts.append("| **A** | 生年忌+大限忌同宫+流年引动（双忌叠冲） | ±1年 | 两个以上四化忌同宫汇聚 |")
            parts.append("| **B** | 大限交接年 ±2年 | ±2年 | 每十年一次，必有结构性变化 |")
            parts.append("| **C** | 流年化忌飞入大限命宫 / 流年命宫=关键宫 | ±2年 | 单层触发但方向明确 |")
            parts.append("| **D** | 四化飞入+三方四正承接 | ±2年 | 需对宫+三合同步配合 |")
            parts.append("| **E** | 大限主星类型变化 | ±3年 | 趋势级，不适合精确验盘 |")
            parts.append("")
            parts.append("### 常见验盘锚点（按可验证性排序）")
            parts.append("")
            parts.append("1. 学业/升学 → 父母宫/官禄宫四化触发")
            parts.append("2. 事业转折 → 官禄宫/大限交接四化触发")
            parts.append("3. 感情/婚姻 → 夫妻宫/福德宫四化触发")
            parts.append("4. 搬家/迁居 → 田宅宫/迁移宫大限变化")
            parts.append("5. 家庭变迁 → 父母宫/田宅宫煞忌触发")
            parts.append(f"6. 健康事件 → 疾厄宫化忌+煞星触发（仅限{ca}岁前）")
            parts.append("")
            parts.append("### 验盘输出格式")
            parts.append("")
            parts.append("严格按以下格式输出，不要自己发挥标题：")
            parts.append("")
            parts.append("## 🔍 命盘验证")
            parts.append("")
            parts.append("推断依据：本命XX宫有XX信号 → ...")
            parts.append("")
            parts.append("1. **XXXX年（±2年，约XX岁）**：事件类型 — 具体推断")
            parts.append("   - 信号等级：S/A/B/C/D")
            parts.append("   - 宫位依据：XX宫 XX触发")
            parts.append("")
            parts.append("2. **XXXX年（±2年，约XX岁）**：...")
            parts.append("")
            parts.append("...")
            parts.append("")
            parts.append("**格式铁律**：每条预测独立成行；年份后用冒号接描述；描述内禁止括号注释、禁止行首标点（、，。；）；描述写完即止，不要用括号补充说明。")
            parts.append("")
            parts.append("请务必在输出完最后一条预测后，单独一行输出：【验盘完毕】")
            parts.append("输出此标记后立即停止，不要继续输出分析。")
            parts.append("")
            parts.append("### 验盘铁律")
            parts.append("")
            parts.append("1. 必须具体：写明年份+岁数+事件类型+宫位依据")
            parts.append("2. 必须有依据：每条写明宫位+四化+信号等级")
            parts.append("3. 诚实跳过：某个领域无信号则说信号不足")
            parts.append("4. 只猜过去，不预测未来")
            parts.append("5. 禁止名人污染，禁止叙事膨化（每条<80字）")
            parts.append("6. 以【验盘完毕】结束，之后立即停止")
            parts.append("")
    # ═══ 验盘阶段结束 ═══

    # 分析要求
    parts.append("## 分析要求")
    parts.append("")
    parts.append("解读时可引用上述古籍原文增加权威性。按以下结构输出 Markdown：")
    parts.append("")
    parts.append("1. ## 🎯 命盘底色 — 命宫主星分析性格底层")
    parts.append("2. ## 💼 事业格局 — 官禄宫 + 财帛宫分析")
    parts.append("3. ## 💰 财运分析 — 财帛宫深度解读")
    parts.append("4. ## ❤️ 感情因缘 — 夫妻宫分析")
    parts.append("5. ## 🔮 当前大限 — 当前十年核心课题")
    parts.append("6. ## 📅 近三年流年 — 关键节点提示")
    parts.append("")
    parts.append("每个章节按三段式展开：")
    parts.append("1. **宫位意义** — 该宫位在此命盘中的核心意涵和基调")
    parts.append("2. **主星与辅星影响** — 主星+辅星+杂曜逐个分析，说明每颗星如何调整宫位吉凶和事件细节")
    parts.append("3. **星系组合** — 将主星、辅星、杂曜、四化串联，给出整合判断和矛盾点的辩证解读")
    parts.append("")
    parts.append("详细充实，充分展开分析，不要简略。每个结论给出依据。每个章节至少写500字以上。")

    return "\n".join(parts)





def analyze_ziwei(plate_dict: dict, timeout: int = 120, bazi_ref: dict = None) -> dict:
    """紫微斗数命盘解读（单 Agent 模式），支持验盘截停

    使用完整的 ziwei-master.md prompt，注入知识库和八字参考
    如果 plate_dict['_verification_mode']=True 且未提供已知事件，则使用 stop_sequences=['【验盘完毕】'] 截停
    """
    if not API_CONFIG.get("api_key"):
        return {"success": False, "error": "未配置 API Key"}

    system_prompt = _load_ziwei_system_prompt()
    user_message = _build_ziwei_user_message(plate_dict, bazi_ref=bazi_ref)
    user_messages = [{"role": "user", "content": user_message}]

    # 验盘模式且无已知事件 → 截停在【验盘完毕】
    verification = plate_dict.get('_verification_mode', False)
    has_known = plate_dict.get('_known_events') or plate_dict.get('_verified_events')
    if verification and not has_known:
        result = _call_api(system_prompt, user_messages,
                           max_tokens=16384, temperature=0.3, timeout=timeout,
                           stop_sequences=['【验盘完毕】'])
        if result.get("success") and result.get("text"):
            result["analysis"] = result.pop("text")
            result["verification"] = _verify_ziwei_predictions(result["analysis"], plate_dict)
        return result

    result = _call_api(system_prompt, user_messages,
                       max_tokens=32768, temperature=0.7, timeout=timeout)

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


def _verify_ziwei_predictions(analysis_text: str, plate_dict: dict) -> dict:
    """后处理硬校验：检查 Agent 验盘预测的合规性
    
    不做正确性判断，只检查格式和信号引用的合理性。
    """
    import re
    issues = []
    predictions = []
    
    # 提取年份
    year_pattern = re.findall(r'(\d{4})\s*年', analysis_text)
    # 提取信号等级
    signal_pattern = re.findall(r'[信号等级|信号].*?([SABCDE])', analysis_text)
    
    current_year = plate_dict.get('_current_year', 2026)
    birth_year = plate_dict.get('birth_year', 0)
    
    # 检查1：至少2条预测
    if len(year_pattern) < 2:
        issues.append("预测条数不足（<2条），无法进行有效验盘")
    
    # 检查2：年份不应超过当前年份
    for y_str in year_pattern:
        y = int(y_str)
        if y > current_year:
            issues.append(f"预测年份{y}年晚于当前年份{current_year}年，违反'只猜过去'规则")
    
    # 检查3：不应包含未来预测
    future_markers = ['未来', '将来', '将会', '有望', '预计', '前程']
    for marker in future_markers:
        if marker in analysis_text:
            issues.append(f"验盘中出现未来预测关键词'{marker}'，验盘应只回顾过去")
            break
    
    # 检查4：不应有名人引用
    if '多尔衮' in analysis_text or '豪格' in analysis_text or '李世民' in analysis_text:
        issues.append("验盘中出现名人引用，违反'禁止名人污染'规则")
    
    return {
        "predictions_count": len(year_pattern),
        "years_found": list(set(year_pattern)),
        "signal_levels_found": signal_pattern,
        "issues": issues,
        "passed": len(issues) == 0,
    }


def continue_ziwei_analysis(messages: list[dict], user_reply: str, timeout: int = 600) -> dict:
    """紫微斗数多轮对话续接"""
    if not API_CONFIG.get("api_key"):
        return {"success": False, "error": "未配置 API Key"}

    url = f"{API_CONFIG['base_url']}/v1/messages"
    headers = {"Content-Type": "application/json", "x-api-key": API_CONFIG["api_key"], "anthropic-version": "2023-06-01"}

    api_messages = []; system_msg = None
    for m in messages:
        if m["role"] == "system": system_msg = m
        else: api_messages.append({"role": m["role"], "content": m["content"]})
    api_messages.append({"role": "user", "content": user_reply})

    payload = {"model": API_CONFIG["model"], "max_tokens": 16384, "temperature": 0.7, "thinking": {"type": "disabled"}, "system": system_msg["content"] if system_msg else "", "messages": api_messages}

    for attempt in range(2):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code != 200: return {"success": False, "error": f"API 错误({resp.status_code}): {resp.text[:200]}"}
            data = resp.json(); text = ""
            for block in data.get("content", []):
                if block.get("type") == "text": text += block["text"]
            if text: return {"success": True, "analysis": text}
            if attempt == 0: time.sleep(3); continue
            return {"success": False, "error": "API 返回空内容"}
        except requests.Timeout: return {"success": False, "error": f"超时({timeout}s)"}
        except Exception as e:
            if attempt == 0: time.sleep(3); continue
            return {"success": False, "error": str(e)}
    return {"success": False, "error": "所有重试失败"}


# ════════════════════════════════════════════════════════
# 解读输出 vs 盘面机器校验（2026-08-04 加，加强审查层）
# PythonAnywhere 基础版约束：纯正则规则，零新依赖，O(文本长度)。
# 策略：高置信低误报——宁可漏检不可误报（误报会把正确解读标错）。
# ════════════════════════════════════════════════════════

_ZW_PALACE_NORM = {'命宮': '命宫', '財帛': '财帛', '官祿': '官禄', '遷移': '迁移'}
_ZW_STARS = ['紫微', '天机', '太阳', '武曲', '天同', '廉贞', '天府', '太阴', '贪狼', '巨门',
             '天相', '天梁', '七杀', '破军', '禄存', '左辅', '右弼', '文昌', '文曲', '天魁',
             '天钺', '擎羊', '陀罗', '火星', '铃星', '地空', '地劫', '天马']
_ZW_CHANGSHENG = ['长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养']

# 宫位/星曜别名归一化（2026-08-04 加，防静默漏检）
# 来源：互证彩排验证（仆役=交友铁证）+ 经典别称（相貌=父母/出外=迁移）。
# 策略：只加安全多字别名，单字（日/月）不映射防误替换。
_PALACE_ALIAS = {'仆役': '交友', '奴仆': '交友', '相貌': '父母', '出外': '迁移',
               '事业宫': '官禄', '男女宫': '子女', '福寿宫': '福德'}
_STAR_ALIAS = {'紫微帝星': '紫微', '帝星': '紫微', '帝座': '紫微', '耗星': '破军', '月亮': '太阴',
               '天机星': '天机', '太阳星': '太阳', '武曲星': '武曲', '天同星': '天同',
               '廉贞星': '廉贞', '天府星': '天府', '太阴星': '太阴', '贪狼星': '贪狼',
               '巨门星': '巨门', '天相星': '天相', '天梁星': '天梁', '七杀星': '七杀',
               '破军星': '破军', '禄存星': '禄存', '左辅星': '左辅', '右弼星': '右弼',
               '文昌星': '文昌', '文曲星': '文曲', '天魁星': '天魁', '天钺星': '天钺',
               '擎羊星': '擎羊', '陀罗星': '陀罗', '火星星': '火星', '铃星星': '铃星',
               '地空星': '地空', '地劫星': '地劫', '天马星': '天马'}


def _normalize_text(text: str) -> str:
    """文本别名归一化：LLM 语料别名 → 规范名，长名优先替换防子串。"""
    mapping = []
    mapping += [(k, v) for k, v in _STAR_ALIAS.items()]
    mapping += [(k, v) for k, v in _PALACE_ALIAS.items()]
    mapping.sort(key=lambda kv: len(kv[0]), reverse=True)
    t = text
    for k, v in mapping:
        t = t.replace(k, v)
    return t


def _norm_palace(name: str) -> str:
    """宫名归一化：繁体→简体，去'宫'后缀（'命宫'本身保留）"""
    n = name or ''
    for k, v in _ZW_PALACE_NORM.items():
        n = n.replace(k, v)
    n = n.replace('宮', '宫')
    # '命宫'/'身宫' 特殊：去掉末尾'宫'后是'命'，需要还原
    if n in ('命宫', '身宫'):
        return n
    return n[:-1] if n.endswith('宫') and len(n) > 1 else n


def _build_plate_oracle(plate_dict: dict) -> dict:
    """从引擎盘面构建真值 oracle"""
    palaces = plate_dict.get('palaces', []) or []
    oracle = {
        'star_palace': {},   # 星名 -> 宫名(简)
        'changsheng': {},    # 宫名(简) -> 长生名
        'mutagens': [],      # [(星, 化, 宫名简)]
        'palace_names': set(),
    }
    for p in palaces:
        pn = _norm_palace(p.get('name', ''))
        oracle['palace_names'].add(pn)
        for s in p.get('major_stars', []) + p.get('minor_stars', []):
            sn = s.get('name', '') if isinstance(s, dict) else str(s)
            if sn:
                oracle['star_palace'].setdefault(sn, pn)
        cs = p.get('changsheng', '')
        if cs:
            oracle['changsheng'][pn] = cs
    for m in plate_dict.get('year_mutagens', []) or []:
        oracle['mutagens'].append((m.get('star', ''), m.get('mutagen', ''),
                                   _norm_palace(m.get('palace', ''))))
    return oracle


def verify_interpretation_against_plate(analysis_text: str, plate_dict: dict) -> dict:
    """加强审查：提取解读文本中的盘面引用，与引擎盘面比对。

    覆盖：星曜落宫、生年四化、长生、大限顺逆/起岁、格局、大限四化。
    大限四化（第八类，2026-08-04 实现）：oracle = 各宫位 decadal 干支 + 钉死四化表并集，
    上下文限定"大限"防误报（跟大限顺逆同套路）。
    精度边界（mose 记档）：联合表判"(星,化)在某个干合法"，非"对得上具体大限干"——
    若将来出现带干支的错配（如"辛巳大限紫微化权"）会漏检；提取到干支时可按具体干判，
    等真出这类样例再决定加精度层。
    返回: {'issues': [不一致项], 'unverified': [因缺少输入未校验的类别]}。
    delivery gate 原则（DataAIHub 防幻觉指南）：缺失输入时标记"未校验"而非静默通过，
    宁缺勿假——默认拒绝未验证声明。
    """
    if not analysis_text or not plate_dict:
        return {'issues': [], 'unverified': []}
    oracle = _build_plate_oracle(plate_dict)
    issues = []
    unverified = []
    # 别名归一化后再提取比对（防 LLM 写仆役/相貌等别名导致静默漏检）
    text = _normalize_text(analysis_text or '')
    palaces = sorted(oracle['palace_names'], key=len, reverse=True)  # 长名优先
    # 宫名正则允许省略'宫'字（'坐命'/'坐命宫'都匹配）
    _pat_palaces = '|'.join(p.replace('宫', '') + r'宫?' for p in palaces)

    # 1. 星曜落宫：X星在/坐/守/入/落 Y宫（含'X星在命宫'、'太阳坐命'等）
    for star in _ZW_STARS:
        for m in re.finditer(
            re.escape(star) + r'\s*星?\s*(?:在|坐|守|入|落于|落)\s*(' + _pat_palaces + ')',
            text,
        ):
            found_palace = _norm_palace(m.group(1))
            expected = oracle['star_palace'].get(star, '')
            if expected and found_palace != expected:
                issues.append({
                    'type': 'star_palace', 'star': star,
                    'found': found_palace, 'expected': expected,
                    'raw': m.group(0),  # 原文命中片段（标红直接用，防措辞变体重构失配）
                })

    # 2. 四化：X化禄/权/科/忌（可带'在/于/入 Y宫'）
    # 联合表校验：生年四化 ∪ 大限四化并集——"不在生年表"可能是合法大限四化
    # （如壬午大限紫微化权），单独按生年表判错会误报（King 04:34 反馈）。
    # 先构建联合表：生年 + 各宫位大限
    try:
        from ziwei_calculator import _GAN_SIHUA_TABLE
        _year_gan = ''
        _birth = (plate_dict.get('input') or {}).get('birth_datetime', '')
        if len(_birth) >= 4 and _birth[:4].isdigit():
            from bazi_calculator import calc_sizhu
            _year_gan = calc_sizhu(int(_birth[:4]), 1, 1, 0, 0)['year']['gz'][0]
        _all_mutagens = set()
        if _year_gan:
            for mu_type, star_name in _GAN_SIHUA_TABLE.get(_year_gan, []):
                _all_mutagens.add((star_name, '化' + mu_type))
        for p in plate_dict.get('palaces', []) or []:
            dz = p.get('decadal_dizhi', '') if isinstance(p, dict) else ''
            if dz and dz[0]:
                for mu_type, star_name in _GAN_SIHUA_TABLE.get(dz[0], []):
                    _all_mutagens.add((star_name, '化' + mu_type))
    except Exception:
        _all_mutagens = set()
    for star in _ZW_STARS:
        for m in re.finditer(r'(?<!大限)' + re.escape(star) + r'化(禄|权|科|忌)'
                             r'(?:\s*(?:在|于|入|落)\s*(' + _pat_palaces + r'))?',
                             text):
            mu = '化' + m.group(1)
            found_palace = _norm_palace(m.group(2)) if m.group(2) else ''
            if _all_mutagens and (star, mu) not in _all_mutagens:
                issues.append({'type': 'mutagen', 'star': star, 'mutagen': mu,
                              'found_palace': found_palace, 'expected': '不在生年或大限四化表',
                              'raw': m.group(0)})
            elif not _all_mutagens:
                unverified.append('mutagen')

    # 3. 长生：X宫(坐/逢/临/守)长生... 或 长生(在/于)X宫
    cs_alt = '|'.join(_ZW_CHANGSHENG)
    for p in palaces:
        for m in re.finditer(re.escape(p) + r'宫?\s*(?:坐|逢|临|守|在|于)?\s*(' + cs_alt + ')', text):
            found_cs = m.group(1)
            expected_cs = oracle['changsheng'].get(p, '')
            if expected_cs and found_cs != expected_cs:
                issues.append({'type': 'changsheng', 'palace': p,
                              'found': found_cs, 'expected': expected_cs,
                              'raw': m.group(0)})
    for cs in _ZW_CHANGSHENG:
        for m in re.finditer(re.escape(cs) + r'\s*(?:在|于|落)\s*(' + _pat_palaces + ')', text):
            found_palace = _norm_palace(m.group(1))
            expected_cs = oracle['changsheng'].get(found_palace, '')
            if expected_cs and expected_cs != cs:
                issues.append({'type': 'changsheng', 'palace': found_palace,
                              'found': cs, 'expected': expected_cs,
                              'raw': m.group(0)})

    # 4. 大限顺逆 + 起岁（简单版，低误报：限定"大限"上下文）
    birth = (plate_dict.get('input') or {}).get('birth_datetime', '')
    gender = (plate_dict.get('input') or {}).get('gender', '')
    five = plate_dict.get('five_elements_class', '')
    jushu = {'水二局': 2, '木三局': 3, '金四局': 4, '土五局': 5, '火六局': 6}
    exp_start = jushu.get(five)
    if len(birth) >= 4 and birth[:4].isdigit() and gender in ('男', '女'):
        yang = ((int(birth[:4]) - 4) % 10) in (0, 2, 4, 6, 8)  # 甲丙戊庚壬=阳
        expected_forward = (yang and gender == '男') or (not yang and gender == '女')
        expected_dir = '顺行' if expected_forward else '逆行'
        for m in re.finditer(r'大限[^。；\n]{0,12}?(顺行|逆行)', text):
            if m.group(1) != expected_dir:
                issues.append({'type': 'decadal_dir', 'found': m.group(1),
                              'expected': expected_dir, 'raw': m.group(0)})
    else:
        unverified.append('decadal_dir')  # 缺少出生信息，不静默通过
    if exp_start:
        for m in re.finditer(r'(\d{1,2})\s*岁起', text):
            if int(m.group(1)) != exp_start:
                issues.append({'type': 'decadal_start', 'found': int(m.group(1)),
                              'expected': exp_start, 'raw': m.group(0)})
    else:
        unverified.append('decadal_start')

    # 6. 大限四化（第八类，2026-08-04 实现）：各宫位大限干支四化并集作 oracle，
    #    上下文限定"大限"防误报（跟大限顺逆同套路）
    try:
        from ziwei_calculator import _GAN_SIHUA_TABLE
        decadal_mutagens = set()
        for p in plate_dict.get('palaces', []) or []:
            dz = p.get('decadal_dizhi', '') if isinstance(p, dict) else ''
            if dz and dz[0]:
                for mu_type, star_name in _GAN_SIHUA_TABLE.get(dz[0], []):
                    decadal_mutagens.add((star_name, '化' + mu_type))
    except Exception:
        decadal_mutagens = set()
    if decadal_mutagens:
        for star in _ZW_STARS:
            for m in re.finditer(r'大限[^。；\n]{0,10}?' + re.escape(star) + r'化(禄|权|科|忌)', text):
                mu = '化' + m.group(1)
                if (star, mu) not in decadal_mutagens:
                    issues.append({'type': 'decadal_mutagen', 'star': star, 'mutagen': mu,
                                  'expected': '不在大限四化表', 'raw': m.group(0)})
    else:
        unverified.append('decadal_mutagen')

    # 5. 格局引用（肯定语境）：LLM 声称有某格局但盘面引擎判无 → 逮
    try:
        from ziwei_calculator import detect_patterns
        engine_pats = {p.get('name', '') for p in detect_patterns(plate_dict)}
    except Exception:
        engine_pats = set()
    if engine_pats:
        _GEJU_ALIAS = {'机月同梁': '机月同梁格', '机月格': '机月同梁格', '杀破狼': '杀破狼格',
                       '紫府朝垣': '紫府朝垣格', '府相朝垣': '府相朝垣格', '火贪': '火贪格',
                       '铃贪': '铃贪格', '日月并明': '日月并明格', '石中隐玉': '石中隐玉格',
                       '紫微天府': '紫府同宫', '君臣庆会': '君臣庆会', '月朗天门': '月朗天门',
                       '日照雷门': '日照雷门'}
        _known_names = sorted(set(engine_pats) | set(_GEJU_ALIAS.keys()) | set(_GEJU_ALIAS.values()), key=len, reverse=True)
        for gname in _known_names:
            canon = _GEJU_ALIAS.get(gname, gname)
            for m in re.finditer(re.escape(gname), text):
                pre = text[max(0, m.start() - 6):m.start()]
                if any(neg in pre for neg in ('无', '未', '不', '非', '不成', '没有', '不具备')):
                    continue
                if canon not in engine_pats:
                    issues.append({'type': 'geju', 'found': gname, 'expected': '盘面无此格局',
                                  'raw': m.group(0)})
                    break
    else:
        unverified.append('geju')  # 引擎格局判读不可用时诚实标注

    return {'issues': issues, 'unverified': unverified}


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    from bazi_calculator import paipan

    # 测试排盘
    plate = paipan(2005, 8, 19, 1, 35, "男", 113.75, "广东省东莞市")

    # 转为字典
    from app import plate_to_dict
    pdict = plate_to_dict(plate)

    print("正在调用 DeepSeek API 进行八字分析...")
    print(f"System prompt 长度: {len(_load_system_prompt())} 字符")
    print(f"User message 长度: {len(_build_user_message(pdict))} 字符")
    print()

    result = analyze_bazi(pdict, timeout=120)

    if result["success"]:
        print("=" * 60)
        print("分析结果：")
        print("=" * 60)
        print(result["analysis"][:2000])
        print("...")
        print(f"\n用时 tokens: {result['usage']}")
    else:
        print(f"失败: {result['error']}")

