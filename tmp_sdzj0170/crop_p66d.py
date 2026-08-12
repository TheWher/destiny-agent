# -*- coding: utf-8 -*-
"""第四版：凶 字本体 8x 单字裁切（y 2930~3180, x 700~950）"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image

src = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages\p66_full300.png"
img = Image.open(src)

c = img.crop((700, 2930, 950, 3180))
c = c.resize((c.width * 8, c.height * 8), Image.LANCZOS)
o = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages\p66_xiong_single_8x.png"
c.save(o)
print("saved", o, c.size)
