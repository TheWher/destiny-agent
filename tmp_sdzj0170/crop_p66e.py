# -*- coding: utf-8 -*-
"""第五版：修正 y 后重裁 凶 字（y 2640~2960）与上下文 有凶禍（y 2480~3000）"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image

src = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages\p66_full300.png"
img = Image.open(src)

c1 = img.crop((700, 2640, 950, 2960))
c1 = c1.resize((c1.width * 8, c1.height * 8), Image.LANCZOS)
o1 = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages\p66_xiong_single2_8x.png"
c1.save(o1)
print("saved", o1, c1.size)

c2 = img.crop((700, 2480, 950, 3000))
c2 = c2.resize((c2.width * 6, c2.height * 6), Image.LANCZOS)
o2 = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages\p66_youxionghuo_6x.png"
c2.save(o2)
print("saved", o2, c2.size)
