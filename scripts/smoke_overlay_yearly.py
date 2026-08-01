#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""叠盘链路冒烟：复现 POST /api/ziwei/analyze/yearly 核心逻辑

本命排盘 → 流年盘 → 三层叠盘 prompt 组装（本命关键宫 + 大限 + 流年 + 流曜）→ LLM 解读
验证"叠盘 → 飞星/流曜注入 → AI 分析"整条链活着（查代码只能证明存在，跑一遍才证明活着）。

运行：python scripts/smoke_overlay_yearly.py
退出码：0 = PASS，1 = FAIL
"""

import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ziwei_calculator import ziwei_paipan, plate_to_dict as ziwei_plate_to_dict, get_horoscope
from analysis_service import _load_ziwei_system_prompt, _call_api

KEY_PALACES = ['命宮', '夫妻', '財帛', '官祿', '遷移', '福德']


def build_overlay_prompt(plate_dict, horo, target_year):
    """与 routes/ziwei.py api_ziwei_analyze_yearly 相同的 prompt 组装"""
    natal_summary = []
    for p in plate_dict.get('palaces', []):
        if p['name'] in KEY_PALACES:
            stars = '、'.join(s['name'] if isinstance(s, dict) else s for s in p.get('major_stars', [])) or '空宫'
            muts = '、'.join(f"{m['star']}{m['mutagen']}" for m in p.get('mutagens', []))
            natal_summary.append(f"{p['name']}({p['dizhi']}): {stars}" + (f" [{muts}]" if muts else ""))

    ym = plate_dict.get('year_mutagens', [])
    sihua_str = ' · '.join(f"{m['star']}{m['mutagen']}({m['palace']})" for m in ym)

    patterns = plate_dict.get('patterns', [])
    pattern_str = ' · '.join(p['name'] for p in patterns) if patterns else '无特殊格局'

    liuyao = horo.get('liuyao', {})
    liuyao_str = ' · '.join(f"{k}→{v}" for k, v in liuyao.items()) if liuyao else '无'

    return (f"## 本命盘关键宫位\n{chr(10).join(natal_summary)}\n\n"
            f"## 生年四化\n{sihua_str}\n\n## 格局\n{pattern_str}\n\n"
            f"## 当前大限\n干支: {horo['decadal_gz']}\n落宫: {horo['decadal_palace']}\n\n"
            f"## {target_year}年流年\n干支: {horo['yearly_gz']}\n流年落宫: {horo['yearly_palace']}\n"
            f"流年四化: {'、'.join(horo['yearly_mutagens']) if horo['yearly_mutagens'] else '无'}\n"
            f"流曜分布: {liuyao_str}"), natal_summary, sihua_str, pattern_str, liuyao_str


def main():
    year, month, day, hour, gender = 2005, 8, 19, 1, "男"
    target_year = 2026
    is_lunar = False

    # 1) 本命排盘
    plate_data = ziwei_paipan(year, month, day, hour, 0, gender, is_lunar)
    plate_dict = ziwei_plate_to_dict(plate_data, {
        "birth_datetime": f"{year}-{month:02d}-{day:02d} {hour:02d}:00",
        "gender": gender,
    })
    assert plate_dict.get("palaces"), "FAIL: 本命盘 palaces 为空"
    print(f"[1/4] 本命排盘 OK，{len(plate_dict['palaces'])} 宫")

    # 2) 流年盘
    horo = get_horoscope(year, month, day, hour, gender, target_year, is_lunar)
    assert horo.get("yearly_gz"), "FAIL: 流年干支为空"
    print(f"[2/4] 流年盘 OK：{target_year} {horo['yearly_gz']} 落 {horo.get('yearly_palace')}，大限 {horo.get('decadal_gz')}")

    # 3) 三层叠盘 prompt 组装
    prompt, natal_summary, sihua, patterns, liuyao = build_overlay_prompt(plate_dict, horo, target_year)
    assert natal_summary and sihua, "FAIL: 关键宫摘要/生年四化为空"
    print(f"[3/4] 叠盘 prompt 组装 OK：关键宫 {len(natal_summary)} 个，格局 {patterns!r}，流曜 {liuyao[:60]!r}")

    # 4) LLM 解读
    system_prompt = _load_ziwei_system_prompt()
    user_msg = (f"请进行紫微斗数流年聚焦解读。结合本命盘、大限盘和流年盘三层信息，重点分析{target_year}年的运势。\n\n"
                + prompt)
    result = _call_api(system_prompt, [{"role": "user", "content": user_msg}],
                       max_tokens=8192, temperature=0.5, timeout=90)
    if not result.get("success"):
        print("FAIL: LLM 调用失败:", result)
        sys.exit(1)
    text = result["text"]
    assert len(text) > 50, "FAIL: 分析文本过短"
    print(f"[4/4] LLM 解读 OK，输出 {len(text)} 字")

    print("\nSMOKE PASS：叠盘链路（排盘→流年→三层叠盘→AI 分析）完整活着")
    print("--- 输出预览 ---")
    print(text[:150])
    sys.exit(0)


if __name__ == "__main__":
    main()
