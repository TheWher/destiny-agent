# -*- coding: utf-8 -*-
"""
verify_fingerprint.py — 补抓源指纹实弹验证（2026-08-12 定稿，双组分层）

验收规则（CHANGELOG 第二波条目，2026-08-12 定）：
  - 古籍层组 6 条（带字形信号）：每源任取 3 条，3/3 精确命中且含異體字形
    = 传统字形底本 → 古籍层入库；全简体形式命中 = 简体注本 → 注疏系入库；
    不命中 = 毙。形态抽检原文占比为次级闸。
  - 简体组 3 条（注疏系/梁系引文保真）：3/3 命中 = 引文保真 → 注疏系入库；
    目标不是传统字形底本，不与古籍层组混用。

用法：
  python scripts/verify_fingerprint.py <文件或目录>
  输出：每组命中/毙判定 + 字形信号 + 入库建议。留痕由调用方记 changelog。
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# 成员集版本（⑩条机器化落地：读数身份三维 = 层|源|成员集版本）
# TRUE_VARIANTS 现为 v4 = 衝沖剋佈尅㐫隂郷（2026-08-12 14:00 三票，成员集扩编 mv3→mv4：判据线扩入 㐫/隂/郷，VARIANT_MAP 扩入 殺/賦/隨）
# ⚠ 升 v5 时三处同步改防版本漂移：本脚本 MEMBER_SET_VERSION +
#    scan_variant_report_r4.py MEMBER_SET_VERSION + TRUE_VARIANTS 成员集（同一版本，跨脚本两处常量）
MEMBER_SET_VERSION = "mv4"

# 指纹验证目标层（本脚本只扫数据层 JSON 导出的 md，渲染层一律不采信）
SCAN_LAYER = "JSON"

def identity():
    """读数身份后缀，格式同扫描脚本：[层|源|成员集版本]"""
    return f"[{SCAN_LAYER}|sd_sdzj0170|{MEMBER_SET_VERSION}]"

# 古籍层组：(指纹句, 篇目, 行号, 字形信号)
CLASSIC_FINGERPRINTS = [
    ("祿逢沖破，吉處藏凶", "太微賦", "L29", "沖=異體"),
    ("星臨廟旺，再觀生剋之機", "太微賦", "L29", "剋"),
    ("諸凶在緊要之鄉最宜制克", "斗數準繩", "L35", "克=簡"),
    ("辨生剋制化以定窮通", "斗數準繩", "L35", "剋"),
    ("命身相克，則心亂而不閑", "斗數發微論", "L37", "克"),
    ("相貌加刑殺，刑剋難免", "斗數發微論", "L37", "剋"),
]

# 简体组（注疏系/梁系引文保真）：(指纹句, 出处实锤)
# 版本敏感字备注（2026-08-12）：夹昌夹曲主贵兮 在 SDZJ0170 作「夹昌夹曲七贵兮」（版本异文非缺失），
# 跨底本验收时版本敏感字单列备注，防异文打成假 ✗；刻本到了第一验这句（同是异文样本和指纹句健壮性样本）
SIMPLIFIED_FINGERPRINTS = [
    ("禄逢冲破，吉处藏凶", "quanlan L1101+注疏系现成"),
    ("夹昌夹曲主贵兮", "quanlan L163+changqu-jiaming L25"),
    ("生克制化之机", "quanlan L335"),
]

# SDZJ0170 数据层指纹（2026-08-12 v4）：古籍层组 6 条按数据层实际字形定稿。
# 数据层形态：殺/㐫/隂/郷/尅/𦂳 保真，祿/沖/廟/鬥 转简（混合态转写）。
# 字形级 5/6（禄逢冲破 ✗），内容级 6/6（字形等价归一化）。
SD_CLASSIC_FINGERPRINTS = [
    ("祿逢沖破，吉處藏凶", "太微賦", "L29", "quanlan保真字形；数据层转简禄逢冲破→✗"),
    ("星臨庙旺，再觀生尅之機", "太微賦", "L29", "庙转简/尅保真"),
    ("諸㐫在𦂳要之鄉，最冝制", "斗數準繩", "L35", "㐫𦂳保真、異文缺克字"),
    ("辨生尅制化以定窮通", "斗數準繩", "L35", "尅保真"),
    ("命身相尅，則心亂而不閑", "斗數發微論", "L37", "尅保真"),
    ("相貌加刑殺，刑尅難免", "斗數發微論", "L37", "殺/尅保真"),
]

# 字形等价归一化表（内容级命中用）：繁简 + 异体同字映射
GLYPH_EQUIV = {
    "剋": "尅", "凶": "㐫", "郷": "鄉", "沖": "衝", "冲": "衝",
    "祿": "禄", "廟": "庙", "鬥": "斗", "陰": "隂", "隨": "随",
    "賦": "赋", "夾": "夹", "冨": "富", "貴": "贵", "㐫": "凶",
}

def glyph_normalize(text):
    """字形等价归一化：把異體/繁体映射到同一字形，用于内容级命中判断。"""
    for a, b in GLYPH_EQUIV.items():
        text = text.replace(a, b)
    return text

# 篇目覆盖探测（2026-08-12 补，hanako 规则缺口：0/6 三语义歧义——不适用/毙/OCR 烂）
# 特征词选篇目内独特、跨篇不串扰的片段，繁简双形态都给；探测时先 glyph_normalize 再搜
# OCR 稳健性（2026-08-12 刻本实测，mose 机制先验回应）：難免1/制化10/之機6/逢冲破2 在 RapidOCR 完好，
# 覆盖探测靠双字组合命中→整句 0 命中→OCR 烂 链路自证，不需要已知底本先验；但这是选词原则的副产品而非设计目标：
# 「篇目独特字位」客观上避开 尅/㐫/緊 等 OCR 高风险異體字。已知漏覆盖：諸凶在 在刻本被 OCR 打散（諸卤→最卤/不卤），
# 準繩覆盖漏 → N 偏小 → 判定方向保守（覆盖不足/不适用），不产生假阳性，方向安全。
CHAPTER_FEATURES = {
    "太微賦": ["藏凶", "逢沖破"],
    "斗數準繩": ["諸凶在", "诸凶在"],
    "斗數發微論": ["難免", "难免", "心亂", "心乱"],
}
# 简体组指纹句覆盖探测（按句）：句子独特片段，繁简双形态
SIMP_COVER = {
    "禄逢冲破，吉处藏凶": "吉处藏凶",
    "夹昌夹曲主贵兮": "夹昌夹曲",
    "生克制化之机": "生克制化",
}
# OCR 错字特征（启发式：覆盖>0 但命中 0 时提示走回图；刻本实测：尅→过/鼓/鞋、㐫→卤、緊→聚、一→千）
# 用凶字位的双字组合：刻本「吉處藏卤」「吉星逢卤」「諸卤福臨」；单字「卤」会撞异体写法（juan1「必有卤祸」卤=祸，2026-08-12 误报教训）
OCR_BAD_SIGNALS = ["藏卤", "逢卤", "諸卤", "诸卤"]


def detect_covered(text_norm_equiv):
    """返回覆盖的篇目列表：任一特征词（glyph 归一后）命中即算覆盖。"""
    covered = []
    for ch, feats in CHAPTER_FEATURES.items():
        if any(glyph_normalize(f) in text_norm_equiv for f in feats):
            covered.append(ch)
    return covered


def detect_simp_covered(text_norm_equiv):
    """返回覆盖的简体组指纹句列表。"""
    return [fp for fp, feat in SIMP_COVER.items()
            if glyph_normalize(feat) in text_norm_equiv]


def classic_verdict(count, covered_n, ocr_bad=False):
    """古籍层组判定（N 随篇目覆盖浮动）：不适用 / 覆盖不足 / 毙(+OCR 烂) / 验收线。"""
    if covered_n == 0:
        return "不适用（指纹句篇目未覆盖此文件）"
    if covered_n < 3:
        return f"覆盖不足（命中 {count}/{covered_n} < 验收线 3，待补判据点）"
    if count >= 3:
        return None  # 走 hit_with_variant / hit_all_simplified 分派
    if ocr_bad:
        return f"毙/OCR 烂（命中 {count}/{covered_n}，文本含 OCR 错字特征 → 走回图）"
    return f"毙（命中 {count}/{covered_n} < 3）"

# 異體/繁简字形信号字（用于判断"含字形差异"）
VARIANT_SIGNALS = "衝沖會當夾剋裏乾麽為無與"


def normalize(text):
    """归一化：去空白、去常见标点，便于子串匹配。"""
    text = re.sub(r"[\s，。、；：？！「」『』（）()\"'']", "", text)
    return text


def has_variant_signal(text):
    return any(ch in text for ch in VARIANT_SIGNALS)


def scan_text(text):
    """对单文件正文跑两组指纹，返回判定（含篇目覆盖）。"""
    norm_text = normalize(text)
    norm_text_equiv = glyph_normalize(norm_text)
    covered = detect_covered(norm_text_equiv)
    covered_n = sum(2 for _ in covered)  # 每篇目 2 条指纹句
    ocr_bad = any(pat in norm_text for pat in OCR_BAD_SIGNALS)

    classic_hits = []
    for fp, book, line, sig in CLASSIC_FINGERPRINTS:
        hit = normalize(fp) in norm_text
        classic_hits.append((fp, book, line, sig, hit))

    simp_covered = detect_simp_covered(norm_text_equiv)
    simp_hits = []
    for fp, src in SIMPLIFIED_FINGERPRINTS:
        hit = normalize(fp) in norm_text
        simp_hits.append((fp, src, hit))

    # 古籍层组判定：篇目覆盖 N 浮动 + 3/3 验收线
    classic_hit_count = sum(1 for _, _, _, _, h in classic_hits if h)
    pre = classic_verdict(classic_hit_count, covered_n, ocr_bad)
    if pre is not None:
        classic_verdict_str = pre
    else:
        # 命中>=3：传统字形 vs 简体注本分派
        hit_with_variant = any(h and has_variant_signal(fp) for fp, _, _, _, h in classic_hits)
        hit_all_simplified = classic_hit_count >= 3 and not any(
            h and has_variant_signal(fp) for fp, _, _, _, h in classic_hits)
        if hit_with_variant:
            classic_verdict_str = "传统字形底本 → 古籍层入库"
        elif hit_all_simplified:
            classic_verdict_str = "简体注本 → 注疏系入库"
        else:
            classic_verdict_str = f"毙（命中 {classic_hit_count}/{covered_n}）"

    # 简体组：按句覆盖浮动
    simp_hit_count = sum(1 for _, _, h in simp_hits if h)
    simp_n = len(simp_covered)
    if simp_n == 0:
        simp_verdict = "不适用（简体组指纹句未覆盖此文件）"
    elif simp_hit_count >= 3:
        simp_verdict = "引文保真 → 注疏系入库"
    else:
        simp_verdict = f"毙（命中 {simp_hit_count}/{simp_n}）"

    return classic_hits, classic_verdict_str, simp_hits, simp_verdict, covered, simp_covered


def scan_text_sd(text):
    """SDZJ0170 数据层专用：古籍层组按数据层字形 + 内容级（字形归一化）双档。"""
    norm_text = normalize(text)
    norm_text_equiv = glyph_normalize(norm_text)
    covered = detect_covered(norm_text_equiv)
    covered_n = sum(2 for _ in covered)
    glyph_hits, content_hits = [], []
    for fp, book, line, sig in SD_CLASSIC_FINGERPRINTS:
        gh = normalize(fp) in norm_text
        ch = glyph_normalize(normalize(fp)) in norm_text_equiv
        glyph_hits.append((fp, book, line, sig, gh))
        content_hits.append((fp, book, line, sig, ch))
    glyph_n = sum(1 for *_, h in glyph_hits if h)
    content_n = sum(1 for *_, h in content_hits if h)
    if covered_n == 0:
        verdict = f"不适用（指纹句篇目未覆盖此文件，篇目覆盖 {len(covered)}/3）{identity()}"
    elif glyph_n >= 3:
        verdict = f"数据层传统字形形态（字形级 {glyph_n}/{covered_n}）→ 古籍层·非底本·数据层繁体保真 {identity()}"
    elif content_n >= 3:
        verdict = f"内容级命中 {content_n}/{covered_n}、字形级 {glyph_n}/{covered_n} → 转写混合态，指纹需按数据层字形定 {identity()}"
    elif covered_n < 3:
        # 覆盖不足：篇目在但句数不够验收线（如卷末引用赋文，v2 实测 2/2）
        verdict = f"覆盖不足（内容级命中 {content_n}/{covered_n} < 验收线 3，待补判据点）{identity()}"
    else:
        verdict = f"毙（内容级 {content_n}/{covered_n}）{identity()}"
    return glyph_hits, content_hits, verdict, covered


def main():
    if len(sys.argv) < 2:
        print("用法：python scripts/verify_fingerprint.py <文件或目录>")
        sys.exit(1)
    target = Path(sys.argv[1])
    if target.is_dir():
        files = sorted(target.glob("*.md"))
    else:
        files = [target]

    print("=" * 72)
    print(f"指纹实弹验证  snapshot: 2026-08-12 v4 {MEMBER_SET_VERSION}（双组分层 + 数据层双档 + 篇目覆盖浮动）")
    print(f"数据身份：{identity()}（数自带户口本，不用问哪来的）")
    print("=" * 72)
    for f in files:
        text = f.read_text(encoding="utf-8")
        is_sd = "sd_sdzj0170" in f.name
        if is_sd:
            glyph_hits, content_hits, cv, covered = scan_text_sd(text)
            print(f"\n--- {f.name} [数据层] ---")
            print(f"  篇目覆盖：{'、'.join(covered) if covered else '无'}")
            print("古籍层组·字形级：")
            for fp, book, line, sig, h in glyph_hits:
                print(f"  [{'✓' if h else '✗'}] {fp}（{book} {line}，{sig}）")
            print("古籍层组·内容级（字形等价归一化）：")
            for fp, book, line, sig, h in content_hits:
                print(f"  [{'✓' if h else '✗'}] {fp}（{book} {line}，{sig}）")
            print(f"  判定：{cv}")
            continue
        classic_hits, cv, simp_hits, sv, covered, simp_covered = scan_text(text)
        print(f"\n--- {f.name} ---")
        print(f"  篇目覆盖：{'、'.join(covered) if covered else '无'} ｜ 简体组覆盖：{len(simp_covered)}/3")
        print("古籍层组：")
        for fp, book, line, sig, h in classic_hits:
            print(f"  [{'✓' if h else '✗'}] {fp}（{book} {line}，{sig}）")
        print(f"  判定：{cv}")
        print("简体组：")
        for fp, src, h in simp_hits:
            print(f"  [{'✓' if h else '✗'}] {fp}（{src}）")
        print(f"  判定：{sv}")


if __name__ == "__main__":
    main()
