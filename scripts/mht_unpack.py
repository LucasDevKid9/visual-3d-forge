#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visual-3d-forge / mht_unpack.py
把 .mht / .mhtml 网页快照拆成可读的 HTML + 资源目录。

为什么需要它
------------
MHTML（RFC 2557）是 Chrome「另存为单个文件」的产物：一个 multipart/related
容器，把 DOM、CSS、SVG、图片按原始字节塞在一起。扩展名通常是 .mht。

它有两个必须先说清楚的性质，否则会误用它：

1. **它是文档存档，不是可运行应用。**
   浏览器打开 .mht 时只还原文档，脚本在多数环境下被沙箱挡住
   （Chrome 从 file:// 打开会直接报 "frame is sandboxed and the
   'allow-scripts' permission is not set"）。所以别把它当成交付形态——
   一个三维页面存成 .mht 只会变成一张不会动的图。

2. **它常常缺件。** 存盘时正在加载的模块脚本、字体、贴图未必被收进去。
   实测一个 2 MB 的 bundle.js 就完全不在分段的名单里。

那它有什么用？——当**参考素材**。别人发来一个「就是这种质感」的网页，
你手上只有 .mht。这个脚本把它拆开，让你能读 DOM、取配色、扒 SVG 轮廓，
喂给 SKILL.md 的 G2 参考闸，而不是对着截图猜。

用法
----
    python3 mht_unpack.py <文件.mht> [--out 目录] [--quiet]
    python3 mht_unpack.py <文件.mht> --report      # 只打印清单，不落盘

输出
----
    <out>/index.html          主文档，cid: 引用已改写成相对路径
    <out>/_assets/...         其余分段按 Content-Location 的路径还原
    <out>/MANIFEST.json       分段清单：类型 / 大小 / 原地址 / 缺件推断

退出码：0 成功（可含警告）；1 输入不是 MHTML；2 文件不可读。
只用标准库。
"""

from __future__ import annotations

import argparse
import base64
import email
import json
import re
import sys
from pathlib import Path

# 存盘时不会被收进 MHT 的东西：用来推断「这页缺什么」
ASSET_EXT = {
    ".js": "脚本", ".mjs": "脚本",
    ".woff": "字体", ".woff2": "字体", ".ttf": "字体", ".otf": "字体",
    ".jpg": "贴图", ".jpeg": "贴图", ".png": "贴图", ".webp": "贴图", ".ktx2": "贴图",
    ".hdr": "环境贴图", ".exr": "环境贴图",
    ".glb": "模型", ".gltf": "模型", ".obj": "模型", ".dae": "模型", ".fbx": "模型",
    ".mp3": "音频", ".ogg": "音频", ".wav": "音频", ".m4a": "音频", ".aac": "音频",
    ".mp4": "视频", ".webm": "视频",
    ".wasm": "解码器", ".bin": "数据",
}

REF_ATTR = re.compile(
    r"""\b(src|href|data|poster|srcset)\s*=\s*(["'])([^"']+)\2""", re.I)


def die(msg: str, code: int = 2) -> None:
    print(f"[mht] {msg}", file=sys.stderr)
    sys.exit(code)


def safe_name(loc: str, ctype: str, idx: int) -> str:
    """把 Content-Location 变成一个安全的相对路径。"""
    if loc.startswith("cid:"):
        ext = {
            "text/css": ".css", "image/svg+xml": ".svg", "text/html": ".html",
            "text/javascript": ".js", "application/javascript": ".js",
        }.get(ctype, f".{ctype.split('/')[-1].split('+')[0]}")
        return f"_assets/inline-{idx}{ext}"
    # https://host/a/b/c.svg → a/b/c.svg
    raw_path = re.sub(r"^[a-z]+://[^/]+/", "", loc, flags=re.I)
    was_dir = raw_path.endswith("/") or not raw_path
    path = raw_path.split("?")[0].split("#")[0].strip("/")
    if was_dir or not path:
        # 目录地址（首页）→ index.html；其它类型的目录地址兜底成带序号的默认名
        path = (path + "/" if path else "") + ("index.html" if ctype == "text/html" else f"index-{idx}")
    elif not Path(path).suffix:
        # 没有扩展名又不像目录 → 按类型补后缀，避免与同名的目录冲突
        path += {"text/html": ".html", "text/css": ".css", "image/svg+xml": ".svg"}.get(ctype, f".{ctype.split('/')[-1]}")
    return "_assets/" + path


def decode_part(part) -> bytes:
    raw = part.get_payload(decode=True)
    if raw is None:
        return b""
    return raw


def main() -> int:
    ap = argparse.ArgumentParser(description="拆开 MHT 网页快照")
    ap.add_argument("file", help=".mht / .mhtml 文件")
    ap.add_argument("--out", help="输出目录（默认与文件同名）")
    ap.add_argument("--report", action="store_true", help="只打印清单，不写文件")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.is_file():
        print(f"[mht] 读不到文件：{path}", file=sys.stderr)
        return 2

    raw = path.read_bytes()
    msg = email.message_from_bytes(raw)
    if not msg.is_multipart():
        print("[mht] 不是 MHTML：缺少 multipart 结构。"
              "（普通 .html 请直接读，不需要这个脚本）", file=sys.stderr)
        return 1

    parts = [p for p in msg.walk() if not p.is_multipart()]
    if not parts:
        print("[mht] MHTML 里没有任何分段", file=sys.stderr)
        return 1

    out = Path(args.out) if args.out else path.with_suffix("")
    mapping: dict[str, str] = {}     # 原地址 → 落盘相对路径
    manifest: list[dict] = []

    html_idx = None
    for i, part in enumerate(parts):
        ctype = part.get_content_type()
        loc = part.get("Content-Location") or part.get("Content-ID", "").strip("<>")
        body = decode_part(part)
        # 主文档固定落在根 index.html：它是要读的那个文件，不该埋进资源目录
        if ctype == "text/html" and html_idx is None:
            html_idx = i
            name = "index.html"
        else:
            name = safe_name(loc, ctype, i)
        mapping[loc] = name
        if loc.startswith("cid:"):
            mapping[loc] = name
        manifest.append({
            "part": i, "type": ctype, "bytes": len(body),
            "location": loc, "saved_as": name,
        })

    # 主文档
    html_part = next((p for p in parts if p.get_content_type() == "text/html"), None)
    if html_part is None:
        print("[mht] 找不到 text/html 分段", file=sys.stderr)
        return 1
    html = decode_part(html_part).decode("utf-8", "replace")

    # cid: 引用改成相对路径
    def fix(m: re.Match) -> str:
        attr, q, url = m.group(1), m.group(2), m.group(3)
        key = url if url.startswith("cid:") else url
        if key in mapping:
            rel = mapping[key]
            # 主文档在根、资源在 _assets/，所以保留 _assets/ 前缀才是对的相对路径
            return f"{attr}={q}{rel}{q}"
        return m.group(0)

    html_fixed = REF_ATTR.sub(fix, html)

    # 缺件推断：文档（含 CSS）里引用了、但分段里没被收进去的资源。
    # 必须扫 CSS —— 字体和贴图是从 @font-face / background 的 url() 引用的，
    # 只看 HTML 的 src/href 会漏掉整类素材。
    css_text = "\n".join(
        decode_part(p).decode("utf-8", "replace")
        for p in parts if p.get_content_type() == "text/css")
    referenced: set[tuple[str, str]] = set()
    for blob in (html, css_text):
        urls = [m.group(3) for m in REF_ATTR.finditer(blob)]
        urls += re.findall(r"""url\(\s*["']?([^"')\s]+)""", blob, re.I)
        for u in urls:
            if u.startswith(("data:", "#", "mailto:", "javascript:", "cid:")):
                continue
            ext = Path(u.split("?")[0]).suffix.lower()
            if ext in ASSET_EXT:
                referenced.add((ASSET_EXT[ext], ext))
    have_ext = {Path(m["saved_as"]).suffix.lower() for m in manifest}
    missing = sorted({(kind, ext) for kind, ext in referenced if ext not in have_ext})

    stats = {
        "source": msg.get("Snapshot-Content-Location"),
        "subject": msg.get("Subject"),
        "saved_by": msg.get("From"),
        "parts": len(parts),
        "scripts_in_html": len(re.findall(r"<script\b", html, re.I)),
        "canvas_in_html": len(re.findall(r"<canvas\b", html, re.I)),
        "missing_kinds": [f"{k}（{e}）" for k, e in missing],
        "manifest": manifest,
    }

    if not args.quiet or args.report:
        print(f"\n=== MHT 拆包 · {path.name} ===")
        print(f"  来源：{stats['source'] or '(未记录)'}")
        print(f"  标题：{stats['subject'] or '(无)'}")
        print(f"  分段：{len(parts)} 个")
        for m in manifest:
            print(f"    [{m['part']:>2}] {m['type']:<18} {m['bytes']:>7d} B  {m['location'][:66]}")
        print(f"  主文档内 <script>：{stats['scripts_in_html']} 个"
              f"　<canvas>：{stats['canvas_in_html']} 个")
        if missing:
            print(f"  缺件推断：{'、'.join(stats['missing_kinds'])}"
                  f" —— 存盘时没被收进容器")
        if stats["scripts_in_html"] == 0:
            print("  ⚠ 主文档里没有任何脚本：这份快照不能执行，只能当参考素材读")
        print()

    if args.report:
        return 0

    out.mkdir(parents=True, exist_ok=True)
    (out / "_assets").mkdir(exist_ok=True)
    for i, (m, part) in enumerate(zip(manifest, parts)):
        if i == html_idx:
            continue          # 主文档单独写（已改写 cid: 引用）
        target = out / m["saved_as"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(decode_part(part))
    (out / "index.html").write_text(html_fixed, encoding="utf-8")
    (out / "MANIFEST.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not args.quiet:
        total = sum(m["bytes"] for m in manifest)
        print(f"  已写出：{out}/index.html + _assets/（{len(manifest)} 个分段，{total/1024:.0f} KB）")
        print(f"  清单：{out}/MANIFEST.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
