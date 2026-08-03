# Changelog

记录对用户或架构有影响的变化。不记录每个 commit。

## 2026-08-03 — 观测报告基线
- **更新** 部署清单补埋点验证知识：匿名三层模型 + 真假 404 body 鉴别法、events 清零方法、子集互证参考事件与参数（report_view + since 锚点日 + limit=2000）
- **重构** 验盘反馈报告读写分离：`report_cache.json` 从 `feedback/ziwei/` 迁至 `data/reports/`（evaluate 默认输出 + 端点读取两端对齐），根治"报告写进扫描目录"自污染
- **新增** 聚合报告 `device_ids` 字段（去重非空设备列表），支持反馈侧与埋点侧设备集合子集互证
- **修复** evaluate 不再依赖手动 `--output`（曾因路径写错导致在线端点读不到报告）

## 2026-07-31 — 账号系统
- **新增** `models/user.py` — PBKDF2 密码哈希 + HMAC-SHA256 JWT（零外部依赖）
- **新增** `routes/auth.py` — 注册/登录/me API
- **新增** 前端登录/注册弹窗（`ziwei.html` 顶部栏）
- **新增** 会话绑定 `user_id`，按用户隔离会话列表
- **修复** `services/ziwei_analysis.py` + `bazi_analysis.py` 缺 `import requests`（重构遗留）
- **修复** `sendChat` 先调 `res.json()` 再检查状态码导致 500 被吞
- **修复** thinking-orbs 动画不动（reducedMotion 冻结 + 圆点太淡 + offscreen 误判）
- **优化** 验盘错误原因「其他」支持自由输入
- **优化** 追问回答用 `formatText()` 渲染 Markdown

## 2026-07-29 — CLI 入口 + 项目记忆基建
- **新增** `cli.py` — 统一命令行入口（测试/分析/验盘报告/会话管理）
- **新增** `docs/adr/` — 5 条架构决策记录
- **新增** `CHANGELOG.md`
- **更新** `AGENTS.md` 加架构状态章节（模块层级 + 数据流 + 技术债）
- **更新** `README.md` 反映当前架构

## 2026-07-25 — 模块化重构
- `app.py` 1942→20 行，拆为 `routes/`(5) + `services/`(5) + `utils/`(6)
- `analysis_service.py` 1531→56 行，变为向后兼容的 re-export shim
- `index.html` 2024→256 行，CSS/JS 外部化到 `static/style.css` + `static/app.js`
- 删除 `knowledge_base/error_patterns.json`、`geju_rules.json`（零引用）
- 脚本统一到 `scripts/`
- **零用户影响**：所有路由 URL 不变

## 2026-07-23 — 紫微验盘闭环
- **新增** 6 级信号优先级表（S ±1年 ~ E ±3年）→ 注入 Agent prompt
- **新增** `stop_sequences=['【验盘完毕】']` 截停验盘阶段
- **新增** 前端逐条确认面板：✓正确 / ✗错误 / △部分对 + 错误原因下拉
- **新增** 反馈保存端点 `/api/ziwei/verify` + 聚合分析脚本 `scripts/evaluate_ziwei_verify.py`
- **新增** 在线报告端点 `/api/ziwei/feedback/report`（ADMIN_TOKEN 保护 + HTML 渲染）
- **新增** 会话磁盘持久化（`sessions/` 目录）+ 报告页会话切换器 + 重命名/删除
- **新增** 报告页复制链接按钮

## 2026-07-21 — 紫微 SSE 流式解读
- 分析从阻塞等待（干等 2-4 分钟）改为 SSE 逐字推送
- **新增** 三点脉冲加载动画 + "深度分析约需 2~4 分钟"提示
- 分析完成后自动平滑滚动到分析区

## 2026-07-20 之前 — 紫微 v8 + 八字验盘
- 紫微 Agent v8：10 步推理链 · 四层四化权重 · 24 格局三列核验 · 破格五层穿透
- 十二长生角标 + 杂曜全量展示 + 飞星标记
- 三层叠盘（大限+流年+流月可叠加）+ 叠盘 AI 分析
- 三合四正连线（hover 高亮）
- 报告页格子三层垂直分区（楷体主星 + 四化色块 + 辅星吉凶）
- 输入页就地渲染 + 确认卡片 5 锚点
- 八字→紫微交叉验证
- 地理编码自动补全 + 真太阳时校正
- 水墨宣纸风全站统一 + 暗色主题
- 输入页历史会话从服务端 API 加载
