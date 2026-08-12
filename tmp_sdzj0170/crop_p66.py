# -*- coding: utf-8 -*-
"""裁切 66 页目标区：左侧最末列下部（擎羊条目 必有卤祸/凶祸 词位），放大供字形结构核对"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image

src = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages\p66_full300.png"
img = Image.open(src)
W, H = img.size
print("full", W, H)

# 最左列（第10列，右起）：x 约 40~400；目标词位在列底部 y 3000~4220
# 第一版：宽一点，列下部 60%，确认词位位置
c1 = img.crop((30, 1600, 420, H))
c1 = c1.resize((c1.width * 2, c1.height * 2), Image.LANCZOS)
o1 = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages\p66_col10_lower.png"
c1.save(o1)
print("saved", o1, c1.size)

# 第二版：底部 32%，目标词位大概率在这，4x 放大
c2 = img.crop((30, 2900, 420, H))
c2 = c2.resize((c2.width * 4, c2.height * 4), Image.LANCZOS)
o2 = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages\p66_target_4x.png"
c2.save(o2)
print("saved", o2, c2.size)
