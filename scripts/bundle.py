#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visual-3d-forge / bundle.py
单文件离线打包：把 HTML + vendor 目录压成一个零外部依赖的 .html。

为什么需要它
------------
交付场景经常要求"双击就能开、断网也能跑、发邮件也不丢"。
CDN 方案做不到（内网 / 断网 / 域名被墙即白屏），多文件方案也做不到（少一个文件就废）。
本脚本把每个 ES 模块转成 data:text/javascript;base64 写回 importmap，
浏览器原生支持 data URL 作为模块源，因此不需要打包器、不需要构建工具。

关键实现：相对依赖必须一起内联
------------------------------
three.module.js 内部有 `import ... from './three.core.js'`。
data URL 模块没有目录概念，相对 import 会直接解析失败。
所以本脚本会递归收集每个模块的相对依赖，给它们分配内部 specifier
（vf-int-N）写进 importmap，并把模块内的 './x.js' 改写成该 specifier。
漏掉这一步的典型症状：页面白屏，控制台报 "Failed to resolve module specifier"。

用法
----
    python3 bundle.py --src scene.html --out scene.offline.html
    python3 bundle.py --src scene.html --out scene.offline.html --report
    python3 bundle.py --self-test

限制
----
· 只处理 <script type="importmap"> 声明的映射；绝对 URL 引入的模块不会被内联。
· base64 使体积增大约 33%（three 核心约 2.1MB → 约 2.8MB），这是"零依赖"的代价。
· web worker 内的 import、fetch 本地资源、字体文件不在覆盖范围内。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path

IMPORTMAP_RE = re.compile(
    r'(<script[^>]*type=["\']importmap["\'][^>]*>)(.*?)(</script>)',
    re.S | re.I,
)
BARE_SPEC_RE = re.compile(r"""['"]([A-Za-z@][^'"\s]*)['"]""")
REL_IMPORT_RE = re.compile(r"""(['"])(\.{1,2}/[^'"\s]+)\1""")
INTERNAL_SPEC_RE = re.compile(r"""['"](vf-int-\d+)['"]""")


def die(msg: str) -> None:
    print(f"[bundle] 错误：{msg}", file=sys.stderr)
    sys.exit(1)


def norm(p: Path) -> Path:
    return Path(os.path.normpath(str(p)))


def to_data_url(raw: bytes) -> str:
    return "data:text/javascript;base64," + base64.b64encode(raw).decode("ascii")


def strip_to_vendor(value: str) -> str:
    """把 '../vendor/addons/OrbitControls.js' 归一成 'addons/OrbitControls.js'。

    --vendor 的语义是：importmap 里所有相对路径都指向同一个 vendor 根，
    只保留 vendor 之后的部分，从而允许 HTML 与 vendor 目录不在一处。
    """
    trailing = value.endswith("/")
    parts = [x for x in value.replace("\\", "/").split("/") if x not in ("", ".", "..")]
    while parts and parts[0] == "vendor":
        parts.pop(0)
    out = "/".join(parts)
    return out + "/" if trailing and out and not out.endswith("/") else out


def resolve_target(value: str, base: Path, vendor: Path | None = None) -> Path:
    if value.startswith("data:"):
        return Path("")
    if value.startswith(("http://", "https://", "//")):
        die(f"importmap 中存在远程地址，无法内联：{value}")
    p = Path(value)
    if vendor is not None and not p.is_absolute():
        rel = strip_to_vendor(value)
        if not rel:
            return Path("")
        return norm(vendor / rel)
    if not p.is_absolute():
        p = norm(base / value)
    return p


def collect(path: Path, spec: str, out: dict[str, str], seen: dict[str, str],
            counter: list[int], stats: list[tuple[str, int, int]], depth: int = 0) -> str:
    """把一个模块及其相对依赖闭包转成 data URL，返回该模块的 spec。"""
    key = str(norm(path))
    if key in seen:
        return seen[key]
    seen[key] = spec

    text = path.read_text(encoding="utf-8", errors="replace")

    def repl(m: re.Match) -> str:
        quote, rel = m.group(1), m.group(2)
        target = norm(path.parent / rel)
        if not target.is_file():
            print(f"[bundle] 警告：相对依赖不存在，保留原样：{path.name} → {rel}", file=sys.stderr)
            return m.group(0)
        key_t = str(norm(target))
        if key_t in seen:
            # 同一模块被引用多次（如 three.module.js 同时 import 与 export './three.core.js'）：
            # 必须复用已注册的 specifier。若仍自增，会产出未注册的 vf-int-N → 白屏。
            return f"{quote}{seen[key_t]}{quote}"
        counter[0] += 1
        sub_spec = f"vf-int-{counter[0]}"
        collect(target, sub_spec, out, seen, counter, stats, depth + 1)
        return f"{quote}{sub_spec}{quote}"

    rewritten = REL_IMPORT_RE.sub(repl, text)
    encoded = to_data_url(rewritten.encode("utf-8"))
    out[spec] = encoded
    stats.append((spec, len(text.encode("utf-8")), len(encoded)))
    return spec


def cmd_bundle(src: Path, out: Path, report: bool, vendor: Path | None = None) -> None:
    if not src.exists():
        die(f"源文件不存在：{src}")
    html = src.read_text(encoding="utf-8")
    m = IMPORTMAP_RE.search(html)
    if not m:
        die('源 HTML 里没有 <script type="importmap">，无法内联')
    try:
        imap = json.loads(m.group(2))
    except json.JSONDecodeError as e:
        die(f"importmap 不是合法 JSON：{e}")

    imports: dict[str, str] = imap.get("imports", {})
    if not imports:
        die("importmap.imports 为空")

    base = src.parent
    if vendor is not None and not vendor.is_dir():
        die(f"--vendor 目录不存在：{vendor}")
    prefixes = {k: v for k, v in imports.items() if k.endswith("/")}
    exacts = {k: v for k, v in imports.items() if not k.endswith("/")}

    used: set[str] = set()
    for spec in BARE_SPEC_RE.findall(html):
        if spec.startswith(("data:", "http", "//", "./", "../", "#")):
            continue
        for pfx, target in prefixes.items():
            if spec != pfx and spec.startswith(pfx):
                exacts[spec] = target + spec[len(pfx):]
                used.add(spec)
                break

    new_imports: dict[str, str] = {}
    seen: dict[str, str] = {}
    counter = [0]
    stats: list[tuple[str, int, int]] = []

    for spec, value in sorted(exacts.items()):
        p = resolve_target(value, base, vendor)
        if not p.is_file():
            tag = "使用中" if spec in used else "未引用"
            print(f"[bundle] 警告：{tag}映射指向的不是文件，已跳过：{spec} → {value}", file=sys.stderr)
            continue
        collect(p, spec, new_imports, seen, counter, stats)

    if not new_imports:
        die("没有任何模块被内联，检查 importmap 路径是否相对 HTML 所在目录")

    new_map = dict(imap)
    new_map["imports"] = new_imports
    payload = json.dumps(new_map, ensure_ascii=False, separators=(",", ":"))
    html_out = html[: m.start(2)] + payload + html[m.end(2):]

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_out, encoding="utf-8")

    src_kb = len(html.encode("utf-8")) / 1024
    out_kb = len(html_out.encode("utf-8")) / 1024
    print(f"[bundle] 内联 {len(new_imports)} 个模块（含相对依赖闭包）→ {out}")
    print(f"[bundle] 体积 {src_kb:.1f} KB → {out_kb:.1f} KB")
    if report:
        print(f"{'specifier':<44}{'raw':>10}{'data':>10}{'膨胀':>8}")
        for spec, raw, enc in stats:
            print(f"{spec:<44}{raw / 1024:>9.1f}K{enc / 1024:>9.1f}K{(enc / max(raw, 1) - 1) * 100:>7.0f}%")
    remaining = re.findall(r'(?:src|href)=["\'](https?://[^"\']+)', html_out)
    if remaining:
        print(f"[bundle] 提示：仍有 {len(remaining)} 个外链资源（字体/图片等），如需完全离线请一并内联：")
        for x in sorted(set(remaining))[:8]:
            print("         " + x)
    else:
        print("[bundle] 无剩余远程引用，可断网运行")


def cmd_self_test() -> None:
    here = Path(__file__).resolve().parent
    root = here.parent
    print("[self-test] bundle.py 自检")
    vendor = root / "assets" / "vendor"
    ok = True
    for name in ("three.module.js", "three.core.js"):
        p = vendor / name
        print(f"  {'OK ' if p.exists() else 'MISS'} vendor/{name}")
        ok = ok and p.exists()
    scaffold = root / "assets" / "scaffold" / "forged-scene.vendor.html"
    if not scaffold.exists():
        scaffold = root / "assets" / "scaffold" / "forged-scene.html"
    if scaffold.exists():
        has_map = bool(IMPORTMAP_RE.search(scaffold.read_text(encoding="utf-8")))
        print(f"  {'OK ' if has_map else 'MISS'} {scaffold.name} 含 importmap")
        ok = ok and has_map
    else:
        print("  MISS assets/scaffold/forged-scene.html")
        ok = False

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        # 模拟 three.module.js → three.core.js 的相对依赖，这是最关键的回归点
        (tdp / "core.js").write_text("export const A = 1;\n", encoding="utf-8")
        (tdp / "entry.js").write_text("import { A } from './core.js';\nexport const B = A + 1;\n", encoding="utf-8")
        # 同一相对依赖被引用两次（three.module.js 的真实形态：import 一次 + export ... from 一次）
        # 漏掉这一步会把 vf-int-2 写进模块体却不注册进 importmap → 产物白屏
        (tdp / "entry2.js").write_text(
            "import { A } from './core.js';\n"
            "export const B = A + 1;\n"
            "export { A } from './core.js';\n", encoding="utf-8")
        html = ('<html><body><script type="importmap">'
                '{"imports":{"m":"./entry.js","m2":"./entry2.js"}}'
                '</script><script type="module">import {B} from "m";</script></body></html>')
        (tdp / "t.html").write_text(html, encoding="utf-8")
        out = tdp / "o.html"
        try:
            cmd_bundle(tdp / "t.html", out, False)
            produced = out.read_text(encoding="utf-8")
            imap2 = json.loads(IMPORTMAP_RE.search(produced).group(2))
            imports_map = imap2["imports"]
            keys = set(imports_map)
            prefixes = {k for k in keys if k.endswith("/")}
            # 解码全部内联模块，检查有没有指向不存在 specifier 的悬空引用
            dangling: list[str] = []
            for spec, val in imports_map.items():
                if not val.startswith("data:text/javascript;base64,"):
                    continue
                body = base64.b64decode(val.split(",", 1)[1]).decode("utf-8", "replace")
                for ref in INTERNAL_SPEC_RE.findall(body):
                    if ref in keys or any(ref.startswith(p) for p in prefixes):
                        continue
                    if ref not in dangling:
                        dangling.append(ref)
            good = ("m" in keys and "m2" in keys
                    and any(k.startswith("vf-int-") for k in keys)
                    and not dangling)
            print(f"  {'OK ' if good else 'FAIL'} 相对依赖递归内联（three.module→three.core 同构场景）")
            if dangling:
                print(f"  FAIL 悬空 specifier：{dangling}（产物会白屏）")
            ok = ok and good
        except SystemExit:
            print("  FAIL 往返测试异常退出")
            ok = False

    print("[self-test] " + ("通过" if ok else "存在缺失"))
    sys.exit(0 if ok else 1)


def main() -> None:
    ap = argparse.ArgumentParser(description="把 vendor 依赖内联成单文件离线 HTML")
    ap.add_argument("--src", help="源 HTML")
    ap.add_argument("--out", help="输出 HTML")
    ap.add_argument("--vendor", help="vendor 根目录；给定后 importmap 的相对路径统一在该目录下解析")
    ap.add_argument("--report", action="store_true", help="打印每个模块的体积明细")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        cmd_self_test()
        return
    if not args.src or not args.out:
        die("需要 --src 与 --out")
    cmd_bundle(Path(args.src).resolve(), Path(args.out).resolve(), args.report,
               Path(args.vendor).resolve() if args.vendor else None)


if __name__ == "__main__":
    main()
