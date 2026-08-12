# -*- coding: utf-8 -*-
"""剥离注疏体里的古籍原文段，落古籍层（2026-08-12，剥离路执行）。

用法: python scripts/strip_fu_sections.py
来源（三篇，均已在素材池，料池保真不动）:
  - ziweishuyuan-baizi-qianjin-jue     → 百字千金诀（加粗诀文行）
  - ziweishuyuan-gusui-fu-zhujie       → 骨髓赋（注解行前一行=原文段）
  - ziweicn-wangtingzhi-taiweifu-jingjie → 太微赋（注解/释行前一行=赋文行）
产出: 素材池/网页快照/2026-08-12-ziwei-quanshu-jieli-*.md（古籍层前缀，进密度账）
"""
import pathlib
import re
import datetime

SNAP = pathlib.Path(__file__).resolve().parent.parent / "knowledge_base/obsidian/素材池/网页快照"
NOW = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def read(fname):
    return (SNAP / fname).read_text(encoding="utf-8")


def write_out(fname, title, url, source, tags, body_notes, segments):
    """segments: list of (原文段, 出处行标注)"""
    body_lines = []
    for i, (seg, note) in enumerate(segments, 1):
        body_lines.append(f"### 段{i}（{note}）\n\n{seg}\n")
    fm = f"""---
title: {title}
url: {url}
source: {source}
fetched_at: {NOW}
status: raw
authority: 注疏体剥离（原文段，来源见各段标注）
system: 古籍
tags:
{chr(10).join('  - ' + t for t in tags)}
type: 剥离原文
content_mode: plain
cleaned_at: {NOW}
---

> 剥离说明：{body_notes}

{chr(10).join(body_lines)}"""
    (SNAP / fname).write_text(fm, encoding="utf-8")
    print(f"写 {fname}：{len(segments)} 段，{sum(len(s) for s, _ in segments)} 字")


def strip_bold_jue(fname):
    """百字千金诀：加粗诀文行"""
    lines = read(fname).splitlines()
    segs = []
    for i, line in enumerate(lines, 1):
        m = re.fullmatch(r"\*\*(.+?)\*\*", line.strip())
        if m:
            t = m.group(1).strip()
            if t.startswith("注解") or t.startswith("转载"):
                continue
            segs.append((t, f"{fname} L{i}"))
    return segs


def strip_before_annotation(fname, anno_patterns):
    """骨髓赋/太微赋：注解/释行前最近非空行=原文段"""
    lines = read(fname).splitlines()
    segs = []
    for i, line in enumerate(lines, 1):
        if re.match(anno_patterns, line.strip()):
            # 向前找最近的非空、非标题、非导航行
            for j in range(i - 2, -1, -1):
                prev = lines[j].strip()
                if not prev:
                    continue
                if prev.startswith("#") or prev.startswith("**注解") or prev.startswith("[") or "热门搜索" in prev:
                    break
                segs.append((prev, f"{fname} L{j + 1}"))
                break
    return segs


def main():
    # 1. 百字千金诀（ziweishuyuan 610）
    segs = strip_bold_jue("2026-08-11-ziweishuyuan-baizi-qianjin-jue.md")
    write_out(
        "2026-08-12-ziwei-quanshu-jieli-baizi-qianjin-jue.md",
        "百字千金诀（原文段，自韫龄注解剥离）",
        "https://www.ziweishuyuan.com/textbook/ziwei-complete-works/610.html",
        "紫微取象派 ziweishuyuan.com",
        ["素材", "古籍", "诀文", "剥离"],
        "从刘韫龄《百字千金诀》注解体剥离加粗诀文行，出处保真（610.html）。",
        segs,
    )

    # 2. 骨髓赋（ziweishuyuan 188）
    segs = strip_before_annotation(
        "2026-08-11-ziweishuyuan-gusui-fu-zhujie.md", r"\*\*注解：")
    write_out(
        "2026-08-12-ziwei-quanshu-jieli-gusui-fu.md",
        "斗数骨髓赋（原文段，自论述篇注解剥离）",
        "https://www.ziweishuyuan.com/textbook/ziwei-complete-works/188.html",
        "紫微取象派 ziweishuyuan.com",
        ["素材", "古籍", "赋文", "骨髓赋", "剥离"],
        "从刘韫龄《斗数骨髓赋（论述篇注解）》剥离注解前原文段，出处保真（188.html）。",
        segs,
    )

    # 3. 太微赋（ziweicn 精解）
    segs = strip_before_annotation(
        "2026-08-11-ziweicn-wangtingzhi-taiweifu-jingjie.md", r"(注解[:：]|﹝释﹞)")
    write_out(
        "2026-08-12-ziwei-quanshu-jieli-taiweifu.md",
        "太微赋（原文段，自王亭之精解剥离）",
        "https://www.ziweicn.com/show/3389.html",
        "紫微斗数学堂 ziweicn.com",
        ["素材", "古籍", "赋文", "太微赋", "剥离"],
        "从王亭之《太微赋》精解剥离注解/释行前赋文行，出处保真（赋文依民初石印本选注）。",
        segs,
    )


if __name__ == "__main__":
    main()
