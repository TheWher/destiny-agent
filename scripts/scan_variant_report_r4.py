# -*- coding: utf-8 -*-
"""
scan_variant_report_r4.py — r4 全层线重扫（数据层口径，2026-08-12 v4 定案）

变更（vs r3）：
  - SDZJ0170 扫描源从渲染层快照（SNAP_DIR/*sdzj0170-*.md）切换为数据层导出
    （tmp_sdzj0170/datalayer_md/sd_sdzj0170_*.md，mose 补提落盘）
  - 数据层用分卷文件（v1~v5/v7/mingtu），排除 all 合并文件避免重复计数
  - 其余层/文件/口径与 r3 完全一致（真异体线成员集 v2：衝沖剋佈；底本线/全层线 v3）
  - 附加统计：尅（数据层特征字形，VARIANT_MAP 加否走三票，见注记）

用法：python scripts/scan_variant_report_r4.py
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SNAP_DIR = ROOT / "knowledge_base/obsidian/素材池/网页快照"
DATALAYER_DIR = ROOT / "tmp_sdzj0170/datalayer_md"
FIXTURE = ROOT / "fixtures/fixture_snap-20260812-0.json"

VARIANT_MAP = {"衝": "冲", "沖": "冲", "會": "会", "當": "当", "夾": "夹", "剋": "克", "佈": "布", "尅": "克", "㐫": "凶", "隂": "阴", "郷": "乡", "殺": "杀", "賦": "赋", "隨": "随"}
# 成员集版本常量（数据身份第三维；v4=衝沖剋佈尅㐫隂郷，2026-08-12 三票收，成员集扩编 mv3→mv4）。
# 判据线扩入 㐫/隂/郷（異體，字典层《玉篇》/汉典有出处）；VARIANT_MAP 扩入 殺/賦/隨（标准繁简，不进判据线）。
# 升 v5 时三处同步改：本脚本 + verify_fingerprint.py 各一 MEMBER_SET_VERSION + TRUE_VARIANTS 成员集（两脚本注释互相点名，谁升都不会只看一个文件）。
MEMBER_SET_VERSION = "mv4"
# 成员集 v4（2026-08-12 三票收，扩编）：判据线并头原则同 v3——判据测"是否转简成简体"，
# 㐫/隂/郷 与 衝沖剋佈尅 同类（異體）；郷/隂 的 MAP value 落最终简体（乡/阴），異體层关系（郷→鄉、隂→陰）记在字典层出处不进 MAP value。
# 注：quanlan 剋=6（实测）、注疏系 剋=56；"quanlan 剋 62"系两源相加串口径，已在报告注释纠正
TRUE_VARIANTS = {"衝", "沖", "剋", "佈", "尅", "㐫", "隂", "郷"}
CANDIDATE_VARIANTS = [
    "崑", "崙", "峩", "峯", "菴", "痾", "逈", "廻", "嶙", "崚", "暦", "厯",
    "冊", "註", "誌", "乗", "傑", "牀", "墻", "雲", "佔",
    "竈", "龜", "響", "鬢", "髪", "亁", "啓", "唘", "嗩",
    "廵", "愼", "懐", "抜", "摯", "攷", "斈", "楳", "漑",
]

LAYER_RULES = [
    ("ziwei-quanshu", "古籍层"),
    # r4：SDZJ0170 定性 v4 定案 = 古籍层·非底本·数据层繁体保真/渲染层简体（2026-08-12 三票）
    ("sdzj0170", "古籍层"),
    ("ziwei-shibafeixing", "十八飞星层"),
    ("ziweicn", "注疏系"),
    ("ziweishuyuan", "摘编层"),
    ("jsdj", "摘编层"),
]

BOTTOM_FILES = ["2026-08-11-ziwei-quanshu-quanlan.md"]

# 数据层分卷文件（排除 all 合并文件；v1~v5/v7/mingtu 对应渲染层 juan1~5/7/mingtu，mulu 渲染层无对应数据层文件）
DATALAYER_FILES = ["sd_sdzj0170_v1.md", "sd_sdzj0170_v2.md", "sd_sdzj0170_v3.md",
                   "sd_sdzj0170_v4.md", "sd_sdzj0170_v5.md", "sd_sdzj0170_v7.md",
                   "sd_sdzj0170_mingtu.md"]


def classify(name):
    for prefix, layer in LAYER_RULES:
        if prefix in name:
            return layer
    return "其他"


def content_chars(raw):
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
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^[#>*\-\d\.\s`|]+", "", text, flags=re.M)
    return text


def iter_scan_files():
    """r4：SDZJ0170 从数据层取，其余从快照目录取。"""
    for f in sorted(SNAP_DIR.glob("*.md")):
        if "sdzj0170" in f.name:
            continue  # 渲染层 SDZJ0170 作废（v4 定案）
        yield f.name, f
    for fn in DATALAYER_FILES:
        f = DATALAYER_DIR / fn
        if f.exists():
            yield fn, f


def scan_sources():
    per_layer = defaultdict(lambda: {"files": 0, "chars": 0, "content": 0, "known": Counter(), "cands": Counter()})
    per_file = []
    for name, f in iter_scan_files():
        layer = classify(name)
        raw = f.read_text(encoding="utf-8")
        text = strip_code(raw)
        chars = len(re.sub(r"\s", "", text))
        cchars = content_chars(raw)
        d = per_layer[layer]
        d["files"] += 1
        d["chars"] += chars
        d["content"] += cchars
        kt = 0
        for ch in VARIANT_MAP:
            n = text.count(ch)
            if n:
                d["known"][ch] += n
        for ch in TRUE_VARIANTS:
            kt += text.count(ch)
        for cand in CANDIDATE_VARIANTS:
            n = text.count(cand)
            if n:
                d["cands"][cand] += n
        per_file.append((name, layer, chars, cchars, kt))
    return per_layer, per_file


def scan_anchors():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    samples = data.get("samples", [])
    pend, real, ok = [], [], []
    for s in samples:
        line = s.get("source_line", "")
        sid = s.get("id", "?")
        if "<PLACEHOLDER" in line or "待核" in line or "PLACEHOLDER" in line:
            if any(k in line for k in ["梁", "刘", "三合", "书院", "ziwei", "体系", "断语"]):
                pend.append(sid)
            else:
                real.append(sid)
        else:
            ok.append(sid)
    return ok, pend, real


def main():
    per_layer, per_file = scan_sources()

    print("=" * 76)
    print("r4 重扫报告（数据层口径 v4，2026-08-12 三票定案；SDZJ0170 源=数据层 JSON 导出）")
    print(f"数据身份（三维）：[层|源|成员集版本]，成员集版本 = {MEMBER_SET_VERSION}（衝沖剋佈尅㐫隂郷）")
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

    print("\n--- 真异体线（成员集 v4：衝沖剋佈尅㐫隂郷；层密度口径 v3：底本线/全层线）---")
    d = per_layer["古籍层"]
    kt = sum(d["known"].get(ch, 0) for ch in TRUE_VARIANTS)
    print(f"古籍层·全层线: {kt} 次（" + " ".join(f"{ch}:{d['known'].get(ch,0)}" for ch in sorted(TRUE_VARIANTS) if d['known'].get(ch, 0)) + f"） 文件级 {kt/d['chars']*10000:.2f}/万字、内容级 {kt/d['content']*10000:.2f}/万字 [古籍层|全层线聚合|{MEMBER_SET_VERSION}]")
    bkt = bchars = 0
    for bf in BOTTOM_FILES:
        braw = (SNAP_DIR / bf).read_text(encoding="utf-8")
        btext = strip_code(braw)
        bchars += len(re.sub(r"\s", "", btext))
        bkt += sum(btext.count(ch) for ch in TRUE_VARIANTS)
    print(f"古籍层·底本线（=判据，激活线输入，书格命中后并入）: {bkt}/{bchars}= {bkt/bchars*10000:.2f}/万字（底本 {len(BOTTOM_FILES)} 个） [古籍层|quanlan|{MEMBER_SET_VERSION}]")
    for layer in ["注疏系", "摘编层", "其他"]:
        d = per_layer[layer]
        if not d["files"]:
            continue
        kt = sum(d["known"].get(ch, 0) for ch in TRUE_VARIANTS)
        if not kt:
            continue
        print(f"{layer}: {kt} 次（" + " ".join(f"{ch}:{d['known'].get(ch,0)}" for ch in sorted(TRUE_VARIANTS) if d['known'].get(ch, 0)) + f"） 文件级 {kt/d['chars']*10000:.2f}/万字、内容级 {kt/d['content']*10000:.2f}/万字 [{layer}|全层聚合|{MEMBER_SET_VERSION}]")

    print("\n--- 载体形态梯度（古籍层按文件，真异体线成员集 v4：衝沖剋佈尅㐫隂郷；保真度由载体决定非层名；每行带层标注⑩）---")
    for name, layer, chars, cchars, kt in sorted(per_file, key=lambda x: -x[4] / max(x[3], 1)):
        if layer != "古籍层":
            continue
        layertag = "JSON" if name.startswith("sd_sdzj0170") else "md"
        den = f"{kt/cchars*10000:.2f}/万字" if kt else "0（无真异体）"
        print(f"{name}: {kt} 次 / {cchars} 内容级字 = {den} [{layertag}|{name}|{MEMBER_SET_VERSION}]")

    print("\n--- r4 附加：尅/剋 分列对照（三票定案后 VARIANT_MAP 分列保留版本指纹）---")
    ke_total = 0
    for name, f in iter_scan_files():
        if "sdzj0170" not in name:
            continue
        text = strip_code(f.read_text(encoding="utf-8"))
        n = text.count("尅")
        if n:
            ke_total += n
            print(f"{name}: 尅 {n} 次")
    print(f"SDZJ0170 数据层 尅 合计: {ke_total} 次（quanlan 剋 6 次、注疏系 剋 56 次，分列对照，书格到后第一验尅/剋；注：62 是 quanlan6+注疏56 之和，别串口径）")

    ok, pend, real = scan_anchors()
    print("\n--- 锚点缺位（fixture 样本级，暂缺/真缺分股）---")
    print(f"已核 {len(ok)}: {ok or '-'}")
    print(f"暂缺（出处可指认、料池未摄取）{len(pend)}: {pend or '-'}")
    print(f"真缺（出处指不出）{len(real)}: {real or '-'}")

    print("\n注：r4 口径 = v3 口径 + SDZJ0170 源切数据层（v4 定案）；密度=已知异体次数/总字数*10000；")
    print("    内容级=剥离原文文件只计段正文、其余文件同文件级；挂起堆候选须过三判定确认后才进表；")
    print("    all 合并文件已排除防重复计数；渲染层 SDZJ0170 数据作废（v4）。")


if __name__ == "__main__":
    main()
