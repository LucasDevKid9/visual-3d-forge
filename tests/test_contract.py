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
