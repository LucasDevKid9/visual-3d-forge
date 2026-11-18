#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""demo 产物门卫：单文件、无 CDN、无外链脚本。

demo/index.html 是压缩后的交付产物（源码不随仓库分发），静态扫描器会把它
误判成「未识别形态」并给出 E02/E06/E07 三条假失败 —— 那是压缩器把 three 库
和业务代码揉在一起的结果，不是页面真的有问题。所以这里不复用
validate_scene.py，只钉住三条真的会伤到访客的硬约束。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo" / "index.html"
FORBIDDEN = ("cdn.jsdelivr", "unpkg.com", "cdnjs.cloudflare.com", "bootcdn", "staticfile.org")


def main() -> int:
    if not DEMO.is_file():
        print("缺少 demo/index.html", file=sys.stderr)
        return 1
    html = DEMO.read_text(encoding="utf-8", errors="replace")

    bad = [p for p in FORBIDDEN if p in html]
    if bad:
        print(f"demo 引用了禁用 CDN：{bad}", file=sys.stderr)
        return 1

    # 外部脚本必须为零：单文件的全部意义就在于双击即开
    ext_scripts = re.findall(r'<script[^>]+src\s*=\s*["\'](https?:)?//', html, re.I)
    if ext_scripts:
        print(f"demo 引用了外部脚本 {len(ext_scripts)} 个", file=sys.stderr)
        return 1

    # 允许的唯一外链是字体（断网时 font-family 回退，不影响渲染）
    external = sorted(set(re.findall(r'https?://[^\s"\'<>)]+', html)))
    allowed_prefix = ("http://www.w3.org/", "https://discourse.threejs.org/",
                      "https://fonts.googleapis.com", "https://fonts.gstatic.com/")
    remote = [u for u in external if not u.startswith(allowed_prefix)]
    if remote:
        print(f"demo 存在未登记的外部地址：{remote[:5]}", file=sys.stderr)
        return 1

    print(f"demo 门卫通过：{len(html.encode()) / 1024:.0f} KB 单文件，无 CDN，"
          f"外部地址仅字体 {len(external)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
