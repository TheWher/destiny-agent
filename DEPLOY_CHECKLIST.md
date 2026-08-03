# DEPLOY_CHECKLIST — 2026-08-02 发布（隐私隔离 + 反馈鉴权 + 安全分享 + 缓存机制）

> 发布轮次：939530e（链：1e224e2 → a498511 → b168075 → 939530e）
> 当前最新：841d8cb（2026-08-03，验盘反馈关联字段：verify 落 device_id + 覆盖率进 evaluate 管线）
> 用途：部署机逐项勾选，每轮发布可复用。全部勾完才发码。

---

## 0. 拉取

- [ ] `git pull` 一次拉全，HEAD = 841d8cb（清单自带更新，若只到 e1ca0c1 说明拉少了）
- [ ] 确认 `scripts/ziwei_sessions_tool.py` 存在
- [ ] 确认 `.gitignore` 含 `routes/share/` 与 `sessions_archive/`

## 1. 重启 + 缓存版本验证（必要验证：机制在不在）

- [ ] 重启服务
- [ ] 三页 curl 验证静态资源版本参数（注入机制生效）：
  - 报告页：`curl -s https://<域名>/ziwei/report/abc | grep -o 'ziwei-verify.js?v=[^"]*'`
  - 排盘页：`curl -s https://<域名>/ziwei | grep -o 'tier.js?v=[^"]*'`
  - 首页：`curl -s https://<域名>/app | grep -o 'app.js?v=[^"]*'`
- [ ] 判定标准：**版本号存在且每次部署会变**即可，值可能是 git hash、DEPLOY_VERSION 或启动时间戳，均正常。不等于 939530e 不代表失败。

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

## 4b. 观测报告初始化（覆盖率/命中率上线即看，不跑则在线端点一直空）

- [ ] 跑 evaluate 生成 report_cache，**必须 --output 到 feedback/ziwei/ 下的绝对路径**（在线端点与 previous 对比都读这里；默认相对路径会写到 scripts/ 下导致扑空）：
  `python3 scripts/evaluate_ziwei_verify.py --output /绝对路径/feedback/ziwei/report_cache.json`
- [ ] 部署机跑完 curl 验证在线端点有数：`curl -s https://<域名>/api/ziwei/feedback/report -H "X-Admin-Token: <token>"`
- [ ] **首跑基线存档**：第一次跑没有 previous 可对比，这份数字就是准确率/覆盖率的历史锚点，单独复制存一份（如 `feedback/ziwei/report_cache.baseline.json`），之后每轮对比都拿它当基准

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
