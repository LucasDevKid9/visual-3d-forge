#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visual-3d-forge / api_lookup.py
API 真实性查证：对着 three.js 源码核对，防止写出不存在的 API。

为什么需要它
------------
三维代码最常见的致命失败不是逻辑错，而是**编造 API**：
`THREE.CapsuleGeomtry`（拼错）、`material.clearcoatRoughness` 写成 `clearCoatRoughness`、
`THREE.PMREMGenerator` 用错构造签名、addon 路径写成 `three/addons/OrbitControls.js`。
这类错误在静态检查里看不出来，只有浏览器控制台报 `undefined is not a constructor`。
本脚本把 21MB 源码变成一张权威符号表，写完代码立刻核对。

用法
----
    # 查一个符号定义在哪、怎么写的
    python3 api_lookup.py --three <three包根> MeshPhysicalMaterial
    python3 api_lookup.py --three <three包根> --find CapsuleGeometry

    # 列出全部导出符号（写代码前扫一眼，别凭记忆）
    python3 api_lookup.py --three <three包根> --list
    python3 api_lookup.py --three <three包根> --list --grep material

    # 校验一段代码里所有 THREE.X 和 addon 路径是否真实存在
    python3 api_lookup.py --three <three包根> --check scene.js
    python3 api_lookup.py --three <three包根> --check scene.js --strict

退出码：--check 且 --strict 时，发现可疑即返回 1。
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path

EXPORT_STAR = re.compile(r"""export\s*\*\s*from\s*['"]([^'"]+)['"]""")
EXPORT_NAMED = re.compile(r"""export\s*\{([^}]*)\}\s*from\s*['"]([^'"]+)['"]""")
EXPORT_DECL = re.compile(r"""export\s+(?:default\s+)?(?:abstract\s+)?(?:class|const|let|var|function)\s+(\w+)""")
# 叶子类最常见的写法：文件里 `class TorusGeometry extends BufferGeometry {...}`，
# 末尾单独 `export { TorusGeometry };`（无 from）。漏掉这种形式会丢掉大半几何体符号。
EXPORT_LOCAL = re.compile(r"""export\s*\{([^}]*)\}""")

CODE_THREE_DOT = re.compile(r"""\bTHREE\.(\w+)""")
CODE_THREE_BRACKET = re.compile(r"""\bTHREE\[\s*['"](\w+)['"]\s*\]""")
CODE_ADDON_PATH = re.compile(r"""['"]three/addons/([^'"]+)['"]""")
CODE_ADDON_REL = re.compile(r"""['"]((?:\.\.?/)*(?:controls|renderers|loaders|environments|postprocessing|shaders|utils|geometries|lines|math|helpers|misc|objects|curves|materials|nodes)/[^'"]+\.js)['"]""")


def die(msg: str) -> None:
    print(f"[api] 错误：{msg}", file=sys.stderr)
    sys.exit(2)


def find_three_root(p: Path) -> Path:
    p = p.resolve()
    for cand in (p, p / "three.js-0.187.0", p.parent):
        if (cand / "src" / "Three.js").exists() and (cand / "examples" / "jsm").is_dir():
            return cand
    die(f"在 {p} 找不到 three.js 源码结构（需要 src/Three.js 与 examples/jsm/）")
    return p


def read_version(three: Path) -> str:
    pkg = three / "package.json"
    if pkg.exists():
        try:
            return json.loads(pkg.read_text(encoding="utf-8")).get("version", "?")
        except Exception:
            pass
    txt = (three / "src" / "constants.js").read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"REVISION\s*=\s*['\"](\d+)['\"]", txt)
    return f"r{m.group(1)}" if m else "?"


def _norm(p: Path) -> str:
    """规范化路径但**不解析符号链接**。

    云盘 / 挂载目录常是符号链接，Path.resolve() 会解析成容器内不可访问的真实路径，
    导致 exists() 误判为 False、依赖文件被静默跳过。这里只用 normpath。
    """
    return os.path.normpath(str(p))


def _record(table: dict[str, str], names_csv: str, rel: str) -> None:
    """把 `A, B as C, D` 形式的导出名记进表（取导出侧的名字）。"""
    for raw in names_csv.split(","):
        raw = raw.strip()
        if not raw:
            continue
        if " as " in raw:
            raw = raw.split(" as ")[-1].strip()
        if re.fullmatch(r"\w+", raw):
            table.setdefault(raw, rel)


def build_symbol_table(three: Path) -> tuple[dict[str, str], dict[str, str]]:
    """返回 (symbol -> 源文件相对路径, symbol -> 定义原文片段)。"""
    src = Path(_norm(three / "src"))
    src_str = str(src)
    table: dict[str, str] = {}
    seen: set[str] = set()
    stack: list[str] = [str(src / "Three.js")]

    while stack:
        fp = stack.pop()
        if fp in seen:
            continue
        seen.add(fp)
        try:
            text = Path(fp).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        parent = Path(fp).parent
        rel = Path(fp).relative_to(src).as_posix() if fp.startswith(src_str) else fp

        for target in EXPORT_STAR.findall(text):
            stack.append(_norm(parent / target))

        for names, target in EXPORT_NAMED.findall(text):
            stack.append(_norm(parent / target))
            _record(table, names, rel)

        # 本地导出块（无 from）。先把带 from 的块剔掉，避免重复计入。
        for names in EXPORT_LOCAL.findall(EXPORT_NAMED.sub("", text)):
            _record(table, names, rel)

        for name in EXPORT_DECL.findall(text):
            table.setdefault(name, rel)

    # 兜底：主链只覆盖 src/Three.js 的导出面；WebGPU / TSL / Legacy 在旁支文件里。
    # 只扫 src 顶层 Three*.js（约 6 个文件），不做全量 rglob——667 文件全读会慢 10 倍。
    if len(table) < 400:
        for f in sorted(src.glob("Three*.js")):
            fp = _norm(f)
            if fp in seen:
                continue
            try:
                text = Path(fp).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel = Path(fp).relative_to(src).as_posix()
            for target in EXPORT_STAR.findall(text):
                stack.append(_norm(Path(fp).parent / target))
            for names, _t in EXPORT_NAMED.findall(text):
                for raw in names.split(","):
                    raw = raw.strip()
                    if " as " in raw:
                        raw = raw.split(" as ")[-1].strip()
                    if re.fullmatch(r"\w+", raw):
                        table.setdefault(raw, rel)
            for name in EXPORT_DECL.findall(text):
                table.setdefault(name, rel)

    return table, {}


def _locate(f: Path, symbol: str, rel: str) -> str | None:
    if not f.exists():
        return None
    lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
    pat = re.compile(rf"""\b(class|const|let|var|function)\s+{re.escape(symbol)}\b""")
    for i, line in enumerate(lines):
        if pat.search(line):
            head = line.strip()
            for j in range(i, min(i + 10, len(lines))):
                if "constructor" in lines[j]:
                    return f"{symbol}  →  src/{rel}:{i + 1}\n    {head}\n    {lines[j].strip()}"
            return f"{symbol}  →  src/{rel}:{i + 1}\n    {head}"
    return None


def describe_symbol(three: Path, symbol: str, table: dict[str, str]) -> str | None:
    rel = table.get(symbol)
    if not rel:
        return None
    hit = _locate(three / "src" / rel, symbol, rel)
    if hit:
        return hit
    # 导出表常指向 barrel（Geometries.js / Materials.js / Three.Core.js），
    # 真实 class 在同名文件里。src 结构是 src/{类别}/{Name}.js，按层级 glob 比 rglob 快一个量级。
    src = three / "src"
    cands = list(src.glob(f"*/{symbol}.js")) + list(src.glob(f"*/*/{symbol}.js"))
    for cand in cands:
        r2 = cand.relative_to(src).as_posix()
        hit = _locate(cand, symbol, r2)
        if hit:
            return hit
    return f"{symbol}  →  src/{rel}（由 barrel 转出，未定位到直接声明，可能是 Object.assign 组装或常量）"


def load_table(three: Path, refresh: bool = False) -> dict[str, str]:
    """建表约需 10~20s（云盘 IO 慢），落盘缓存后二次调用 <0.1s。"""
    cache_dir = Path(__file__).resolve().parent / ".cache"
    ver = read_version(three)
    cache_file = cache_dir / f"symbols-three-{ver}.json"
    src_key = _norm(three / "src")
    if not refresh and cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if data.get("src") == src_key and len(data.get("table", {})) > 100:
                return data["table"]
        except (json.JSONDecodeError, OSError):
            pass
    table, _ = build_symbol_table(three)
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            json.dumps({"src": src_key, "version": ver, "table": table}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass
    return table


def cmd_find(three: Path, symbols: list[str], table: dict[str, str]) -> int:
    bad = 0
    for s in symbols:
        out = describe_symbol(three, s, table)
        if out:
            print(out)
        else:
            bad += 1
            near = difflib.get_close_matches(s, table.keys(), n=5, cutoff=0.6)
            print(f"{s}  →  不存在")
            if near:
                print("    相近符号：" + ", ".join(near))
    return 1 if bad else 0


def cmd_list(table: dict[str, str], grep: str | None) -> None:
    names = sorted(table)
    if grep:
        g = grep.lower()
        names = [n for n in names if g in n.lower()]
    print(f"共 {len(names)} 个导出符号")
    cols = 3
    width = max((len(n) for n in names), default=10) + 2
    for i in range(0, len(names), cols):
        print("".join(n.ljust(width) for n in names[i:i + cols]).rstrip())


def cmd_check(three: Path, target: Path, table: dict[str, str], strict: bool) -> int:
    if not target.exists():
        die(f"文件不存在：{target}")
    text = target.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    jsm = three / "examples" / "jsm"

    problems: list[tuple[int, str, str]] = []
    checked = 0

    for idx, line in enumerate(lines, 1):
        for sym in CODE_THREE_DOT.findall(line) + CODE_THREE_BRACKET.findall(line):
            checked += 1
            if sym not in table:
                near = difflib.get_close_matches(sym, table.keys(), n=3, cutoff=0.62)
                hint = ("；是否想用 " + " / ".join(near)) if near else ""
                problems.append((idx, sym, hint))

        for path in CODE_ADDON_PATH.findall(line):
            checked += 1
            if not (jsm / path).exists():
                base = path.split("/")[-1]
                near = [p.relative_to(jsm).as_posix() for p in jsm.rglob(base)]
                hint = ("；实际路径 " + " / ".join(near[:3])) if near else "；该 addon 不存在"
                problems.append((idx, "addons/" + path, hint))

    # 相对路径 import 只在同目录有 addon 结构时校验
    for idx, line in enumerate(lines, 1):
        for path in CODE_ADDON_REL.findall(line):
            if path.startswith("./") or path.startswith("../"):
                continue
            checked += 1
            if not (jsm / path).exists():
                problems.append((idx, path, "；相对 addon 路径不存在，应以 three/addons/ 为基准"))

    print(f"[api] three.js {read_version(three)} · 符号表 {len(table)} 项 · 检查 {target.name}")
    print(f"[api] 共核对 {checked} 处引用")
    if not problems:
        print("[api] 全部通过：未发现编造或路径错误的 API")
        return 0
    print(f"[api] 可疑 {len(problems)} 处：")
    for ln, sym, hint in problems:
        print(f"  行 {ln:>5}  {sym}{hint}")
    print("[api] 说明：命中不代表一定错（可能是自定义命名空间或字符串误匹配），逐条确认后修正")
    return 1 if strict else 0


def main() -> None:
    argv = sys.argv[1:]
    # 同时支持两种调用风格：
    #   子命令式： api_lookup.py check  a.html --three ROOT
    #              api_lookup.py find   InstancedMesh --three ROOT
    #              api_lookup.py list   --filter Geometry --three ROOT
    #   flag 式：  api_lookup.py --three ROOT --check a.html  （旧写法，保留兼容）
    sub = argv[0] if argv and argv[0] in ("find", "list", "check") else None
    if sub:
        argv = argv[1:]

    ap = argparse.ArgumentParser(
        prog="api_lookup.py",
        description="three.js API 真实性查证",
        epilog="示例： api_lookup.py check scene.html --three ./three.js-0.187.0 --strict",
    )
    ap.add_argument("--three", required=True, help="three.js 发行包根目录（含 src/ 与 examples/jsm/）")
    ap.add_argument("rest", nargs="*", help="子命令参数：find 的符号名 / check 的目标文件")
    ap.add_argument("--check", help="校验该 JS/HTML 文件里的 THREE.X 与 addon 路径")
    ap.add_argument("--find", nargs="+", help="要查询的符号名（可多个）")
    ap.add_argument("--list", action="store_true", help="列出全部导出符号")
    ap.add_argument("--grep", "--filter", dest="grep", help="配合 list 做子串过滤")
    ap.add_argument("--strict", action="store_true", help="发现问题时返回非零退出码")
    ap.add_argument("--refresh", action="store_true", help="忽略符号表缓存，强制重建")
    args = ap.parse_args(argv)

    three = find_three_root(Path(args.three))
    table = load_table(three, refresh=args.refresh)

    want_check = sub == "check" or bool(args.check)
    want_list = sub == "list" or args.list
    want_find = sub == "find" or bool(args.find)

    if want_check:
        target = args.check or (args.rest[0] if args.rest else None)
        if not target:
            die("check 需要目标文件：api_lookup.py check <file.html> --three ROOT")
        sys.exit(cmd_check(three, Path(os.path.normpath(target)), table, args.strict))

    if want_list:
        cmd_list(table, args.grep)
        return

    targets = list(args.find or []) + ([] if sub == "find" else list(args.rest))
    if sub == "find":
        targets = list(args.find or []) + list(args.rest)
    if not targets:
        die("没有指定符号；用法：find <Symbol...> / list --filter X / check <file>")
    sys.exit(cmd_find(three, targets, table))


if __name__ == "__main__":
    main()
