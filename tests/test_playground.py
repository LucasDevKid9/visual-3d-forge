"""实验台与展示资产的契约测试。

playground/ 不是装饰：它是这个仓库唯一「零安装可验证」的部分。
所以它同样要被断言盯住——路径断一个，在线体验就白屏；
SVG 混进一个 <script>，GitHub 会直接拒绝渲染。

覆盖三层：
1. 可运行性  —— importmap 与 vendor 路径逐条落地、无外链依赖
2. 求解器    —— 三条装配约束与传动比公式必须真的在页面里
3. 展示资产  —— SVG 可解析且不含脚本、GIF 尺寸与体积在可接受区间
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PLAY = ROOT / "playground" / "index.html"
ASSETS = ROOT / "docs" / "assets"
VENDOR = ROOT / "assets" / "vendor"


@pytest.fixture(scope="module")
def html() -> str:
    return PLAY.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. 可运行性
# ---------------------------------------------------------------------------

class Test可运行性:

    def test_页面存在且声明语言(self, html: str) -> None:
        assert PLAY.is_file()
        assert html.lstrip().lower().startswith("<!doctype html>")
        assert 'lang="zh-CN"' in html

    def test_importmap_指向仓库内_vendor(self, html: str) -> None:
        m = re.search(r'<script type="importmap">(.*?)</script>', html, re.S)
        assert m, "缺少 importmap"
        assert "../assets/vendor/three.module.js" in m.group(1)
        assert "../assets/vendor/addons/" in m.group(1)

    @pytest.mark.parametrize("rel", ["three.module.js", "addons/controls/OrbitControls.js",
                                     "addons/environments/RoomEnvironment.js"])
    def test_importmap_引用的文件真实存在(self, rel: str) -> None:
        assert (VENDOR / rel).is_file(), f"vendor 缺文件：{rel}"

    def test_importmap_地址都是_url_like(self, html: str) -> None:
        """import map 的地址必须以 ./ ../ / 或绝对 URL 开头。

        写成 "assets/vendor/x.js" 语法上像路径，但不符合 import map 的
        URL-like 要求，Chromium 会把该条目解析成 null，模块一个都不加载。
        症状是控制台报 `blocked by a null value`，而网络面板一片空白——
        很难从现象反推到语法，所以在这里钉死。
        """
        import json

        m = re.search(r'<script type="importmap">(.*?)</script>', html, re.S)
        assert m
        imports = json.loads(m.group(1))["imports"]
        bad = [v for v in imports.values()
               if not v.startswith(("./", "../", "/", "http://", "https://"))]
        assert not bad, f"import map 地址不是 URL-like：{bad}"

    def test_不依赖远程_cdn(self, html: str) -> None:
        body = re.sub(r"<!--.*?-->", "", html, flags=re.S)
        remote = re.findall(r'from\s+[\'"](https?://[^\'"]+)', body)
        assert not remote, f"模块引入了远程依赖：{remote}"
        assert "cdn.jsdelivr" not in body
        assert "unpkg.com" not in body

    def test_有_webgl_降级出口(self, html: str) -> None:
        assert 'id="fallback"' in html
        assert "WebGL" in html


# ---------------------------------------------------------------------------
# 2. 求解器
# ---------------------------------------------------------------------------

class Test求解器:

    def test_三条装配约束都在(self, html: str) -> None:
        for kw in ("同心", "装配", "邻接"):
            assert kw in html, f"缺少约束：{kw}"

    def test_传动比公式(self, html: str) -> None:
        assert re.search(r"1\s*\+\s*z3\s*/\s*z1", html), "传动比应为 1 + z₃/z₁（固定内齿圈）"

    def test_行星轮齿数由同心条件导出(self, html: str) -> None:
        assert re.search(r"z2\s*=\s*dz\s*/\s*2", html), "z₂ 必须由 (z₃−z₁)/2 导出"

    def test_装配条件判据(self, html: str) -> None:
        assert re.search(r"\(\s*z1\s*\+\s*z3\s*\)\s*%\s*3", html), "均布条件应为 (z₁+z₃) % 3"

    def test_邻接条件判据(self, html: str) -> None:
        assert "Math.sin(Math.PI / 3)" in html, "邻接条件用到 sin60°"
        assert "z2 + 2" in html, "比较对象是行星轮齿顶圆 z₂+2"

    def test_非法参数有修正出口(self, html: str) -> None:
        assert "nearestLegal" in html
        assert 'id="fix"' in html

    def test_运动学用威利斯方程而非各转各的(self, html: str) -> None:
        assert "z1 / (s.z1 + s.z3)" in html or "z1/(z1+z3)" in html.replace(" ", "")
        assert re.search(r"wc\s*-\s*\(s\.z1\s*/\s*s\.z2\)", html), "行星轮自转必须相对行星架换算"


# ---------------------------------------------------------------------------
# 3. 展示资产
# ---------------------------------------------------------------------------

class Test展示资产:

    @pytest.mark.parametrize("name", ["banner.svg", "pipeline.svg"])
    def test_svg_可解析且无脚本(self, name: str) -> None:
        p = ASSETS / name
        assert p.is_file(), f"缺资产：{name}"
        text = p.read_text(encoding="utf-8")
        root = ET.fromstring(text)  # 解析失败即抛错
        assert root.tag.endswith("svg")
        assert "<script" not in text.lower(), "GitHub 会清洗 SVG 内脚本，不要写"
        assert "onload=" not in text.lower()

    @pytest.mark.parametrize("name", ["banner.svg", "pipeline.svg"])
    def test_svg_适配明暗主题(self, name: str) -> None:
        text = (ASSETS / name).read_text(encoding="utf-8")
        assert "prefers-color-scheme" in text
        assert "light" in text and "dark" not in text.split("prefers-color-scheme")[0][-80:]

    def test_gif_存在且体积可控(self) -> None:
        p = ASSETS / "demo.gif"
        assert p.is_file(), "缺首屏动图"
        size = p.stat().st_size
        assert 400_000 < size < 8_000_000, f"GIF 体积异常：{size/1048576:.1f} MB"

    def test_gif_是真正的动图(self) -> None:
        from PIL import Image

        with Image.open(ASSETS / "demo.gif") as im:
            assert im.n_frames > 40, "帧数太少，不像动图"
            w, h = im.size
        assert 640 <= w <= 1200, f"宽度不合适：{w}"
        assert 1.2 < w / h < 2.0, "宽高比偏离 16:10 太多"

    def test_截图仍在且非空(self) -> None:
        p = ROOT / "docs" / "screenshot.png"
        assert p.is_file() and p.stat().st_size > 50_000
