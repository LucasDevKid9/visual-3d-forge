#!/usr/bin/env python3
"""把在线实验台逐帧录成图片序列，交给 ffmpeg 合成 GIF。

为什么不用屏幕录制：录屏会掉帧、会受窗口大小影响、会把鼠标指针录进去。
这里走的是 `?still=1` 的 `window.__seek(t)` 通道——每一帧都是精确的 t，
且与实时渲染共用同一个 `setPose()`，不存在"为录制特调"的分支。

依赖（可选，仅录制用）：
    pip install playwright && playwright install chromium
    无 GPU 的机器还需要 xvfb：apt install xvfb

用法：
    xvfb-run -a python3 tools/record_demo.py --out /tmp/frames
    # 然后按 docs/VALIDATION.md 第五节里的 ffmpeg 命令合成

    # 已有静态服务器时可直接指定 URL
    python3 tools/record_demo.py --url http://localhost:8000/playground/ --fps 15 --duration 6.6
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="逐帧录制 Visual 3D Forge 实验台")
    p.add_argument("--url", default=None,
                   help="实验台地址；不填则自动在仓库根起一个临时静态服务器")
    p.add_argument("--out", default="/tmp/frames", help="输出目录（会被清空）")
    p.add_argument("--fps", type=int, default=15, help="帧率，默认 15")
    p.add_argument("--duration", type=float, default=6.6,
                   help="时长（秒）。6.6 秒正好是一个完整爆炸周期")
    p.add_argument("--width", type=int, default=960)
    p.add_argument("--height", type=int, default=600)
    p.add_argument("--keep", action="store_true", help="保留输出目录里已有的帧")
    return p.parse_args(argv)


async def record(args: argparse.Namespace, url: str) -> int:
    from playwright.async_api import async_playwright

    out = Path(args.out)
    if out.exists() and not args.keep:
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    frames = int(args.fps * args.duration)
    sep = "&" if "?" in url else "?"
    target = f"{url}{sep}demo=1&bare=1&still=1"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--enable-unsafe-swiftshader",
                "--use-gl=angle",
                "--use-angle=swiftshader",
                "--disable-dev-shm-usage",
            ],
        )
        page = await browser.new_page(viewport={"width": args.width, "height": args.height},
                                      device_scale_factor=1)
        page.on("pageerror", lambda e: print(f"[pageerror] {e}", file=sys.stderr))
        await page.goto(target, wait_until="load")
        await page.wait_for_function("window.__ready === true", timeout=30_000)

        # 预热：首帧常因着色器编译而偏暗
        await page.evaluate("window.__seek(0)")
        await page.wait_for_timeout(700)

        for i in range(frames):
            await page.evaluate(f"window.__seek({i / args.fps})")
            await page.screenshot(path=str(out / f"f{i:03d}.png"))
            if i % 20 == 0:
                print(f"[record] {i}/{frames}", file=sys.stderr)

        await browser.close()

    print(f"[record] {frames} 帧 → {out}")
    print("[record] 合成：", file=sys.stderr)
    print(
        '  ffmpeg -framerate {fps} -i {out}/f%03d.png \\\n'
        '    -vf "fps=12,scale=760:-1,split[a][b];'
        '[a]palettegen=max_colors=112:stats_mode=diff[p];'
        '[b]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \\\n'
        '    -loop 0 docs/assets/demo.gif'.format(fps=args.fps, out=out),
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.url is None:
        # 起一个只读静态服务器：实验台的 importmap 用 ../assets/vendor/，必须从仓库根解析
        import http.server
        import socketserver
        import threading

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=str(ROOT), **kw)

            def log_message(self, *a):  # 录 99 帧会刷屏，静音
                pass

        httpd = socketserver.TCPServer(("127.0.0.1", 0), Quiet)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{port}/playground/"
        try:
            return asyncio.run(record(args, url))
        finally:
            httpd.shutdown()
    return asyncio.run(record(args, args.url))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ImportError as exc:  # playwright 缺失
        print(f"缺少依赖：{exc}\n请先 pip install playwright && playwright install chromium",
              file=sys.stderr)
        raise SystemExit(2) from exc
