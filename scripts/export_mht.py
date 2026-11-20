#!/usr/bin/env python3
"""把 HTML 封装成 MHTML(.mht) 单文件归档。

边界（先读，能省一次返工）：
  MHTML 是【只读档案容器】，不是【运行时】。
  - 实测（Linux Chromium）：.mht 能打开，样式 / SVG / 图片正常渲染，
    但【普通 script 与 module script 都不执行】，页面停在首帧外壳。
  - 所以归档只能承担「长什么样」，承担不了「能跑」。
  - 要可运行 → 先跑 build_standalone.py 出 standalone HTML。
  - 要可读的归档 → 用 --poster 预烘一张首帧，做成「图 + 规格 + 玩法」的档案版。

用法：
  python3 export_mht.py scene.html                       # 输出 scene.mht
  python3 export_mht.py scene.html -o out.mht
  python3 export_mht.py scene.html --poster shot.png --caption "首帧：雨中整车视图"
  python3 export_mht.py scene.html --no-inline           # 只包装 HTML，不收集本地资源
  python3 export_mht.py scene.html --verify              # 打包后回读校验
  python3 export_mht.py scene.html --json                # 机器可读报告

退出码：0 成功；2 参数/文件错误；3 回读校验失败。
"""

import argparse
import base64
import email
import email.utils
import hashlib
import json
import mimetypes
import re
import sys
import uuid
from pathlib import Path

CRLF = "\r\n"

REF_RE = re.compile(
    r"""(?P<attr>\b(?:src|href|poster|data-src)\s*=\s*)(?P<q>["'])(?P<url>[^"']+)(?P=q)""",
    re.IGNORECASE,
)
SKIP_PREFIX = ("http://", "https://", "//", "data:", "cid:", "#", "mailto:", "javascript:", "blob:")

IMPORTMAP_RE = re.compile(
    r'<script[^>]*type=["\']importmap["\'][^>]*>(.*?)</script>', re.IGNORECASE | re.DOTALL
)
BODY_RE = re.compile(r"<body[^>]*>", re.IGNORECASE)


def is_local(url: str) -> bool:
    u = url.strip()
    return bool(u) and not u.startswith(SKIP_PREFIX)


def collect_refs(html: str, base_dir: Path):
    """返回 [(原始 url, 绝对路径)]，去重且保持出现顺序。"""
    seen, out = set(), []
    for m in REF_RE.finditer(html):
        url = m.group("url").strip()
        if not is_local(url):
            continue
        clean = url.split("?")[0].split("#")[0]
        p = (base_dir / clean).resolve()
        if not p.is_file():
            continue
        if str(p) in seen:
            continue
        seen.add(str(p))
        out.append((url, p))
    return out


def collect_module_refs(html: str):
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


def part_bytes(content_type: str, payload: bytes, cid: str | None = None) -> bytes:
    head = [f"Content-Type: {content_type}"]
    if cid:
        head.append(f"Content-ID: <{cid}>")
        head.append(f"Content-Location: cid:{cid}")
    head.append("Content-Transfer-Encoding: base64")
    head.append("")
    body = base64.encodebytes(payload).decode("ascii").replace("\n", CRLF)
    return (CRLF.join(head) + CRLF + body).encode("utf-8")


def insert_poster(html: str, caption: str) -> str:
    """在 <body> 之后插一张带说明的首帧图，引用 cid:poster。"""
    block = (
        '<figure class="mht-poster" style="margin:24px auto;max-width:960px;text-align:center">'
        '<img src="cid:poster@visual-3d-forge" alt="preview" '
        'style="width:100%;height:auto;display:block;border-radius:6px">'
        f'<figcaption style="font:12px/1.6 ui-monospace,Menlo,Consolas,monospace;'
        f'opacity:.72;margin-top:8px">{caption}</figcaption></figure>'
    )
    m = BODY_RE.search(html)
    if not m:
        return block + html
    return html[: m.end()] + block + html[m.end():]


def build(html_path: Path, out_path: Path, inline: bool = True,
          poster: Path | None = None, caption: str = "", subject: str | None = None):
    html_path = Path(html_path).resolve()
    raw = html_path.read_text(encoding="utf-8", errors="replace")
    base_dir = html_path.parent
    boundary = "----MultipartBoundary--" + uuid.uuid4().hex + "----"

    assets, missing, risk = [], [], []
    mod_refs = collect_module_refs(raw)
    seen_digest = {}

    if poster:
        cid = "poster@visual-3d-forge"
        data = Path(poster).read_bytes()
        assets.append((cid, mimetypes.guess_type(str(poster))[0] or "image/png", data, Path(poster).name))
        seen_digest[hashlib.sha1(data).hexdigest()] = cid
        raw = insert_poster(raw, caption or Path(poster).name)

    if inline:
        for url, p in collect_refs(raw, base_dir):
            data = p.read_bytes()
            digest = hashlib.sha1(data).hexdigest()
            if digest in seen_digest:                      # 同一份资源出现两次 → 复用 cid
                raw = raw.replace(url, f"cid:{seen_digest[digest]}")
                continue
            cid = f"{p.name}@{digest[:12]}.forge"
            mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            if p.suffix in (".js", ".mjs"):
                mime = "text/javascript"
                risk.append(p.name)
            elif p.suffix == ".css":
                mime = "text/css"
            elif p.suffix == ".svg":
                mime = "image/svg+xml"
            assets.append((cid, mime, data, p.name))
            seen_digest[digest] = cid
            raw = raw.replace(url, f"cid:{cid}")

    for m in REF_RE.finditer(raw):
        u = m.group("url").strip()
        if is_local(u) and not u.startswith("cid:"):
            missing.append(u)

    chunks = [
        b"From: <Saved by visual-3d-forge>",
        f"Snapshot-Content-Location: {html_path.as_uri()}".encode(),
        f"Subject: {subject or html_path.stem}".encode(),
        b"MIME-Version: 1.0",
        ("Date: " + email.utils.formatdate(localtime=True)).encode(),
        f'Content-Type: multipart/related; type="text/html"; boundary="{boundary}"'.encode(),
        b"",
        f"--{boundary}".encode(),
        part_bytes('text/html; charset="utf-8"', raw.encode("utf-8")),
    ]
    for cid, mime, data, _name in assets:
        chunks.append(f"--{boundary}".encode())
        chunks.append(part_bytes(mime, data, cid))
    chunks.append(f"--{boundary}--".encode())
    chunks.append(b"")

    out = CRLF.encode().join(c.replace(b"\r\n", b"\n").replace(b"\n", CRLF.encode()) for c in chunks)
    Path(out_path).write_bytes(out)

    return {
        "output": str(out_path),
        "size": Path(out_path).stat().st_size,
        "boundary": boundary,
        "parts": 1 + len(assets),
        "assets": [{"name": n, "mime": m, "bytes": len(d)} for _, m, d, n in assets],
        "unresolved_refs": sorted(set(missing)),
        "script_assets": sorted(set(risk)),
        "module_refs": mod_refs,
        "poster": bool(poster),
    }


def verify(mht_path: Path):
    """回读校验：part 数、正文存在、每个 cid 引用都有对应 part。"""
    msg = email.message_from_bytes(Path(mht_path).read_bytes())
    if not msg.is_multipart():
        return {"ok": False, "reason": "顶层不是 multipart/related"}
    html, cids = None, set()
    for p in msg.get_payload():
        cid = (p.get("Content-ID") or "").strip("<>")
        if cid:
            cids.add(cid)
        if p.get_content_type() == "text/html" and html is None:
            html = p.get_payload(decode=True) or b""
    if not html:
        return {"ok": False, "reason": "没有 text/html part"}
    used = set(re.findall(r'cid:([^"\'\s)]+)', html.decode("utf-8", "replace")))
    return {
        "ok": not (used - cids),
        "parts": len(msg.get_payload()),
        "cids": len(cids),
        "dangling_cids": sorted(used - cids),
        "unused_parts": sorted(cids - used),
        "html_bytes": len(html),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="把 HTML 封装为 MHTML 单文件归档")
    ap.add_argument("input", help="输入 HTML 文件")
    ap.add_argument("-o", "--output", help="输出 .mht 路径")
    ap.add_argument("--no-inline", action="store_true", help="不收集本地资源，只包装 HTML")
    ap.add_argument("--poster", help="档案版首帧图（png/jpg），插入正文顶部")
    ap.add_argument("--caption", default="", help="首帧图说明文字")
    ap.add_argument("--subject", help="归档主题（默认用文件名）")
    ap.add_argument("--verify", action="store_true", help="打包后回读校验")
    ap.add_argument("--json", action="store_true", help="输出 JSON 报告")
    a = ap.parse_args()

    src = Path(a.input)
    if not src.is_file():
        print(f"[FAIL] 找不到文件: {src}", file=sys.stderr)
        return 2
    poster = Path(a.poster) if a.poster else None
    if poster and not poster.is_file():
        print(f"[FAIL] 找不到首帧图: {poster}", file=sys.stderr)
        return 2
    dst = Path(a.output) if a.output else src.with_suffix(".mht")

    rep = build(src, dst, inline=not a.no_inline, poster=poster, caption=a.caption, subject=a.subject)
    chk = verify(dst) if a.verify else None

    if a.json:
        print(json.dumps({**rep, "verify": chk}, ensure_ascii=False, indent=2))
        return 0 if (chk is None or chk["ok"]) else 3

    print(f"[OK] {rep['output']}")
    print(f"     部件 {rep['parts']} 个 · {rep['size'] / 1024:.1f} KB")
    for x in rep["assets"][:20]:
        print(f"       - {x['name']:<30} {x['mime']:<26} {x['bytes'] / 1024:>7.1f} KB")
    if rep["script_assets"]:
        print(f"[WARN] 含 {len(rep['script_assets'])} 个 JS 资源：归档打开时脚本通常不执行，只作留档。")
    if rep["module_refs"]:
        print(f"[WARN] importmap 含 {len(rep['module_refs'])} 条本地模块映射，归档中无法解析。")
    if rep["unresolved_refs"]:
        print(f"[WARN] {len(rep['unresolved_refs'])} 个相对引用未内联：")
        for u in rep["unresolved_refs"][:10]:
            print(f"       - {u}")
    if chk:
        print(f"[VERIFY] parts={chk['parts']} cids={chk['cids']} "
              f"dangling={len(chk['dangling_cids'])} unused={len(chk['unused_parts'])} "
              f"html={chk['html_bytes'] / 1024:.1f}KB -> {'PASS' if chk['ok'] else 'FAIL'}")
        if not chk["ok"]:
            return 3
    print("[NOTE] 归档只能带「长什么样」，带不走「能跑」。可运行版请交付 standalone HTML。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
