# DEPLOY_CHECKLIST — 2026-08-02 发布（隐私隔离 + 反馈鉴权 + 安全分享 + 缓存机制）

> 发布轮次：939530e（链：1e224e2 → a498511 → b168075 → 939530e）
> 用途：部署机逐项勾选，每轮发布可复用。全部勾完才发码。
> HEAD 判定：不写死版本号（清单自身更新会让值漂移，写死必错），以 `git log --oneline -3` 最新一条为准，能对上即拉全。

---

## 0. 拉取

- [ ] `git pull` 一次拉全，对照 `git log --oneline -3` 最新一条（如 3e8a5b8 或更新的 commit），能对上即拉全
- [ ] 确认 `scripts/ziwei_sessions_tool.py` 存在
- [ ] 确认 `.gitignore` 含 `routes/share/` 与 `sessions_archive/`

## 1. 重启 + 缓存版本验证（必要验证：机制在不在）

- [ ] 重启服务
- [ ] 三页 curl 验证静态资源版本参数（注入机制生效）：
  - 报告页：`curl -s https://<域名>/ziwei/report/abc | grep -o 'ziwei-verify.js?v=[^"]*'`
  - 排盘页：`curl -s https://<域名>/ziwei | grep -o 'tier.js?v=[^"]*'`
  - 首页：`curl -s https://<域名>/app | grep -o 'app.js?v=[^"]*'`
- [ ] 判定标准：**版本号存在且每次部署会变**即可，值可能是 git hash、DEPLOY_VERSION 或启动时间戳，均正常。不等于清单里的示例值不代表失败。

## 2. 数据卫生（三段，归档后必须重启）

- [ ] `python3 scripts/ziwei_sessions_tool.py list` 产出 CSV
- [ ] `python3 scripts/ziwei_sessions_tool.py archive --all-unowned` 清无主会话（确认后执行）
- [ ] **假绑定清理**：`--all-unowned` 只清无 user_id 的会话，假绑定（user_id 非空但库里无此用户，如 dev-a/dev-b 隔离测试的假 UUID）会被跳过，成了永久死数据。对比法两步：
  1. 打库里的真实 user_id：`python3 -c "import sqlite3;c=sqlite3.connect('data/users.db');print(*[r[0] for r in c.execute('SELECT id FROM users')], sep='\n')"`
  2. CSV 里 user_id 非空但不在上面列表的即假绑定，逐个圈定归档：`python3 scripts/ziwei_sessions_tool.py archive --sid <sid> <sid> ...`（--sid 需手点名，已绑定会话默认不归档）
- [ ] 归档后**重启服务**（sessions 启动时一次性加载进内存，不重启不生效）

## 3. 自测四项

- [ ] 隔离验证：注册两个小号，互相翻不到对方的盘
- [ ] 分享页走一遍：免登录可打开；署名/CTA 在；看不到登录入口和追问
- [ ] Safari **无痕模式**重验两笔旧账：推算不卡、密码窗不弹（无痕排掉 Safari 自身缓存，防假阳性）
- [ ] 微信间接验证：排盘、开报告页全程不卡不双弹窗（旧 JS 才带那两个毛病）

## 4. 埋点两段式验证

- [ ] 第一段：POST 打一发测试事件，**body 里带显式 device_id**（后端只读 body，不读 X-Device-Id 头）：
  `curl -s -X POST https://<域名>/api/events -H "Content-Type: application/json" -d '{"event":"share_view","device_id":"curl-test"}'`
- [ ] 第二段：带 admin 凭据 GET 读口，确认能读到：
  `curl -s https://<域名>/api/admin/events/stats -H "X-Admin-Token: <token>"`（只看 POST 不算验了读口）
- [ ] 明细过滤验证：`/api/admin/events?event=share_view` 里 `device_id=curl-test` 那条即测试发，真机漏斗可与之区分
- [ ] 匿名访问三层模型（验端点先分清是哪层，别被 404 唬住）：
  - 真实 admin 路由（`/api/admin/events`、`/api/admin/events/stats`）→ 401 `{"error":"unauthorized"}`
  - report 端点（`/api/ziwei/feedback/report`）→ 假 404 裸文本 `Not Found`（伪装，不暴露端点存在）
  - 不存在路由 → 真 404，Flask 默认完整 HTML 页
  - **body 鉴别法**：curl 拉 body 一秒分真假，裸 `Not Found` 是伪装，`<!doctype html>` 是真 404
- [ ] events 清零（服务端无 DELETE 端点，直连 sqlite，只删行不删表）：
  `python3 -c "import sqlite3; c=sqlite3.connect('data/users.db'); c.execute('DELETE FROM events'); c.commit(); print('cleared')"`

## 4b. 观测报告初始化（覆盖率/命中率上线即看，不跑则在线端点一直空）

- [ ] 跑 evaluate 生成 report_cache（默认写到 `data/reports/report_cache.json`，与反馈记录目录分离，无需 --output；在线端点与 previous 对比都读这里）：
  `python3 scripts/evaluate_ziwei_verify.py`
- [ ] 部署机跑完 curl 验证在线端点有数：`curl -s https://<域名>/api/ziwei/feedback/report -H "X-Admin-Token: <token>"`
- [ ] **首跑基线存档**：第一次跑没有 previous 可对比，这份数字就是准确率/覆盖率的历史锚点，单独复制存一份（如 `data/reports/report_cache.baseline.json`），之后每轮对比都拿它当基准

## 4c. 子集互证（反馈侧 ⊆ 事件侧，真机闭环对账）

- [ ] 参考事件选 **report_view**：ziwei-report.html:595 页面加载即发，验盘反馈必然发生在它之后；page_view 前端从不发（纯测试流量），chart_created 在直链/分享进报告页的路径缺失，都不能当参考
- [ ] 事件侧拉集合参数钉死：`?event=report_view&since=<T0 锚点日>&limit=2000`（显式传参，防默认 200 截断；上限 2000，超量仍截断，非万全；since 固定锚点日不移动，窗口只宽不窄）
- [ ] 拉完看 count 是否顶到 2000：顶到 = 截断告警，子集结果先打问号（limit 取最新 N 条，旧事件里的设备会漏，假阴性）
- [ ] 取 events rows 的 `device_id` 去重非空
- [ ] 快照时点：先重跑 evaluate → 拉 report 集合 → 拉事件集合 → 比较（report 侧是全量快照、events 侧实时查询，时点别搞反）
- [ ] 方向：反馈侧 ⊆ 事件侧。测试流量（curl-test 等）天然不在参考集，别拿"两集合相等"当指标
- [ ] 注意 stats 的 today 与 since 均按 UTC 日界（time.gmtime()），本地凌晨 0-8 点的事件归 UTC 前一天

## 5. 真机闭环验收（产品视角，等 King 有空走）

- [ ] 分享者真机：排盘 → 分享 → 复制链接
- [ ] 另一台**没登录**的设备点开分享链接 → 免登录看到盘 → 点 CTA → 落地页 → 注册
- [ ] 该接收设备建议直接用手机微信开，顺带收掉 ?v= 充分性验证（全程不卡不双弹窗）
- [ ] 回 stats 查漏斗三环：share_view → share_cta_click → chart_created 落在**同一 device_id**（接收者设备），串得起来
- [ ] 注意：分享者自己那台产的是 report_share，与漏斗三环不同组，查 stats 别混着对

## 6. ~~旧盘找回~~（已作废：2026-08-03 King 清空历史数据重新上线，此节不再执行）

- [x] ~~部署机先跑 `list` 出 CSV 备着~~
- [x] ~~King 报邮箱 + 圈选范围 → `claim --email <邮箱>`~~
- [x] ~~补完重启 → King 登录验证可见~~

## 7. 发码

- [ ] 以上全部勾完 → 发码
