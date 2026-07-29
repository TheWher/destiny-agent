# ADR-004: 为什么用 SSE 而非 WebSocket

**日期**: 2026-07-29  
**状态**: 已采纳 (Accepted)

## 背景

AI 分析耗时 2-4 分钟。用户需要实时看到分析进展（验盘阶段逐句呈现、正式分析逐段输出），不能干等。

## 决策

使用 SSE (Server-Sent Events)，通过 `text/event-stream` MIME 类型 + `ReadableStream` 前端消费。

## 代价

- 单向推送（服务端 → 客户端），前端无法在流中发消息
- 多轮对话的"用户追问"需要开新的请求，无法复用连接
- 浏览器对同域名 SSE 连接数有限制（通常 6 个）

## 为什么不

- **WebSocket**：分析场景是单向推送，不需要双向通信。WebSocket 需要协议升级（HTTP → WS），在 PythonAnywhere 免费账户上可能有兼容性问题
- **Polling**：2-4 分钟的等待如果靠轮询，要么延迟高（轮询间隔长），要么浪费请求（轮询间隔短）
- **Server-Side Rendering + 全量返回**：看起来最简单，但 4 分钟的白屏体验不可接受

## 技术细节

- 验盘阶段使用**非流式** + `stop_sequences` 截停：验盘需要精确控制在【验盘完毕】处停止，非流式可以配合 Anthropic 的 stop_sequences 参数
- 正式分析使用**流式 SSE**：token-by-token 推送，前端实时显示
- 前端通过 `ReadableStream` + `TextDecoder` 解析 SSE 事件流，不依赖 `EventSource`（因为需要 POST 请求）
