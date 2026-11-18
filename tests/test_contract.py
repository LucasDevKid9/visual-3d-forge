"""契约测试：把这个 skill 的承诺变成可执行的断言。

原则（与 SKILL.md 的「不要相信记忆」同源）：
凡是文档里写下的数字与路径，都必须有一条测试能在 10 秒内证伪它。

覆盖四层：
1. 文档完整性   —— frontmatter、章节、索引与文件双向一致
2. 依赖完整性   —— vendor 清单哈希、three 版本
3. 工具行为     —— 四个脚本的 --help / --self-test / 退出码
4. 端到端       —— D2 骨架 → 打包成 D1 → 19 项校验全过、零远程引用
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
SKILL = ROOT / "SKILL.md"
REFS = ROOT / "references"
VENDOR = ROOT / "assets" / "vendor"
SCAFFOLD = ROOT / "assets" / "scaffold"
MHT_FIXTURE = ROOT / "tests" / "fixtures" / "sample.mht"
TIMELINE_EXAMPLE = ROOT / "examples" / "timeline-122s" / "timeline.json"


def run(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# 1. 文档完整性
# ---------------------------------------------------------------------------

class Test文档:
    def test_frontmatter三字段齐全(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        fm = text.split("---", 2)[1]
        for key in ("name:", "display_name:", "description:"):
            assert key in fm, f"frontmatter 缺少 {key}"

    def test_name与目录名一致(self) -> None:
        fm = SKILL.read_text(encoding="utf-8").split("---", 2)[1]
        assert "name: visual-3d-forge" in fm
        assert ROOT.name == "visual-3d-forge"

    def test_description足够具体(self) -> None:
        fm = SKILL.read_text(encoding="utf-8").split("---", 2)[1]
        m = re.search(r'description:\s*"(.+)"', fm, re.S)
        assert m, "description 必须是双引号字符串"
        # 触发词密度：至少覆盖四个交付形态之一与三类以上典型场景
        desc = m.group(1)
        assert len(desc) > 200
        for token in ("D0", "D3", "爆炸图", "离线"):
            assert token in desc, token

    def test_索引里的参考文件全部存在(self) -> None:
        """SKILL.md 里出现的每个 NN-*.md 文件名，磁盘上都必须真有。"""
        text = SKILL.read_text(encoding="utf-8")
        cited = set(re.findall(r"([0-9]{2}-[0-9a-z\-]+\.md)", text))
        assert len(cited) >= 13, cited
        missing = [n for n in cited if not (REFS / n).exists()]
        assert not missing, missing

    def test_每个参考文件都被索引引用(self) -> None:
        """反向：磁盘上的每个参考文件都必须被 SKILL.md 提到，不允许幽灵文档。"""
        text = SKILL.read_text(encoding="utf-8")
        on_disk = {p.name for p in REFS.glob("*.md")}
        orphans = [n for n in on_disk if n not in text]
        assert not orphans, f"这些文件没有被 SKILL.md 索引：{orphans}"

    def test_脚本路径全部存在(self) -> None:
        cited = set(re.findall(r"scripts/([a-z_]+\.py)", SKILL.read_text(encoding="utf-8")))
        assert cited == {"api_lookup.py", "bundle.py", "validate_scene.py", "vendor.py"}
        for name in cited:
            assert (SCRIPTS / name).exists(), name

    def test_骨架路径全部存在(self) -> None:
        for p in ("assets/scaffold/forged-scene.html",
                  "assets/scaffold/forged-scene.vendor.html",
                  "assets/scaffold/r3f-app/package.json"):
            assert (ROOT / p).exists(), p

    def test_没有未完成的占位标记(self) -> None:
        offenders = []
        for p in [SKILL, *REFS.glob("*.md")]:
            text = p.read_text(encoding="utf-8")
            if re.search(r"\bTODO\b|\bFIXME\b|待补|占位符", text):
                offenders.append(p.name)
        assert not offenders, offenders

    def test_没有硬编码本机绝对路径(self) -> None:
        bad = re.compile(r"/Users/|/home/\w|C:\\\\|/root/")
        offenders = []
        for p in [SKILL, *REFS.glob("*.md"), *SCRIPTS.glob("*.py"), *SCAFFOLD.glob("*.html")]:
            if bad.search(p.read_text(encoding="utf-8", errors="ignore")):
                offenders.append(p.name)
        assert not offenders, offenders


# ---------------------------------------------------------------------------
# 2. 依赖完整性
# ---------------------------------------------------------------------------

class Test依赖:
    def test_清单可解析且版本固定(self) -> None:
        m = json.loads((VENDOR / "manifest.json").read_text(encoding="utf-8"))
        assert m["three_version"] == "0.187.0"
        assert m["profile"] == "standard"
        # 18 个文件 = 16 个 addon + three.module.js + three.core.js
        assert m["file_count"] == len(m["files"]) == 18
        assert len(m["include"]) == 16
        assert {"three.module.js", "three.core.js"} <= {r["path"] for r in m["files"]}

    def test_每个文件的哈希都对得上(self) -> None:
        m = json.loads((VENDOR / "manifest.json").read_text(encoding="utf-8"))
        for row in m["files"]:
            f = VENDOR / row["path"]
            assert f.exists(), row["path"]
            h = hashlib.sha256(f.read_bytes()).hexdigest()[:12]
            assert h == row["sha256_12"], f"{row['path']} 哈希不符，vendor 被改动过"

    def test_three_revision与清单一致(self) -> None:
        core = (VENDOR / "three.core.js").read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"REVISION\s*=\s*'(\d+)'", core)
        assert m and m.group(1) == "187"

    def test_importmap覆盖全部addons(self) -> None:
        imp = json.loads((VENDOR / "importmap.json").read_text(encoding="utf-8"))
        imports = imp["imports"]
        for key in ("three", "three/addons/"):
            assert key in imports, key
        # 目录级映射：three/addons/ 指向 ./vendor/addons/，addon 数由 manifest 保证
        assert imports["three"] == "./vendor/three.module.js"
        assert imports["three/addons/"] == "./vendor/addons/"
        assert len(list((VENDOR / "addons").rglob("*.js"))) == 16


# ---------------------------------------------------------------------------
# 3. 工具行为
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("script", ["vendor.py", "bundle.py", "api_lookup.py", "validate_scene.py"])
def test_脚本可执行且给出帮助(script: str) -> None:
    r = run([str(SCRIPTS / script), "--help"], timeout=60)
    assert r.returncode == 0, r.stderr
    assert "usage:" in r.stdout.lower()


def test_bundle自检通过() -> None:
    r = run([str(SCRIPTS / "bundle.py"), "--self-test"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[self-test] 通过" in r.stdout


def test_vendor自检通过() -> None:
    r = run([str(SCRIPTS / "vendor.py"), "--self-test"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[self-test] 通过" in r.stdout


def test_脚本只用标准库() -> None:
    """scripts/ 下不许有第三方依赖：这些脚本要能在任何有 python3 的机器上跑。

    判据用 `sys.stdlib_module_names`（3.10+），不是手写白名单。
    手写白名单的问题是：每加一个脚本就要补一次，漏了会红，而红的原因是
    白名单旧了、不是依赖脏了——测试开始替自己造噪音。
    """
    stdlib = set(sys.stdlib_module_names)
    for p in SCRIPTS.glob("*.py"):
        mods = re.findall(r"^(?:import|from)\s+([A-Za-z_][\w.]*)", p.read_text(encoding="utf-8"), re.M)
        third = {m.split(".")[0] for m in mods} - stdlib
        assert not third, f"{p.name} 引入了非标准库依赖：{third}"


def test_api_lookup缺源码时给出可读错误() -> None:
    """已知边界：本包只含 build 产物，查证需要 npm 源码。错误必须可读，不能静默。"""
    r = run([str(SCRIPTS / "api_lookup.py"), "--three", str(ROOT), "find", "InstancedMesh"], timeout=60)
    assert r.returncode != 0
    assert "找不到 three.js 源码" in (r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# 4. 端到端
# ---------------------------------------------------------------------------

class Test端到端:
    def test_D0骨架校验全过(self) -> None:
        r = run([str(SCRIPTS / "validate_scene.py"), str(SCAFFOLD / "forged-scene.html")])
        assert r.returncode == 0, r.stdout + r.stderr
        assert "0 失败" in r.stdout
        assert "18 通过" in r.stdout

    def test_D2骨架校验全过(self) -> None:
        r = run([str(SCRIPTS / "validate_scene.py"), str(SCAFFOLD / "forged-scene.vendor.html")])
        assert r.returncode == 0, r.stdout + r.stderr

    def test_打包到校验全链路(self, tmp_path: Path) -> None:
        out = tmp_path / "offline.html"
        b = run([str(SCRIPTS / "bundle.py"),
                 "--src", str(SCAFFOLD / "forged-scene.vendor.html"),
                 "--out", str(out),
                 "--vendor", str(VENDOR)])
        assert b.returncode == 0, b.stdout + b.stderr
        assert out.exists()

        html = out.read_text(encoding="utf-8", errors="ignore")
        assert not re.search(r"https?://", html), "D1 产物不允许残留远程引用"
        assert "data:text/javascript;base64," in html
        # 体积量级：实测 2.8MB 上下，防止打包退化成「假内联」
        mb = out.stat().st_size / 1024 / 1024
        assert 2.0 < mb < 4.0, f"D1 体积异常：{mb:.2f} MB"

        v = run([str(SCRIPTS / "validate_scene.py"), str(out)])
        assert v.returncode == 0, v.stdout + v.stderr
        assert "19 通过" in v.stdout, "D1 模式应为 19 项检查"

    @pytest.mark.parametrize("example", sorted((ROOT / "examples").rglob("*.html")),
                             ids=lambda p: p.name)
    def test_示例产物通过strict校验(self, example: Path) -> None:
        """仓库里的示例必须自己先过得去——不允许"演示用，不校验"。"""
        r = run([str(SCRIPTS / "validate_scene.py"), str(example), "--strict"])
        assert r.returncode == 0, r.stdout + r.stderr
        assert "0 警告" in r.stdout or "0 失败" in r.stdout

    def test_校验器能抓出被破坏的产物(self, tmp_path: Path) -> None:
        """反向测试：把 D2 骨架的 importmap 删掉，校验器必须变红。"""
        src = (SCAFFOLD / "forged-scene.vendor.html").read_text(encoding="utf-8")
        broken = re.sub(r'<script type="importmap">.*?</script>', "", src, flags=re.S)
        p = tmp_path / "broken.html"
        p.write_text(broken, encoding="utf-8")
        # 默认模式：缺 importmap 只告警（W01），不阻断——这是刻意的宽松档
        lenient = run([str(SCRIPTS / "validate_scene.py"), str(p)])
        assert lenient.returncode == 0 and "W01" in lenient.stdout
        # strict 模式：告警即失败，必须变红
        strict = run([str(SCRIPTS / "validate_scene.py"), str(p), "--strict"])
        assert strict.returncode != 0, "strict 模式下缺 importmap 竟然通过了校验"


# ---------------------------------------------------------------------------
# 8. 本仓库真的踩过的坑（每个用例对应一次真实事故）
# ---------------------------------------------------------------------------

class Test已知回归:
    def test_vendor_文件不含_NUL(self) -> None:
        """BufferGeometryUtils.js 曾在 16 KiB 处被 NUL 截断。

        表现是 GLTFLoader 一 import 就 SyntaxError，而哈希校验、静态校验、
        全部测试都绿——因为哈希是对损坏文件算的，静态检查不解析 JS。
        """
        bad = []
        for p in VENDOR.rglob("*.js"):
            if b"\x00" in p.read_bytes():
                bad.append(p.relative_to(ROOT).as_posix())
        assert not bad, f"vendor 里有二进制损坏的文件（尾部被 NUL 填充）：{bad}"

    def test_vendor_addon_能被解析器读入(self) -> None:
        """NUL 检查之外再钉一道：用 node 解析每个 addon。没 node 就跳过。"""
        import shutil as _sh, subprocess as _sp
        node = _sh.which("node")
        if not node:
            import pytest as _pytest
            _pytest.skip("没有 node，跳过语法解析")
        broken = []
        for p in sorted((VENDOR / "addons").rglob("*.js")):
            r = _sp.run([node, "--check", str(p)], capture_output=True, text=True)
            if r.returncode != 0:
                broken.append(p.relative_to(VENDOR).as_posix())
        assert not broken, f"vendor addon 语法错误：{broken}"

    def test_形态判定认得任意层级的_vendor(self) -> None:
        """playground 用 ../assets/vendor/，spec/out 用 ../../assets/vendor/。

        旧正则只认 `<.>/vendor/` 紧跟 vendor，这两处会被判成 D0，
        接着 E03「未锁定 three@0.187.0」假失败——而它们的 importmap 明明指向本地。
        """
        import sys as _sys
        _sys.path.insert(0, str(SCRIPTS))
        import validate_scene  # noqa: E402
        for rel in ("../vendor/x.js", "../assets/vendor/x.js",
                    "../../assets/vendor/x.js", "./assets/vendor/x.js"):
            html = f'<script type="importmap">{{"imports":{{"three":"{rel}"}}}}</script>'
            assert "D2" in validate_scene.detect_mode(html), f"{rel} 未识别为 D2"

    def test_压缩产物识别只对压缩产物成立(self) -> None:
        """is_bundled 一旦误判，所有计数类检查都会被静默跳过——比误报更危险。"""
        import sys as _sys
        _sys.path.insert(0, str(SCRIPTS))
        import validate_scene  # noqa: E402
        demo = (ROOT / "demo" / "index.html").read_text(encoding="utf-8", errors="replace")
        got, why = validate_scene.is_bundled(demo)
        assert got, f"demo 应识别为压缩产物，实际 {got}（{why}）"
        for rel in ("assets/scaffold/forged-scene.html", "playground/index.html",
                    "spec/out/nema23-actuator.html"):
            html = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
            g, w = validate_scene.is_bundled(html)
            assert not g, f"{rel} 被误判成压缩产物（{w}），计数类检查会被跳过"


# ---------------------------------------------------------------------------
# 9. 提示表（E2/E3 的数据层）与网页存档（参考素材入口）
# ---------------------------------------------------------------------------

class Test时序与存档:
    def test_示例提示表全过(self) -> None:
        r = run([str(SCRIPTS / "timeline_check.py"), str(TIMELINE_EXAMPLE), "--strict"])
        assert r.returncode == 0, r.stdout + r.stderr
        assert "0 警告 / 0 失败" in r.stdout, r.stdout[-400:]

    def test_缺主时钟必然失败(self, tmp_path: Path) -> None:
        """多时钟是时序作品最难查的 bug，必须当硬错误。"""
        spec = json.loads(TIMELINE_EXAMPLE.read_text(encoding="utf-8"))
        spec.pop("master_clock", None)
        p = tmp_path / "no-clock.json"
        p.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        r = run([str(SCRIPTS / "timeline_check.py"), str(p)])
        assert r.returncode == 1 and "T02" in r.stdout, r.stdout[-400:]

    def test_重复id与越界必然失败(self, tmp_path: Path) -> None:
        spec = {"duration": 5.0, "master_clock": "raf",
                "cues": [{"t": 0, "id": "x", "dur": 1, "ease": "linear", "apply": "a"},
                         {"t": 2, "id": "x", "dur": 4, "ease": "linear", "apply": "b"}]}
        p = tmp_path / "dup.json"
        p.write_text(json.dumps(spec), encoding="utf-8")
        r = run([str(SCRIPTS / "timeline_check.py"), str(p)])
        assert r.returncode == 1
        assert "T06" in r.stdout and "T07" in r.stdout

    def test_降级档只改像素比会告警(self, tmp_path: Path) -> None:
        """只降 devicePixelRatio 不叫降级——算法复杂度一点没降。"""
        spec = {"duration": 10.0, "master_clock": "raf", "reduced_motion": "skip",
                "quality_tiers": {"LOW": {"pixelRatio": 1}, "HIGH": {"pixelRatio": 2}},
                "cues": [{"t": 0, "id": "a", "dur": 10, "ease": "linear", "apply": "x"}]}
        p = tmp_path / "pixonly.json"
        p.write_text(json.dumps(spec), encoding="utf-8")
        r = run([str(SCRIPTS / "timeline_check.py"), str(p), "--strict"])
        assert r.returncode == 1, "只改像素比的降级档竟然通过了 strict"
        assert "T13" in r.stdout

    def test_拆包_MHT_产出主文档与清单(self, tmp_path: Path) -> None:
        out = tmp_path / "ref"
        r = run([str(SCRIPTS / "mht_unpack.py"), str(MHT_FIXTURE), "--out", str(out), "--quiet"])
        assert r.returncode == 0, r.stdout + r.stderr
        assert (out / "index.html").is_file()
        man = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
        assert man["parts"] >= 10
        assert man["scripts_in_html"] == 0, "样本快照里本来就没有脚本"
        assert man["missing_kinds"], "应当推断出缺件"

    def test_拆包后_cid_引用已改写(self, tmp_path: Path) -> None:
        out = tmp_path / "ref2"
        run([str(SCRIPTS / "mht_unpack.py"), str(MHT_FIXTURE), "--out", str(out), "--quiet"])
        html = (out / "index.html").read_text(encoding="utf-8")
        assert "cid:" not in html, "还有没改写的 cid: 引用，浏览器会加载失败"
        for m in re.finditer(r'(?:href|src)="(_assets/[^"]+)"', html):
            assert (out / m.group(1)).is_file(), m.group(1)

    def test_不是_MHTML_时给出可读错误(self, tmp_path: Path) -> None:
        plain = tmp_path / "x.html"
        plain.write_text("<html><body>hi</body></html>", encoding="utf-8")
        r = run([str(SCRIPTS / "mht_unpack.py"), str(plain)])
        assert r.returncode == 1 and "不是 MHTML" in (r.stdout + r.stderr)
