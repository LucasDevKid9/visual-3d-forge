#!/usr/bin/env python3
"""把 CDN 版单文件页面转换为完全离线的 standalone 单文件。

原理：
    CDN 版靠 <script type="importmap"> + <script type="module"> 从 jsDelivr 拉 three。
    standalone 版把预打包的 three.bundle.min.js（IIFE，含 THREE + 常用 addons）
    直接内联进 HTML，并把 module 脚本降级为普通 script。
    转换后：双击即开、断网可用、file:// 协议下也不会被 CORS 拦。

用法：
    python3 build_standalone.py <输入.html> [-o 输出.html]

退出码：0 成功；1 转换失败（页面不符合可转换规范）；2 参数/文件错误。
只用标准库。
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent / "assets" / "three" / "three.bundle.min.js"

USAGE = """usage: build_standalone.py <输入.html> [-o 输出.html] [-h]

把 CDN 版单文件页面转换为完全离线的 standalone 单文件。

原理：CDN 版靠 importmap + module 从 jsDelivr 拉 three；
standalone 版把预打包的 three.bundle.min.js（IIFE，含 THREE + 常用 addons）
直接内联进 HTML，并把 module 脚本降级为普通 script。
转换后：双击即开、断网可用、file:// 协议下也不会被 CORS 拦。

options:
  -o OUTPUT   输出路径（默认 <输入名>.standalone.html）
  -h, --help  显示本帮助

退出码：0 成功；1 转换失败（页面不符合可转换规范）；2 参数/文件错误。
只用标准库。"""

# 骨架里可能出现的 addon 名，用于生成解构语句
KNOWN_ADDONS = [
    # controls
    "OrbitControls", "MapControls", "PointerLockControls",
    "TransformControls", "DragControls", "FlyControls",
    # environments
    "RoomEnvironment", "ColorEnvironment",
    # postprocessing
    "EffectComposer", "RenderPass", "OutputPass", "ShaderPass",
    "UnrealBloomPass", "SSAOPass", "LUTPass", "OutlinePass", "FilmPass",
    # loaders
    "RGBELoader", "GLTFLoader", "OBJLoader", "SVGLoader", "FontLoader",
    "STLLoader", "PLYLoader", "MeshoptDecoder",
    # geometries
    "ParametricGeometry", "TeapotGeometry", "RoundedBoxGeometry",
    "ConvexGeometry", "DecalGeometry", "LoftGeometry",
    # objects
    "Sky", "Water", "Reflector", "Refractor", "Lensflare", "LensflareElement",
    "MarchingCubes", "ShadowMesh",
    # math
    "MeshSurfaceSampler", "ConvexHull", "SimplexNoise", "ImprovedNoise",
    # lines
    "Line2", "LineGeometry", "LineMaterial",
    # interactive
    "SelectionBox", "SelectionHelper", "InteractiveGroup", "HTMLMesh",
    # misc / animation / modifiers / exporters / helpers / lights
    "GPUComputationRenderer", "Gyroscope", "CCDIKSolver", "CCDIKHelper",
    "TessellateModifier", "SimplifyModifier",
    "GLTFExporter", "STLExporter", "PLYExporter", "ViewHelper",
    "RectAreaLightUniformsLib",
    # libs（默认导出也纳入解构）
    "GUI", "Stats", "TWEEN",
]

# 默认导入别名 → bundle 键（默认导入会被剥掉，必须登记才会被解构出来）
DEFAULT_IMPORTS = {"Stats": "Stats", "TWEEN": "TWEEN", "GUI": "GUI"}


def strip_imports(code: str):
    """删除 import 语句，返回 (剩余代码, 需要从 bundle 解构的符号)。"""
    needed = set()

    # import * as X from 'y'
    for m in re.finditer(r"^\s*import\s+\*\s+as\s+(\w+)\s+from\s+['\"][^'\"]+['\"];?\s*$", code, re.M):
        if m.group(1) == "THREE":
            needed.add("THREE")
        code = code.replace(m.group(0), "")

    # import { A, B as C } from 'y'
    for m in re.finditer(r"^\s*import\s*\{([^}]*)\}\s*from\s*['\"][^'\"]+['\"];?\s*$", code, re.M):
        for part in m.group(1).split(","):
            part = part.strip()
            if not part:
                continue
            alias = part.split(" as ")[-1].strip()
            if alias in KNOWN_ADDONS or alias == "THREE":
                needed.add(alias)
            elif part.split(" as ")[0].strip() in ("BufferGeometryUtils", "SkeletonUtils"):
                needed.add(part.split(" as ")[0].strip())
        code = code.replace(m.group(0), "")

    # import X from 'y'（默认导入：登记过的别名收进 needed，其余直接删）
    def _default(m):
        alias = m.group(1)
        if alias in DEFAULT_IMPORTS:
            needed.add(DEFAULT_IMPORTS[alias])
        return ""
    code = re.sub(r"^\s*import\s+(\w+)\s+from\s+['\"][^'\"]+['\"];?\s*$", _default, code, flags=re.M)
    return code, needed


def main() -> int:
    argv = sys.argv[1:]
    src, out = None, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            print(USAGE)
            return 0
        if a == "-o" and i + 1 < len(argv):
            out = Path(argv[i + 1]); i += 2
        elif a.startswith("-"):
            i += 1
        else:
            if src is None:
                src = Path(a)
            i += 1

    if src is None:
        print(USAGE)
        return 2
    if not src.is_file():
        print(f"读不到文件：{src}")
        return 2
    if out is None:
        out = src.with_name(src.stem + ".standalone.html")

    if not BUNDLE.is_file():
        print(f"缺少运行时 bundle：{BUNDLE}\n请先确认 assets/three/three.bundle.min.js 存在。")
        return 2

    html = src.read_text(encoding="utf-8")

    if "THREE_BUNDLE" in html and "globalThis.THREE_BUNDLE" not in html:
        print("该文件已经是 standalone 版本，无需转换。")
        return 0

    # 定位 module 脚本
    m = re.search(r'<script\s+type=["\']module["\']\s*>(.*?)</script>', html, re.S | re.I)
    if not m:
        print("未找到 <script type=\"module\">，无法转换。")
        return 1

    code, needed = strip_imports(m.group(1))

    if re.search(r"^\s*import\s", code, re.M):
        leftover = re.findall(r"^\s*import\s.*$", code, re.M)[:3]
        print("仍有无法解析的 import 语句，请手工调整后再试：")
        for l in leftover:
            print("   ", l.strip())
        return 1

    # 常见 addon 兜底：代码里用到但没写 import（骨架可能直接用全局）
    for name in KNOWN_ADDONS:
        if re.search(rf"\bnew\s+{name}\s*\(", code):
            needed.add(name)
    needed.add("THREE")

    ordered = ["THREE"] + [n for n in KNOWN_ADDONS if n in needed]
    destructure = (
        "const { " + ", ".join(ordered) + " } = window.THREE_BUNDLE;\n"
        "if (!window.THREE_BUNDLE) { throw new Error('THREE_BUNDLE 未注入'); }\n"
    )

    bundle_src = BUNDLE.read_text(encoding="utf-8")

    # 移除 importmap（必须在定位 module 脚本之前完成，否则索引会错位）
    html = re.sub(r'<script\s+type=["\']importmap["\']\s*>.*?</script>\s*', "", html, flags=re.S | re.I)

    # 重新定位 module 脚本（此时索引与 html 一致）
    m2 = re.search(r'<script\s+type=["\']module["\']\s*>.*?</script>', html, re.S | re.I)
    if not m2:
        print("移除 importmap 后找不到 module 脚本，转换中止。")
        return 1

    # module -> 普通 script，并注入 bundle + 解构
    new_script = (
        "<script>\n/* three.js r187 + addons · 预打包内联（离线可用） */\n"
        + bundle_src
        + "\n</script>\n<script>\n"
        + destructure
        + code
        + "\n</script>"
    )
    html = html[:m2.start()] + new_script + html[m2.end():]

    # 体积告警
    out.write_text(html, encoding="utf-8")
    kb = out.stat().st_size / 1024
    print(f"已生成：{out}")
    print(f"体积：{kb:.0f} KB（内联 three 运行时，离线可用）")
    print(f"解构符号：{', '.join(ordered)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
