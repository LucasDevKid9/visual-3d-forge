#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三维造物引擎 · 交付前自检 v2
================================
静态扫描一个三维页面，检查那些"看起来能跑、实际会翻车"的问题：
依赖形态、API 真实性、性能预算、光照契约、R3F 反模式、兜底与生命周期。

用法
----
    python3 validate_scene.py <页面.html>                        # 基础检查
    python3 validate_scene.py <页面.html> --three <three包根>     # 追加 API 真实性核对
    python3 validate_scene.py <页面.html> --json                  # 机器可读输出（CI 用）
    python3 validate_scene.py <页面.html> --strict                # 有 warning 也返回非零

退出码：0 通过（可含 warning）；1 存在 error 或 strict 下有 warning；2 文件不可读。
只用标准库，可在任何环境运行。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FORBIDDEN_CDN = ("unpkg.com", "bootcdn", "staticfile.org", "polyfill.io", "cdn.bootcss")
REQUIRED_VER = "three@0.187.0"

LIGHT_KINDS = (
    "DirectionalLight", "HemisphereLight", "AmbientLight",
    "PointLight", "SpotLight", "RectAreaLight",
)


class Report:
    def __init__(self) -> None:
        self.errors: list[tuple[str, str]] = []
        self.warns: list[tuple[str, str]] = []
        self.passes: list[str] = []
        self.meta: dict[str, object] = {}

    def err(self, code: str, msg: str) -> None:
        self.errors.append((code, msg))

    def warn(self, code: str, msg: str) -> None:
        self.warns.append((code, msg))

    def ok(self, msg: str) -> None:
        self.passes.append(msg)

    def dump(self, as_json: bool) -> int:
        code = 1 if self.errors else 0
        if as_json:
            print(json.dumps({
                "ok": not self.errors,
                "meta": self.meta,
                "passes": self.passes,
                "warnings": [{"code": c, "message": m} for c, m in self.warns],
                "errors": [{"code": c, "message": m} for c, m in self.errors],
            }, ensure_ascii=False, indent=2))
            return code
        print("\n=== 三维造物引擎 · 交付前自检 v2 ===\n")
        for k, v in self.meta.items():
            print(f"  · {k}：{v}")
        print()
        for m in self.passes:
            print(f"  [PASS] {m}")
        if self.warns:
            print()
            for c, m in self.warns:
                print(f"  [WARN {c}] {m}")
        if self.errors:
            print()
            for c, m in self.errors:
                print(f"  [FAIL {c}] {m}")
        print()
        print(f"  结果：{len(self.passes)} 通过 / {len(self.warns)} 警告 / {len(self.errors)} 失败")
        return code


# ---------------------------------------------------------------- 工具

def _num(s: str) -> float | None:
    try:
        return float(s.strip())
    except (ValueError, AttributeError):
        return None


def detect_mode(html: str) -> str:
    if "data:text/javascript;base64" in html:
        return "D1 单文件内嵌（零外部依赖）"
    # 允许中间目录：`../../assets/vendor/xxx` 与 `./vendor/xxx` 都是本地 vendor。
    # 原正则只认「相对路径后紧跟 vendor/」，把 `spec/out/` 下这种多退一级的
    # 合法写法判成了 D0，进而误报「版本未锁定」。这是漏判，不是宽松。
    if re.search(r"""["']\.{1,2}/(?:[^"']*/)?vendor/""", html):
        return "D2 本地 vendor 目录"
    if "jsdelivr" in html.lower() and "importmap" in html:
        return "D0 单文件 CDN"
    if "@react-three/fiber" in html or ("react" in html.lower() and "useFrame" in html):
        return "D3 React Three Fiber 工程"
    if "importmap" in html:
        return "D0 单文件 CDN（非 jsDelivr）"
    return "未识别（可能未用模块化引入）"


def estimate_tris(html: str) -> tuple[int, list[str]]:
    """按几何构造参数粗估三角形数量。目的是量级判断，不是精确计数。"""
    total = 0
    detail: list[str] = []

    for m in re.finditer(r"new\s+THREE\.(\w*Geometry)\s*\(([^;]{0,200}?)\)", html):
        kind, raw = m.group(1), m.group(2)
        args = [a.strip() for a in raw.split(",")]

        def g(i: int, default: float = 0.0) -> float:
            if i < len(args):
                v = _num(args[i])
                return v if v is not None else default
            return default

        if kind == "SphereGeometry":
            t = max(1, g(1, 32)) * max(1, g(2, 16)) * 2
        elif kind == "CylinderGeometry":
            t = max(1, g(3, 32)) * max(1, g(4, 1)) * 4
        elif kind == "ConeGeometry":
            t = max(1, g(2, 32)) * 2
        elif kind == "TorusGeometry":
            t = max(1, g(2, 12)) * max(1, g(3, 48)) * 2
        elif kind == "TorusKnotGeometry":
            t = max(1, g(4, 64)) * max(1, g(5, 8)) * 2
        elif kind == "BoxGeometry":
            t = 12
        elif kind == "PlaneGeometry":
            t = max(1, g(2, 1)) * max(1, g(3, 1)) * 2
        elif kind == "CircleGeometry":
            t = max(1, g(1, 32))
        elif kind == "RingGeometry":
            t = max(1, g(3, 32)) * 2
        elif kind == "LatheGeometry":
            t = 20 * max(1, g(1, 12)) * 2
        elif kind == "TubeGeometry":
            t = max(1, g(3, 64)) * max(1, g(4, 8)) * 2
        elif kind == "ExtrudeGeometry":
            t = 800
        elif kind == "EdgesGeometry":
            t = 0
        else:
            t = 200
        total += int(t)
        detail.append(f"{kind}≈{int(t)}")

    return total, detail


def _dangling_specifiers(html: str) -> list[str]:
    """D1 专项：解码 importmap 里的 data URL 模块，检查每个 vf-int-N 引用是否都已注册。

    bundle.py 若对同一相对依赖二次自增编号，会把未注册的 vf-int-2 写进模块体：
    浏览器报 Failed to resolve module specifier，页面白屏，而其余静态检查全绿。
    """
    import base64

    m = re.search(r"""<script[^>]*type=["']importmap["'][^>]*>([\s\S]*?)</script>""", html, re.I)
    if not m:
        return []
    try:
        imap = json.loads(m.group(1)).get("imports", {})
    except json.JSONDecodeError:
        return []
    keys = set(imap)
    refs: dict[str, str] = {}
    for spec, val in imap.items():
        if not isinstance(val, str) or not val.startswith("data:text/javascript;base64,"):
            continue
        try:
            body = base64.b64decode(val.split(",", 1)[1]).decode("utf-8", "replace")
        except (ValueError, TypeError):
            continue
        for ref in re.findall(r"""['"](vf-int-\d+)['"]""", body):
            if ref not in keys:
                refs.setdefault(ref, spec)
    return sorted(refs)


def check_r3f(html: str, r: Report) -> None:
    blocks = re.findall(r"useFrame\s*\(([\s\S]{0,1500}?)\}\s*\)", html)
    if not blocks:
        return
    r.ok(f"检测到 {len(blocks)} 处 useFrame（R3F 逐帧回调）")
    for body in blocks:
        if re.search(r"\bset[A-Z]\w*\s*\(", body):
            r.err("E20", "useFrame 内调用了 setState：每帧触发 React 重渲染，必然掉帧。改用 useRef 直接改对象")
        if re.search(r"new\s+THREE\.", body):
            r.warn("W20", "useFrame 内 new 了 three 对象：每帧分配内存会触发 GC 抖动，应提到模块级或 useMemo")
    if re.search(r"args=\{\[[^\]]*[a-zA-Z_]\w*[^\]]*\]\}", html):
        r.warn("W21", "geometry/material 的 args 含变量：args 变化会销毁并重建对象，改用 props 传递")
    if "invalidate" in html:
        r.ok("使用了 invalidate（按需渲染），静止时不再空转")


def main() -> int:
    ap = argparse.ArgumentParser(description="三维页面交付前自检")
    ap.add_argument("file", help="待检查的 HTML 文件")
    ap.add_argument("--three", help="three.js 发行包根目录；提供则追加 API 真实性核对")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--strict", action="store_true", help="有 warning 也视为失败")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.is_file():
        print(f"读不到文件：{path}")
        return 2

    html = path.read_text(encoding="utf-8", errors="replace")
    r = Report()
    r.meta["文件"] = path.name
    r.meta["体积"] = f"{path.stat().st_size / 1024:.0f} KB"
    mode = detect_mode(html)
    r.meta["交付形态"] = mode

    # 1 单文件自包含
    local_js = re.findall(r'(?:src|href)\s*=\s*["\']((?!https?:|data:|#)[^"\']+\.(?:js|css))["\']', html, re.I)
    if local_js and "D2" not in mode:
        r.err("E01", f"引用了外部本地脚本/样式：{local_js[:5]}")
    elif local_js:
        r.ok(f"D2 模式：引用本地资源 {len(local_js)} 个（需连同目录一起交付）")
    else:
        r.ok("单文件自包含：无外部 .js/.css 引用")

    # 2 ES module + importmap
    has_module = bool(re.search(r"""type\s*=\s*['"]module['"]""", html))
    has_dynamic = bool(re.search(r"""\bimport\s*\(\s*['"]""", html))
    if has_module:
        r.ok("存在 <script type=\"module\">")
    elif has_dynamic and "importmap" in html:
        r.ok("使用 importmap + 动态 import()（classic script 模式，合法）")
    else:
        r.err("E02", "既无 module 脚本也无动态 import，无法加载 ES 模块")

    if "importmap" in html:
        if "D1" in mode:
            r.ok("importmap 全部指向 data URL（离线可用）")
            # D1 专项：内联闭包里不能有指向未注册 specifier 的引用（否则白屏且静态看不见）
            dangling = _dangling_specifiers(html)
            if dangling:
                r.err("E16", f"内联闭包存在悬空 specifier：{dangling[:6]}（运行时会 "
                             f"Failed to resolve module specifier，页面白屏）")
            else:
                r.ok("内联闭包无悬空 specifier（每个 vf-int-N 都已注册）")
        elif "D2" in mode:
            local_vendor = re.findall(r'"(\.{0,2}/[^"]*vendor/[^"]*)"', html)
            if local_vendor:
                r.ok(f"D2 模式：importmap 指向本地 vendor（{len(local_vendor)} 条，无需版本锁定）")
            else:
                r.err("E03", "D2 模式但 importmap 未指向本地 vendor 目录")
        elif REQUIRED_VER in html:
            r.ok(f"three.js 版本已锁定 {REQUIRED_VER}")
        else:
            r.err("E03", f"importmap 未锁定 {REQUIRED_VER}（版本漂移会让页面随时坏掉）")
    else:
        r.warn("W01", "没有 importmap：确认引入方式是否需要服务端模式")

    # 3 CDN 黑名单
    hit = [c for c in FORBIDDEN_CDN if c in html.lower()]
    if hit:
        r.err("E04", f"使用了禁用 CDN（供应链风险）：{hit}")
    else:
        r.ok("未使用禁用 CDN")

    # 4 像素比封顶
    if "setPixelRatio" in html:
        if re.search(r"setPixelRatio\s*\([^)]*Math\.min", html):
            r.ok("像素比已封顶（Math.min 夹取）")
        else:
            r.err("E05", "setPixelRatio 未用 Math.min 封顶，高分屏会掉帧发烫")
    elif "D3" not in mode:
        r.warn("W02", "未设置像素比，默认按 devicePixelRatio 全量渲染")

    # 5 色彩管理唯一性
    tm = len(re.findall(r"\.toneMapping\s*=", html))
    if tm == 0:
        r.warn("W03", "未设置 toneMapping，高光可能过曝死白")
    elif tm > 1:
        r.err("E06", f"toneMapping 被赋值 {tm} 次，可能造成双重色彩转换（画面发灰）")
    else:
        r.ok("toneMapping 只设置一次")
    cs = len(re.findall(r"\.outputColorSpace\s*=", html))
    if cs > 1:
        r.err("E07", f"outputColorSpace 被赋值 {cs} 次，色彩转换重复")

    # 6 resize
    if re.search(r"""addEventListener\s*\(\s*['"]resize""", html) or "ResizeObserver" in html:
        r.ok("有 resize 处理")
    elif "D3" not in mode:
        r.err("E08", "缺少 resize 处理，拉伸窗口会变形")

    # 7 后台暂停
    if "visibilitychange" in html:
        r.ok("有后台暂停（visibilitychange）")
    else:
        r.warn("W04", "未处理 visibilitychange，切到后台仍会持续渲染耗电")

    # 8 相机限位
    if "OrbitControls" in html:
        need = ["minPolarAngle", "maxPolarAngle", "minDistance", "maxDistance"]
        miss = [k for k in need if k not in html]
        if miss:
            r.err("E09", f"使用 OrbitControls 但缺少限位参数：{miss}（会转到空壳或穿进物体）")
        else:
            r.ok("相机极角与距离均已限位")
        if "enablePan" not in html:
            r.warn("W05", "未设置 enablePan，用户可能把主体拖出画面")

    # 9 fov
    m = re.search(r"PerspectiveCamera\s*\(\s*([0-9.]+)", html)
    if m:
        fov = float(m.group(1))
        if fov >= 70:
            r.err("E10", f"fov={fov} 是库默认值级别的广角，等于没选镜头（建议 32–45）")
        elif 32 <= fov <= 45:
            r.ok(f"fov={fov}，属于稳健的产品镜头区间")
        else:
            r.warn("W06", f"fov={fov}，确认这是有意的选择")

    # 10 无 WebGL 兜底
    probe = bool(re.search(r"""getContext\s*\(\s*['"](webgl2?|experimental-webgl)""", html, re.I))
    probe = probe or any(k in html for k in (
        "isWebGLAvailable", "hasWebGL", "WebGLRenderingContext", "WebGL2RenderingContext"))
    guarded = "WebGLRenderer" in html and bool(re.search(r"\btry\s*\{", html))
    if probe:
        r.ok("有无 WebGL 能力探测")
    elif guarded:
        r.warn("W16", "用 try/catch 兜住渲染器创建，但没有前置能力探测（建议显式 getContext 检测后再初始化）")
    elif "webgl" in html.lower() and "fallback" in html.lower():
        r.ok("有无 WebGL 兜底路径")
    else:
        r.err("E11", "未检测 WebGL 能力，也没有兜底内容，弱设备会白屏")

    # 11 渲染循环
    if "setAnimationLoop" in html or "requestAnimationFrame" in html:
        r.ok("存在渲染循环")
        if re.search(r"Math\.min\s*\([^)]*(?:getDelta|dt)", html) or re.search(r"dt\s*>\s*0?\.\d", html):
            r.ok("帧间隔已钳制（切回标签页不会大跳）")
        else:
            r.warn("W07", "未钳制 dt，切回标签页时可能出现画面跳变")
    elif "D3" not in mode:
        r.err("E12", "没有渲染循环")

    # 12 危险 API
    if "document.write" in html:
        r.err("E13", "使用了 document.write")

    # 13 光照结构
    lights = {k: len(re.findall(rf"new\s+THREE\.{k}", html)) for k in LIGHT_KINDS}
    used = {k: v for k, v in lights.items() if v}
    total_lights = sum(used.values())
    if total_lights == 0:
        if "D3" in mode:
            r.warn("W11", "未发现显式光源（R3F 可能在组件内声明，确认是否有环境光）")
        else:
            r.warn("W11", "未发现任何光源，场景会全黑（除非纯自发光材质）")
    elif total_lights == 1:
        r.warn("W12", f"只有 1 个光源（{list(used)[0]}），形体没有层次，建议主光 + 补光 + 轮廓光")
    else:
        r.ok(f"光照结构：{total_lights} 个光源 {used}")

    # 14 接触关系（阴影）
    has_shadowmap = bool(re.search(r"shadowMap\s*\.\s*enabled\s*=\s*true", html))
    has_blob = bool(re.search(r"(radialGradient|createRadialGradient|shadowTexture|ContactShadow)", html))
    if has_shadowmap:
        r.ok("启用了实时阴影贴图")
    elif has_blob:
        r.ok("使用了贴图/渐变假阴影（低成本接触阴影）")
    else:
        r.warn("W13", "没有阴影也没有接触暗部，物体看起来会浮在空中")

    # 15 规模
    meshes = len(re.findall(r"new\s+THREE\.Mesh\s*\(", html))
    inst = "InstancedMesh" in html
    if meshes >= 30 and not inst:
        r.warn("W08", f"直接创建了 {meshes} 个 Mesh 且未用实例化，注意绘制调用预算")
    elif meshes:
        r.ok(f"Mesh 创建数 {meshes}，实例化：{'有' if inst else '无'}")

    tris, detail = estimate_tris(html)
    r.meta["估算三角面"] = f"≈{tris:,}"
    if tris > 600_000:
        r.err("E14", f"估算 {tris:,} 三角面，远超中端设备预算（建议 <200k）")
    elif tris > 200_000:
        r.warn("W14", f"估算 {tris:,} 三角面，移动端可能掉帧（预算 <200k）")
    elif tris:
        r.ok(f"三角面预算合理（≈{tris:,}）")

    # 16 材质分裂
    if html.count("metalness: 0.5") >= 1 or html.count("metalness:0.5") >= 1:
        r.warn("W09", "出现 metalness 0.5：金属度是二元物理属性，中间值只应出现在真实混合区")

    # 17 R3F 专项
    check_r3f(html, r)

    # 18 体量
    kb = path.stat().st_size / 1024
    if kb > 6000:
        r.warn("W10", f"文件体积 {kb:.0f}KB，首帧解析会很慢（D1 内嵌约 3MB 属正常）")
    else:
        r.ok(f"文件体积 {kb:.0f}KB")

    # 19 API 真实性（可选，需要 three 源码）
    if args.three:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import api_lookup  # type: ignore

            three_root = api_lookup.find_three_root(Path(args.three))
            table = api_lookup.load_table(three_root)
            bad: list[str] = []
            checked = 0
            for sym in re.findall(r"\bTHREE\.(\w+)", html):
                checked += 1
                if sym not in table:
                    import difflib
                    near = difflib.get_close_matches(sym, table.keys(), n=2, cutoff=0.62)
                    bad.append(sym + ("（是否想用 " + " / ".join(near) + "）" if near else ""))
            if bad:
                uniq = sorted(set(bad))
                r.err("E15", f"{len(uniq)} 个 THREE 符号在源码中不存在：{uniq[:8]}")
            elif checked:
                r.ok(f"API 真实性：{checked} 处 THREE.X 引用全部存在于 three.js {table and '源码'}")
            r.meta["符号表"] = f"{len(table)} 项"
        except Exception as e:  # noqa: BLE001
            r.warn("W15", f"API 核对跳过：{e}")

    code = r.dump(args.json)
    if args.strict and r.warns and not r.errors:
        return 1
    return code


if __name__ == "__main__":
    sys.exit(main())
