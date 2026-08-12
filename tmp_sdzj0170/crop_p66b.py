# -*- coding: utf-8 -*-
"""第二版裁切：横向覆盖左侧 3~4 列，纵向下部，定位 必有凶祸/卤祸 词位"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image

src = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages\p66_full300.png"
img = Image.open(src)
W, H = img.size
print("full", W, H)

c = img.crop((30, 2600, 1000, H))
c = c.resize((c.width * 2, c.height * 2), Image.LANCZOS)
o = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages\p66_zone2.png"
c.save(o)
print("saved", o, c.size)
