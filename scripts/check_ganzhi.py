#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""干支自算残留检查 — 指纹: (x-4)%10 / (x-4)%12

配套铁律 (CLAUDE.md): 干支一律用引擎注入值, 禁止项目层按公历年自算。
前端任何干支相关计算默认视为残留, 不存在"合法的前端干支计算"。

用法:  python scripts/check_ganzhi.py
判定:  白名单外零命中 = 合规 (exit 0); 有违规 = exit 1。
       流年/大运引擎化后清空白名单, 零命中零白名单 = "干支自算彻底清零"的客观判据。

2026-08-04 建 (hanako 固化教训 / mose 白名单设计):
  凌晨与当日两轮扫描都靠一次性 grep + 当时注意力, 仍漏 6 处 → 教训必须变工具。
  白名单防"跑一次报一堆, 人看麻了"的麻木盲区, 输出只剩违规项才可机械判定。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 扫描范围: 项目层(前端模板/静态 + 路由 + 服务)。
# 引擎本体 (bazi_calculator.py / ziwei_calculator.py) 内部干支计算是本职, 排除。
SCAN_DIRS = ['templates', 'static', 'routes', 'services']
EXCLUDE_FILES = ['bazi_calculator.py', 'ziwei_calculator.py']
SKIP_DIRS = ['node_modules']

# 指纹: 括号内以 ±4 收尾后取模 10/12 (干支序列换算常数: 1984=甲子)
PATTERN = re.compile(r'\([^()\n]*?[-+]\s*4\s*\)\s*%\s*(10|12)')

# 白名单: 引擎化完成后已清空（2026-09-09 TODO-GZ-LIUNIAN 落地）。
# 引擎注入: ziwei_calculator.year_gz / year_gz_labels / get_horoscope(year_grid, yearly_gan,
# yearly_zhi, today_day_zhi) + bazi_calculator.year_ganzhi；前端流年/流月/流日标签全部消费注入值。
# 生命周期: 零命中零白名单 = "干支自算彻底清零"判据达成；新残留直接报违规，先记档再入白名单。
# 防止白名单变成新暂缓区 (hanako 2026-08-04)。
WHITELIST = []


def main():
    violations, whitelisted = [], []
    for d in SCAN_DIRS:
        base = os.path.join(ROOT, d)
        for root, _dirs, files in os.walk(base):
            if any(skip in root for skip in SKIP_DIRS):
                continue
            for fn in files:
                if not fn.endswith(('.py', '.js', '.html')):
                    continue
                if fn in EXCLUDE_FILES:
                    continue
                fp = os.path.join(root, fn)
                rel = os.path.relpath(fp, ROOT).replace('\\', '/')
                try:
                    with open(fp, encoding='utf-8') as f:
                        lines = f.read().splitlines()
                except Exception:
                    continue
                for i, ln in enumerate(lines, 1):
                    if PATTERN.search(ln):
                        item = (rel, i)
                        if item in WHITELIST:
                            whitelisted.append(item)
                        else:
                            violations.append((rel, i, ln.strip()[:100]))

    if violations:
        print('❌ 干支自算残留 (白名单外) {} 处:'.format(len(violations)))
        for rel, i, ln in violations:
            print('   {}:{}  {}'.format(rel, i, ln))
        print('  白名单已记档 {} 条。残留需删除或改引擎注入; 新口径须先记档再入白名单。'.format(len(whitelisted)))
        sys.exit(1)

    print('✅ 白名单外零命中。白名单 {} 条 (流年/大运已记档口径)。'.format(len(whitelisted)))
    if not whitelisted:
        print('  零命中零白名单 — 干支自算彻底清零 (客观判据达成)')
    sys.exit(0)


if __name__ == '__main__':
    main()
