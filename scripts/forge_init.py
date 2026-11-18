#!/usr/bin/env python3
"""三维造物引擎 v2.0 · 工程初始化

从骨架创建一个可运行的 3D 场景工程，按需要的运行模式铺好文件。

用法：
    python3 forge_init.py <目标目录> [选项]

选项：
    --title "标题"     写入页面 <title> 与 HUD 标题
    --mode cdn        单文件，importmap 走 jsDelivr（默认，需联网）
    --mode standalone 单文件，内联 three 运行时（离线、双击即开，约 1.3MB）
    --mode local      单文件 + 同级 three/ 资源目录（离线、可读源码、便于换 addons）
    --force           目标文件已存在时覆盖

示例：
    python3 forge_init.py ./my-scene --title "行星齿轮减速器" --mode standalone

退出码：0 成功；2 参数错误。
只用标准库。
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
SCAFFOLD = SKILL_ROOT / "assets" / "scaffold" / "forged-scene.html"
THREE_DIR = SKILL_ROOT / "assets" / "three"


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2

    target = Path(args[0])
    title = None
    mode = "cdn"
    force = "--force" in sys.argv

    if "--title" in sys.argv:
        i = sys.argv.index("--title")
        if i + 1 < len(sys.argv):
            title = sys.argv[i + 1]
    if "--mode" in sys.argv:
        i = sys.argv.index("--mode")
        if i + 1 < len(sys.argv):
            mode = sys.argv[i + 1]

    if mode not in ("cdn", "standalone", "local"):
        print(f"未知 mode：{mode}（可选 cdn / standalone / local）")
        return 2

    if not SCAFFOLD.is_file():
        print(f"缺少骨架：{SCAFFOLD}")
        return 2

    target.mkdir(parents=True, exist_ok=True)
    out_html = target / "index.html"

    if out_html.exists() and not force:
        print(f"已存在：{out_html}\n加 --force 覆盖，或换一个目录。")
        return 2

    html = SCAFFOLD.read_text(encoding="utf-8")
    if title:
        html = html.replace("<title>三维造物引擎 · 场景骨架</title>",
                            f"<title>{title}</title>")
        html = html.replace("<!-- HUD_TITLE -->", title)

    out_html.write_text(html, encoding="utf-8")
    print(f"[1/3] 骨架已写入：{out_html}")

    if mode == "local":
        dst = target / "three"
        if dst.exists():
            print(f"[2/3] three/ 已存在，跳过复制")
        else:
            shutil.copytree(THREE_DIR / "build", dst / "build")
            shutil.copytree(THREE_DIR / "addons", dst / "addons")
            print(f"[2/3] three 运行时已复制到：{dst}")
        # 把 importmap 改成相对路径（用正则，不依赖原文件的空格排版）
        html = out_html.read_text(encoding="utf-8")
        html = re.sub(r"https://fastly\.jsdelivr\.net/npm/three@0\.187\.0/build/three\.module\.js",
                      "./three/build/three.module.js", html)
        html = re.sub(r"https://fastly\.jsdelivr\.net/npm/three@0\.187\.0/examples/jsm/",
                      "./three/addons/", html)
        out_html.write_text(html, encoding="utf-8")
        print("[3/3] importmap 已指向本地 three/")

    elif mode == "standalone":
        import subprocess
        r = subprocess.run([sys.executable, str(HERE / "build_standalone.py"),
                            str(out_html), "-o", str(out_html)], capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode != 0:
            print("standalone 转换失败，已保留 CDN 版 index.html")
            return 0
        print("[3/3] 已内联 three 运行时（离线可用）")

    else:
        print("[3/3] CDN 模式：保持单文件，运行时从 jsDelivr 加载")

    print("\n下一步：")
    print(f"  1. 编辑 {out_html} 的 buildSubject() 与 boot()")
    print(f"  2. 自检：python3 {HERE/'validate_scene.py'} {out_html}")
    print(f"  3. 打开验收（交互、拖拽限位、切后台、缩放窗口）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
