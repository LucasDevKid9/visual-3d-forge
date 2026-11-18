#!/usr/bin/env python3
"""把 HTML 场景封装成 MHTML(.mht) 单文件归档。

用途：交付一个可被邮件客户端、文档系统、旧版浏览器当作「单个附件」处理的网页归档。

重要边界（务必先读）：
  MHTML 是【归档容器】，不是【应用运行时】。
  - 静态资源（图片 / CSS / 字体 / SVG）经 cid: 重写后可以正常显示。
  - ES Module（<script type="module"> + import）在多数浏览器打开 .mht 时无法执行，
    因为 cid: 不提供模块解析所需的 base URL。
  - 因此：需要「能跑」的交付物，用 standalone HTML；需要「能存」的交付物，用 MHT。

用法：
  python3 export_mht.py scene.html                      # 输出 scene.mht
  python3 export_mht.py scene.html -o out.mht
  python3 export_mht.py scene.html --no-inline          # 只包装 HTML，不收集本地资源
  python3 export_mht.py scene.html --json               # 机器可读报告
"""

import argparse
import base64
import json
import mimetypes
import re
import sys
import uuid
from pathlib import Path

CRLF = "\r\n"

# 只重写这些引用；script 的 src 也收集，但会在报告里标注风险
REF_RE = re.compile(
    r"""(?P<attr>\b(?:src|href|poster|data-src)\s*=\s*)(?P<q>["'])(?P<url>[^"']+)(?P=q)""",
    re.IGNORECASE,
)
SKIP_PREFIX = ("http://", "https://", "//", "data:", "cid:", "#", "mailto:", "javascript:", "blob:")


def is_local(url: str) -> bool:
    u = url.strip()
    if not u or u.startswith(SKIP_PREFIX):
        return False
    return True


def collect_refs(html: str, base_dir: Path):
    """返回 [(原始 url, 绝对路径)]，保持出现顺序去重。"""
    seen, out = set(), []
    for m in REF_RE.finditer(html):
        url = m.group("url").strip()
        if not is_local(url):
            continue
        clean = url.split("?")[0].split("#")[0]
        p = (base_dir / clean).resolve()
        if not p.is_file():
            continue
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append((url, p))
    return out


IMPORTMAP_RE = re.compile(
    r'<script[^>]*type=["\']importmap["\'][^>]*>(.*?)</script>', re.IGNORECASE | re.DOTALL
)


def collect_module_refs(html: str):
    """importmap 里的本地模块路径。这些在 MHTML 中无法解析，只报告、不改写。"""
    refs = []
    for m in IMPORTMAP_RE.finditer(html):
        try:
            spec = json.loads(m.group(1))
        except Exception:
            continue
        for alias, target in (spec.get("imports") or {}).items():
            if isinstance(target, str) and is_local(target):
                refs.append({"alias": alias, "target": target})
    return refs


def part_bytes(content_type: str, cid: str | None, payload: bytes) -> bytes:
    head = [f"Content-Type: {content_type}"]
    if cid:
        head.append(f"Content-ID: <{cid}>")
        head.append(f"Content-Location: cid:{cid}")
    head.append("Content-Transfer-Encoding: base64")
    head.append("")
    body = base64.encodebytes(payload).decode("ascii").replace("\n", CRLF)
    return (CRLF.join(head) + CRLF + body).encode("utf-8")


def build(html_path: Path, out_path: Path, inline: bool = True):
    html_path = html_path.resolve()
    raw = html_path.read_text(encoding="utf-8", errors="replace")
    base_dir = html_path.parent
    boundary = "----MultipartBoundary--" + uuid.uuid4().hex + "----"

    assets, missing, risk = [], [], []
    mod_refs = collect_module_refs(raw)
    if inline:
        for url, p in collect_refs(raw, base_dir):
            cid = f"{p.name}@{uuid.uuid5(uuid.NAMESPACE_URL, str(p)).hex[:12]}.forge"
            mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            if p.suffix in (".js", ".mjs"):
                mime = "text/javascript"
                risk.append(p.name)
            elif p.suffix == ".css":
                mime = "text/css"
            elif p.suffix == ".svg":
                mime = "image/svg+xml"
            assets.append((cid, mime, p.read_bytes(), p.name))
            raw = raw.replace(url, f"cid:{cid}")

    # 检查仍残留的相对引用（无法内联的资源）
    for m in REF_RE.finditer(raw):
        u = m.group("url").strip()
        if is_local(u) and not u.startswith("cid:"):
            missing.append(u)

    html_part = part_bytes('text/html; charset="utf-8"', None, raw.encode("utf-8"))

    chunks = [
        f"From: <Saved by visual-3d-forge>".encode(),
        f"Snapshot-Content-Location: {html_path.as_uri()}".encode(),
        f"Subject: {html_path.stem}".encode(),
        b"MIME-Version: 1.0",
        f'Content-Type: multipart/related; type="text/html"; boundary="{boundary}"'.encode(),
        b"",
        f"--{boundary}".encode(),
        html_part,
    ]
    for cid, mime, data, _name in assets:
        chunks.append(f"--{boundary}".encode())
        chunks.append(part_bytes(mime, cid, data))
    chunks.append(f"--{boundary}--".encode())
    chunks.append(b"")

    out = CRLF.encode().join(
        c.replace(b"\r\n", b"\n").replace(b"\n", CRLF.encode()) for c in chunks
    )
    out_path.write_bytes(out)

    return {
        "output": str(out_path),
        "size": out_path.stat().st_size,
        "parts": 1 + len(assets),
        "assets": [{"name": n, "mime": m, "bytes": len(d)} for _, m, d, n in assets],
        "unresolved_refs": sorted(set(missing)),
        "script_assets": sorted(set(risk)),
        "module_refs": mod_refs,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="把 HTML 场景封装为 MHTML 单文件归档")
    ap.add_argument("input", help="输入 HTML 文件")
    ap.add_argument("-o", "--output", help="输出 .mht 路径")
    ap.add_argument("--no-inline", action="store_true", help="不收集本地资源，只包装 HTML")
    ap.add_argument("--json", action="store_true", help="输出 JSON 报告")
    a = ap.parse_args()

    src = Path(a.input)
    if not src.is_file():
        print(f"[FAIL] 找不到文件: {src}", file=sys.stderr)
        return 2
    dst = Path(a.output) if a.output else src.with_suffix(".mht")

    rep = build(src, dst, inline=not a.no_inline)

    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0

    print(f"[OK] {rep['output']}")
    print(f"     部件 {rep['parts']} 个 · {rep['size'] / 1024:.1f} KB")
    if rep["assets"]:
        print("     内联资源:")
        for x in rep["assets"][:20]:
            print(f"       - {x['name']:<28} {x['mime']:<24} {x['bytes']/1024:>7.1f} KB")
    if rep["script_assets"]:
        print(f"[WARN] 含 {len(rep['script_assets'])} 个 JS 资源：MHTML 打开时 ES Module 通常无法执行，")
        print("       此归档适合「留存/传阅」，不适合「运行」。要可运行请交付 standalone HTML。")
    if rep["module_refs"]:
        print(f"[WARN] importmap 含 {len(rep['module_refs'])} 条本地模块映射，MHTML 中无法解析：")
        for x in rep["module_refs"][:6]:
            print(f"       - {x['alias']} -> {x['target']}")
    if rep["unresolved_refs"]:
        print(f"[WARN] {len(rep['unresolved_refs'])} 个相对引用未内联（文件不存在或为动态路径）:")
        for u in rep["unresolved_refs"][:10]:
            print(f"       - {u}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
