#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visual-3d-forge / vendor.py
依赖提取与离线化工具：把 three.js 完整发行包裁剪成最小可用 vendor 集。

为什么需要它
------------
three.js 完整包有 1400+ 文件，但一个三维场景真正用到的通常不超过 10 个 addon。
手工挑文件极易漏掉 addon 之间的相对 import（例如 EffectComposer 依赖
CopyShader / MaskPass / ShaderPass / Pass），漏一个就是运行期白屏。
本脚本递归解析相对 import，保证闭包完整。

用法
----
    python3 vendor.py --three <three包根目录> --out <vendor输出目录> [--profile core|standard|full|all]
    python3 vendor.py --three <three包根目录> --out <目录> --include OrbitControls,CSS2DRenderer
    python3 vendor.py --three <three包根目录> --list
    python3 vendor.py --self-test

输出结构
--------
    <out>/three.module.js
    <out>/three.core.js
    <out>/addons/controls/OrbitControls.js
    <out>/addons/...
    <out>/importmap.json     可直接粘进 HTML 的 importmap 片段
    <out>/manifest.json      版本 / 文件清单 / 字节 / sha256 前 12 位
    <out>/README.md          该目录的用法说明

约束
----
· three.module.js 与 three.core.js 必须同目录，前者从后者 re-export，拆开即报错。
· DRACOLoader / KTX2Loader / MeshoptDecoder 依赖外部 wasm 或独立 js 解码器，
  本脚本只复制调用代码，解码器文件需另行部署，manifest 中会标记 external:true。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

CORE_BUILD = ["three.module.js", "three.core.js"]

# addon 之间的相对 import：from './x.js' / from '../shaders/y.js'
REL_IMPORT = re.compile(r"""(?:from|import)\s*['"](\.[^'"]+)['"]""")

PROFILES: dict[str, list[str]] = {
    "core": [
        "controls/OrbitControls.js",
        "renderers/CSS2DRenderer.js",
        "environments/RoomEnvironment.js",
        "utils/BufferGeometryUtils.js",
    ],
    "standard": [
        "controls/OrbitControls.js",
        "controls/MapControls.js",
        "controls/TrackballControls.js",
        "renderers/CSS2DRenderer.js",
        "renderers/CSS3DRenderer.js",
        "environments/RoomEnvironment.js",
        "utils/BufferGeometryUtils.js",
        "utils/SkeletonUtils.js",
        "loaders/GLTFLoader.js",
        "loaders/RGBELoader.js",
        "lines/Line2.js",
        "lines/LineMaterial.js",
        "lines/LineGeometry.js",
        "lines/LineSegments2.js",
        "lines/LineSegmentsGeometry.js",
    ],
    "post": [
        "postprocessing/EffectComposer.js",
        "postprocessing/RenderPass.js",
        "postprocessing/ShaderPass.js",
        "postprocessing/UnrealBloomPass.js",
        "postprocessing/OutputPass.js",
        "postprocessing/SMAAPass.js",
    ],
}
PROFILES["full"] = PROFILES["standard"] + PROFILES["post"] + [
    "loaders/EXRLoader.js",
    "loaders/DRACOLoader.js",
    "loaders/KTX2Loader.js",
    "geometries/ConvexGeometry.js",
    "geometries/ParametricGeometry.js",
    "geometries/TeapotGeometry.js",
    "geometries/RoundedBoxGeometry.js",
    "math/MeshSurfaceSampler.js",
]

# 需要外部解码器文件、无法靠纯 js 自足的 addon
EXTERNAL_DEPS = {
    "loaders/DRACOLoader.js": "需要 draco_decoder.wasm + draco_wasm_wrapper.js，自行部署并 setDecoderPath()",
    "loaders/KTX2Loader.js": "需要 basis_transcoder.js + .wasm，自行部署并 setTranscoderPath()",
    "loaders/MeshoptDecoder.js": "需要 meshopt_decoder.module.js",
    "loaders/MeshoptDecoderLocation.js": "需要 meshopt_decoder.module.js",
}


def die(msg: str) -> None:
    print(f"[vendor] 错误：{msg}", file=sys.stderr)
    sys.exit(1)


def find_three_root(p: Path) -> Path:
    """允许传入包根、解压后的子目录，或 build 目录本身。"""
    p = p.resolve()
    for cand in (p, p / "three.js-0.187.0", p.parent):
        if (cand / "build" / "three.module.js").exists() and (cand / "examples" / "jsm").is_dir():
            return cand
    die(f"在 {p} 找不到 three.js 发行包结构（需要 build/three.module.js 与 examples/jsm/）")
    return p


def norm_rel(base_rel: str, spec: str) -> str:
    """把 addon 内部的相对 specifier 归一化成相对 examples/jsm 的路径。"""
    base = Path(base_rel).parent
    joined = (base / spec).as_posix()
    parts: list[str] = []
    for seg in joined.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
            continue
        parts.append(seg)
    return "/".join(parts)


def resolve_include(jsm: Path, token: str) -> str:
    """把短名 / 相对路径统一成 examples/jsm 下的相对路径。"""
    token = token.strip().replace("\\", "/")
    if token.startswith("./"):
        token = token[2:]
    if token.startswith("addons/"):
        token = token[len("addons/"):]
    if token.endswith(".js") and (jsm / token).exists():
        return token
    stem = token[:-3] if token.endswith(".js") else token
    hits = sorted(p.relative_to(jsm).as_posix() for p in jsm.rglob(f"{Path(stem).name}.js"))
    if not hits:
        die(f"找不到 addon：{token}")
    if len(hits) > 1:
        exact = [h for h in hits if h == f"{stem}.js" or h.endswith("/" + f"{stem}.js")]
        if len(exact) == 1:
            return exact[0]
        die(f"addon 名称有歧义：{token} → {hits[:6]}；请改用完整相对路径")
    return hits[0]


def collect(jsm: Path, rel: str, out_addons: Path, seen: set[str]) -> list[str]:
    if rel in seen:
        return []
    seen.add(rel)
    src = jsm / rel
    if not src.exists():
        die(f"依赖文件不存在：{rel}")
    dst = out_addons / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    added = [rel]
    text = src.read_text(encoding="utf-8", errors="ignore")
    for spec in REL_IMPORT.findall(text):
        dep = norm_rel(rel, spec)
        added += collect(jsm, dep, out_addons, seen)
    return added


def sha12(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def read_version(three: Path) -> str:
    pkg = three / "package.json"
    if pkg.exists():
        try:
            return json.loads(pkg.read_text(encoding="utf-8")).get("version", "unknown")
        except Exception:
            pass
    head = (three / "build" / "three.module.js").read_text(encoding="utf-8", errors="ignore")[:2000]
    m = re.search(r"REVISION\s*=\s*['\"](\d+)['\"]", head)
    return f"r{m.group(1)}" if m else "unknown"


def cmd_list(three: Path) -> None:
    jsm = three / "examples" / "jsm"
    rels = sorted(p.relative_to(jsm).as_posix() for p in jsm.rglob("*.js"))
    by_dir: dict[str, list[str]] = {}
    for r in rels:
        by_dir.setdefault(r.split("/")[0], []).append(r)
    print(f"three.js {read_version(three)} · examples/jsm 共 {len(rels)} 个模块")
    for d in sorted(by_dir):
        print(f"\n[{d}] {len(by_dir[d])}")
        for r in by_dir[d][:200]:
            print("  " + r)
    print("\n可用 profile：" + " / ".join(PROFILES))


def cmd_build(three: Path, out: Path, profile: str | None, includes: list[str]) -> None:
    jsm = three / "examples" / "jsm"
    build = three / "build"
    out.mkdir(parents=True, exist_ok=True)

    wanted: list[str] = []
    if profile:
        if profile == "all":
            wanted = sorted(p.relative_to(jsm).as_posix() for p in jsm.rglob("*.js"))
        elif profile in PROFILES:
            wanted = list(PROFILES[profile])
        else:
            die(f"未知 profile：{profile}；可选 {'/'.join(list(PROFILES) + ['all'])}")
    for token in includes:
        wanted.append(resolve_include(jsm, token))
    if not wanted:
        die("没有指定任何 addon：用 --profile 或 --include")

    # 1) 核心构建产物
    for name in CORE_BUILD:
        src = build / name
        if not src.exists():
            die(f"缺少构建产物：{name}")
        shutil.copy2(src, out / name)

    # 2) addon 闭包
    out_addons = out / "addons"
    seen: set[str] = set()
    for rel in wanted:
        collect(jsm, rel, out_addons, seen)

    # 3) importmap
    importmap = {
        "imports": {
            "three": "./vendor/three.module.js",
            "three/addons/": "./vendor/addons/",
        }
    }
    (out / "importmap.json").write_text(json.dumps(importmap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 4) manifest
    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name not in ("manifest.json", "README.md", "importmap.json"))
    total = sum(p.stat().st_size for p in files)
    manifest = {
        "tool": "visual-3d-forge/vendor.py",
        "three_version": read_version(three),
        "profile": profile,
        "include": sorted(seen),
        "file_count": len(files),
        "total_bytes": total,
        "files": [
            {
                "path": p.relative_to(out).as_posix(),
                "bytes": p.stat().st_size,
                "sha256_12": sha12(p),
            }
            for p in files
        ],
        "external": {k: v for k, v in EXTERNAL_DEPS.items() if k in seen},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    readme = f"""# vendor · three.js {manifest['three_version']}

由 `scripts/vendor.py` 生成，**不要手工编辑**。重新生成：

```bash
python3 scripts/vendor.py --three <three包根> --out assets/vendor --profile {profile or 'custom'}
```

- 文件数：{len(files)}
- 总体积：{total / 1024:.1f} KB
- addon：{', '.join(sorted(seen)) if seen else '（无）'}

## 用法 A · 本地工程（D2）

目录结构保持 `vendor/` 与 HTML 同级，importmap 指向相对路径：

```html
<script type="importmap">
{json.dumps(importmap, indent=2)}
</script>
```

## 用法 B · 单文件离线（D1）

```bash
python3 scripts/bundle.py --src scene.html --vendor vendor --out scene.offline.html
```

bundle.py 会把每个模块转成 `data:text/javascript;base64,...` 写回 importmap，
产出的 HTML 不再需要任何外部文件，可直接双击、邮件附件、内网分发。

## 注意

- `three.module.js` 从 `three.core.js` re-export，两者必须同目录，不可拆分。
- 以下模块需额外部署解码器：{json.dumps(manifest['external'], ensure_ascii=False, indent=2)}
"""
    (out / "README.md").write_text(readme, encoding="utf-8")

    print(f"[vendor] three.js {manifest['three_version']} · profile={profile} · {len(files)} 文件 · {total / 1024:.1f} KB")
    print(f"[vendor] addon 闭包：{', '.join(sorted(seen))}")
    print(f"[vendor] 输出：{out}")
    if manifest["external"]:
        print("[vendor] 提醒：以下模块还需要外部解码器 →")
        for k, v in manifest["external"].items():
            print(f"         {k}: {v}")


def cmd_self_test() -> None:
    here = Path(__file__).resolve().parent
    root = here.parent
    print("[self-test] vendor.py 结构自检")
    ok = True
    for name in CORE_BUILD:
        p = root / "assets" / "vendor" / name
        exists = p.exists()
        print(f"  {'OK ' if exists else 'MISS'} assets/vendor/{name}")
        ok = ok and exists
    man = root / "assets" / "vendor" / "manifest.json"
    if man.exists():
        data = json.loads(man.read_text(encoding="utf-8"))
        print(f"  OK  manifest: three {data.get('three_version')}, {data.get('file_count')} 文件, {data.get('total_bytes', 0) / 1024:.1f} KB")
        for entry in data.get("files", []):
            f = root / "assets" / "vendor" / entry["path"]
            if not f.exists():
                print(f"  MISS {entry['path']}")
                ok = False
    else:
        print("  MISS assets/vendor/manifest.json")
        ok = False
    print("[self-test] " + ("通过" if ok else "存在缺失"))
    sys.exit(0 if ok else 1)


def main() -> None:
    ap = argparse.ArgumentParser(description="three.js vendor 裁剪工具")
    ap.add_argument("--three", help="three.js 发行包根目录")
    ap.add_argument("--out", help="vendor 输出目录")
    ap.add_argument("--profile", default="standard", help="core | standard | post | full | all")
    ap.add_argument("--include", default="", help="额外 addon，逗号分隔，可用短名")
    ap.add_argument("--list", action="store_true", help="列出所有可用 addon")
    ap.add_argument("--self-test", action="store_true", help="检查已生成的 vendor 是否完整")
    args = ap.parse_args()

    if args.self_test:
        cmd_self_test()
        return
    if not args.three:
        die("需要 --three <three包根目录>")
    three = find_three_root(Path(args.three))
    if args.list:
        cmd_list(three)
        return
    if not args.out:
        die("需要 --out <vendor输出目录>")
    includes = [x for x in args.include.split(",") if x.strip()]
    cmd_build(three, Path(args.out).resolve(), args.profile, includes)


if __name__ == "__main__":
    main()
