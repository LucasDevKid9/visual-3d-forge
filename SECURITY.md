# 安全策略 / Security Policy

## 报告漏洞 / Reporting a vulnerability

请不要开公开 issue。用 GitHub 的 **Private vulnerability reporting**：

<https://github.com/LucasDevKid9/visual-3d-forge/security/advisories/new>

请在报告里写明：受影响的文件或脚本、复现步骤、影响范围。三个工作日内会收到第一次回复。

Please do **not** open a public issue. Use GitHub's private vulnerability reporting
form above, with the affected file, reproduction steps, and impact. You will get a
first response within three business days.

## 本项目的安全边界 / Scope

这个仓库交付的是**静态产物**：一段 HTML、一个 vendor 目录、四个本地脚本。它不运行服务、
不接收请求、不处理用户数据。所以威胁模型很窄，但有三条必须说清楚：

**1. 交付物会被放到别人的机器上双击打开。**
任何进入 `examples/` 或 `assets/scaffold/` 的 HTML 都必须真的零远程请求（D1 档）或只引用
白名单 CDN（D0 档）。`validate_scene.py` 会数每一个 URL，这条不靠自觉。

**2. `vendor/` 是第三方代码。**
这里提交的是 three.js r187 的裁剪产物，逐文件记录了 sha256。任何对 `vendor/` 的手工修改
都会让 `tests/test_contract.py` 的哈希校验失败——这是故意的，不是障碍。升级依赖请走
`scripts/vendor.py`，它会重新生成清单。

**3. 脚本只读本地文件。**
`scripts/*.py` 不发起网络请求、不写仓库外路径、不执行子进程（`--self-test` 除外，
它调用自己）。CI 里有一条断言检查它们只 import 标准库。

不在范围内：three.js 上游自身的渲染缺陷、浏览器 WebGL 实现的差异、用户在产物里自行加入的
第三方脚本。

## 支持版本 / Supported versions

只有最新 tag 会收到修复。这是一个人维护的仓库，不做多分支回补。
