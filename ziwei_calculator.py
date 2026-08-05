#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""紫微斗数排盘计算模块

基于 iztro-py 库进行精确的紫微斗数排盘计算:
  - 十二宫干支/星曜分布
  - 生年四化
  - 大限范围
  - 命宫/身宫判定
  - 五行局

用法:
    from ziwei_calculator import ziwei_paipan, plate_to_dict

    plate = ziwei_paipan(1991, 8, 15, 1, 0, '男')
    data = plate_to_dict(plate, input_info)
"""

# ---- 常量表 ----

# iztro-py 英文 key → 中文名称映射
STEM_CN = {
    'jiaHeavenly': '甲', 'yiHeavenly': '乙', 'bingHeavenly': '丙',
    'dingHeavenly': '丁', 'wuHeavenly': '戊', 'jiHeavenly': '己',
    'gengHeavenly': '庚', 'xinHeavenly': '辛', 'renHeavenly': '壬',
    'guiHeavenly': '癸',
}

BRANCH_CN = {
    'ziEarthly': '子', 'chouEarthly': '丑', 'yinEarthly': '寅',
    'maoEarthly': '卯', 'chenEarthly': '辰', 'siEarthly': '巳',
    'wuEarthly': '午', 'weiEarthly': '未', 'shenEarthly': '申',
    'youEarthly': '酉', 'xuEarthly': '戌', 'haiEarthly': '亥',
}

FIVE_ELEMENTS_CN = {
    'water2': '水二局', 'wood3': '木三局', 'metal4': '金四局',
    'earth5': '土五局', 'fire6': '火六局',
}

MUTAGEN_CN = {'禄': '化禄', '权': '化权', '科': '化科', '忌': '化忌'}

# 时辰索引映射 (hour 0-23 → iztro-py hour_index 0-12)
# 0=早子(00-01), 1=丑(01-03), 2=寅(03-05), ..., 11=亥(21-23), 12=晚子(23-24)
# ⚠️ 23 点必须是 12(晚子)：iztro 晚子时安星日数按次日；映射成 0(早子)会把晚子时盘
# 排成当天早子时盘（紫微/命宫/四化全错位）。历史写法 {23: 0} 是 bug，已修正。
_HOUR_TO_SHICHEN = {_h: (_h + 1) // 2 for _h in range(23)}
_HOUR_TO_SHICHEN[23] = 12

# 十二宫名称 (iztro-py index order: 疾厄/财帛/子女/夫妻/兄弟/命宫/父母/福德/田宅/官禄/交友/迁移)
PALACE_NAMES_CN = [
    '疾厄', '財帛', '子女', '夫妻', '兄弟', '命宮',
    '父母', '福德', '田宅', '官祿', '交友', '遷移',
]

# 宫名繁简统一（iztro 翻译表繁简混合，来因宫等展示层输出走简体）
PALACE_NAME_SIMP = {
    '命宮': '命宫', '財帛': '财帛', '官祿': '官禄', '遷移': '迁移',
}

# 来因宫锚位表（钦天派定式，2026-08-05 收编定案）：
# 甲戌 乙酉 丙申 丁未 戊午 己巳 庚辰 辛卯 壬寅 癸亥——个体制（宫干=生年干）+ 子丑不取。
# 子=天丑=地（邵雍《皇极经世》『天开于子，地辟于丑，人生于寅』），子丑不参与后天因果造化，
# 故辛取卯弃丑、壬取寅弃子。出处：6da.net 钦天派技法介绍之来因宫【九】【十】 + 常先·易（2026-08-05 网络查证，多源一致）。
LAIYIN_ANCHOR = {
    '甲': '戌', '乙': '酉', '丙': '申', '丁': '未', '戊': '午',
    '己': '巳', '庚': '辰', '辛': '卯', '壬': '寅', '癸': '亥',
}
# ⚠️ PALACE_NAMES_CN 是按地支序(index 0=寅)排列的固定表，恰好等于"命宫在未"时的
# 功能分布，不能直接当功能名用（命宫不在未时全部错位）。
# 功能名必须按命宫相对旋转，唯一正确来源是 iztro-py 原生 palace.name（英文功能码）。

# iztro-py 原生 palace.name(英文功能码) → 中文功能名
_PALACE_KEY_MAP = {'spousePalace':'夫妻','siblingsPalace':'兄弟','soulPalace':'命宮',
    'parentsPalace':'父母','spiritPalace':'福德','propertyPalace':'田宅','careerPalace':'官祿',
    'friendsPalace':'交友','surfacePalace':'遷移','healthPalace':'疾厄','wealthPalace':'財帛',
    'childrenPalace':'子女'}

# 宫位地支 → 4x4 网格坐标 (for frontend display)
BRANCH_GRID = {
    '巳': (1, 1), '午': (1, 2), '未': (1, 3), '申': (1, 4),
    '辰': (2, 1), '酉': (2, 4),
    '卯': (3, 1), '戌': (3, 4),
    '寅': (4, 1), '丑': (4, 2), '子': (4, 3), '亥': (4, 4),
}

SHICHEN_NAMES = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']

# ═══ 十四主星亮度修正表（令东来参考，5级→7级映射）═══
# 庙→庙 旺→旺 平→得 闲→不 陷→陷
# 此表覆盖引擎输出，确保亮度符合经典标准
_BRIGHTNESS_FIX = {star: dict(zip('子丑寅卯辰巳午未申酉戌亥', [
    {'庙':'庙','旺':'旺','平':'得','闲':'不','陷':'陷'}[c]
    for c in vals]))
    for star, vals in {
    '紫微': '闲庙庙旺闲旺庙庙旺平陷旺',
    '天机': '庙陷旺旺旺平庙陷旺旺旺陷平',
    '太阳': '陷陷旺庙旺旺庙旺平陷陷平陷',
    '武曲': '旺庙平陷庙平旺庙平旺庙平平',
    '天同': '旺陷平庙旺陷陷平旺平庙平庙',
    '廉贞': '平旺庙闲旺陷平庙平平旺陷陷',
    '天府': '旺庙庙平庙旺旺庙旺平庙旺旺',
    '太阴': '庙庙陷陷陷陷陷陷旺旺庙庙',
    '贪狼': '旺庙平旺庙庙平庙平旺庙陷陷',
    '巨门': '旺陷庙旺陷庙旺陷庙旺陷旺庙',
    '天相': '庙庙庙陷旺平旺平庙陷平陷平',
    '天梁': '庙旺庙庙旺陷庙旺陷平旺陷陷',
    '七杀': '旺旺庙陷庙平旺旺庙平庙平平',
    '破军': '庙庙陷旺旺陷庙庙陷陷旺平平',
}.items()}

# ═══ 十天干四化表（宫干飞星用，简体星名）═══
# 与前端 ziwei-report.html GAN_SIHUA 保持一致
_GAN_SIHUA_TABLE = {
    '甲': [('禄','廉贞'),('权','破军'),('科','武曲'),('忌','太阳')],
    '乙': [('禄','天机'),('权','天梁'),('科','紫微'),('忌','太阴')],
    '丙': [('禄','天同'),('权','天机'),('科','文昌'),('忌','廉贞')],
    '丁': [('禄','太阴'),('权','天同'),('科','天机'),('忌','巨门')],
    '戊': [('禄','贪狼'),('权','太阴'),('科','右弼'),('忌','天机')],
    '己': [('禄','武曲'),('权','贪狼'),('科','天梁'),('忌','文曲')],
    '庚': [('禄','太阳'),('权','武曲'),('科','太阴'),('忌','天同')],
    '辛': [('禄','巨门'),('权','太阳'),('科','文曲'),('忌','文昌')],
    '壬': [('禄','天梁'),('权','紫微'),('科','左辅'),('忌','武曲')],
    '癸': [('禄','破军'),('权','巨门'),('科','太阴'),('忌','贪狼')],
}

# 繁简归一化（iztro 星名可能返回繁体，飞星表用简体）
_FAN_TO_JIAN = str.maketrans('機陰貪門', '机阴贪门')
def _norm_star(name: str) -> str:
    return name.translate(_FAN_TO_JIAN)


def hour_to_shichen_index(hour: int) -> int:
    """0-23 小时 → iztro-py hour_index (0=早子, 1=丑, ..., 11=亥, 12=晚子)"""
    return _HOUR_TO_SHICHEN.get(hour, 0)


def _translate_name(obj) -> str:
    """从 iztro-py star/palace 对象提取中文名称"""
    if hasattr(obj, 'translate_name'):
        return obj.translate_name()
    return str(obj)


def ziwei_paipan(year: int, month: int, day: int, hour: int, minute: int = 0,
                 gender: str = '男', is_lunar: bool = False) -> dict:
    """紫微斗数排盘入口 — 一步返回 dict（无中间对象）

    Args:
        year, month, day: 出生日期
        hour: 0-23
        minute: 暂忽略（时辰以 2 小时为粒度）
        gender: "男" 或 "女"
        is_lunar: True 表示输入为农历

    Returns:
        dict: 含 palaces、year_mutagens、five_elements_class 等
    """
    from iztro_py import astro

    date_str = f"{year}-{month}-{day}"
    shichen_idx = hour_to_shichen_index(hour)

    if is_lunar:
        chart = astro.by_lunar(date_str, shichen_idx, gender, False, True, 'zh-CN')
    else:
        chart = astro.by_solar(date_str, shichen_idx, gender, 'zh-CN')

    # 五行局
    five_elements = FIVE_ELEMENTS_CN.get(chart.five_elements_class, chart.five_elements_class)

    # 命宫/身宫
    soul_idx = chart.get_soul_palace().index
    body_idx = chart.get_body_palace().index
    soul_p = chart.palaces[soul_idx]
    body_p = chart.palaces[body_idx]

    # 生年四化
    year_mutagens = []
    for p in chart.palaces:
        for s in list(p.major_stars) + list(p.minor_stars):
            if hasattr(s, 'mutagen') and s.mutagen:
                year_mutagens.append({
                    'star': _translate_name(s),
                    'mutagen': MUTAGEN_CN.get(s.mutagen, s.mutagen),
                    'palace': _PALACE_KEY_MAP.get(p.name, _translate_name(p)),
                    'branch': BRANCH_CN.get(p.earthly_branch, ''),
                })

    # 星曜类型→前端CSS类映射
    _TYPE_CLASS = {
        'major': 'star-major', 'soft': 'star-auspicious', 'tough': 'star-malefic',
        'adjective': 'star-neutral', 'flower': 'star-flower', 'helper': 'star-helper',
        'lucun': 'star-lucun', 'tianma': 'star-tianma',
    }
    _MUTAGEN_MARK = {'禄': '◈', '权': '▲', '科': '◎', '忌': '✕'}

    def _make_star_obj(s):
        """构建单个星曜的富信息对象"""
        obj = {'name': _translate_name(s), 'type': getattr(s, 'type', ''), 'css': _TYPE_CLASS.get(getattr(s, 'type', ''), '')}
        b = getattr(s, 'brightness', None)
        if b:
            obj['brightness'] = b
            obj['brightness_css'] = {'庙': 'b-miao', '旺': 'b-wang', '得': 'b-de', '利': 'b-li', '平': 'b-ping', '不': 'b-bu', '陷': 'b-xian'}.get(b, '')
        m = getattr(s, 'mutagen', None)
        if m:
            obj['mutagen'] = m
            obj['mutagen_mark'] = _MUTAGEN_MARK.get(m, '')
            obj['mutagen_css'] = {'禄': 'm-lu', '权': 'm-quan', '科': 'm-ke', '忌': 'm-ji'}.get(m, '')
        return obj

    # 十二宫
    palaces = []
    for p in chart.palaces:
        major = [_make_star_obj(s) for s in p.major_stars]
        minor = [_make_star_obj(s) for s in p.minor_stars]
        adj = [_make_star_obj(s) for s in getattr(p, 'adjective_stars', [])]

        star_mutagens = [
            {'star': _translate_name(s), 'mutagen': s.mutagen}
            for s in list(p.major_stars) + list(p.minor_stars)
            if hasattr(s, 'mutagen') and s.mutagen
        ]

        dec = p.decadal
        decadal_range = f"{dec.range[0]}-{dec.range[1]}" if dec else ""
        decadal_stem = STEM_CN.get(dec.heavenly_stem, '') if dec else ""
        decadal_branch = BRANCH_CN.get(dec.earthly_branch, '') if dec else ""

        branch = BRANCH_CN.get(p.earthly_branch, '')
        stem = STEM_CN.get(p.heavenly_stem, '')

        tags = []
        if p.index == soul_idx:
            tags.append('命宫')
        if p.index == body_idx:
            tags.append('身宫')

        # 空宫检测（无主星）
        is_empty = len(major) == 0 and '祿存' not in major and '天馬' not in major

        # 十二长生：取 iztro-py 原生 changsheng12（按五行局长生位起，紫微斗数标准排法，已是中文）
        changsheng = getattr(p, 'changsheng12', '') or ''

        grid = BRANCH_GRID.get(branch, (1, 1))

        palaces.append({
            'index': p.index,
            'name': _PALACE_KEY_MAP.get(p.name, PALACE_NAMES_CN[p.index] if p.index < len(PALACE_NAMES_CN) else str(p.index)),
            'heavenly_stem': stem,
            'earthly_branch': branch,
            'dizhi': stem + branch,
            'changsheng': changsheng,
            'major_stars': major,
            'minor_stars': minor,
            'adjective_stars': adj,
            'mutagens': star_mutagens,
            'decadal_range': decadal_range,
            'decadal_dizhi': decadal_stem + decadal_branch,
            'is_empty': is_empty,
            'tags': tags,
            'grid_row': grid[0],
            'grid_col': grid[1],
        })

    # ═══ 亮度修正：仅覆盖 iztro 明确错误的位置 ═══
    for pal in palaces:
        branch = pal['earthly_branch']
        for s in pal['major_stars']:
            star_name = s.get('name', '')
            if star_name in _BRIGHTNESS_FIX and branch in _BRIGHTNESS_FIX[star_name]:
                fix_b = _BRIGHTNESS_FIX[star_name][branch]
                s['brightness'] = fix_b
                s['brightness_css'] = {'庙': 'b-miao', '旺': 'b-wang', '得': 'b-de', '利': 'b-li', '平': 'b-ping', '不': 'b-bu', '陷': 'b-xian'}.get(fix_b, '')

    # ═══ 飞星：宫干四化飞入他宫 ═══
    # 建归一化星名 → 宫位索引（同星多宫取首命中）
    _star_to_palace = {}
    for _pal in palaces:
        for _s in _pal.get('major_stars', []) + _pal.get('minor_stars', []) + _pal.get('adjective_stars', []):
            _n = _norm_star(_s.get('name', ''))
            if _n:
                _star_to_palace.setdefault(_n, _pal)
    for _pal in palaces:
        _gan = _pal.get('heavenly_stem', '')
        _sihua_list = _GAN_SIHUA_TABLE.get(_gan, [])
        _flying = []
        for _mu_type, _star_name in _sihua_list:
            _target = _star_to_palace.get(_norm_star(_star_name))
            if _target:
                _flying.append({
                    'from': _pal['name'],
                    'from_branch': _pal['earthly_branch'],
                    'to': _target['name'],
                    'to_branch': _target['earthly_branch'],
                    'type': _mu_type,
                    'star': _star_name,
                })
        _pal['flying_sihua'] = _flying

    result = {
        'five_elements_class': five_elements,
        'soul_palace': BRANCH_CN.get(soul_p.earthly_branch, ''),
        'body_palace': BRANCH_CN.get(body_p.earthly_branch, ''),
        'palaces': palaces,
        'year_mutagens': year_mutagens,
        'shichen': SHICHEN_NAMES[shichen_idx] + '时' if shichen_idx < 12 else '子时',
    }
    # 生年干支（引擎口径，立春分界）— 前端来因宫/年干显示直接用，禁止公历年自算（年初立春前会错一年）
    try:
        from bazi_calculator import calc_sizhu
        _sz = calc_sizhu(year, month, day, hour, minute)
        result['year_gz'] = _sz['year']['gz']
    except Exception:
        result['year_gz'] = ''
    # 来因宫（钦天派收编，2026-08-05 定案）：锚位地支（口径层，子丑排除）+ 盘面映射（锚位→宫名）。
    # year_gz 缺失时显式空串（前端显 '—'，缺失即暴露，不兑底自算，干支铁律）。
    result['laiyin'] = ''
    result['laiyin_anchor'] = ''
    if result.get('year_gz'):
        _anchor = LAIYIN_ANCHOR.get(result['year_gz'][0], '')
        result['laiyin_anchor'] = _anchor
        for _p in palaces:
            if _p.get('earthly_branch', '') == _anchor:
                result['laiyin'] = PALACE_NAME_SIMP.get(_p.get('name', ''), _p.get('name', ''))
                break
    # 格局判读交由 Agent v6 严格规则执行，后端不做预判
    result['patterns'] = []
    return result


def plate_to_dict(plate_data: dict, input_info: dict = None) -> dict:
    """将排盘 dict 包装为前端 JSON 格式"""
    return {
        'input': input_info or {},
        'shichen': plate_data.get('shichen', ''),
        'five_elements_class': plate_data.get('five_elements_class', ''),
        'soul_palace': plate_data.get('soul_palace', ''),
        'body_palace': plate_data.get('body_palace', ''),
        'palaces': plate_data.get('palaces', []),
        'year_mutagens': plate_data.get('year_mutagens', []),
        'year_gz': plate_data.get('year_gz', ''),
        'laiyin': plate_data.get('laiyin', ''),
        'laiyin_anchor': plate_data.get('laiyin_anchor', ''),
        'patterns': plate_data.get('patterns', []),
    }


def get_horoscope(year: int, month: int, day: int, hour: int, gender: str,
                  target_year: int, is_lunar: bool = False) -> dict:
    """获取指定年份的流年盘数据"""
    from iztro_py import astro

    date_str = f"{year}-{month}-{day}"
    shichen_idx = hour_to_shichen_index(hour)

    if is_lunar:
        chart = astro.by_lunar(date_str, shichen_idx, gender, False, True, 'zh-CN')
    else:
        chart = astro.by_solar(date_str, shichen_idx, gender, 'zh-CN')

    # ⚠️ iztro 的流年按"目标日期所在农历年"(正月初一分界, horoscopeDivide=normal)取干支。
    # 用 {Y}-01-01 探测会永远落在农历年前一年（春节最晚 2/20），导致整个流年盘错一年。
    # 改用 {Y}-03-01：春节恒在 1/21~2/20 之间，03-01 必在农历 Y 年内，零边界风险。
    horo = chart.horoscope(f"{target_year}-03-01", 0)
    yi = horo.yearly
    dec = horo.decadal

    # 流年四化 — mutagen is a list of star name strings
    yearly_mutagen_stars = []
    if hasattr(yi, 'mutagen') and yi.mutagen:
        for sname in yi.mutagen:
            # sname is like 'lianzhenMaj' — need to translate
            yearly_mutagen_stars.append(_translate_star_key(sname))

    # 流年落宫（流年命宫=年支宫，功能名按本命盘相对命宫旋转）
    yi_idx = yi.index if hasattr(yi, 'index') else -1
    yi_palace_name = _PALACE_KEY_MAP.get(chart.palaces[yi_idx].name, '?') if 0 <= yi_idx < 12 else '?'

    # 流年十二宫映射（pn 为 iztro-py 原生功能码，直接映射中文功能名）
    yearly_palaces = []
    pns = getattr(yi, 'palace_names', [])
    for i, pn in enumerate(pns):
        cn_name = _PALACE_KEY_MAP.get(pn, pn)
        yearly_palaces.append({'index': i, 'name': cn_name, 'maps_to': cn_name})

    # 大限
    decadal_info = {
        'heavenly_stem': STEM_CN.get(dec.heavenly_stem, '') if hasattr(dec, 'heavenly_stem') else '',
        'earthly_branch': BRANCH_CN.get(dec.earthly_branch, '') if hasattr(dec, 'earthly_branch') else '',
        'palace_index': dec.index if hasattr(dec, 'index') else -1,
    }
    dec_palace = _PALACE_KEY_MAP.get(chart.palaces[decadal_info['palace_index']].name, '?') if 0 <= decadal_info['palace_index'] < 12 else '?'

    # 流曜
    yi_gan = STEM_CN.get(yi.heavenly_stem, '') if hasattr(yi, 'heavenly_stem') else ''
    yi_zhi = BRANCH_CN.get(yi.earthly_branch, '') if hasattr(yi, 'earthly_branch') else ''
    # 需要本命十二宫来做地支→宫名映射
    natal_palaces = chart.palaces
    natal_list = []
    for p in natal_palaces:
        natal_list.append({
            'name': _PALACE_KEY_MAP.get(p.name, PALACE_NAMES_CN[p.index] if p.index < len(PALACE_NAMES_CN) else str(p.index)),
            'earthly_branch': BRANCH_CN.get(p.earthly_branch, ''),
        })
    liuyao = calculate_liuyao(yi_gan, yi_zhi, natal_list)

    # ═══ 流月四化 ═══
    mo = getattr(horo, 'monthly', None)
    monthly_mutagen_stars = []
    monthly_gz = ''
    monthly_palace_name = '?'
    monthly_palace_index = -1
    monthly_gan = ''
    monthly_zhi = ''
    if mo:
        if hasattr(mo, 'mutagen') and mo.mutagen:
            for sname in mo.mutagen:
                monthly_mutagen_stars.append(_translate_star_key(sname))
        mo_idx = mo.index if hasattr(mo, 'index') else -1
        monthly_palace_name = _PALACE_KEY_MAP.get(chart.palaces[mo_idx].name, '?') if 0 <= mo_idx < 12 else '?'
        monthly_palace_index = mo_idx
        monthly_gan = STEM_CN.get(mo.heavenly_stem, '') if hasattr(mo, 'heavenly_stem') else ''
        monthly_zhi = BRANCH_CN.get(mo.earthly_branch, '') if hasattr(mo, 'earthly_branch') else ''
        monthly_gz = monthly_gan + monthly_zhi

    return {
        'year': target_year,
        'yearly_gz': yi_gan + yi_zhi,
        'yearly_palace': yi_palace_name,
        'yearly_palace_index': yi_idx,
        'yearly_palaces': yearly_palaces,
        'yearly_mutagens': yearly_mutagen_stars,
        'decadal_gz': decadal_info['heavenly_stem'] + decadal_info['earthly_branch'],
        'decadal_palace': dec_palace,
        'decadal_palace_index': decadal_info['palace_index'],
        'liuyao': liuyao,
        'yearly_gan': yi_gan,
        'yearly_zhi': yi_zhi,
        'monthly_gz': monthly_gz,
        'monthly_palace': monthly_palace_name,
        'monthly_palace_index': monthly_palace_index,
        'monthly_mutagens': monthly_mutagen_stars,
        'monthly_gan': monthly_gan,
        'monthly_zhi': monthly_zhi,
    }


# iztro-py 内部星名 → 中文名（horoscope mutagen 用）
def _translate_star_key(key: str) -> str:
    _STAR_KEY_MAP = {
        'ziweiMaj': '紫微', 'tianjiMaj': '天機', 'taiyangMaj': '太陽', 'wuquMaj': '武曲',
        'tianfuMaj': '天府', 'taiyinMaj': '太陰', 'tanlangMaj': '貪狼', 'jumenMaj': '巨門',
        'tianxiangMaj': '天相', 'tianliangMaj': '天梁', 'qishaMaj': '七殺', 'pojunMaj': '破軍',
        'lianzhenMaj': '廉貞', 'tiantongMaj': '天同',
        'zuofuMin': '左輔', 'youbiMin': '右弼', 'wenchangMin': '文昌', 'wenquMin': '文曲',
        'tiankuiMin': '天魁', 'tianyueMin': '天鉞',
        'qingyangMin': '擎羊', 'tuoluoMin': '陀羅', 'huoxinMin': '火星', 'lingxinMin': '鈴星',
        'dikongMin': '地空', 'dijieMin': '地劫',
        'lucunMin': '祿存', 'tianmaMin': '天馬',
    }
    return _STAR_KEY_MAP.get(key, key)


def calculate_liuyao(liunian_gan: str, liunian_zhi: str, palaces: list) -> dict:
    """计算流年流曜落在哪些本命宫位。

    流曜包括：流禄、流羊、流陀、流昌、流曲、流魁、流钺、流马、流鸾、流喜

    Returns:
        {'流禄': ['命宫', '夫妻'], '流羊': ['财帛'], ...}
        每个流曜可能落在多个宫（如果多个宫地支相同则不重复）
    """
    ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']

    # 流禄（流年天干定）
    GAN_LUCUN = {'甲': '寅', '乙': '卯', '丙': '巳', '丁': '午', '戊': '巳', '己': '午',
                 '庚': '申', '辛': '酉', '壬': '亥', '癸': '子'}
    # 流昌（流年天干定）
    GAN_CHANG = {'甲': '巳', '乙': '午', '丙': '申', '丁': '酉', '戊': '申', '己': '酉',
                 '庚': '亥', '辛': '子', '壬': '寅', '癸': '卯'}
    # 流曲（流年天干定）
    GAN_QU = {'甲': '亥', '乙': '子', '丙': '寅', '丁': '卯', '戊': '寅', '己': '卯',
              '庚': '巳', '辛': '午', '壬': '申', '癸': '酉'}
    # 流魁（流年天干定）
    GAN_KUI = {'甲': '丑', '乙': '子', '丙': '亥', '丁': '酉', '戊': '丑', '己': '子',
               '庚': '未', '辛': '午', '壬': '卯', '癸': '巳'}
    # 流钺（流年天干定）
    GAN_YUE = {'甲': '未', '乙': '申', '丙': '酉', '丁': '亥', '戊': '未', '己': '申',
               '庚': '丑', '辛': '寅', '壬': '巳', '癸': '卯'}
    # 流马（流年地支三合局冲位）
    SANHE_CHONG = {'寅': '申', '午': '申', '戌': '申', '申': '寅', '子': '寅', '辰': '寅',
                   '亥': '巳', '卯': '巳', '未': '巳', '巳': '亥', '酉': '亥', '丑': '亥'}
    # 流鸾（流年地支定）
    ZHI_LUAN = {'子': '卯', '丑': '寅', '寅': '丑', '卯': '子', '辰': '亥', '巳': '戌',
                '午': '酉', '未': '申', '申': '未', '酉': '午', '戌': '巳', '亥': '辰'}
    # 流喜（流年地支定）
    ZHI_XI = {'子': '酉', '丑': '申', '寅': '未', '卯': '午', '辰': '巳', '巳': '辰',
              '午': '卯', '未': '寅', '申': '丑', '酉': '子', '戌': '亥', '亥': '戌'}

    lu_zhi = GAN_LUCUN.get(liunian_gan, '')
    lu_idx = ZHI.index(lu_zhi) if lu_zhi in ZHI else -1
    yang_zhi = ZHI[(lu_idx + 1) % 12] if lu_idx >= 0 else ''
    tuo_zhi = ZHI[(lu_idx - 1) % 12] if lu_idx >= 0 else ''

    liuyao_map = {
        '流禄': lu_zhi,
        '流羊': yang_zhi,
        '流陀': tuo_zhi,
        '流昌': GAN_CHANG.get(liunian_gan, ''),
        '流曲': GAN_QU.get(liunian_gan, ''),
        '流魁': GAN_KUI.get(liunian_gan, ''),
        '流钺': GAN_YUE.get(liunian_gan, ''),
        '流马': SANHE_CHONG.get(liunian_zhi, ''),
        '流鸾': ZHI_LUAN.get(liunian_zhi, ''),
        '流喜': ZHI_XI.get(liunian_zhi, ''),
    }

    # 建地支→宫名索引
    branch_to_palace = {}
    for p in palaces:
        b = p.get('earthly_branch', '')
        if b:
            branch_to_palace[b] = p.get('name', b)

    result = {}
    for name, zhi_val in liuyao_map.items():
        if zhi_val and zhi_val in branch_to_palace:
            result[name] = branch_to_palace[zhi_val]

    return result


def detect_patterns(plate_data: dict) -> list[dict]:
    """自动检测命盘格局，基于 ziwei-doushu patterns.ts 体系。

    Level: 上吉=excellent, 吉=good, 中=neutral, 忌=caution
    每格局含 conditions required/bonus/breaking 三层 + 古籍出处 source
    """
    palaces = plate_data.get('palaces', [])
    patterns = []

    by_name = {p['name']: p for p in palaces}
    by_branch = {p.get('earthly_branch', ''): p for p in palaces}
    major_names = lambda p: [s['name'] if isinstance(s, dict) else s for s in p.get('major_stars', [])]
    minor_names = lambda p: [s['name'] if isinstance(s, dict) else s for s in p.get('minor_stars', [])]
    all_star_names = lambda p: set(major_names(p) + minor_names(p))

    def _brightness(p, star_name):
        for s in p.get('major_stars', []) + p.get('minor_stars', []):
            n = s['name'] if isinstance(s, dict) else s
            if n == star_name and isinstance(s, dict):
                b = s.get('brightness', '')
                if b in ('庙', '旺'): return True
                if b in ('陷',): return False
        return None

    def _si_hua(p, star_name):
        for m in p.get('mutagens', []):
            if m.get('star') == star_name:
                return m.get('mutagen', '')
        return ''

    def _has_star(p, name):
        return name in all_star_names(p)

    def _find_star_palace(name):
        for p in palaces:
            if name in all_star_names(p): return p
        return None

    def _get_palace_by_branch(branch):
        return by_branch.get(branch, {})

    ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']

    def _sansifang_branches(ming_branch):
        if ming_branch not in ZHI: return set()
        idx = ZHI.index(ming_branch)
        return {ZHI[(idx) % 12], ZHI[(idx+4) % 12], ZHI[(idx+8) % 12], ZHI[(idx+6) % 12]}

    def _sansifang_stars(ming_branch):
        sf_b = _sansifang_branches(ming_branch)
        stars = set()
        for p in palaces:
            if p.get('earthly_branch', '') in sf_b:
                stars |= all_star_names(p)
        return stars

    def _jiagong(branch):
        if branch not in ZHI: return {}, {}
        idx = ZHI.index(branch)
        prev = _get_palace_by_branch(ZHI[(idx-1)%12])
        next_p = _get_palace_by_branch(ZHI[(idx+1)%12])
        return prev or {}, next_p or {}

    def _sha_count(p, sha_list=None):
        if sha_list is None: sha_list = {'擎羊', '陀罗', '火星', '铃星'}
        return sum(1 for s in all_star_names(p) if s in sha_list)
    SHA_NAMES = {'擎羊', '陀罗', '火星', '铃星', '地空', '地劫'}
    SHA_HARD = {'擎羊', '陀罗', '火星', '铃星'}
    SHA_KONG = {'地空', '地劫'}
    ZUO_YOU = {'左辅', '右弼'}
    CHANG_QU = {'文昌', '文曲'}
    KUI_YUE = {'天魁', '天钺'}
    JYTL = {'天机', '太阴', '天同', '天梁'}

    def _has_sha(p, sha_list=None):
        if sha_list is None: sha_list = SHA_NAMES
        return bool(all_star_names(p) & sha_list)

    # 命宫 = soul palace（tag 为 '命宫' 的宫），不是固定 12 宫名
    ming = next((p for p in palaces if '命宫' in p.get('tags', [])), by_name.get('命宮', {}))
    ming_branch = ming.get('earthly_branch', '')
    sf_set = _sansifang_stars(ming_branch)
    sf_palaces = [p for p in palaces if p.get('earthly_branch', '') in _sansifang_branches(ming_branch)]
    sf_sha_count = sum(_sha_count(p, SHA_HARD) for p in sf_palaces)
    ym = plate_data.get('year_mutagens', [])

    def add_pat(name, desc, level='中', conditions=None, source=''):
        if not any(p['name'] == name for p in patterns):
            p = {'name': name, 'desc': desc, 'level': level}
            if conditions: p['conditions'] = conditions
            if source: p['source'] = source
            patterns.append(p)

    # ═══ 紫微系 ═══
    if _has_star(ming, '紫微'):
        if _has_star(ming, '天府'):
            add_pat('紫府同宫', '紫微天府同守命宫，帝王+库星，格局宏大', '上吉',
                    {'required': ['紫微天府同守命宫']}, '《紫微斗数全书》')
        elif _has_star(ming, '天相'):
            add_pat('紫微天相', '紫微天相在命，稳重贵气，善于协调', '吉', None, '《紫微斗数全书》')
        elif _has_star(ming, '破军'):
            add_pat('紫微破军', '紫破在命，开创精神，变动中成大事', '中')
        elif _has_star(ming, '七杀'):
            add_pat('紫微七杀', '紫杀在命，魄力十足，适合军警/创业', '中')
        elif _has_star(ming, '贪狼'):
            add_pat('紫微贪狼', '紫贪在命，社交强多才艺但需节制', '中')
        elif len(set(major_names(ming))) == 1:
            add_pat('紫微独坐', '紫微独坐命宫，帝王孤星，需辅星来朝', '中', None, '《紫微斗数全书》')
        # 君臣庆会
        if bool(sf_set & ZUO_YOU):
            breaking = []
            if _has_sha(ming, SHA_HARD): breaking.append('命宫坐煞')
            if sf_sha_count >= 3: breaking.append('三方煞重')
            add_pat('君臣庆会', '紫微入命辅弼同会三方，帝王得贤臣辅佐',
                    '吉' if breaking else '上吉',
                    {'required': ['紫微在命宫', '辅弼在命三方四正'], 'bonus': [], 'breaking': breaking},
                    '《紫微斗数全书·君臣庆会格》')

    # ═══ 日月系 ═══
    # 日月并明（庙旺会照版，古书本义）：太阳太阴各居庙旺并会照命三方。
    # 《斗数全书》『日月并明佐九重于尧殿』主流解=日月同处庙旺；王亭之《太微赋》精解
    # 『守不如照』，且丑未同宫版被拆台（丑宫太阴入庙而太阳失地，总有一颗欠缺明朗）。
    # 2026-08-05 King 拍板并存口径，本义优先；同宫为变体备注不单列。
    _sun_p = _find_star_palace('太阳')
    _moon_p = _find_star_palace('太阴')
    if (_sun_p and _moon_p and _sun_p is not _moon_p
            and _brightness(_sun_p, '太阳') and _brightness(_moon_p, '太阴')
            and _sun_p.get('earthly_branch', '') in _sansifang_branches(ming_branch)
            and _moon_p.get('earthly_branch', '') in _sansifang_branches(ming_branch)):
        add_pat('日月并明', '太阳太阴各居庙旺会照命三方，日月辉映', '上吉', None,
                '《斗数全书》『日月并明佐九重于尧殿』（庙旺会照主流解）+ 王亭之《太微赋》精解『守不如照』')
    # 明珠出海（古诀专名）：日卯月亥、安命未。
    # 《斗数全书》『日卯月亥，安命未，多折桂』；《骨髓赋》『三合明珠生旺地，稳步蟾宫』，
    # 注文『未宫安命，日卯月亥来朝，为明珠出海，定主财官双美』。
    # 2026-08-05 King 拍板并存口径补表，与日月并明（庙旺会照版）各自独立判定、各自带出处。
    if (ming_branch == '未' and _sun_p and _sun_p.get('earthly_branch') == '卯'
            and _moon_p and _moon_p.get('earthly_branch') == '亥'
            and _brightness(_sun_p, '太阳') and _brightness(_moon_p, '太阴')):
        add_pat('明珠出海', '太阳卯庙+太阴亥庙+命坐未，日月辉映如明珠出海', '上吉', None,
                '《斗数全书》『日卯月亥，安命未，多折桂』；《骨髓赋》『三合明珠生旺地，稳步蟾宫』（未宫安命日卯月亥来朝）')
    # 日月同臨（《骨髓赋》『日月同临官居侯伯』）：日月同宫于丑或未 + 命坐丑或未。
    # 注文『命安丑宫日月在未、命安未宫日月在丑谓之同临』；机检实证（2026-08-05）日月同宫
    # 只出现在丑未两宫。不要求庙旺——丑宫太阳本陷（王亭之拆台的正是这一点），同臨钉的是
    # 同宫结构，与日月并明（庙旺会照+不同宫）正交：同宫/不同宫天然互斥，不重叠。
    # 拆台样本（命丑日月守丑，原双判无）2026-08-05 King 指示待办现在做 → 翻正命中日月同臨。
    if (_sun_p and _moon_p and _sun_p is _moon_p
            and _sun_p.get('earthly_branch', '') in ('丑', '未')
            and ming_branch in ('丑', '未')):
        add_pat('日月同臨', '日月同宫于丑未、命坐丑未，日月临照（同宫古籍本名）', '吉', None,
                '《骨髓赋》『日月同临官居侯伯』注文『命安丑宫日月在未、命安未宫日月在丑谓之同临』')
    if _has_star(ming, '太阳') and _has_star(ming, '巨门'):
        add_pat('巨日同宫', '太阳巨门在命，口才出众，适合法律/教育/传媒', '中')
    for p in palaces:
        if _has_star(p, '太阴') and p.get('earthly_branch') == '亥':
            b = _brightness(p, '太阴')
            add_pat('月朗天门', '太阴在亥宫庙旺，月朗天门。情感丰富文艺天赋',
                    '上吉' if b else '吉', None, '《骨髓赋》')
        if _has_star(p, '太阳') and p.get('earthly_branch') == '卯':
            b = _brightness(p, '太阳')
            add_pat('日照雷门', '太阳在卯宫庙旺，日照雷门。热情开朗',
                    '上吉' if b else '吉', None, '《骨髓赋》')

    # ═══ 杀破狼 ═══
    sp = {'七杀', '破军', '贪狼'} & sf_set
    if len(sp) >= 3:
        bonus = []; breaking = []
        if sf_set & {'化禄', '化权'}: bonus.append('三方有化禄/权')
        if (sf_set & ZUO_YOU) == ZUO_YOU: bonus.append('辅弼同会')
        if sf_sha_count >= 3: breaking.append('煞重')
        if sf_set & SHA_KONG: breaking.append('坐空劫')
        add_pat('杀破狼格', '七杀破军贪狼三方齐聚，大起大落，变动中求发展',
                '中', {'required': ['杀破狼三星齐入三方四正'], 'bonus': bonus, 'breaking': breaking},
                '《紫微斗数全书》')
    elif sp:
        add_pat('杀破狼格', f'命三方坐{"·".join(sorted(sp))}（不全），有变动倾向', '中')

    # ═══ 机月同梁 ═══
    jy = JYTL & sf_set
    if len(jy) >= 4:
        breaking = []
        if sf_sha_count >= 3: breaking.append('煞重')
        if _has_sha(ming, SHA_HARD): breaking.append('命坐煞')
        add_pat('机月同梁格', '天机太阴天同天梁四星齐入命三方四正，宜文职',
                '吉' if breaking else '上吉',
                {'required': ['机月同梁四星齐入三方四正'], 'bonus': [], 'breaking': breaking},
                '《紫微斗数全书》')
    elif len(jy) >= 2:
        add_pat('机月同梁格', f'命三方有{",".join(sorted(jy))}（不全），偏文职', '吉')

    # ═══ 府相朝垣 ═══
    tf = _find_star_palace('天府'); tx = _find_star_palace('天相')
    if tf and tx and tf != tx:
        if tf.get('earthly_branch','') in _sansifang_branches(ming_branch) and            tx.get('earthly_branch','') in _sansifang_branches(ming_branch):
            add_pat('府相朝垣', '天府天相分守命宫三方四正，权印双辉',
                    '上吉', None, '《紫微斗数全书·府相朝垣格》')

    # ═══ 火贪/铃贪 ═══
    tan = _find_star_palace('贪狼')
    if tan:
        for sha_name, sha in [('火星', '火贪格'), ('铃星', '铃贪格')]:
            sha_p = _find_star_palace(sha_name)
            if sha_p and (sha_p.get('earthly_branch') == tan.get('earthly_branch') or
                          sha_p.get('earthly_branch') in _sansifang_branches(tan.get('earthly_branch',''))):
                adj = '同宫' if sha_p.get('earthly_branch') == tan.get('earthly_branch') else '会照'
                bonus = []
                if _brightness(tan, '贪狼'): bonus.append('贪狼庙旺')
                sihua = _si_hua(tan, '贪狼')
                if sihua in ('禄', '权'): bonus.append(f'贪狼化{sihua}')
                add_pat(sha, f'贪狼{adj}{sha_name}，爆发力强，横发之格',
                        '吉' if bonus else '中',
                        {'required': [f'贪狼{adj}{sha_name}'], 'bonus': bonus}, '《骨髓赋》')

    # ═══ 四化格局 ═══
    for m in ym:
        mu = m.get('mutagen', ''); star = m.get('star', ''); pal = m.get('palace', '')
        if not pal: continue
        if mu == '化忌':
            if pal in ('命宮', '命宫'):
                add_pat('命宫化忌', f'{star}化忌在命宫，内心执念，一生课题是自我和解', '忌')
            elif pal == '夫妻':
                add_pat('夫妻宫化忌', f'{star}化忌在夫妻宫，感情是人生大课题', '忌')
            elif pal == '財帛':
                add_pat('财帛宫化忌', f'{star}化忌在财帛宫，财运需格外经营', '忌')
            elif pal in ('官祿', '官禄'):
                add_pat('官禄宫化忌', f'{star}化忌在官禄宫，事业需经历波折成长', '忌')
        elif mu == '化禄' and pal in ('命宮', '命宫'):
            add_pat('命宫化禄', f'{star}化禄在命宫，天生福气，人缘好', '上吉')
        elif mu == '化禄' and pal == '財帛':
            add_pat('财帛化禄', f'{star}化禄在财帛宫，财运亨通', '吉')
        elif mu == '化权' and pal in ('命宮','命宫','官祿','官禄'):
            add_pat(f'{pal}化权', f'{star}化权在{pal}，有领导力和掌控欲', '吉')

    # ═══ 三奇嘉会 ═══
    lu_s = [m for m in ym if m.get('mutagen') == '化禄']
    quan_s = [m for m in ym if m.get('mutagen') == '化权']
    ke_s = [m for m in ym if m.get('mutagen') == '化科']
    if lu_s and quan_s and ke_s:
        sf_b = _sansifang_branches(ming_branch)
        qi = set()
        for m in lu_s + quan_s + ke_s:
            for pp in palaces:
                if pp.get('name') == m.get('palace','') and pp.get('earthly_branch','') in sf_b:
                    qi.add(m.get('palace',''))
        if len(qi) >= 2:
            add_pat('三奇嘉会', f'化禄化权化科会于命三方({"·".join(sorted(qi))})，好格局',
                    '上吉', None, '《紫微斗数全书》')

    # ═══ 禄马交驰 ═══
    for p in palaces:
        if _has_star(p, '禄存') and _has_star(p, '天马'):
            add_pat('禄马交驰', f'禄存天马同守{p["name"]}，财从远方来', '吉')

    # ═══ 夹宫格 ═══
    prev, next_p = _jiagong(ming_branch)
    jia_stars = all_star_names(prev) | all_star_names(next_p)
    if '火星' in jia_stars and '铃星' in jia_stars:
        add_pat('火铃夹命', '火星铃星分居命宫前后夹命，性急冲动', '忌', None, '《紫微斗数全书》')
    if ZUO_YOU <= jia_stars:
        add_pat('辅弼夹命', '左辅右弼夹命，贵人运极强', '上吉')
    if CHANG_QU <= jia_stars:
        add_pat('昌曲夹命', '文昌文曲夹命，学术才艺出众', '吉')
    if KUI_YUE <= jia_stars:
        add_pat('魁钺夹命', '天魁天钺夹命，社会贵人提携', '吉')

    # ═══ 命无正曜 + 基础双星 ═══
    if not set(major_names(ming)):
        add_pat('命无正曜', '命宫无主星，借对宫迁移宫来看', '中')

    for s1, s2, nm, desc, lv in [
        ('武曲', '天府', '府武同宫', '实干型领袖', '吉'),
        ('武曲', '七杀', '武杀同宫', '刚猛果决', '中'),
        ('天机', '天梁', '机梁善谈', '善谈有谋', '吉'),
        ('天同', '太阴', '同月同宫', '温和细腻', '吉'),
        ('天同', '天梁', '同梁同宫', '福寿双星', '吉'),
        ('廉贞', '天相', '廉相同宫', '才艺+协调', '中'),
        ('廉贞', '贪狼', '廉贪同宫', '双桃花星', '中'),
        ('廉贞', '七杀', '廉杀同宫', '刚烈果敢', '中'),
        ('廉贞', '破军', '廉破同宫', '执着变革', '中'),
        ('天梁', '太阳', '阳梁同宫', '正直光明', '吉'),
    ]:
        if _has_star(ming, s1) and _has_star(ming, s2):
            add_pat(nm, desc, lv)

    return patterns[:12]



# ---- 自检 ----
if __name__ == '__main__':
    import json
    # 测试：马斯克生辰 (1971-06-28, 约7:30am, 南非比勒陀利亚)
    data = ziwei_paipan(1991, 8, 15, 1, 0, '男')
    result = plate_to_dict(data, {
        'birth_datetime': '1991-08-15 01:00',
        'gender': '男',
        'location': '测试',
        'longitude': 120,
    })
    print(f"五行局: {result['five_elements_class']}")
    print(f"命宫: {result['soul_palace']}, 身宫: {result['body_palace']}")
    print(f"生年四化: {len(result['year_mutagens'])} 条")
    print(f"十二宫: {len(result['palaces'])} 个")
    for p in result['palaces']:
        stars = '、'.join(p['major_stars']) if p['major_stars'] else '(空宫)'
        tags = ' [' + ','.join(p['tags']) + ']' if p['tags'] else ''
        print(f"  {p['name']:4s} {p['dizhi']:4s} {stars:20s} 大限{p['decadal_range']:6s}{tags}")
    print("OK" if len(result['palaces']) == 12 else "FAIL")
