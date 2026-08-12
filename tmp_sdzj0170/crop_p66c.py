# -*- coding: utf-8 -*-
"""第三版裁切：必有凶禍 词位，宽版 4x + 凶字本体 8x，核对字形结构"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image

src = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages\p66_full300.png"
img = Image.open(src)

# 宽版：必有凶禍 四字（y 2280~3220，x 700~1100）
c1 = img.crop((700, 2280, 1100, 3220))
c1 = c1.resize((c1.width * 4, c1.height * 4), Image.LANCZOS)
o1 = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages\p66_biyou_4x.png"
c1.save(o1)
print("saved", o1, c1.size)

# 凶字本体：y 2730~3080，x 770~1040
c2 = img.crop((770, 2730, 1040, 3080))
c2 = c2.resize((c2.width * 8, c2.height * 8), Image.LANCZOS)
o2 = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages\p66_xiong_char_8x.png"
c2.save(o2)
print("saved", o2, c2.size)
