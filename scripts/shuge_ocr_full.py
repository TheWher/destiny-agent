# -*- coding: utf-8 -*-
"""书格刻本全量 OCR：逐页识别 + 列排序（竖排从右到左）+ 指纹句探针

输出：
  tmp_sdzj0170/shuge_ocr/fulltext.txt        全文（每页带页标记，列序已校正）
  tmp_sdzj0170/shuge_ocr/probe_report.txt    指纹句探针报告（定位页 + OCR 字形）
"""
import sys, os, re, time
sys.stdout.reconfigure(encoding="utf-8")
import fitz
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

PDF = r"D:\OH-WorkSpace\Destiny_agent\新锓希夷陈先生紫微斗数全书.七卷.宋.陈抟撰.明.潘希尹补.明代南阳堂刊本.黑白版.pdf"
OUT = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr"
os.makedirs(OUT, exist_ok=True)
DPI = 200

# 指纹句探针（内容级定位用；字形级需回图核对，OCR 字形不可直接采信）
PROBES = [
    ("禄逢冲破/祿逢沖破/禄逢冲", ["禄逢", "祿逢", "沖破", "冲破", "冲"]),
    ("生尅之機/生剋之機", ["生尅", "生剋", "尅之機", "剋之機", "之機"]),
    ("辨生尅制化", ["辨生尅", "辨生剋", "生尅制化", "生剋制化"]),
    ("相貌加刑殺", ["相貌加刑", "刑殺", "刑鼓", "刑尅", "刑剋"]),
    ("其星分布一十二垣", ["其星分布", "十二垣", "分佈", "分布", "佈"]),
    ("夾昌夾曲", ["夾昌夾曲", "夹昌夹曲", "昌夾曲", "昌夾"]),
    ("諸㐫/諸凶", ["諸㐫", "諸凶", "諸", "㐫"]),
    ("吉處藏㐫/吉处藏凶", ["藏㐫", "藏凶", "吉處", "吉处"]),
]

ocr = RapidOCR()

def render_png(doc, pno):
    pix = doc[pno].get_pixmap(dpi=DPI)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    p = os.path.join(OUT, "_tmp_page.png")
    img.save(p)
    return p

def sort_columns(res):
    """竖排列排序：按检测框 x 中心降序（右列在前），同列按 y 升序合并。"""
    items = []
    for box, text, score in res:
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        cx = sum(xs) / 4
        cy = sum(ys) / 4
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        items.append((cx, cy, w, h, text, score))
    # 列聚合：按 x 中心距离聚成列（容差 = 列宽的 1.5 倍）
    items.sort(key=lambda t: -t[0])
    cols = []
    for it in items:
        cx, cy, w, h, text, score = it
        placed = False
        for col in cols:
            colw = max(t[3] for t in col["items"])
            if abs(col["cx"] - cx) < max(w, colw) * 0.6:
                col["items"].append(it)
                placed = True
                break
        if not placed:
            cols.append({"cx": cx, "items": [it]})
    for col in cols:
        col["items"].sort(key=lambda t: t[1])  # 列内按 y 升序（上到下）
    cols.sort(key=lambda c: -c["cx"])
    lines = []
    for col in cols:
        line = "".join(t[4] for t in col["items"])
        if line.strip():
            lines.append(line)
    return lines

def ocr_page(doc, pno):
    p = render_png(doc, pno)
    res, elapse = ocr(p)
    t = elapse[0] if isinstance(elapse, (list, tuple)) and elapse else 0
    if not res:
        return [], t
    lines = sort_columns(res)
    return lines, t

def main():
    start = time.time()
    doc = fitz.open(PDF)
    total = doc.page_count
    start_p = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    end_p = int(sys.argv[2]) if len(sys.argv) > 2 else total
    end_p = min(end_p, total)
    print(f"总页数 {total}，DPI {DPI}，OCR 范围 [{start_p}, {end_p}]")

    all_pages = []
    probe_hits = {}  # probe -> [(page, hit_text)]
    # 归一化指纹文本用：去空白标点
    def norm(s):
        return re.sub(r"[\s，。、；：？！「」『』（）()《》·\-—]", "", s)

    for pno in range(start_p - 1, end_p):
        lines, t = ocr_page(doc, pno)
        all_pages.append(lines)
        # 探针：整页文本（列序已校正）里找关键词
        page_text = "".join(lines)
        npt = norm(page_text)
        for name, kws in PROBES:
            for kw in kws:
                if norm(kw) in npt:
                    probe_hits.setdefault(name, []).append((pno + 1, kw))
                    break
        if (pno + 1) % 50 == 0:
            print(f"  [{pno+1}/{total}] {time.time()-start:.0f}s", flush=True)
    doc.close()

    # 写全文（按段存，最后合并）
    seg = f"fulltext_p{start_p}_{end_p}.txt"
    with open(os.path.join(OUT, seg), "w", encoding="utf-8") as f:
        for i, lines in enumerate(all_pages):
            real_p = start_p + i
            f.write(f"\n===== 第{real_p}页 =====\n")
            f.write("\n".join(lines))
            f.write("\n")

    print(f"\n完成，耗时 {time.time()-start:.0f}s")
    print(f"输出：{os.path.join(OUT, seg)}")

if __name__ == "__main__":
    main()
