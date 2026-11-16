---
name: scrapling-fetch
description: 用加固版 Scrapling 抓取公开网页（静态或隐身浏览器、可选 Cloudflare 过盾）。需要抓页面、提取列表、对付简单反爬时用；只允许 http/https。
---
# scrapling-fetch（加固版 Scrapling 抓取模板）

## 前提
- 仓库：/workspace/scrapling-skill（D4Vinci/Scrapling @95cf901 + 加固补丁），venv：`.venv`。
- 隐身模式需浏览器：先人工确认后执行 `.venv/bin/scrapling install`（会下载 Playwright 浏览器，不要用 curl|sh）。

## 用法
```bash
PY=/workspace/scrapling-skill/.venv/bin/python
W=/workspace/scrapling-skill/.cursor/skills/scrapling-fetch/fetch.py
$PY $W https://quotes.toscrape.com --css ".quote .text"          # 静态
$PY $W https://example.com --mode stealth --solve-cloudflare      # 隐身 + 过盾校验
```
输出 JSON：`ok/status/results` 或 `text_head`；失败 `{"ok":false,"error":...}`，退出码 2=被安全限制拦截/过盾失败，1=HTTP≥400。

## 安全限制（已在库内强制）
1. URL 只允许 http/https 且必须有主机名；file://、ftp://、data:、javascript: 等直接 ValueError（`scrapling/core/url_safety.py`，上游 PR #542 合并前保留）。
2. 隐身浏览器不再忽略 HTTPS 证书错误（`ignore_https_errors=False`）。
3. Cloudflare 过盾后校验：最终页仍含 challenge 标记或状态码 ≥400 → 抛 `CloudflareChallengeNotSolved`，不会假报成功。
- 遵守 robots.txt 与站点条款，控制频率；不抓需登录/个人数据页面；不启用远程 MCP 服务，除非辉确认。

## 示例：杭州房源采集底座
对列表页用 `--css` 取卡片字段，多页循环时每页间隔 ≥2s；被 Cloudflare 拦时加 `--mode stealth --solve-cloudflare`，失败即停，不要重试轰炸。
