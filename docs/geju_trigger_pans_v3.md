# 破格触发盘构造清单 v3（2026-08-14 hanako）

盘型=构造盘（验规则自洽）。扫描 20000 盘，火贪命中 2167（同宫 548 / 仅会照 1619）。
对照列：我的教材口径标签 vs 引擎新 geju_status（成立/受损/破格/不成立），供 expected 真值列与 diff harness 裁决。

## 火贪格（命中 2167 盘）
- **clean(同宫+贪狼庙旺)** | 1941-02-01 04时 | 命子 | 引擎level=吉 breaking=[] | 引擎状态=成立（[]）
  - 贪狼庙 | 火同贪=True 铃同贪=False | 三方硬煞2 羊陀=False 化忌=False 空劫=False 天刑=False | 紫贪=False 廉贪=False
- **clean(其他)** | 1941-02-02 08时 | 命戌 | 引擎level=中 breaking=[] | 引擎状态=成立（[]）
  - 贪狼得 | 火同贪=True 铃同贪=False | 三方硬煞2 羊陀=False 化忌=False 空劫=False 天刑=False | 紫贪=False 廉贪=False
- **breaking(三方羊陀/化忌)** | 1941-03-04 06时 | 命子 | 引擎level=忌 breaking=[] | 引擎状态=破格（['ht-brk-004']弱化:ht-wkn-001）
  - 贪狼得 | 火同贪=True 铃同贪=False | 三方硬煞2 羊陀=True 化忌=False 空劫=True 天刑=False | 紫贪=False 廉贪=False
- **breaking(三方羊陀/化忌)** | 1941-03-07 18时 | 命午 | 引擎level=中 breaking=[] | 引擎状态=破格（['ht-brk-004']弱化:ht-wkn-001）
  - 贪狼旺 | 火同贪=True 铃同贪=False | 三方硬煞2 羊陀=True 化忌=False 空劫=True 天刑=False | 紫贪=False 廉贪=False
- **reject(羊陀与火/铃同宫)** | 1941-05-08 14时 | 命戌 | 引擎level=吉 breaking=[] | 引擎状态=不成立（['ht-brk-001']弱化:ht-wkn-001）
  - 贪狼庙 | 火同贪=True 铃同贪=False | 三方硬煞2 羊陀=True 化忌=False 空劫=True 天刑=False | 紫贪=False 廉贪=False
- **weakener(紫贪/廉贪同宫)** | 1941-02-26 12时 | 命酉 | 引擎level=吉 breaking=[] | 引擎状态=受损（[]弱化:ht-wkn-001,ht-wkn-002）
  - 贪狼旺 | 火同贪=True 铃同贪=False | 三方硬煞1 羊陀=False 化忌=False 空劫=True 天刑=False | 紫贪=True 廉贪=False
- **huizhao_only(教材口径非成格)** | 1941-01-27 02时 | 命丑 | 引擎level=忌 breaking=[] | 引擎状态=破格（['ht-brk-004']弱化:ht-wkn-002）
  - 贪狼旺 | 火同贪=False 铃同贪=False | 三方硬煞2 羊陀=True 化忌=False 空劫=False 天刑=False | 紫贪=True 廉贪=False
## 铃贪格（命中 2247 盘）
- **clean(同宫+贪狼庙旺)** | 1941-01-28 04时 | 命子 | 引擎level=吉 breaking=[] | 引擎状态=成立（[]）
  - 贪狼旺 | 火同贪=False 铃同贪=True | 三方硬煞2 羊陀=False 化忌=False 空劫=False 天刑=False | 紫贪=False 廉贪=False
- **clean(同宫+贪狼庙旺)** | 1941-01-28 12时 | 命申 | 引擎level=吉 breaking=[] | 引擎状态=成立（[]）
  - 贪狼庙 | 火同贪=False 铃同贪=True | 三方硬煞2 羊陀=False 化忌=False 空劫=False 天刑=False | 紫贪=False 廉贪=False
- **breaking(三方羊陀/化忌)** | 1941-02-06 08时 | 命戌 | 引擎level=忌 breaking=[] | 引擎状态=破格（['lt-brk-004']）
  - 贪狼得 | 火同贪=False 铃同贪=True | 三方硬煞2 羊陀=True 化忌=True 空劫=False 天刑=False | 紫贪=False 廉贪=False
- **breaking(三方羊陀/化忌)** | 1941-02-06 12时 | 命申 | 引擎level=中 breaking=[] | 引擎状态=破格（['lt-brk-004']）
  - 贪狼庙 | 火同贪=False 铃同贪=True | 三方硬煞2 羊陀=True 化忌=True 空劫=False 天刑=False | 紫贪=False 廉贪=False
- **reject(羊陀与火/铃同宫)** | 1941-02-08 00时 | 命寅 | 引擎level=吉 breaking=[] | 引擎状态=不成立（['lt-brk-001']）
  - 贪狼庙 | 火同贪=False 铃同贪=True | 三方硬煞3 羊陀=True 化忌=True 空劫=False 天刑=False | 紫贪=False 廉贪=False
- **weakener(紫贪/廉贪同宫)** | 1941-08-12 22时 | 命酉 | 引擎level=吉 breaking=[] | 引擎状态=受损（[]弱化:lt-wkn-002）
  - 贪狼旺 | 火同贪=False 铃同贪=True | 三方硬煞1 羊陀=False 化忌=False 空劫=False 天刑=False | 紫贪=True 廉贪=False
- **huizhao_only(教材口径非成格)** | 1941-01-27 16时 | 命午 | 引擎level=中 breaking=[] | 引擎状态=成立（[]）
  - 贪狼得 | 火同贪=False 铃同贪=False | 三方硬煞2 羊陀=False 化忌=False 空劫=False 天刑=False | 紫贪=False 廉贪=False
## 君臣庆会（命中 738 盘）
- **clean(上吉)** | 1941-01-03 16时 | 命巳 | 引擎level=上吉 breaking=[] | 引擎状态=成立（[]）
  - 贪狼庙 | 火同贪=False 铃同贪=False | 三方硬煞1 羊陀=True 化忌=False 空劫=False 天刑=False | 紫贪=False 廉贪=False
- **clean(上吉)** | 1941-01-07 20时 | 命卯 | 引擎level=上吉 breaking=[] | 引擎状态=成立（[]）
  - 贪狼旺 | 火同贪=False 铃同贪=False | 三方硬煞2 羊陀=True 化忌=False 空劫=True 天刑=False | 紫贪=True 廉贪=False
- **breaking(命坐煞/煞重)** | 1941-01-07 12时 | 命未 | 引擎level=中 breaking=['命宫坐煞'] | 引擎状态=破格（['jc-brk-001']）
  - 贪狼陷 | 火同贪=False 铃同贪=False | 三方硬煞1 羊陀=True 化忌=False 空劫=False 天刑=False | 紫贪=False 廉贪=True
- **breaking(命坐煞/煞重)** | 1941-01-13 08时 | 命酉 | 引擎level=中 breaking=['命宫坐煞'] | 引擎状态=破格（['jc-brk-001']）
  - 贪狼旺 | 火同贪=False 铃同贪=False | 三方硬煞1 羊陀=True 化忌=False 空劫=True 天刑=False | 紫贪=True 廉贪=False
## 杀破狼格（命中 5001 盘）
- **clean** | 1941-01-02 00时 | 命丑 | 引擎level=中 breaking=[] | 引擎状态=成立（[]）
  - 贪狼庙 | 火同贪=False 铃同贪=False | 三方硬煞2 羊陀=True 化忌=False 空劫=False 天刑=False | 紫贪=False 廉贪=True
- **clean** | 1941-01-03 04时 | 命亥 | 引擎level=中 breaking=[] | 引擎状态=成立（[]）
  - 贪狼陷 | 火同贪=False 铃同贪=False | 三方硬煞1 羊陀=True 化忌=False 空劫=False 天刑=False | 紫贪=False 廉贪=True
- **breaking(坐空劫)** | 1941-01-01 18时 | 命辰 | 引擎level=中 breaking=['坐空劫'] | 引擎状态=成立（[]）
  - 贪狼庙 | 火同贪=False 铃同贪=False | 三方硬煞0 羊陀=False 化忌=False 空劫=True 天刑=False | 紫贪=False 廉贪=False
- **breaking(坐空劫)** | 1941-01-03 02时 | 命子 | 引擎level=忌 breaking=['坐空劫'] | 引擎状态=破格（['sp-brk-002']）
  - 贪狼庙 | 火同贪=False 铃同贪=False | 三方硬煞0 羊陀=False 化忌=False 空劫=True 天刑=False | 紫贪=False 廉贪=False
## 机月同梁格（命中 2486 盘）
- **clean(上吉)** | 1941-01-02 02时 | 命子 | 引擎level=上吉 breaking=[] | 引擎状态=成立（[]）
  - 贪狼庙 | 火同贪=False 铃同贪=False | 三方硬煞0 羊陀=False 化忌=True 空劫=True 天刑=False | 紫贪=False 廉贪=True
- **clean(上吉)** | 1941-01-03 06时 | 命戌 | 引擎level=上吉 breaking=[] | 引擎状态=成立（[]）
  - 贪狼陷 | 火同贪=False 铃同贪=False | 三方硬煞0 羊陀=False 化忌=True 空劫=True 天刑=False | 紫贪=False 廉贪=True
- **breaking(命坐煞)** | 1941-01-27 04时 | 命子 | 引擎level=中 breaking=['命坐煞'] | 引擎状态=破格（['jy-brk-002']）
  - 贪狼旺 | 火同贪=False 铃同贪=False | 三方硬煞2 羊陀=False 化忌=True 空劫=False 天刑=False | 紫贪=True 廉贪=False
- **breaking(命坐煞)** | 1941-01-27 12时 | 命申 | 引擎level=中 breaking=['命坐煞'] | 引擎状态=破格（['jy-brk-002']）
  - 贪狼庙 | 火同贪=False 铃同贪=False | 三方硬煞2 羊陀=False 化忌=True 空劫=False 天刑=False | 紫贪=False 廉贪=True

## 说明
- 引擎当前不消费破格表：reject 型盘（羊陀与火/铃同宫）引擎仍报火贪格，注入后应剔除，是 diff harness 的现成对照样本
- 引擎火贪/铃贪判定含「会照」分支，教材（陆斌兆/王亭之）口径为同宫庙旺；仅会照盘是潜在误判样本，基线 diff 重点关注
- 构造盘生辰为合成数据，仅供规则验证，禁止当真人命例引用
