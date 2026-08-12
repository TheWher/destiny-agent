# -*- coding: utf-8 -*-
"""
scan_variant_report.py — 首波开扫：异体出现率 / 挂起堆 / 锚点缺位（2026-08-12 定口径）

口径（2026-08-12 凌晨共识）：
  - 料池保真存储不动，词表保持规范字单一来源；已知异体=确定性转换，未收录异体进缺词清单
  - 首波必报：异体出现率（分来源层、带基数）、挂起堆规模（未收录候选）、锚点缺位
  - 判据 = 古籍层密度（先量后切桶）；本脚本只出数，不划线
  - 分层草案：ziwei-quanshu* = 古籍层；ziweicn* = 注疏系（王亭之太微赋注解等）；
    ziweishuyuan* / jsdj* = 摘编层。分层标签供确认，数值机械统计。

用法：python scripts/scan_variant_report.py
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SNAP_DIR = ROOT / "knowledge_base/obsidian/素材池/网页快照"
FIXTURE = ROOT / "fixtures/fixture_snap-20260812-0.json"

# 与 verify_fixture_snap.py VARIANT_MAP 同源（改须同步）
# 剋→克 真异体（quanlan 同文异写实证：L29「生剋之機」/ L334「论星辰生克制化」L335「生克制化之机」L942「生克制化之垣」）
# 佈→布 真异体（2026-08-12 三判定：字典层教育部《異體字字典》B00040《正字通》「佈，通作布」；实证层 quanlan L27「其星分布一十二垣」vs 太微赋段 L32「其星分佈一十二垣」同文异写；规则层跨三层清 5 条=古籍1/注疏2/摘编2，义项全在分布/佈置/宣告，不沾布匹义，不挂语境条件）
VARIANT_MAP = {"衝": "冲", "沖": "冲", "會": "会", "當": "当", "夾": "夹", "剋": "克", "佈": "布"}

# 真异体线成员集（2026-08-12 三票定，v2）：衝沖剋佈。成员集是活表，字头转正自动并入；
# 繁简字（會當夾）单走繁简线不混入。读数必须带成员集版本，旧读数随转正自动降级历史值。
# v1（首波 2026-08-12）= 衝沖，判据 5.2/万字（32/61,665）；v2（佈 转正后）= 衝沖剋佈，判据 6.16/万字（38/61,665）
TRUE_VARIANTS = {"衝", "沖", "剋", "佈"}

# 挂起堆候选（未收录古籍用字，含繁简与异体，是否进表待三判定/人工确认）。
# 排除规范字（斗=紫微斗数/北斗，规范字形）与纯繁简常用字（為無與後見時氣數斷壽對處發轉類來祿殺
# 等，繁简转换是另一条线，不混入异体挂起堆）；本表只收真异体/生僻古籍字形。
# 2026-08-12 核转正清理：剋→克 真异体已入 VARIANT_MAP（quanlan 同文异写实证 L29/L334/L335/L942）；
# 裏/麼/麽 为繁简线（裏→里、麼麽→么）、乾 分义（乾坤/乾造/乾卦/雄宿乾元 正确用法保留，乾净/乾燥/枯乾/乾爹 繁简残留转干），转出候选表走繁简线。
CANDIDATE_VARIANTS = [
    "崑", "崙", "峩", "峯", "菴", "痾", "逈", "廻", "嶙", "崚", "暦", "厯",
    "冊", "註", "誌", "乗", "傑", "牀", "墻", "雲", "佔",
    "竈", "龜", "響", "鬢", "髪", "亁", "啓", "唘", "嗩",
    "廵", "愼", "懐", "抜", "摯", "攷", "斈", "楳", "漑",
]

# 层级分组（按文件名前缀，草案）：ziwei-shibafeixing=十八飞星盘制层（2026-08-12 实弹后定：
# 识典《紫微斗数》为十八飞星体系，指纹全 0 命中，非全书体系，独立成层不进古籍密度账，价值=版本对照/星曜体系参考）
LAYER_RULES = [
    ("ziwei-quanshu", "古籍层"),
    # SDZJ0170=识典《新锓希夷陈先生紫微斗数全书》简体转写对照本（南阳堂较梓，与书格同底本，2026-08-12 三票定）
    # 古籍层·非底本·不当裁决数（同剥离段）；数据层字形待查（注文层繁体保真，坐实则触发定性复查）
    ("sdzj0170", "古籍层"),
    ("ziwei-shibafeixing", "十八飞星层"),
    ("ziweicn", "注疏系"),
    ("ziweishuyuan", "摘编层"),
    ("jsdj", "摘编层"),
]

# 底本线文件（传统字形底本，指纹验收判定「传统字形底本 → 古籍层入库」；层密度口径 v3：底本线/全层线）。
# 当前仅 quanlan（古籍层组 6/6 含異體）；书格刻本指纹命中后加入此表，底本线密度随之合并。
BOTTOM_FILES = ["2026-08-11-ziwei-quanshu-quanlan.md"]


def classify(name):
    for prefix, layer in LAYER_RULES:
        if prefix in name:
            return layer
    return "其他"


def content_chars(raw):
    """内容级字数（2026-08-12 口径，第二波报告判断基数用）：
    剥离原文文件（type: 剥离原文）只计原文段正文（去 frontmatter/剥离说明/段头）；
    其余文件（纯原文/注疏/摘编）内容级=文件级，保持首波口径连续。
    依据：剥离文件 5,755 字中原文段仅 1,041 字，82% 为结构开销，文件级密度被灌水压低。"""
    text = strip_code(raw)
    if "type: 剥离原文" in raw:
        body = re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.S)
        keep = []
        in_seg = False
        for ln in body.splitlines():
            s = ln.strip()
            if s.startswith("### 段"):
                in_seg = True
                continue
            if not in_seg or not s or s.startswith(">") or s.startswith("#") or s.startswith("["):
                continue
            keep.append(s)
        text = "".join(keep)
    return len(re.sub(r"\s", "", text))


def strip_code(text):
    """去代码块/链接标记，只留正文文字。"""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^[#>*\-\d\.\s`|]+", "", text, flags=re.M)
    return text


def scan_sources():
    files = sorted(SNAP_DIR.glob("*.md"))
    per_layer = defaultdict(lambda: {"files": 0, "chars": 0, "content": 0, "known": Counter(), "cands": Counter()})
    for f in files:
        layer = classify(f.name)
        raw = f.read_text(encoding="utf-8")
        text = strip_code(raw)
        chars = len(re.sub(r"\s", "", text))
        cchars = content_chars(raw)
        d = per_layer[layer]
        d["files"] += 1
        d["chars"] += chars
        d["content"] += cchars
        for ch in VARIANT_MAP:
            n = text.count(ch)
            if n:
                d["known"][ch] += n
        for cand in CANDIDATE_VARIANTS:
            if len(cand) == 1:
                n = text.count(cand)
            else:
                n = text.count(cand)
            if n:
                d["cands"][cand] += n
    return per_layer


def scan_anchors():
    """锚点缺位：从 fixture 样本数。暂缺=出处可指认（注明体系/人物）但料池未摄取；
    真缺=出处都指不出。"""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    samples = data.get("samples", [])
    pend, real, ok = [], [], []
    for s in samples:
        line = s.get("source_line", "")
        sid = s.get("id", "?")
        if "<PLACEHOLDER" in line or "待核" in line or "PLACEHOLDER" in line:
            # 出处可指认性：占位符里有体系/人物线索（梁系/刘韫龄/三合等）→ 暂缺
            if any(k in line for k in ["梁", "刘", "三合", "书院", "ziwei", "体系", "断语"]):
                pend.append(sid)
            else:
                real.append(sid)
        else:
            ok.append(sid)
    return ok, pend, real


def main():
    per_layer = scan_sources()

    print("=" * 76)
    print("首波开扫报告（草案分层，数值机械统计）  snapshot: 2026-08-12")
    print("=" * 76)
    print(f"\n{'层':<8}{'文件数':>6}{'总字数':>10}{'内容级':>10}{'已知异体次数':>12}{'文件级密度':>12}{'内容级密度':>12}")
    print("-" * 88)
    for layer in ["古籍层", "注疏系", "摘编层", "其他"]:
        d = per_layer[layer]
        if not d["files"]:
            continue
        k_total = sum(d["known"].values())
        fdensity = k_total / d["chars"] * 10000 if d["chars"] else 0
        cdensity = k_total / d["content"] * 10000 if d["content"] else 0
        print(f"{layer:<8}{d['files']:>6}{d['chars']:>10}{d['content']:>10}{k_total:>12}{fdensity:>12.2f}{cdensity:>12.2f}")

    print("\n--- 已知异体明细（按层）---")
    for layer in ["古籍层", "注疏系", "摘编层", "其他"]:
        d = per_layer[layer]
        if not d["known"]:
            continue
        items = "  ".join(f"{k}:{v}" for k, v in sorted(d["known"].items()))
        print(f"{layer}: {items}")

    print("\n--- 挂起堆（未收录异体候选，按层 Top15）---")
    for layer in ["古籍层", "注疏系", "摘编层", "其他"]:
        d = per_layer[layer]
        if not d["cands"]:
            continue
        top = d["cands"].most_common(15)
        items = "  ".join(f"{k}:{v}" for k, v in top)
        print(f"{layer}: {items}")

    ok, pend, real = scan_anchors()

    # 真异体线（成员集 v2：衝沖剋佈）+ 层密度口径 v3 双线（底本线/全层线）+ 载体形态梯度
    print("\n--- 真异体线（成员集 v2：衝沖剋佈；层密度口径 v3：底本线/全层线，2026-08-12 三票定）---")
    d = per_layer["古籍层"]
    kt = sum(d["known"].get(ch, 0) for ch in TRUE_VARIANTS)
    print(f"古籍层·全层线: {kt} 次（" + " ".join(f"{ch}:{d['known'].get(ch,0)}" for ch in sorted(TRUE_VARIANTS) if d['known'].get(ch, 0)) + f"） 文件级 {kt/d['chars']*10000:.2f}/万字、内容级 {kt/d['content']*10000:.2f}/万字")
    bkt = bchars = 0
    for bf in BOTTOM_FILES:
        braw = (SNAP_DIR / bf).read_text(encoding="utf-8")
        btext = strip_code(braw)
        bchars += len(re.sub(r"\s", "", btext))
        bkt += sum(btext.count(ch) for ch in TRUE_VARIANTS)
    print(f"古籍层·底本线（=判据，激活线输入，书格命中后并入）: {bkt}/{bchars}= {bkt/bchars*10000:.2f}/万字（底本 {len(BOTTOM_FILES)} 个）")
    for layer in ["注疏系", "摘编层", "其他"]:
        d = per_layer[layer]
        if not d["files"]:
            continue
        kt = sum(d["known"].get(ch, 0) for ch in TRUE_VARIANTS)
        if not kt:
            continue
        print(f"{layer}: {kt} 次（" + " ".join(f"{ch}:{d['known'].get(ch,0)}" for ch in sorted(TRUE_VARIANTS) if d['known'].get(ch, 0)) + f"） 文件级 {kt/d['chars']*10000:.2f}/万字、内容级 {kt/d['content']*10000:.2f}/万字")

    print("\n--- 载体形态梯度（古籍层按文件，真异体线成员集 v2；保真度由载体决定非层名）---")
    for f in sorted(SNAP_DIR.glob("*.md")):
        if classify(f.name) != "古籍层":
            continue
        raw = f.read_text(encoding="utf-8")
        text = strip_code(raw)
        cchars = content_chars(raw)
        kt = sum(text.count(ch) for ch in TRUE_VARIANTS)
        den = f"{kt/cchars*10000:.2f}/万字" if kt else "0（无真异体）"
        print(f"{f.name}: {kt} 次 / {cchars} 内容级字 = {den}")

    print("\n--- 锚点缺位（fixture 样本级，暂缺/真缺分股）---")
    print(f"已核 {len(ok)}: {ok or '-'}")
    print(f"暂缺（出处可指认、料池未摄取）{len(pend)}: {pend or '-'}")
    print(f"真缺（出处指不出）{len(real)}: {real or '-'}")

    print("\n注：密度=已知异体次数/总字数*10000；文件级=文件全文（含 frontmatter/段头结构开销），内容级=剥离原文文件只计段正文、其余文件同文件级（2026-08-12 口径：判断基数走内容级，文件级保纵向可比）；挂起堆候选须过三判定确认后才进表，")
    print("    繁简字（為無與等）走繁简线不混入异体挂起堆；分层标签为草案，供确认。")


if __name__ == "__main__":
    main()
