# ADR-005: 为什么用 PythonAnywhere 部署

**日期**: 2026-07-29  
**状态**: 已采纳 (Accepted)

## 背景

项目需要公网可访问的 Flask 应用。目标用户规模小（个人使用 + 少量访客），预算极低。

## 决策

使用 PythonAnywhere 免费账户，Flask 通过 WSGI 部署。

## 代价

- 唯一可靠重启方式：Disable → 等几秒 → Enable（Reload 不够）
- Python 版本不一致：WSGI 用 3.11，Bash 默认 3.13，pip install 必须用 `python3.11 -m pip --user`
- 免费账户无环境变量 UI，API Key 需通过 `config.local.py` 手动上传
- 外网 CDN 被拦截（`cdn.jsdelivr.net`），所有静态资源必须本地化
- GitHub 偶尔 DNS 污染，需要用代理
- 进程重启后限流计数器清零

## 为什么不

- **Render**：有 `render.yaml` 备用配置，支持环境变量。但免费层有冷启动延迟（~30s），不适合需保持连接的分析场景
- **自建 VPS**：需要运维能力（安全更新、Nginx 配置、SSL 证书），月度成本高于免费方案
- **Vercel/Netlify**：适合静态前端，不适合 Flask 后端。需要额外后端服务，增加架构复杂度

## 未来方向

如果用户量增长到需要稳定运行环境（无冷启动、支持环境变量、不限流），迁移到 Render 或 Railway 的付费层。
